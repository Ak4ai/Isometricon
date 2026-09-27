"""Offline gradient-domain garment retargeting using whole-mesh connectivity.

Each source garment triangle picks one nearby cage frame. Its three directed
edges are transported together; a global least-squares solve makes all face
gradients consistent. This does not change runtime behavior.
"""
from collections import defaultdict
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
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def choose_face_frames(faces, trace):
    """Assign one cage frame to each garment triangle, using its centroid."""
    source = trace["source_vertices"]
    selected = trace["face_indices"]
    cage_faces = trace["projection_faces"]
    cage = trace["source_outer"]
    target = trace["target_outer"]
    frames = np.empty((len(faces), 3, 3), dtype=np.float64)
    labels = np.empty(len(faces), dtype=np.int32)
    for i, garment_face in enumerate(faces):
        center = source[garment_face].mean(axis=0)
        options = np.unique(selected[garment_face])
        nearest = min(options, key=lambda face_id: np.linalg.norm(
            center - closest_point_on_triangle(center, *cage[cage_faces[face_id]])[0]))
        labels[i] = nearest
        cage_face = cage_faces[nearest]
        frames[i] = _local_map(*cage[cage_face], *target[cage_face],
                               normal_sign=trace["cage_normal_sign"])
    return frames, labels


def geometric_seam_pairs(vertices, faces, normal_threshold=0.7):
    """Pair coincident UV-split vertices only if their source normals agree."""
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    vertex_normal = np.zeros_like(vertices, dtype=np.float64)
    np.add.at(vertex_normal, faces.reshape(-1), np.repeat(normals, 3, axis=0))
    vertex_normal /= np.maximum(np.linalg.norm(vertex_normal, axis=1)[:, None], 1e-12)
    groups = defaultdict(list)
    for index, point in enumerate(vertices):
        groups[tuple(np.round(point, 5))].append(index)
    pairs = []
    for indices in groups.values():
        for offset, a in enumerate(indices):
            for b in indices[offset + 1:]:
                if np.dot(vertex_normal[a], vertex_normal[b]) >= normal_threshold:
                    pairs.append((a, b))
    return np.asarray(pairs, dtype=np.int32).reshape(-1, 2)


def solve_surface(source, faces, trace, anchor_weight=0.2, seam_weight=4.0,
                  max_iterations=400):
    """Solve transported face gradients with sparse Laplacian CG in NumPy."""
    baseline = np.asarray(trace["target_vertices"], dtype=np.float64)
    frames, face_labels = choose_face_frames(faces, trace)
    # All three edges of each triangle share the same cage frame.
    first = np.concatenate((faces[:, 0], faces[:, 1], faces[:, 2]))
    second = np.concatenate((faces[:, 1], faces[:, 2], faces[:, 0]))
    transforms = np.concatenate((frames, frames, frames))
    desired = np.einsum("nij,nj->ni", transforms, source[second] - source[first])
    weights = np.ones(len(first), dtype=np.float64)
    seams = geometric_seam_pairs(source, faces)
    if len(seams):
        first = np.concatenate((first, seams[:, 0]))
        second = np.concatenate((second, seams[:, 1]))
        desired = np.vstack((desired, np.zeros((len(seams), 3))))
        weights = np.concatenate((weights, np.full(len(seams), seam_weight)))
    degree = np.bincount(np.concatenate((first, second)),
                         weights=np.concatenate((weights, weights)), minlength=len(source))
    anchors = anchor_weight * np.maximum(degree, 1)
    rhs = anchors[:, None] * baseline
    np.add.at(rhs, first, -weights[:, None] * desired)
    np.add.at(rhs, second, weights[:, None] * desired)

    def matrix_multiply(x):
        out = anchors[:, None] * x
        difference = weights[:, None] * (x[first] - x[second])
        np.add.at(out, first, difference)
        np.add.at(out, second, -difference)
        return out

    x = baseline.copy()
    residual = rhs - matrix_multiply(x)
    diagonal = anchors + degree
    z = residual / diagonal[:, None]
    direction = z.copy()
    rho = float(np.sum(residual * z))
    initial = max(float(np.linalg.norm(residual)), 1e-12)
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        action = matrix_multiply(direction)
        alpha = rho / max(float(np.sum(direction * action)), 1e-30)
        x += alpha * direction
        residual -= alpha * action
        if np.linalg.norm(residual) < initial * 1e-7:
            break
        z = residual / diagonal[:, None]
        next_rho = float(np.sum(residual * z))
        direction = z + (next_rho / rho) * direction
        rho = next_rho
    return x, {"iterations": iterations, "seam_pairs": len(seams),
               "face_frame_changes": int(np.count_nonzero(
                   face_labels != trace["face_indices"][faces[:, 0]]))}


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
        fitted, solver = solve_surface(trace["source_vertices"], faces, trace)
        report[asset] = {"baseline": edges_report(vertices, baseline, faces),
                         "surface": edges_report(vertices, fitted, faces),
                         "face_changes": face_change_report(faces, baseline, fitted),
                         "solver": solver}
        if preview:
            shared = np.vstack((baseline, fitted))
            for label, output in (("baseline", baseline), ("surface", fitted)):
                path = ROOT / f"artifacts/clothing_audit/surface_poisson_{asset}_{label}.png"
                report[asset][label + "_visibility"] = depth_preview(
                    body, body_faces, output, faces, path, shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
    path = ROOT / "artifacts/clothing_audit/WRAP_SURFACE_POISSON.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({asset: {"baseline": result["baseline"],
                              "surface": result["surface"],
                              "face_changes": result["face_changes"],
                              "solver": result["solver"]}
                      for asset, result in report.items()}, indent=2))


if __name__ == "__main__":
    main()
