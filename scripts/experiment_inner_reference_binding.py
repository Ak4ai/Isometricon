"""Offline control: bind visible clothing to WrapLayer's inner reference cage.

The current fitter binds the visible mesh to the authored outer cage. This
control uses the reference/inner cage in parent MeshPart coordinates and maps
it directly to the target body cage. It is not asserted to reproduce Roblox.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS
from scripts.benchmark_wrap_frames import edges_report
from scripts.experiment_chart_blend import face_change_report, load_body_for_preview
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _closest_triangle, _local_map, retarget_garment_with_wrap_layer


def bind_visible_to_inner(garment, trace):
    """Return the direct inner-to-target fit and its source binding audit."""
    source = np.asarray(trace["reference_parent"], dtype=np.float64)
    target = np.asarray(trace["target_body"], dtype=np.float64)
    all_faces = np.asarray(trace["projection_faces"], dtype=np.int32)
    source_area = np.linalg.norm(np.cross(
        source[all_faces[:, 1]] - source[all_faces[:, 0]],
        source[all_faces[:, 2]] - source[all_faces[:, 0]]), axis=1)
    target_area = np.linalg.norm(np.cross(
        target[all_faces[:, 1]] - target[all_faces[:, 0]],
        target[all_faces[:, 2]] - target[all_faces[:, 0]]), axis=1)
    valid = (source_area > 1e-8) & (target_area > 1e-10)
    for face_index in np.flatnonzero(valid):
        face = all_faces[face_index]
        if _local_map(*source[face], *target[face],
                      normal_sign=trace["cage_normal_sign"]) is None:
            valid[face_index] = False
    faces = all_faces[valid]
    original_face_indices = np.flatnonzero(valid)
    triangles = source[faces]
    lo = triangles.min(axis=1)
    hi = triangles.max(axis=1)
    result = np.empty((len(garment), 3), dtype=np.float64)
    distances = np.empty(len(garment), dtype=np.float64)
    identity_error = 0.0
    selected = np.empty(len(garment), dtype=np.int32)
    for i, point in enumerate(np.asarray(garment, dtype=np.float64)):
        distance, found = _closest_triangle(point, source, faces, lo, hi,
                                            closest_point_on_triangle)
        if found is None:
            raise ValueError("Inner reference cage has no valid binding triangle")
        face_index, q, barycentric = found
        selected[i] = original_face_indices[face_index]
        face = faces[face_index]
        source_triangle = source[face]
        target_triangle = target[face]
        transform = _local_map(*source_triangle, *target_triangle,
                               normal_sign=trace["cage_normal_sign"])
        if transform is None:
            raise ValueError("Degenerate inner reference triangle")
        result[i] = np.asarray(barycentric) @ target_triangle + transform @ (point - q)
        distances[i] = distance
        # The binding should reproduce its original point when the target is
        # exactly the source reference, including points outside the cage.
        identity_transform = _local_map(*source_triangle, *source_triangle)
        identity_point = (np.asarray(barycentric) @ source_triangle +
                          identity_transform @ (point - q))
        identity_error = max(identity_error, float(np.linalg.norm(identity_point - point)))
    return result, {
        "source_distance_median": float(np.median(distances)),
        "source_distance_p99": float(np.quantile(distances, .99)),
        "identity_max_error": identity_error,
        "excluded_degenerate_reference_faces": int(np.count_nonzero(~valid)),
        "selected_face_indices": selected,
    }


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    preview = "--preview" in sys.argv
    if preview:
        body, body_faces = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report = {}
    for asset in ASSETS:
        garment, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        baseline, info = retarget_garment_with_wrap_layer(
            engine, garment, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        inner, audit = bind_visible_to_inner(garment, trace)
        selected = audit.pop("selected_face_indices")
        report[asset] = {
            "outer_binding": edges_report(garment, baseline, faces),
            "inner_binding": edges_report(garment, inner, faces),
            "face_changes_vs_outer": face_change_report(faces, baseline, inner),
            "outer_source_distance_median": info["median_source_distance"],
            "outer_source_distance_p99": info["p99_source_distance"],
            "inner_binding_audit": audit,
            "different_binding_face_fraction": float(np.mean(selected != trace["face_indices"])),
        }
        if preview:
            shared = np.vstack((baseline, inner))
            for label, output in (("outer_binding", baseline), ("inner_binding", inner)):
                path = ROOT / f"artifacts/clothing_audit/inner_reference_{asset}_{label}.png"
                report[asset][label + "_visibility"] = depth_preview(
                    body, body_faces, output, faces, path, shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
    path = ROOT / "artifacts/clothing_audit/WRAP_INNER_REFERENCE_BINDING.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({asset: {"outer_edges": row["outer_binding"]["over_3x"],
                               "inner_edges": row["inner_binding"]["over_3x"],
                               "inner_distance_p99": row["inner_binding_audit"]["source_distance_p99"],
                               "identity_error": row["inner_binding_audit"]["identity_max_error"],
                               "normal_changes": row["face_changes_vs_outer"]["normal_reversed"]}
                      for asset, row in report.items()}, indent=2))


if __name__ == "__main__":
    main()
