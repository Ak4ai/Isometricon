"""Radial outer-cage transfer whose per-vertex map also stretches locally, scored against Roblox.

The original radial carries each thickness offset with a pure local rotation
times one global bulk scale. Where a limb widens much more than the body as a
whole (thin reference legs -> wide Blocky legs), the offset does not follow.
Here each body-cage vertex uses the least-squares linear map of its ring
neighbourhood (rotation + local stretch), optionally blended with the old one.
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
from src.clothing.multi_influence_shell import _neighborhoods, _rotation, transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def local_maps(reference, target, faces, parity, rings, stretch):
    """Row-vector maps: offset @ map. stretch=0 -> rotation * bulk (original), 1 -> full local linear fit."""
    extent_s, extent_t = np.ptp(reference, 0), np.ptp(target, 0)
    bulk = float(np.median(extent_t[extent_s > 1e-8] / extent_s[extent_s > 1e-8]))
    maps = np.empty((len(reference), 3, 3))
    for index, ids in enumerate(_neighborhoods(faces, len(reference), rings)):
        src, dst = reference[ids] - reference[index], target[ids] - target[index]
        rotation = _rotation(src, dst, parity) * bulk
        linear, *_ = np.linalg.lstsq(src, dst, rcond=None)
        # The neighbourhood is nearly flat, so the least-squares map is undetermined
        # along the surface normal: take the normal part from the rotation.
        u, s, vt = np.linalg.svd(src, full_matrices=False)
        normal = vt[-1] if s[-1] < 0.2 * s[0] else None
        if normal is not None:
            tangent = np.eye(3) - np.outer(normal, normal)
            linear = tangent @ linear + np.outer(normal, normal) @ rotation
        maps[index] = (1 - stretch) * rotation + stretch * linear
    return maps


def radial_with_maps(reference, outer, target, maps, radius_factor=1.0):
    thickness = np.linalg.norm(outer - reference, axis=1)
    total, weight_total = np.zeros_like(outer), np.zeros(len(outer))
    for source_id, center in enumerate(reference):
        distance = np.linalg.norm(outer - center, axis=1)
        selected = np.flatnonzero(distance <= max(radius_factor * thickness[source_id], 1e-8))
        if source_id not in selected:
            selected = np.append(selected, source_id)
        weights = 1.0 / np.maximum(distance[selected], 1e-6)
        weights /= weights.sum()
        predicted = target[source_id] + (outer[selected] - center) @ maps[source_id]
        np.add.at(total, selected, weights[:, None] * predicted)
        np.add.at(weight_total, selected, weights)
    return total / weight_total[:, None]


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
        ref, out, tgt, cf = trace["reference_parent"], trace["outer_parent"], trace["target_body"], trace["projection_faces"]
        shells = {"radial original": transfer_outer_cage_radial(ref, out, tgt, cf, parity=trace["cage_normal_sign"], radius_factor=1.0)}
        for rings in (1, 2):
            for stretch in (0.5, 1.0):
                maps = local_maps(ref, tgt, cf, trace["cage_normal_sign"], rings, stretch)
                shells[f"estica {stretch:g} anel {rings}"] = radial_with_maps(ref, out, tgt, maps)
        entry = {}
        for label, shell in shells.items():
            fitted = bind_dual_cage(source, trace, shell)[0][keep]
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            row = {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                   "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
            low = roblox[:, 2] < roblox[:, 2].min() + 0.25
            if roblox[:, 2].min() < -0.5:
                mask = low & (roblox[:, 0] > 0)
                row["barra esq x cm"] = round(float((roblox[mask, 0].mean() - fitted[mask, 0].mean()) * STUD_CM), 1)
            entry[label] = row
        report[case] = entry
        print(f"{case:16s}", " | ".join(f"{k}: {v['acima_5cm_pct']}% ar{v['arestas_3x']}" + (f" bx{v['barra esq x cm']}" if 'barra esq x cm' in v else "") for k, v in entry.items()), flush=True)
    (GT / "local_stretch_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
