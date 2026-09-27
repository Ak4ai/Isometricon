"""Try mesh-coherent cage binding without changing the production fitter.

Each garment vertex considers the cage faces selected by itself and its
one-ring neighbours. Candidate outputs are scored jointly for source-cage
distance and excessive stretching of garment edges.
"""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def optimize_bindings(vertices, faces, trace, rounds=5):
    source = trace["source_vertices"]
    baseline = trace["target_vertices"]
    cage_faces = trace["projection_faces"]
    outer = trace["source_outer"]
    target_outer = trace["target_outer"]
    baseline_faces = trace["face_indices"]
    neighbours = [set() for _ in source]
    for a, b, c in faces:
        neighbours[a].update((b, c))
        neighbours[b].update((a, c))
        neighbours[c].update((a, b))
    neighbours = [np.fromiter(sorted(n), dtype=np.int32) for n in neighbours]
    candidates = []
    for i, point in enumerate(source):
        candidate_faces = {int(baseline_faces[i])}
        candidate_faces.update(int(baseline_faces[j]) for j in neighbours[i])
        options = []
        for face_id in candidate_faces:
            face = cage_faces[face_id]
            sa, sb, sc = outer[face]
            q, u, v, w = closest_point_on_triangle(point, sa, sb, sc)
            ta, tb, tc = target_outer[face]
            transform = _local_map(sa, sb, sc, ta, tb, tc)
            if transform is None:
                continue
            target = np.array([u, v, w]) @ np.array([ta, tb, tc]) + transform @ (point - q)
            distance = float(np.linalg.norm(point - q))
            options.append((face_id, target, distance))
        candidates.append(options)

    current = np.asarray(baseline, dtype=np.float64).copy()
    selected = np.asarray(baseline_faces, dtype=np.int32).copy()
    changes = []
    for _ in range(rounds):
        changed = 0
        for i, options in enumerate(candidates):
            n = neighbours[i]
            if not len(n) or len(options) < 2:
                continue
            rest = np.linalg.norm(source[i] - source[n], axis=1)
            valid = rest > 1e-4
            if not np.any(valid):
                continue
            n = n[valid]
            rest = rest[valid]
            best_energy = float("inf")
            best = None
            for face_id, target, distance in options:
                ratio = np.linalg.norm(target - current[n], axis=1) / rest
                # Only punish conspicuous spikes. Log scaling prevents the
                # smallest source edges from dominating every decision.
                distortion = np.maximum(np.log(np.maximum(ratio, 1e-8) / 1.8), 0)
                energy = ((distance - trace["distances"][i]) / .05) ** 2
                energy += 2.0 * float(np.mean(distortion ** 2))
                if energy < best_energy:
                    best_energy = energy
                    best = face_id, target
            if best is not None and best[0] != selected[i]:
                selected[i] = best[0]
                current[i] = best[1]
                changed += 1
        changes.append(changed)
        if not changed:
            break
    return current, selected, changes


def edge_metrics(source, fitted, faces, minimum_source_length=0):
    edges = set()
    for a, b, c in faces:
        edges.update(tuple(sorted(pair)) for pair in ((a, b), (b, c), (c, a)))
    edges = np.asarray(sorted(edges), dtype=np.int32)
    rest = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    moved = np.linalg.norm(fitted[edges[:, 0]] - fitted[edges[:, 1]], axis=1)
    valid = rest >= minimum_source_length
    rest = rest[valid]
    moved = moved[valid]
    ratios = moved / np.maximum(rest, 1e-7)
    return {"p99": float(np.quantile(ratios, .99)),
            "max": float(np.max(ratios)),
            "over_3x": int(np.count_nonzero(ratios > 3))}


def run(asset_id, engine):
    directory = ROOT / "assets/models/clothing"
    obj = next(directory.glob(f"*_{asset_id}.obj"))
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    vertices, faces, uvs, face_uvs = engine.load_obj(str(obj))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, vertices, str(rbxm), directory / "wrap_cages", binding_audit=trace)
    optimized, selected, changes = optimize_bindings(vertices, faces, trace)
    report = {
        "asset": asset_id,
        "baseline": edge_metrics(vertices, baseline, faces),
        "optimized": edge_metrics(vertices, optimized, faces),
        "changed_vertices": int(np.count_nonzero(selected != trace["face_indices"])),
        "changes_by_round": changes,
    }
    artifact = ROOT / "artifacts/clothing_audit"
    (artifact / f"experiment_binding_{asset_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (artifact / f"experiment_binding_{asset_id}.obj").open("w", encoding="utf-8") as out:
        # Convert engine XYZ to the same display OBJ coordinates as previews.
        for x, y, z in optimized:
            out.write(f"v {-x:.9f} {z:.9f} {-y:.9f}\n")
        for u, v in uvs:
            out.write(f"vt {u:.9f} {v:.9f}\n")
        for face, uv_face in zip(faces, face_uvs):
            out.write("f " + " ".join(f"{i+1}/{j+1}" for i, j in zip(face[::-1], uv_face[::-1])) + "\n")
    return report


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    for asset in sys.argv[1:] or ["16185652164", "72628400373948", "133331049150205", "16899958482"]:
        print(json.dumps(run(asset, engine), indent=2))
