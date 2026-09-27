"""Offline cage-shell controls blending local transport and global bulk.

Weights come from source-cage geometry, never garment names. This evaluates
whether the coherent global-shell skirt can be retained near long offsets
while close-fitting regions still follow local body frames.
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
from scripts.experiment_shell_global_affine import global_shell, remap_visible
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def source_edge_scale(trace):
    reference = trace["reference_parent"]
    faces = trace["projection_faces"]
    edges = np.unique(np.sort(np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1), axis=0)
    length = np.linalg.norm(reference[edges[:, 0]] - reference[edges[:, 1]], axis=1)
    totals = np.bincount(np.concatenate((edges[:, 0], edges[:, 1])),
                         weights=np.concatenate((length, length)), minlength=len(reference))
    counts = np.bincount(np.concatenate((edges[:, 0], edges[:, 1])), minlength=len(reference))
    return totals / np.maximum(counts, 1)


def frame_disagreement(trace):
    """RMS disagreement among local face transports at each cage vertex."""
    reference = trace["reference_parent"]
    target = trace["target_body"]
    delta = trace["outer_parent"] - reference
    faces = trace["projection_faces"]
    total = np.zeros_like(delta)
    squared = np.zeros(len(delta))
    count = np.zeros(len(delta))
    for face in faces:
        transform = _local_map(*reference[face], *target[face],
                               normal_sign=trace["cage_normal_sign"])
        if transform is None:
            continue
        moved = delta[face] @ transform.T
        np.add.at(total, face, moved)
        np.add.at(squared, face, np.sum(moved * moved, axis=1))
        np.add.at(count, face, 1)
    mean = total / np.maximum(count[:, None], 1)
    variance = np.maximum(squared / np.maximum(count, 1) -
                          np.sum(mean * mean, axis=1), 0)
    rms = np.sqrt(variance)
    amplitude = np.linalg.norm(mean, axis=1)
    return rms / np.maximum(rms + amplitude, 1e-12)


def shell_weights(trace):
    delta = trace["outer_parent"] - trace["reference_parent"]
    distance = np.linalg.norm(delta, axis=1)
    edge_scale = source_edge_scale(trace)
    distance_weight = distance**2 / np.maximum(distance**2 + edge_scale**2, 1e-16)
    disagreement_weight = frame_disagreement(trace)
    return {"distance": distance_weight,
            "disagreement": disagreement_weight,
            "combined": 1 - (1 - distance_weight) * (1 - disagreement_weight)}


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
        global_outer, _ = global_shell(trace)
        local_outer = trace["reference_order_target_outer"]
        source_outer = trace["outer_parent"]
        source_body = trace["reference_parent"]
        source_normals, valid = outward_vertex_normals(source_body,
                                                       trace["projection_faces"])
        signed = np.einsum("ij,ij->i", source_outer - source_body, source_normals)
        threshold = np.quantile(np.abs(signed[valid]), .99) * .1
        expanded = trace["projection_faces"][
            np.any(np.abs(signed[trace["projection_faces"]]) > threshold, axis=1)]
        report[asset] = {"baseline": edges_report(vertices, baseline, faces)}
        shared_outputs = {"baseline": baseline}
        for label, weight in shell_weights(trace).items():
            outer = local_outer * (1 - weight[:, None]) + global_outer * weight[:, None]
            fitted = remap_visible(trace, outer)
            shared_outputs[label] = fitted
            report[asset][label] = {
                "edge": edges_report(vertices, fitted, faces),
                "face_changes": face_change_report(faces, baseline, fitted),
                "weight_quantiles": np.quantile(weight, [.1, .5, .9, .99]).tolist(),
            }
            if preview:
                cage_path = ROOT / f"artifacts/clothing_audit/adaptive_cage_{asset}_{label}.png"
                depth_preview(body, body_faces, outer, expanded, cage_path)
                report[asset][label]["cage_image"] = str(cage_path.relative_to(ROOT))
        if preview:
            shared = np.vstack(list(shared_outputs.values()))
            for label, fitted in shared_outputs.items():
                path = ROOT / f"artifacts/clothing_audit/adaptive_{asset}_{label}.png"
                report[asset][label + "_visibility"] = depth_preview(
                    body, body_faces, fitted, faces, path, shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
    path = ROOT / "artifacts/clothing_audit/WRAP_ADAPTIVE_SHELL.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({asset: {name: {"edges": data["edge"]["over_3x"],
                                      "reversed": data["face_changes"]["normal_reversed"],
                                      "weights": data["weight_quantiles"]}
                              for name, data in results.items()
                              if name in ("distance", "disagreement", "combined")}
                      for asset, results in report.items()}, indent=2))


if __name__ == "__main__":
    main()
