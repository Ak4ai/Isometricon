"""Measure welded mesh connectivity and manifold boundaries of clothes/cages."""
from collections import Counter
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer


def audit(vertices, faces, precision=5):
    _, inverse = np.unique(np.round(vertices, precision), axis=0, return_inverse=True)
    welded = inverse[np.asarray(faces, dtype=np.int32)]
    parent = np.arange(int(inverse.max()) + 1)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, c in welded:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[rc] = ra
    roots = np.asarray([find(i) for i in range(len(parent))])
    component_sizes = Counter(roots)
    edges = Counter()
    for a, b, c in welded:
        for i, j in ((a, b), (b, c), (c, a)):
            if i != j:
                edges[tuple(sorted((int(i), int(j))))] += 1
    boundary = [edge for edge, count in edges.items() if count == 1]
    boundary_adj = {}
    for a, b in boundary:
        boundary_adj.setdefault(a, set()).add(b)
        boundary_adj.setdefault(b, set()).add(a)
    pending = set(boundary_adj)
    boundary_groups = []
    while pending:
        seed = pending.pop()
        group = {seed}
        stack = [seed]
        while stack:
            for neighbor in boundary_adj[stack.pop()]:
                if neighbor not in group:
                    group.add(neighbor)
                    pending.discard(neighbor)
                    stack.append(neighbor)
        boundary_groups.append(len(group))
    return {"raw_vertices": len(vertices), "welded_vertices": len(parent),
            "faces": len(faces), "components": len(component_sizes),
            "largest_components": sorted(component_sizes.values(), reverse=True)[:10],
            "boundary_edges": sum(v == 1 for v in edges.values()),
            "boundary_loops_or_chains": sorted(boundary_groups, reverse=True),
            "boundary_vertices_not_degree_2": sum(len(adj) != 2 for adj in boundary_adj.values()),
            "nonmanifold_edges": sum(v > 2 for v in edges.values())}


engine = RobloxWearEngine(body_type="female")
directory = ROOT / "assets/models/clothing"
cache = directory / "wrap_cages"
for asset_id in sys.argv[1:] or ["114590471167431", "109837605892174", "133331049150205"]:
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    obj = next(directory.glob(f"*_{asset_id}.obj"))
    wrap = read_wrap_layer(rbxm)
    for name, path in (("visible", obj),
                       ("inner", cache / (wrap["reference_id"] + ".obj")),
                       ("outer", cache / (wrap["cage_id"] + ".obj"))):
        vertices, faces, _, _ = engine.load_obj(str(path))
        print(asset_id, name, audit(vertices, faces))
