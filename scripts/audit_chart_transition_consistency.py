"""Test whether a garment edge can be mapped coherently by either endpoint's cage face.

This is diagnostic only: a low edge length does not prove a valid surface fit.
"""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS, face_charts
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def map_on_face(point, face_id, trace):
    face = trace["projection_faces"][face_id]
    sa, sb, sc = trace["source_outer"][face]
    q, u, v, w = closest_point_on_triangle(point, sa, sb, sc)
    target = trace["target_outer"][face]
    transform = _local_map(sa, sb, sc, *target,
                           normal_sign=trace["cage_normal_sign"])
    if transform is None:
        return None
    return np.asarray([u, v, w]) @ target + transform @ (point - q)


def audit_asset(engine, asset):
    directory = ROOT / "assets/models/clothing"
    vertices, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
    trace = {}
    fitted, _ = retarget_garment_with_wrap_layer(
        engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
        directory / "wrap_cages", binding_audit=trace)
    edge = np.unique(np.sort(np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1), axis=0)
    original_length = np.linalg.norm(vertices[edge[:, 0]] - vertices[edge[:, 1]], axis=1)
    fitted_length = np.linalg.norm(fitted[edge[:, 0]] - fitted[edge[:, 1]], axis=1)
    selected = trace["face_indices"]
    charts = face_charts(trace["projection_faces"], trace["uv_index"])
    cross = charts[selected[edge[:, 0]]] != charts[selected[edge[:, 1]]]
    stretched = (original_length >= 0.01) & (fitted_length > 3 * original_length)
    cases = edge[cross & stretched]
    coherent = 0
    disagreement = []
    for a, b in cases:
        a, b = int(a), int(b)
        a_face, b_face = int(selected[a]), int(selected[b])
        # Compare two consistent edge mappings against the independently
        # selected mapping. Both vertices are evaluated in the same frame.
        aa = map_on_face(trace["source_vertices"][a], a_face, trace)
        ba = map_on_face(trace["source_vertices"][b], a_face, trace)
        ab = map_on_face(trace["source_vertices"][a], b_face, trace)
        bb = map_on_face(trace["source_vertices"][b], b_face, trace)
        if any(value is None for value in (aa, ba, ab, bb)):
            continue
        common_length = min(np.linalg.norm(aa - ba), np.linalg.norm(ab - bb))
        if common_length <= 3 * np.linalg.norm(vertices[a] - vertices[b]):
            coherent += 1
        disagreement.append(float(min(np.linalg.norm(aa - ab),
                                      np.linalg.norm(ba - bb))))
    return {
        "asset": asset,
        "stretched_cross_chart_edges": int(len(cases)),
        "same_face_could_remove_stretch": coherent,
        "endpoint_prediction_disagreement_median": float(np.median(disagreement))
        if disagreement else None,
        "endpoint_prediction_disagreement_p90": float(np.quantile(disagreement, .9))
        if disagreement else None,
    }


def main():
    engine = RobloxWearEngine(body_type="female")
    report = [audit_asset(engine, asset) for asset in ASSETS]
    output = ROOT / "artifacts/clothing_audit/WRAP_CHART_TRANSITION_CONSISTENCY.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
