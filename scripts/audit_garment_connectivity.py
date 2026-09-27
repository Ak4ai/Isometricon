"""Measure whether OBJ vertex connectivity matches geometric garment panels."""
from collections import defaultdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def connectivity_report(vertices, faces, fitted=None):
    n = len(vertices)
    parent = np.arange(n)

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, c in faces:
        parent[root(b)] = root(a)
        parent[root(c)] = root(a)
    roots, counts = np.unique([root(i) for i in range(n)], return_counts=True)
    position_groups = defaultdict(list)
    for i, position in enumerate(vertices):
        position_groups[tuple(np.round(position, 5))].append(i)
    split_groups = [ids for ids in position_groups.values()
                    if len({root(i) for i in ids}) > 1]
    face_position = vertices[faces]
    face_normal = np.cross(face_position[:, 1] - face_position[:, 0],
                           face_position[:, 2] - face_position[:, 0])
    face_length = np.linalg.norm(face_normal, axis=1)
    face_normal /= np.maximum(face_length[:, None], 1e-12)
    vertex_normal = np.zeros_like(vertices, dtype=np.float64)
    np.add.at(vertex_normal, faces.reshape(-1),
              np.repeat(face_normal, 3, axis=0))
    vertex_normal /= np.maximum(np.linalg.norm(vertex_normal, axis=1)[:, None], 1e-12)
    cross_component_pairs = 0
    aligned_pairs = 0
    opposed_pairs = 0
    aligned_seam_gaps = []
    opposed_panel_gaps = []
    for ids in split_groups:
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if root(a) == root(b):
                    continue
                cross_component_pairs += 1
                dot = np.dot(vertex_normal[a], vertex_normal[b])
                aligned_pairs += dot > 0.7
                opposed_pairs += dot < -0.7
                if fitted is not None:
                    gap = float(np.linalg.norm(fitted[a] - fitted[b]))
                    if dot > 0.7:
                        aligned_seam_gaps.append(gap)
                    elif dot < -0.7:
                        opposed_panel_gaps.append(gap)
    def joined_components(minimum_dot):
        joined = np.arange(n)

        def group(i):
            while joined[i] != i:
                joined[i] = joined[joined[i]]
                i = joined[i]
            return i

        for a, b, c in faces:
            joined[group(b)] = group(a)
            joined[group(c)] = group(a)
        for ids in position_groups.values():
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if np.dot(vertex_normal[a], vertex_normal[b]) >= minimum_dot:
                        joined[group(b)] = group(a)
        _, sizes = np.unique([group(i) for i in range(n)], return_counts=True)
        return len(sizes), sorted(map(int, sizes), reverse=True)[:5]

    aligned_components, aligned_sizes = joined_components(0.7)
    position_components, position_sizes = joined_components(-1.1)
    # A common position alone is not a seam. Reconnect face patches only
    # across an entire geometric edge, and reject opposing surface normals.
    face_parent = np.arange(len(faces))

    def face_root(i):
        while face_parent[i] != i:
            face_parent[i] = face_parent[face_parent[i]]
            i = face_parent[i]
        return i

    edge_owners = defaultdict(list)
    for face_id, (a, b, c) in enumerate(faces):
        for first, second in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((tuple(np.round(vertices[first], 5)),
                                tuple(np.round(vertices[second], 5)))))
            edge_owners[key].append(face_id)
    geometric_edge_links = 0
    rejected_opposed_edges = 0
    for owners in edge_owners.values():
        for i, left in enumerate(owners):
            for right in owners[i + 1:]:
                if np.dot(face_normal[left], face_normal[right]) < 0:
                    rejected_opposed_edges += 1
                    continue
                if face_root(left) != face_root(right):
                    face_parent[face_root(right)] = face_root(left)
                    geometric_edge_links += 1
    _, face_component_sizes = np.unique(
        [face_root(i) for i in range(len(faces))], return_counts=True)
    return {
        "vertices": n,
        "faces": len(faces),
        "raw_components": len(roots),
        "largest_raw_components": sorted(map(int, counts), reverse=True)[:10],
        "duplicate_position_groups": sum(len(ids) > 1 for ids in position_groups.values()),
        "duplicate_groups_across_components": len(split_groups),
        "vertices_in_cross_component_duplicates": sum(map(len, split_groups)),
        "cross_component_duplicate_pairs": cross_component_pairs,
        "normal_aligned_duplicate_pairs": int(aligned_pairs),
        "normal_opposed_duplicate_pairs": int(opposed_pairs),
        "aligned_weld_components": aligned_components,
        "largest_aligned_weld_components": aligned_sizes,
        "all_position_weld_components": position_components,
        "largest_all_position_weld_components": position_sizes,
        "geometric_edge_face_components": len(face_component_sizes),
        "largest_geometric_edge_face_components": sorted(
            map(int, face_component_sizes), reverse=True)[:5],
        "geometric_edge_links": geometric_edge_links,
        "rejected_opposed_edge_pairs": rejected_opposed_edges,
        "aligned_seam_gaps_over_0p01_units": sum(gap > 0.01 for gap in aligned_seam_gaps),
        "aligned_seam_gap_p90": float(np.quantile(aligned_seam_gaps, .9))
        if aligned_seam_gaps else None,
        "aligned_seam_gap_max": max(aligned_seam_gaps, default=0),
        "opposed_panel_gap_p90": float(np.quantile(opposed_panel_gaps, .9))
        if opposed_panel_gaps else None,
    }


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    report = {}
    for asset in ASSETS:
        vertices, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        fitted, _ = retarget_garment_with_wrap_layer(
            engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages")
        report[asset] = connectivity_report(vertices, faces, fitted)
    output = ROOT / "artifacts/clothing_audit/WRAP_GARMENT_CONNECTIVITY.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
