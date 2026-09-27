"""Offline moving-least-squares cage deformation experiment."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, retarget_garment_with_wrap_layer
from scripts.experiment_wrap_binding import edge_metrics


def weighted_affine(source, target, points, neighbours=32):
    output = np.empty_like(points, dtype=np.float64)
    for start in range(0, len(points), 128):
        chunk = points[start:start + 128]
        distance2 = np.sum((chunk[:, None, :] - source[None, :, :]) ** 2, axis=2)
        nearest = np.argpartition(distance2, neighbours - 1, axis=1)[:, :neighbours]
        for local, ids in enumerate(nearest):
            p = chunk[local]
            src = source[ids]
            dst = target[ids]
            d2 = distance2[local, ids]
            weight = 1 / np.maximum(d2, .0025)
            center_source = np.average(src, axis=0, weights=weight)
            center_target = np.average(dst, axis=0, weights=weight)
            x = src - center_source
            y = dst - center_target
            matrix = (x * weight[:, None]).T @ x
            covariance = (x * weight[:, None]).T @ y
            regularizer = np.eye(3) * (np.trace(matrix) * .001 + 1e-10)
            affine = np.linalg.solve(matrix + regularizer, covariance)
            output[start + local] = center_target + (p - center_source) @ affine
    return output


def run(asset_id, engine):
    directory = ROOT / "assets/models/clothing"
    obj = next(directory.glob(f"*_{asset_id}.obj"))
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    vertices, faces, uvs, face_uvs = engine.load_obj(str(obj))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, vertices, str(rbxm), directory / "wrap_cages", binding_audit=trace)
    transformed = weighted_affine(trace["source_outer"], trace["target_outer"], trace["source_vertices"])
    alternative_outer = weighted_affine(trace["reference_parent"], trace["target_body"],
                                        trace["outer_parent"])
    alternative = np.empty_like(transformed)
    for i, point in enumerate(trace["source_vertices"]):
        face = trace["projection_faces"][trace["face_indices"][i]]
        source_triangle = trace["source_outer"][face]
        target_triangle = alternative_outer[face]
        q, u, v, w = closest_point_on_triangle(point, *source_triangle)
        transform = _local_map(*source_triangle, *target_triangle)
        alternative[i] = np.asarray([u, v, w]) @ target_triangle + transform @ (point - q)
    report = {"asset": asset_id,
              "baseline": edge_metrics(vertices, baseline, faces),
              "mls": edge_metrics(vertices, transformed, faces),
              "reference_field": edge_metrics(vertices, alternative, faces),
              "outer_cage": edge_metrics(trace["source_outer"], trace["target_outer"],
                                         trace["projection_faces"], minimum_source_length=.01),
              "alternative_outer_cage": edge_metrics(trace["source_outer"], alternative_outer,
                                                    trace["projection_faces"], minimum_source_length=.01),
              "reference_to_body": edge_metrics(trace["reference_parent"], trace["target_body"],
                                                trace["projection_faces"], minimum_source_length=.01),
              "reference_to_source_outer": edge_metrics(trace["reference_parent"], trace["outer_parent"],
                                                        trace["projection_faces"], minimum_source_length=.01)}
    artifact = ROOT / "artifacts/clothing_audit"
    (artifact / f"experiment_mls_{asset_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (artifact / f"experiment_mls_{asset_id}.obj").open("w", encoding="utf-8") as out:
        for x, y, z in transformed:
            out.write(f"v {-x:.9f} {z:.9f} {-y:.9f}\n")
        for u, v in uvs:
            out.write(f"vt {u:.9f} {v:.9f}\n")
        for face, uv_face in zip(faces, face_uvs):
            out.write("f " + " ".join(f"{i+1}/{j+1}" for i, j in zip(face[::-1], uv_face[::-1])) + "\n")
    with (artifact / f"experiment_reference_field_{asset_id}.obj").open("w", encoding="utf-8") as out:
        for x, y, z in alternative:
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
