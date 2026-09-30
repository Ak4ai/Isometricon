"""Locate garment edge breaks across connected cage UV charts."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

ASSETS = ("133331049150205", "72628400373948", "109837605892174",
          "114590471167431", "16185652164")


def face_charts(faces, uv_ids):
    """Connect faces sharing a complete canonical cage-UV edge."""
    parent = np.arange(len(faces))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edge_owner = {}
    for face_index, face in enumerate(faces):
        a, b, c = [int(uv_ids[vertex]) for vertex in face]
        for first, second in ((a, b), (b, c), (c, a)):
            edge = tuple(sorted((first, second)))
            if edge in edge_owner:
                parent[root(face_index)] = root(edge_owner[edge])
            else:
                edge_owner[edge] = face_index
    _, components = np.unique([root(i) for i in range(len(faces))], return_inverse=True)
    return components


def audit_asset(engine, asset):
    directory = ROOT / "assets/models/clothing"
    vertices, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
    trace = {}
    fitted, info = retarget_garment_with_wrap_layer(
        engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
        directory / "wrap_cages", trace)
    charts = face_charts(trace["projection_faces"], trace["uv_index"])
    vertex_chart = charts[trace["face_indices"]]
    uv_regions = {}
    for name, part in engine.body_cages.items():
        if name.endswith("Forearm"):
            continue
        for uv in part["face_uvs"].reshape(-1, 2):
            uv_regions[tuple(np.round(uv, 5))] = name
    chart_regions = defaultdict(Counter)
    for face, chart_id in zip(trace["projection_faces"], charts):
        for vertex in face:
            uv = trace["target_uv"][trace["uv_index"][vertex]]
            chart_regions[int(chart_id)][uv_regions.get(tuple(np.round(uv, 5)), "Unknown")] += 1
    chart_labels = {chart: counts.most_common(1)[0][0] for chart, counts in chart_regions.items()}
    mesh_edges = np.unique(np.sort(np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1), axis=0)
    original = np.linalg.norm(vertices[mesh_edges[:, 0]] - vertices[mesh_edges[:, 1]], axis=1)
    deformed = np.linalg.norm(fitted[mesh_edges[:, 0]] - fitted[mesh_edges[:, 1]], axis=1)
    valid = original >= .01
    stretched = valid & (deformed > original * 3)
    cross_chart = vertex_chart[mesh_edges[:, 0]] != vertex_chart[mesh_edges[:, 1]]
    chart_counts = np.bincount(vertex_chart, minlength=int(charts.max()) + 1)
    crossing_regions = Counter(tuple(sorted((chart_labels[int(vertex_chart[a])],
                                             chart_labels[int(vertex_chart[b])])))
                               for a, b in mesh_edges[stretched & cross_chart])
    return {"asset": asset,
            "cage_charts": int(len(np.unique(charts))),
            "charts_used_by_garment": int(np.count_nonzero(chart_counts)),
            "mesh_edges_over_3x": int(stretched.sum()),
            "over_3x_cross_chart": int(np.count_nonzero(stretched & cross_chart)),
            "over_3x_within_chart": int(np.count_nonzero(stretched & ~cross_chart)),
            "cross_chart_edges": int(np.count_nonzero(valid & cross_chart)),
            "worst_crossing_regions": [
                {"regions": list(pair), "edges_over_3x": count}
                for pair, count in crossing_regions.most_common(5)],
            "source_outer_p99": info["outer_edge_stretch_p99"]}


def main():
    engine = RobloxWearEngine(body_type="female")
    report = [audit_asset(engine, asset) for asset in ASSETS]
    output = ROOT / "artifacts/clothing_audit/WRAP_BINDING_CHARTS.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
