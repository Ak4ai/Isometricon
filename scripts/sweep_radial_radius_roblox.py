"""Sweep the radial outer-cage radius and score each value against Roblox Studio exports."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_roblox_globalness import affine_residual, regions
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, edge_ratio, load_obj_groups
from scripts.compare_variants_roblox import CASES
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

FACTORS = [float(x) for x in sys.argv[1:]] or [1.0, 2.0, 3.0, 4.0, 6.0]


def score(fitted, roblox, faces, garment_source, masks):
    distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
    row = {"mediana_cm": round(float(np.median(distance)), 2),
           "acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
           "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
    everything = np.ones(len(fitted), bool)
    for name, mask in masks.items():
        if mask.sum() >= 12:
            row[f"{name}: acima_5cm_pct"] = round(float((distance[mask] > 5).mean() * 100), 1)
            row[f"{name}: global_cm"] = affine_residual(garment_source, fitted, everything, mask)
    return row


def main():
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    report = {}
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
        for factor in FACTORS:
            shell, audit = transfer_outer_cage_radial(
                trace["reference_parent"], trace["outer_parent"], trace["target_body"], trace["projection_faces"],
                parity=trace["cage_normal_sign"], radius_factor=factor, return_audit=True)
            fitted = bind_dual_cage(source, trace, shell)[0]
            report[case][f"raio {factor:g}x"] = score(fitted, roblox, faces, trace["source_vertices"], masks)
            print(case, factor, report[case][f"raio {factor:g}x"], flush=True)
    out = ROOT / "artifacts/roblox_ground_truth/radius_sweep_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
