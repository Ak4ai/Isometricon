"""Offline diagnosis of foot-cage influence on the jeans-with-boots asset."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import face_charts
from scripts.experiment_chart_blend import load_body_for_preview
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _closest_triangle, _local_map, retarget_garment_with_wrap_layer

ASSET = "109837605892174"


def chart_labels(engine, trace):
    charts = face_charts(trace["projection_faces"], trace["uv_index"])
    uv_regions = {}
    for name, part in engine.r15_female_cages.items():
        if name.endswith("Forearm"):
            continue
        for uv in part["face_uvs"].reshape(-1, 2):
            uv_regions[tuple(np.round(uv, 5))] = name
    counts = defaultdict(Counter)
    for face, chart in zip(trace["projection_faces"], charts):
        for vertex in face:
            uv = trace["target_uv"][trace["uv_index"][vertex]]
            counts[int(chart)][uv_regions.get(tuple(np.round(uv, 5)), "Unknown")] += 1
    labels = {chart: count.most_common(1)[0][0] for chart, count in counts.items()}
    return charts, labels


def edge_metrics(source, target, faces):
    edges = np.unique(np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]],
                                               faces[:, [2, 0]])), axis=1), axis=0)
    a = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    b = np.linalg.norm(target[edges[:, 0]] - target[edges[:, 1]], axis=1)
    valid = a >= .01
    return {"over_3x": int(np.count_nonzero(valid & (b > 3 * a))),
            "over_5x": int(np.count_nonzero(valid & (b > 5 * a))),
            "max_length_m": float(b[valid].max())}


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    obj = next(directory.glob(f"*_{ASSET}.obj"))
    garment, mesh_faces, _, _ = engine.load_obj(str(obj))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, garment, str(next(directory.glob(f"*_{ASSET}.rbxm"))),
        directory / "wrap_cages", binding_audit=trace)
    charts, labels = chart_labels(engine, trace)
    selected = charts[trace["face_indices"]]
    foot_charts = [chart for chart, label in labels.items() if label in ("LeftFoot", "RightFoot")]
    foot = np.isin(selected, foot_charts)
    source = trace["source_vertices"]
    baseline = np.asarray(baseline, dtype=np.float64)
    output = baseline.copy()
    allowed = ~np.isin(charts, foot_charts)
    faces = trace["projection_faces"][allowed]
    outer = trace["source_outer"]
    target_outer = trace["target_outer"]
    lo, hi = outer[faces].min(axis=1), outer[faces].max(axis=1)
    alternate_distances = []
    for index in np.flatnonzero(foot):
        distance, found = _closest_triangle(source[index], outer, faces, lo, hi,
                                            closest_point_on_triangle)
        face_id, q, bary = found
        face = faces[face_id]
        transform = _local_map(*outer[face], *target_outer[face],
                               normal_sign=trace["cage_normal_sign"])
        output[index] = np.asarray(bary) @ target_outer[face] + transform @ (source[index] - q)
        alternate_distances.append(distance)

    foot_displacement = np.linalg.norm(output[foot] - baseline[foot], axis=1)
    face_vertex_foot = foot[mesh_faces].any(axis=1)
    report = {
        "asset": obj.name,
        "mesh_vertices": len(garment),
        "foot_bound_vertices": int(foot.sum()),
        "foot_bound_fraction": float(foot.mean()),
        "foot_bound_source_y_range": [float(source[foot, 1].min()), float(source[foot, 1].max())],
        "foot_bound_target_z_range": [float(baseline[foot, 2].min()), float(baseline[foot, 2].max())],
        "foot_bound_faces_fraction": float(face_vertex_foot.mean()),
        "alternate_distance_p50_m": float(np.median(alternate_distances)),
        "alternate_distance_p99_m": float(np.quantile(alternate_distances, .99)),
        "change_p50_m": float(np.median(foot_displacement)),
        "change_p99_m": float(np.quantile(foot_displacement, .99)),
        "edge_metrics_baseline": edge_metrics(garment, baseline, mesh_faces),
        "edge_metrics_without_foot": edge_metrics(garment, output, mesh_faces),
        "bindings_by_part": dict(Counter(labels[int(chart)] for chart in selected)),
    }
    body, body_faces = load_body_for_preview(
        ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    shared = np.vstack((baseline, output))
    out_dir = ROOT / "artifacts/clothing_audit"
    for name, vertices in (("baseline", baseline), ("no_foot", output)):
        depth_preview(body, body_faces, vertices, mesh_faces,
                      out_dir / f"jeans_foot_binding_{name}.png",
                      shared_garment_vertices=shared)
    (out_dir / "JEANS_FOOT_BINDING.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
