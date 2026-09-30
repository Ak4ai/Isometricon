"""Two targeted fixes, scored against Roblox Studio exports.

1. Anchored residual: garment vertices far outside every prism (hanging bows,
   strings) stop choosing their own prism. Each follows the prism frame of the
   nearest vertex, along the garment's own edges, that does sit in a prism, so
   a hanging piece moves rigidly with the point where it is attached.
2. Outer-cage source for baggy pants: radial vs the runtime's per-face transfer
   vs the authored thickness kept unrotated.
"""
from collections import deque
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_prism_residual_roblox import bind_parts
from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, edge_ratio, load_obj_groups
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

ANCHOR_CM = 1.0  # residual above this = the vertex hangs outside the cage prisms


def anchored(points, faces, base, residual, maps):
    """Hanging vertices follow the frame of their nearest (by mesh edges) prism-bound vertex."""
    length = np.linalg.norm(residual, axis=1) * STUD_CM
    bound = length <= ANCHOR_CM
    neighbors = [[] for _ in points]
    for a, b, c in faces:
        for i, j in ((a, b), (b, c), (c, a)):
            neighbors[i].append(j)
            neighbors[j].append(i)
    anchor = np.where(bound, np.arange(len(points)), -1)
    queue = deque(np.flatnonzero(bound))
    while queue:  # multi-source BFS over garment edges
        i = queue.popleft()
        for j in neighbors[i]:
            if anchor[j] < 0:
                anchor[j] = anchor[i]
                queue.append(j)
    result = base + np.einsum("nij,nj->ni", maps, residual)
    for i in np.flatnonzero(~bound & (anchor >= 0)):
        a = anchor[i]
        anchor_target = base[a] + maps[a] @ residual[a]
        result[i] = anchor_target + maps[a] @ (points[i] - points[a])
    return result, int((~bound).sum()), int((anchor < 0).sum())


def score(fitted, roblox, faces):
    distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
    return {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
            "mediana_cm": round(float(np.median(distance)), 2),
            "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}


def main():
    names = sys.argv[1:] or list(CASES)
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
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
        try:
            retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                             DIRECTORY / "wrap_cages", binding_audit=trace)
        except Exception as exc:
            report[case] = {"erro": str(exc)}
            continue
        radial = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                            trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
        shells = {"radial": radial,
                  "por face (runtime)": trace["reference_order_target_outer"],
                  "espessura sem girar": trace["target_body"] + (trace["outer_parent"] - trace["reference_parent"]) * 1.5}
        entry = {}
        for shell_name, shell in shells.items():
            base, residual, maps = bind_parts(points, trace, shell)
            plain = base + np.einsum("nij,nj->ni", maps, residual)
            entry[f"cage {shell_name}"] = score(plain, roblox, faces)
            fixed, hanging, orphan = anchored(points, faces, base, residual, maps)
            entry[f"cage {shell_name} + fitas ancoradas"] = {**score(fixed, roblox, faces),
                                                             "vertices_pendurados": hanging, "sem_ancora": orphan}
            meshes[f"{case}|{shell_name}|ancorado"] = fixed
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "anchor_shell_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    np.savez_compressed(GT / "anchor_shell_meshes.npz", **meshes)


if __name__ == "__main__":
    main()
