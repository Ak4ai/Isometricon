"""Offline garment-topology blend at boundaries of canonical cage UV charts."""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS, face_charts
from scripts.benchmark_wrap_frames import edges_report
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer


def blend_boundary_bindings(faces, trace):
    """Blend source-near transforms offered by connected garment neighbours."""
    source = trace["source_vertices"]
    baseline = trace["target_vertices"]
    selected = trace["face_indices"]
    cage_faces = trace["projection_faces"]
    source_cage = trace["source_outer"]
    target_cage = trace["target_outer"]
    charts = face_charts(cage_faces, trace["uv_index"])
    selected_charts = charts[selected]
    neighbours = [set() for _ in source]
    for a, b, c in faces:
        neighbours[a].update((b, c))
        neighbours[b].update((a, c))
        neighbours[c].update((a, b))
    out = np.asarray(baseline, dtype=np.float64).copy()
    changed = 0
    for i, adjacent in enumerate(neighbours):
        if not adjacent or all(selected_charts[j] == selected_charts[i] for j in adjacent):
            continue
        candidate_faces = {int(selected[i])}
        candidate_faces.update(int(selected[j]) for j in adjacent)
        if len(candidate_faces) == 1:
            continue
        point = source[i]
        positions = []
        distances = []
        for face_id in candidate_faces:
            face = cage_faces[face_id]
            sa, sb, sc = source_cage[face]
            q, u, v, w = closest_point_on_triangle(point, sa, sb, sc)
            target_triangle = target_cage[face]
            transform = _local_map(sa, sb, sc, *target_triangle,
                                   normal_sign=trace["cage_normal_sign"])
            if transform is None:
                continue
            positions.append(np.array([u, v, w]) @ target_triangle + transform @ (point - q))
            distances.append(float(np.linalg.norm(point - q)))
        if len(positions) < 2:
            continue
        distances = np.asarray(distances)
        # The garment's source-to-cage spacing supplies the local influence
        # length. No asset name or clothing category enters the calculation.
        local_gap = max(float(np.median(distances)), 1e-4)
        scores = -(distances**2 - distances.min()**2) / (2 * local_gap**2)
        weights = np.exp(scores - scores.max())
        out[i] = np.average(positions, axis=0, weights=weights)
        changed += 1
    return out, changed


def load_body_for_preview(path):
    """Triangulate Blender OBJ and express it in engine XYZ."""
    vertices = []
    faces = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            vertices.append([float(value) for value in line.split()[1:4]])
        elif line.startswith("f "):
            polygon = [int(item.split("/")[0]) - 1 for item in line.split()[1:]]
            faces.extend((polygon[0], polygon[i], polygon[i + 1])
                         for i in range(1, len(polygon) - 1))
    raw = np.asarray(vertices, dtype=np.float64)
    return raw[:, [0, 2, 1]] * [1, -1, 1], np.asarray(faces, dtype=np.int32)


def face_change_report(faces, baseline, blended):
    """Detect folds introduced by blending relative to the current result."""
    tri = np.asarray(faces, dtype=np.int32)
    before = np.cross(baseline[tri[:, 1]] - baseline[tri[:, 0]],
                      baseline[tri[:, 2]] - baseline[tri[:, 0]])
    after = np.cross(blended[tri[:, 1]] - blended[tri[:, 0]],
                     blended[tri[:, 2]] - blended[tri[:, 0]])
    before_area = np.linalg.norm(before, axis=1)
    after_area = np.linalg.norm(after, axis=1)
    valid = before_area > 1e-10
    ratios = after_area[valid] / before_area[valid]
    cosine = np.sum(before[valid] * after[valid], axis=1) / (
        before_area[valid] * after_area[valid] + 1e-20)
    return {
        "faces": int(len(tri)),
        "area_under_quarter": int(np.count_nonzero(ratios < 0.25)),
        "area_over_fourfold": int(np.count_nonzero(ratios > 4)),
        "normal_reversed": int(np.count_nonzero(cosine < 0)),
        "area_ratio_p01": float(np.percentile(ratios, 1)),
    }


def constrain_blend_faces(faces, baseline, proposal, minimum_area_ratio=0.5):
    """Accept a vertex move only while its incident faces retain orientation/area."""
    tri = np.asarray(faces, dtype=np.int32)
    incident = [[] for _ in baseline]
    for face_id, face in enumerate(tri):
        for vertex in face:
            incident[vertex].append(face_id)
    original_normal = np.cross(baseline[tri[:, 1]] - baseline[tri[:, 0]],
                               baseline[tri[:, 2]] - baseline[tri[:, 0]])
    original_area = np.linalg.norm(original_normal, axis=1)
    result = np.asarray(baseline, dtype=np.float64).copy()
    accepted = 0
    for vertex in range(len(result)):
        if not incident[vertex] or np.allclose(result[vertex], proposal[vertex]):
            continue
        ids = incident[vertex]
        face = tri[ids]
        previous = result[vertex].copy()
        for alpha in (1.0, 0.5, 0.25, 0.125, 0.0625):
            result[vertex] = previous + alpha * (proposal[vertex] - previous)
            current = np.cross(result[face[:, 1]] - result[face[:, 0]],
                               result[face[:, 2]] - result[face[:, 0]])
            area = np.linalg.norm(current, axis=1)
            signed = np.sum(current * original_normal[ids], axis=1)
            if np.all(area >= minimum_area_ratio * original_area[ids]) and np.all(signed > 0):
                accepted += 1
                break
        else:
            result[vertex] = previous
    return result, accepted


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
        baseline, info = retarget_garment_with_wrap_layer(
            engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        blended, changed = blend_boundary_bindings(faces, trace)
        constrained, accepted = constrain_blend_faces(faces, baseline, blended)
        report[asset] = {"baseline": edges_report(vertices, baseline, faces),
                         "blended": edges_report(vertices, blended, faces),
                         "constrained": edges_report(vertices, constrained, faces),
                         "changed_vertices": changed,
                         "accepted_vertices": accepted,
                         "face_changes": face_change_report(faces, baseline, blended),
                         "constrained_face_changes": face_change_report(faces, baseline, constrained),
                         "outer_p99": info["outer_edge_stretch_p99"]}
        if preview:
            shared = np.vstack((baseline, blended, constrained))
            for label, output in (("baseline", baseline), ("chart_blend", blended),
                                  ("constrained", constrained)):
                image = ROOT / f"artifacts/clothing_audit/chart_blend_{asset}_{label}.png"
                coverage = depth_preview(body, body_faces, output, faces, image,
                                         shared_garment_vertices=shared)
                report[asset][label + "_visibility"] = coverage
                report[asset][label + "_image"] = str(image.relative_to(ROOT))
    output = ROOT / "artifacts/clothing_audit/WRAP_CHART_BLEND.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
