"""Hanging parts keep their authored direction; where the baggy-pants error comes from.

1. Hanging vertices (outside every prism) take their anchor's *position* but
   carry their offset with the single global cage map (scale + axis change),
   not the anchor's local rotation.
2. For prism-bound vertices, the error against Roblox is split by layer depth
   t (0 = body side, 1 = outer cage) and by direction (outward / front-back /
   up-down), per garment.
"""
from collections import deque
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, edge_ratio, load_obj_groups
from scripts.experiment_anchor_and_shell_roblox import ANCHOR_CM, anchored
from scripts.experiment_dual_cage_prism import closest_prism_binding
from scripts.experiment_shell_global_affine import global_shell
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def bind_details(points, trace, target_outer):
    inner, outer, target_inner = trace["reference_parent"], trace["outer_parent"], trace["target_body"]
    faces = trace["projection_faces"]
    area = lambda v: np.linalg.norm(np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]]), axis=1)
    faces = faces[(area(inner) > 1e-8) & (area(outer) > 1e-8)]
    six = np.concatenate((inner[faces], outer[faces]), axis=1)
    lower, upper = six.min(1), six.max(1)
    out = {k: [] for k in ("base", "residual", "map", "t", "normal")}
    for point in points:
        _, (face_id, t, bary, residual) = closest_prism_binding(point, inner, outer, faces, lower, upper)
        face = faces[face_id]
        source_section = (1 - t) * inner[face] + t * outer[face]
        target_section = (1 - t) * target_inner[face] + t * target_outer[face]
        for s, d in ((source_section, target_section), (inner[face], target_inner[face]), (outer[face], target_outer[face])):
            transform = _local_map(*s, *d, normal_sign=trace["cage_normal_sign"])
            if transform is not None:
                break
        body_face = target_inner[face]
        normal = np.cross(body_face[1] - body_face[0], body_face[2] - body_face[0])
        # Point the body-face normal away from the body side (toward the outer layer).
        if np.dot(normal, bary @ (target_outer[face] - body_face)) < 0:
            normal = -normal
        out["base"].append(bary @ target_section)
        out["residual"].append(residual)
        out["map"].append(transform)
        out["t"].append(t)
        out["normal"].append(normal / max(np.linalg.norm(normal), 1e-12))
    return {k: np.array(v) for k, v in out.items()}


def hanging_global(points, faces, base, residual, maps, global_matrix):
    """Like ``anchored`` but the hanging offset keeps its authored direction (global map only)."""
    length = np.linalg.norm(residual, axis=1) * STUD_CM
    bound = length <= ANCHOR_CM
    neighbors = [[] for _ in points]
    for a, b, c in faces:
        for i, j in ((a, b), (b, c), (c, a)):
            neighbors[i].append(j)
            neighbors[j].append(i)
    anchor = np.where(bound, np.arange(len(points)), -1)
    queue = deque(np.flatnonzero(bound))
    while queue:
        i = queue.popleft()
        for j in neighbors[i]:
            if anchor[j] < 0:
                anchor[j] = anchor[i]
                queue.append(j)
    result = base + np.einsum("nij,nj->ni", maps, residual)
    for i in np.flatnonzero(~bound & (anchor >= 0)):
        a = anchor[i]
        result[i] = result[a] + (points[i] - points[a]) @ global_matrix
    return result


def score(fitted, roblox, faces):
    distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
    return {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
            "mediana_cm": round(float(np.median(distance)), 2),
            "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}


def main():
    names = sys.argv[1:] or [c for c in CASES if c != "sueter oversized"]
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    report, meshes = {}, {}
    for case in names:
        asset, export = CASES[case]
        groups = load_obj_groups(export)
        roblox_raw, faces, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, all_faces, _, _ = engine.load_obj(next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj")) if "fitted" not in p))
        keep = np.unique(all_faces[:len(faces)])
        points = source[keep].astype(float)
        trace = {}
        retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                         DIRECTORY / "wrap_cages", binding_audit=trace)
        shell = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                           trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
        d = bind_details(points, trace, shell)
        plain = d["base"] + np.einsum("nij,nj->ni", d["map"], d["residual"])
        local_anchor, _, _ = anchored(points, faces, d["base"], d["residual"], d["map"])
        _, global_matrix = global_shell(trace)
        global_anchor = hanging_global(points, faces, d["base"], d["residual"], d["map"], global_matrix)
        entry = {"atual": score(plain, roblox, faces),
                 "pendurados: ancora + rotacao local": score(local_anchor, roblox, faces),
                 "pendurados: ancora + direcao original": score(global_anchor, roblox, faces)}
        meshes[f"{case}|direcao original"] = global_anchor
        # Error decomposition for prism-bound vertices.
        inside = np.linalg.norm(d["residual"], axis=1) * STUD_CM <= ANCHOR_CM
        error = (roblox - plain) * STUD_CM
        breakdown = {}
        for name, lo, hi in (("t 0-0.2 (lado do corpo)", 0, .2), ("t 0.2-0.8 (meio)", .2, .8), ("t 0.8-1 (cage externa)", .8, 1.01)):
            mask = inside & (d["t"] >= lo) & (d["t"] < hi)
            if mask.sum() < 5:
                continue
            e = error[mask]
            outward = np.einsum("ij,ij->i", e, d["normal"][mask])
            breakdown[name] = {
                "vertices": int(mask.sum()),
                "erro_mediano_cm": round(float(np.median(np.linalg.norm(e, axis=1))), 2),
                "acima_5cm_pct": round(float((np.linalg.norm(e, axis=1) > 5).mean() * 100), 1),
                # Mean of Roblox minus ours: + outward = Roblox sits farther from the body than we do.
                "Roblox_menos_nosso_medio_cm": {"para_fora_do_corpo": round(float(outward.mean()), 2),
                                                "lateral_x": round(float(e[:, 0].mean()), 2),
                                                "frente_tras_y": round(float(e[:, 1].mean()), 2),
                                                "cima_baixo_z": round(float(e[:, 2].mean()), 2)},
            }
        entry["erro por profundidade no prisma"] = breakdown
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "hanging_pants_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    np.savez_compressed(GT / "hanging_meshes.npz", **meshes)


if __name__ == "__main__":
    main()
