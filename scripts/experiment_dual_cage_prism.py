"""Offline dual-cage volume binding using corresponding inner/outer faces.

Each visible vertex is fitted to a paired triangular prism of the authored
inner and outer cage, then evaluated between the corresponding target body
and transferred garment outer cage. This is a geometric control, not a
claim to reproduce Roblox's unpublished runtime algorithm.
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
from scripts.experiment_shell_global_affine import global_shell
from scripts.experiment_shell_adaptive import shell_weights
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def closest_prism_binding(point, inner, outer, faces, lower, upper):
    """Fit a point to a matched inner/outer triangle pair."""
    lower_bound = np.linalg.norm(np.maximum(np.maximum(lower - point, point - upper), 0), axis=1)
    order = np.argsort(lower_bound)
    best_distance = float("inf")
    best = None
    for face_id in order:
        if lower_bound[face_id] > best_distance + 1e-10:
            break
        face = faces[face_id]
        inner_face = inner[face]
        outer_face = outer[face]
        # Alternating exact triangle projection and closed-form layer depth.
        # Multiple starts avoid freezing on a coincident or degenerate inner
        # triangle. The t=0 and t=1 surfaces are always considered.
        for start in (0.0, 0.5, 1.0):
            t = start
            for _ in range(4):
                section = (1 - t) * inner_face + t * outer_face
                q, u, v, w = closest_point_on_triangle(point, *section)
                bary = np.asarray((u, v, w))
                inner_q = bary @ inner_face
                direction = bary @ (outer_face - inner_face)
                denom = float(np.dot(direction, direction))
                if denom > 1e-16:
                    t = float(np.clip(np.dot(point - inner_q, direction) / denom, 0, 1))
            section = (1 - t) * inner_face + t * outer_face
            q, u, v, w = closest_point_on_triangle(point, *section)
            distance = float(np.linalg.norm(point - q))
            if distance < best_distance:
                best_distance = distance
                best = (int(face_id), t, np.asarray((u, v, w)), point - q)
    return best_distance, best


def bind_dual_cage(garment, trace, target_outer):
    inner = np.asarray(trace["reference_parent"], dtype=np.float64)
    outer = np.asarray(trace["outer_parent"], dtype=np.float64)
    target_inner = np.asarray(trace["target_body"], dtype=np.float64)
    target_outer = np.asarray(target_outer, dtype=np.float64)
    all_faces = np.asarray(trace["projection_faces"], dtype=np.int32)
    inner_area = np.linalg.norm(np.cross(inner[all_faces[:, 1]] - inner[all_faces[:, 0]],
                                         inner[all_faces[:, 2]] - inner[all_faces[:, 0]]), axis=1)
    outer_area = np.linalg.norm(np.cross(outer[all_faces[:, 1]] - outer[all_faces[:, 0]],
                                         outer[all_faces[:, 2]] - outer[all_faces[:, 0]]), axis=1)
    valid = (inner_area > 1e-8) & (outer_area > 1e-8)
    faces = all_faces[valid]
    six = np.concatenate((inner[faces], outer[faces]), axis=1)
    lower = six.min(axis=1)
    upper = six.max(axis=1)
    result = np.empty((len(garment), 3), dtype=np.float64)
    distances = np.empty(len(garment))
    levels = np.empty(len(garment))
    face_ids = np.empty(len(garment), dtype=np.int32)
    identity_error = 0.0
    for index, point in enumerate(np.asarray(garment, dtype=np.float64)):
        distance, found = closest_prism_binding(point, inner, outer, faces, lower, upper)
        if found is None:
            raise ValueError("No paired inner/outer prism for garment vertex")
        face_id, t, bary, residual = found
        face_ids[index] = face_id
        face = faces[face_id]
        source_section = (1 - t) * inner[face] + t * outer[face]
        target_section = (1 - t) * target_inner[face] + t * target_outer[face]
        transform = _local_map(*source_section, *target_section,
                               normal_sign=trace["cage_normal_sign"])
        if transform is None:
            # The nearest well-defined boundary frame is used only for the
            # residual. Barycentric cage interpolation remains unchanged.
            transform = _local_map(*inner[face], *target_inner[face],
                                   normal_sign=trace["cage_normal_sign"])
        if transform is None:
            transform = _local_map(*outer[face], *target_outer[face],
                                   normal_sign=trace["cage_normal_sign"])
        if transform is None:
            raise ValueError("Paired prism has no usable source/target frame")
        result[index] = bary @ target_section + transform @ residual
        distances[index] = distance
        levels[index] = t
        identity_transform = _local_map(*source_section, *source_section)
        if identity_transform is None:
            identity_transform = np.eye(3)
        identity_error = max(identity_error, float(np.linalg.norm(
            bary @ source_section + identity_transform @ residual - point)))
    return result, {
        "source_prism_distance_p99": float(np.quantile(distances, .99)),
        "source_prism_distance_median": float(np.median(distances)),
        "inside_prism_fraction_1e_minus_4": float(np.mean(distances < 1e-4)),
        "layer_level_quantiles": np.quantile(levels, [.1, .5, .9]).tolist(),
        "identity_max_error": identity_error,
        "excluded_degenerate_faces": int(np.count_nonzero(~valid)),
        "face_ids": face_ids,
    }


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    preview = "--preview" in sys.argv
    chosen = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or list(ASSETS)
    if preview:
        body, body_faces = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report_path = ROOT / "artifacts/clothing_audit/WRAP_DUAL_PRISM.json"
    report = (json.loads(report_path.read_text(encoding="utf-8"))
              if report_path.exists() else {})
    for asset in chosen:
        garment, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        baseline, _ = retarget_garment_with_wrap_layer(
            engine, garment, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        global_outer, _ = global_shell(trace)
        local_outer = trace["reference_order_target_outer"]
        disagreement = shell_weights(trace)["disagreement"]
        candidate_outer = {
            "local": local_outer,
            "global": global_outer,
            "adaptive": local_outer * (1 - disagreement[:, None]) +
                        global_outer * disagreement[:, None],
        }
        report[asset] = {"baseline": edges_report(garment, baseline, faces)}
        outputs = {"baseline": baseline}
        for label, outer in candidate_outer.items():
            fitted, audit = bind_dual_cage(garment, trace, outer)
            audit.pop("face_ids")
            outputs[label] = fitted
            report[asset][label] = {
                "edges": edges_report(garment, fitted, faces),
                "face_changes_vs_baseline": face_change_report(faces, baseline, fitted),
                "binding": audit,
            }
        if preview:
            shared = np.vstack(list(outputs.values()))
            for label, fitted in outputs.items():
                path = ROOT / f"artifacts/clothing_audit/dual_prism_{asset}_{label}.png"
                report[asset][label + "_visibility"] = depth_preview(
                    body, body_faces, fitted, faces, path, shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({a: {k: {"edges": v["edges"]["over_3x"],
                              "normals_over_90_vs_baseline": v["face_changes_vs_baseline"]["normal_reversed"],
                              "prism_p99": v["binding"]["source_prism_distance_p99"]}
                         for k, v in row.items() if k in candidate_outer}
                      for a, row in report.items()}, indent=2))


if __name__ == "__main__":
    main()
