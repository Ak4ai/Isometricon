"""Audit which body cage regions a Roblox garment binds to in the static pose."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _nearest_uv_indices, retarget_garment_with_wrap_layer


def audit_asset(engine, asset_id):
    cache = ROOT / "assets/models/clothing"
    source = next(cache.glob(f"*_{asset_id}.obj"))
    rbxm = next(cache.glob(f"*_{asset_id}.rbxm"))
    vertices, faces, _, _ = engine.load_obj(str(source))
    trace = {}
    fitted, diagnostic = retarget_garment_with_wrap_layer(
        engine, vertices, str(rbxm), cache / "wrap_cages", binding_audit=trace)

    # UV identities, rather than spatial proximity, tell us which R15 part
    # each outer-cage face represents. At part seams multiple names may occur.
    uv_parts = defaultdict(set)
    for name, part in engine.body_cages.items():
        if name.endswith("Forearm"):
            continue
        part_uv = np.asarray([uv for uv_face in part["face_uvs"] for uv in uv_face])
        for uv_id in _nearest_uv_indices(part_uv, trace["target_uv"]):
            uv_parts[int(uv_id)].add(name)
    face_parts = []
    for face in trace["projection_faces"]:
        candidate = Counter()
        for index in face:
            uv_id = int(trace["uv_index"][index])
            for name in uv_parts[uv_id]:
                candidate[name] += 1
        face_parts.append(candidate.most_common(1)[0][0] if candidate else "Unknown")
    face_parts = np.asarray(face_parts)
    chosen = face_parts[trace["face_indices"]]

    edges = set()
    for a, b, c in faces:
        edges.update((tuple(sorted(pair)) for pair in ((a, b), (b, c), (c, a))))
    edge_array = np.asarray(sorted(edges), dtype=np.int32)
    source_lengths = np.linalg.norm(vertices[edge_array[:, 0]] - vertices[edge_array[:, 1]], axis=1)
    fit_lengths = np.linalg.norm(fitted[edge_array[:, 0]] - fitted[edge_array[:, 1]], axis=1)
    ratios = fit_lengths / np.maximum(source_lengths, 1e-7)
    cross = chosen[edge_array[:, 0]] != chosen[edge_array[:, 1]]
    worst = np.argsort(ratios)[-15:][::-1]
    counts = Counter(chosen)
    report = {
        "asset": asset_id,
        "vertices": len(vertices),
        "source_cage_distance": diagnostic,
        "bound_regions": dict(counts),
        "cross_region_edges": int(cross.sum()),
        "total_edges": len(edges),
        "edge_stretch_p99": float(np.quantile(ratios, .99)),
        "edge_stretch_max": float(ratios.max()),
        "edges_stretched_over_3x": int(np.count_nonzero(ratios > 3)),
        "cross_region_edges_stretched_over_3x": int(np.count_nonzero(cross & (ratios > 3))),
        "worst_edges": [
            {"vertices": [int(x) for x in edge_array[i]],
             "regions": [str(chosen[x]) for x in edge_array[i]],
             "ratio": round(float(ratios[i]), 3),
             "distance": [round(float(trace["distances"][x]), 4) for x in edge_array[i]]}
            for i in worst],
    }

    out_dir = ROOT / "artifacts/clothing_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"binding_{asset_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Vertex colors make wrong-part bindings reviewable in Blender or MeshLab.
    palette = {
        "UpperTorso": (1, .3, .3), "LowerTorso": (1, .7, .3),
        "LeftUpperArm": (.2, .8, 1), "LeftLowerArm": (.1, .5, 1),
        "RightUpperArm": (.2, 1, .8), "RightLowerArm": (.1, .7, .5),
        "LeftUpperLeg": (.9, .2, .9), "RightUpperLeg": (.6, .2, .9),
    }
    with (out_dir / f"binding_{asset_id}.obj").open("w", encoding="utf-8") as handle:
        for p, name in zip(vertices, chosen):
            color = palette.get(name, (.7, .7, .7))
            handle.write("v " + " ".join(f"{x:.6f}" for x in (*p, *color)) + "\n")
        for face in faces:
            handle.write("f " + " ".join(str(i + 1) for i in face) + "\n")
    return report


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    for asset in sys.argv[1:] or ["16185652164", "72628400373948", "133331049150205", "16899958482"]:
        report = audit_asset(engine, asset)
        print(json.dumps({k: v for k, v in report.items() if k != "worst_edges"}, indent=2))
