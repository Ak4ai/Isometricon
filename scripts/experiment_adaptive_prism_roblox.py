"""Adaptive outer cage (local <-> global blend) + prism binding, scored against Roblox exports."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_roblox_globalness import regions
from scripts.compare_roblox_ground_truth import align_studio_to_engine, load_obj_groups
from scripts.compare_variants_roblox import CASES
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.experiment_shell_adaptive import shell_weights
from scripts.experiment_shell_global_affine import global_shell
from scripts.sweep_radial_radius_roblox import score
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def shells(trace):
    radial = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                        trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
    global_outer, _ = global_shell(trace)
    out = {"radial 1x (so local)": radial, "global (so global)": global_outer}
    for local_name, local in (("runtime", trace["reference_order_target_outer"]), ("radial", radial)):
        for weight_name, weight in shell_weights(trace).items():
            out[f"{local_name}<->global por {weight_name}"] = local * (1 - weight[:, None]) + global_outer * weight[:, None]
    return out


def main():
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
    report, fitted_meshes = {}, {}
    for case, (asset, export) in CASES.items():
        groups = load_obj_groups(export)
        roblox_raw, _, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{asset}.obj"))))
        trace = {}
        retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                         DIRECTORY / "wrap_cages", binding_audit=trace)
        masks = regions(roblox, (roblox[:, 2].min(), roblox[:, 2].max()))
        report[case] = {"Roblox": score(roblox, roblox, faces, trace["source_vertices"], masks)}
        weights = shell_weights(trace)
        report[case]["pesos (mediana/p90)"] = {k: [round(float(np.median(w)), 3), round(float(np.quantile(w, .9)), 3)]
                                              for k, w in weights.items()}
        for label, outer in shells(trace).items():
            fitted = bind_dual_cage(source, trace, outer)[0]
            fitted_meshes[f"{case}|{label}"] = fitted
            report[case][label] = score(fitted, roblox, faces, trace["source_vertices"], masks)
            print(case, label, report[case][label], flush=True)
    out = ROOT / "artifacts/roblox_ground_truth"
    (out / "adaptive_prism_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    np.savez_compressed(out / "adaptive_prism_meshes.npz", **fitted_meshes)


if __name__ == "__main__":
    main()
