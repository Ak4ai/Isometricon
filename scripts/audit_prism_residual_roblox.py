"""Is the prism residual (garment point outside its inner/outer prism) what goes wrong?

Compares, against Roblox Studio exports, three ways of carrying the residual:
the current local map (rotation + stretch), its closest pure rotation, and no
transform at all. Also bins the error by residual length.
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
from scripts.experiment_dual_cage_prism import closest_prism_binding
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def nearest_rotation(matrix):
    u, _, vt = np.linalg.svd(matrix)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:  # Keep the frame's handedness (parity is already in the map).
        u[:, -1] *= -1
        rotation = u @ vt
    return rotation


def bind_parts(garment, trace, target_outer):
    """bind_dual_cage split into (prism point in target, residual, local map)."""
    inner, outer = trace["reference_parent"], trace["outer_parent"]
    target_inner = trace["target_body"]
    faces = trace["projection_faces"]
    area = lambda v: np.linalg.norm(np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]]), axis=1)
    faces = faces[(area(inner) > 1e-8) & (area(outer) > 1e-8)]
    six = np.concatenate((inner[faces], outer[faces]), axis=1)
    lower, upper = six.min(1), six.max(1)
    base, residuals, maps = [], [], []
    for point in np.asarray(garment, float):
        _, (face_id, t, bary, residual) = closest_prism_binding(point, inner, outer, faces, lower, upper)
        face = faces[face_id]
        source_section = (1 - t) * inner[face] + t * outer[face]
        target_section = (1 - t) * target_inner[face] + t * target_outer[face]
        transform = None
        for s, d in ((source_section, target_section), (inner[face], target_inner[face]), (outer[face], target_outer[face])):
            transform = _local_map(*s, *d, normal_sign=trace["cage_normal_sign"])
            if transform is not None:
                break
        base.append(bary @ target_section)
        residuals.append(residual)
        maps.append(transform)
    return np.array(base), np.array(residuals), np.array(maps)


def main():
    names = sys.argv[1:] or ["calca skater", "saia-short", "jeans com bota", "vestido", "camisa social", "jaqueta bomber"]
    body, _, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
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
        shell = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                           trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
        base, residual, maps = bind_parts(source[keep], trace, shell)
        stretch = np.array([np.linalg.svd(m, compute_uv=False) for m in maps])
        variants = {
            "atual (gira + estica)": base + np.einsum("nij,nj->ni", maps, residual),
            "so rotacao": base + np.einsum("nij,nj->ni", np.array([nearest_rotation(m) for m in maps]), residual),
            "sem transformar": base + residual,
        }
        length = np.linalg.norm(residual, axis=1) * STUD_CM
        entry = {"residuo_cm": {"mediana": round(float(np.median(length)), 2), "p90": round(float(np.quantile(length, .9)), 2),
                                "max": round(float(length.max()), 1)},
                 "esticamento_do_mapa_p50_p99": [round(float(np.quantile(stretch.max(1), q)), 2) for q in (.5, .99)]}
        bins = [(0, .5), (.5, 3), (3, 8), (8, 1e9)]
        for label, fitted in variants.items():
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            row = {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                   "mediana_cm": round(float(np.median(distance)), 2),
                   "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
            for lo, hi in bins:
                mask = (length >= lo) & (length < hi)
                if mask.any():
                    row[f"residuo {lo}-{hi if hi < 1e8 else 'mais'} cm ({mask.sum()} v): erro mediano"] = round(float(np.median(distance[mask])), 1)
            entry[label] = row
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "prism_residual_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
