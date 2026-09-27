"""How "global" is Roblox's fit per region?

For each garment, fit one affine map (source garment -> fitted garment) and
measure the residual per region. Small residual = the region moved as one
rigid/stretched block; large residual = it followed local body parts.
The body cage itself (reference -> Blocky) is measured the same way as a
control: if the body is non-global in a region but Roblox's garment is
global there, Roblox is smoothing the local body motion away.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, load_obj_groups
from scripts.compare_variants_roblox import CASES
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.experiment_shell_global_affine import global_shell
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def affine_residual(source, target, fit_mask, eval_mask):
    """Fit target ~ [source, 1] @ A on fit_mask; RMS residual (cm) on eval_mask."""
    design = np.hstack((source, np.ones((len(source), 1))))
    matrix, *_ = np.linalg.lstsq(design[fit_mask], target[fit_mask], rcond=None)
    error = np.linalg.norm(design[eval_mask] @ matrix - target[eval_mask], axis=1) * STUD_CM
    return round(float(np.sqrt(np.mean(error ** 2))), 2)


def regions(points, bounds):
    """Regions by where the garment ends up on the Blocky (engine: z up, torso |x| < 1).

    ``bounds`` is the (low, high) height span of the Roblox garment, so the body
    control is cut at the same heights as the garment it sits under.
    """
    low, high = bounds
    inside = (points[:, 2] >= low) & (points[:, 2] <= high)
    sleeve = inside & (np.abs(points[:, 0]) > 1.0) & (points[:, 2] > 1.0)
    lower = inside & (points[:, 2] < low + (high - low) / 3) & ~sleeve
    return {"manga": sleeve, "terco inferior": lower, "tronco/resto": inside & ~sleeve & ~lower}


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
        source, _, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{asset}.obj"))))
        trace = {}
        runtime, _ = retarget_garment_with_wrap_layer(
            engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))), DIRECTORY / "wrap_cages", binding_audit=trace)
        garment_source = trace["source_vertices"]
        radial = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                            trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
        outputs = {"Roblox": roblox, "runtime atual": runtime,
                   "radial + prisma": bind_dual_cage(source, trace, radial)[0],
                   "cage global + prisma": bind_dual_cage(source, trace, global_shell(trace)[0])[0]}
        bounds = (roblox[:, 2].min(), roblox[:, 2].max())
        garment_regions = regions(roblox, bounds)
        everything = np.ones(len(roblox), bool)
        rows = {"vertices_por_regiao": {k: int(v.sum()) for k, v in garment_regions.items()}}
        for label, fitted in outputs.items():
            rows[label] = {name: {"uma_transformacao_para_a_roupa_toda": affine_residual(garment_source, fitted, everything, mask),
                                  "uma_transformacao_so_desta_regiao": affine_residual(garment_source, fitted, mask, mask)}
                           for name, mask in garment_regions.items() if mask.sum() >= 12}
        # Control: the body cage under the same test, restricted to the height band each region covers.
        body_source, body_target = trace["reference_parent"], trace["target_body"]
        body_regions = regions(body_target, bounds)
        rows["controle: cage do corpo"] = {
            name: {"uma_transformacao_para_a_roupa_toda": affine_residual(body_source, body_target, np.ones(len(body_target), bool), mask),
                   "uma_transformacao_so_desta_regiao": affine_residual(body_source, body_target, mask, mask)}
            for name, mask in body_regions.items() if mask.sum() >= 12}
        report[case] = rows
        print(case, json.dumps(rows, ensure_ascii=False), flush=True)
    out = ROOT / "artifacts/roblox_ground_truth/globalness_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
