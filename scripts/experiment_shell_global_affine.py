"""Offline control: transfer garment shell displacement with one global map.

This preserves authored shell coherence but cannot follow all local body shape.
It tests whether local frame rotations are causing skirt/leg crossover.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS
from scripts.audit_outer_cage_clearance import outward_vertex_normals
from scripts.benchmark_wrap_frames import edges_report
from scripts.experiment_chart_blend import face_change_report, load_body_for_preview
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def global_shell(trace):
    reference = trace["reference_parent"]
    target = trace["target_body"]
    source_outer = trace["outer_parent"]
    source_center = reference.mean(axis=0)
    target_center = target.mean(axis=0)
    matrix, _, _, _ = np.linalg.lstsq(reference - source_center,
                                      target - target_center, rcond=None)
    outer = target + (source_outer - reference) @ matrix
    return outer, matrix


def remap_visible(trace, target_outer):
    result = np.empty_like(trace["target_vertices"])
    source = trace["source_vertices"]
    source_outer = trace["source_outer"]
    for i, point in enumerate(source):
        face = trace["projection_faces"][trace["face_indices"][i]]
        source_triangle = source_outer[face]
        target_triangle = target_outer[face]
        q, u, v, w = closest_point_on_triangle(point, *source_triangle)
        transform = _local_map(*source_triangle, *target_triangle,
                               normal_sign=trace["cage_normal_sign"])
        result[i] = np.asarray([u, v, w]) @ target_triangle + transform @ (point - q)
    return result


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    preview = "--preview" in sys.argv
    if preview:
        body, body_faces = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report = {}
    for asset in ASSETS:
        vertices, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        baseline, _ = retarget_garment_with_wrap_layer(
            engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        outer, matrix = global_shell(trace)
        fitted = remap_visible(trace, outer)
        report[asset] = {
            "baseline": edges_report(vertices, baseline, faces),
            "global_shell": edges_report(vertices, fitted, faces),
            "face_changes": face_change_report(faces, baseline, fitted),
            "global_map": matrix.tolist(),
        }
        if preview:
            shared = np.vstack((baseline, fitted))
            for label, output in (("baseline", baseline), ("global_shell", fitted)):
                path = ROOT / f"artifacts/clothing_audit/global_shell_{asset}_{label}.png"
                report[asset][label + "_visibility"] = depth_preview(
                    body, body_faces, output, faces, path, shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
            cage_faces = trace["projection_faces"]
            source_normal, valid = outward_vertex_normals(trace["reference_parent"],
                                                           cage_faces)
            offsets = np.einsum("ij,ij->i",
                                trace["outer_parent"] - trace["reference_parent"],
                                source_normal)
            threshold = np.quantile(np.abs(offsets[valid]), .99) * .1
            expanded = cage_faces[np.any(np.abs(offsets[cage_faces]) > threshold, axis=1)]
            cage_path = ROOT / f"artifacts/clothing_audit/global_shell_cage_{asset}.png"
            depth_preview(body, body_faces, outer, expanded, cage_path)
            report[asset]["global_shell_cage_image"] = str(cage_path.relative_to(ROOT))
    path = ROOT / "artifacts/clothing_audit/WRAP_GLOBAL_SHELL.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({a: {"baseline": r["baseline"],
                          "global_shell": r["global_shell"],
                          "face_changes": r["face_changes"]}
                      for a, r in report.items()}, indent=2))


if __name__ == "__main__":
    main()
