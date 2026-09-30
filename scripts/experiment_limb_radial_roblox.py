"""Radial outer-cage transfer with influences kept inside one limb, scored against Roblox.

Hypothesis: the inside of one trouser leg is pulled toward the other leg
because the radial search lets body-cage points of the other leg influence it.
Limbs: left leg, right leg, torso, left arm, right arm, head (by R15 part of
the UV-matched body cage vertex).
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
from scripts.experiment_part_rotation_roblox import part_labels
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import _neighborhoods, _rotation, transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def limb_of(part):
    for side in ("Left", "Right"):
        if part.startswith(side):
            return side + ("Leg" if any(k in part for k in ("Leg", "Foot")) else "Arm")
    return "Head" if part == "Head" else "Torso"


def radial_within(reference, outer, target, faces, groups, parity, radius_factor=1.0):
    """transfer_outer_cage_radial with influences restricted to the same group."""
    source_extent, target_extent = np.ptp(reference, axis=0), np.ptp(target, axis=0)
    valid = source_extent > 1e-8
    bulk_scale = float(np.median(target_extent[valid] / source_extent[valid]))
    rotations = np.empty((len(reference), 3, 3))
    for index, adjacent in enumerate(_neighborhoods(faces, len(reference), 1)):
        rotations[index] = _rotation(reference[adjacent] - reference[index], target[adjacent] - target[index], parity)
    thickness = np.linalg.norm(outer - reference, axis=1)
    total, weight_total = np.zeros_like(outer), np.zeros(len(outer))
    for source_id, center in enumerate(reference):
        distance = np.linalg.norm(outer - center, axis=1)
        selected = np.flatnonzero((distance <= max(radius_factor * thickness[source_id], 1e-8))
                                  & (groups == groups[source_id]))
        if source_id not in selected:
            selected = np.append(selected, source_id)
        weights = 1.0 / np.maximum(distance[selected], 1e-6)
        weights /= weights.sum()
        predicted = target[source_id] + bulk_scale * ((outer[selected] - center) @ rotations[source_id])
        np.add.at(total, selected, weights[:, None] * predicted)
        np.add.at(weight_total, selected, weights)
    return total / weight_total[:, None]


def main():
    names = sys.argv[1:] or [c for c in CASES if c != "sueter oversized"]
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
        limbs = np.array([limb_of(p) for p in part_labels(engine, trace)])
        args = (trace["reference_parent"], trace["outer_parent"], trace["target_body"], trace["projection_faces"])
        shells = {"radial (livre)": transfer_outer_cage_radial(*args, parity=trace["cage_normal_sign"], radius_factor=1.0),
                  "radial (so dentro do membro)": radial_within(*args, limbs, trace["cage_normal_sign"])}
        entry = {}
        for label, shell in shells.items():
            fitted = bind_dual_cage(source, trace, shell)[0][keep]
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            row = {"acima_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                   "mediana_cm": round(float(np.median(distance)), 2),
                   "arestas_3x": int((edge_ratio(roblox, fitted, faces) > 3).sum())}
            low = roblox[:, 2] < roblox[:, 2].min() + 0.25
            for side, name in ((1, "esq"), (-1, "dir")):
                mask = low & (np.sign(roblox[:, 0]) == side)
                if mask.sum() > 20 and roblox[:, 2].min() < -0.5:  # trouser hems only
                    row[f"barra {name}: centro Roblox-nosso x cm"] = round(float((roblox[mask, 0].mean() - fitted[mask, 0].mean()) * STUD_CM), 1)
            entry[label] = row
        report[case] = entry
        print(f"{case:16s}", json.dumps(entry, ensure_ascii=False), flush=True)
    (GT / "limb_radial_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
