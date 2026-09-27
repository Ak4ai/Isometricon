"""Outer cage carried by one transform per R15 body part, scored against Roblox exports.

Between the per-triangle rotation (radial / runtime) and one transform for the
whole body (global), each body part (UpperLeg, LowerLeg, Foot, ...) gets its own
best linear map from the garment's reference cage to the target body cage. The
garment thickness (outer - inner) of every cage vertex is carried by the map of
its part. "polar" keeps only rotation + uniform scale of that map.
"""
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, edge_ratio, load_obj_groups
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def part_labels(engine, trace):
    parts_by_uv = {tuple(np.round(u, 5)): name for name, part in engine.r15_female_cages.items()
                   if not name.endswith("Forearm") for u in part["face_uvs"].reshape(-1, 2)}
    return np.array([parts_by_uv[tuple(np.round(trace["target_uv"][i], 5))] for i in trace["uv_index"]])


def part_maps(reference, target, labels, polar):
    maps = {}
    for name in np.unique(labels):
        mask = labels == name
        src = reference[mask] - reference[mask].mean(0)
        dst = target[mask] - target[mask].mean(0)
        matrix, *_ = np.linalg.lstsq(src, dst, rcond=None)  # row vectors: dst ~ src @ matrix
        if polar:
            u, s, vt = np.linalg.svd(matrix)
            matrix = (u @ vt) * float(np.cbrt(abs(np.linalg.det(matrix))))
        maps[name] = matrix
    return maps


def part_shell(trace, labels, polar=False, smooth_rounds=0):
    reference, target, outer = trace["reference_parent"], trace["target_body"], trace["outer_parent"]
    maps = part_maps(reference, target, labels, polar)
    offsets = np.array([(outer[i] - reference[i]) @ maps[labels[i]] for i in range(len(reference))])
    if smooth_rounds:  # average the carried thickness with cage neighbours to soften part seams
        faces = trace["projection_faces"]
        for _ in range(smooth_rounds):
            total = offsets.copy()
            count = np.ones(len(offsets))
            for a, b in np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])):
                total[a] += offsets[b]; total[b] += offsets[a]
                count[a] += 1; count[b] += 1
            offsets = total / count[:, None]
    return target + offsets


def main():
    names = sys.argv[1:] or [c for c in CASES if c != "sueter oversized"]
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    report = {}
    for case in names:
        asset, export = CASES[case]
        groups = load_obj_groups(export)
        roblox_raw, faces, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, all_faces, _, _ = engine.load_obj(next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj")) if "fitted" not in p))
        keep = np.unique(all_faces[:len(faces)])
        trace = {}
        retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                         DIRECTORY / "wrap_cages", binding_audit=trace)
        labels = part_labels(engine, trace)
        shells = {
            "radial (por triangulo)": transfer_outer_cage_radial(
                trace["reference_parent"], trace["outer_parent"], trace["target_body"], trace["projection_faces"],
                parity=trace["cage_normal_sign"], radius_factor=1.0),
            "por parte (afim)": part_shell(trace, labels),
            "por parte (rotacao+escala)": part_shell(trace, labels, polar=True),
            "por parte (rotacao+escala) suavizado": part_shell(trace, labels, polar=True, smooth_rounds=3),
        }
        entry = {}
        for label, shell in shells.items():
            fitted = bind_dual_cage(source, trace, shell)[0][keep]
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            entry[label] = {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                            "mediana_cm": round(float(np.median(distance)), 2),
                            "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
        report[case] = entry
        print(f"{case:16s}", " | ".join(f"{k}: {v['acima_5cm_pct']}% ar {v['arestas_3x']}" for k, v in entry.items()), flush=True)
    (GT / "part_rotation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
