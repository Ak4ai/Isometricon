"""Offline test: bind visible mesh using authored outer-cage faces."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import (
    _closest_triangle, _local_map, _nearest_uv_indices, read_wrap_layer,
    retarget_garment_with_wrap_layer,
)
from scripts.experiment_wrap_binding import edge_metrics


def run(asset_id, engine):
    directory = ROOT / "assets/models/clothing"
    cache = directory / "wrap_cages"
    obj = next(directory.glob(f"*_{asset_id}.obj"))
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    garment, garment_faces, uvs, face_uvs = engine.load_obj(str(obj))
    trace = {}
    baseline, base_info = retarget_garment_with_wrap_layer(
        engine, garment, str(rbxm), cache, binding_audit=trace)
    wrap = read_wrap_layer(rbxm)
    outer, outer_faces, outer_uv, _ = engine.load_obj(str(cache / (wrap["cage_id"] + ".obj")))
    outer = np.asarray(outer, dtype=np.float64)
    outer_faces = np.asarray(outer_faces, dtype=np.int32)
    outer_to_ref = _nearest_uv_indices(np.asarray(outer_uv), trace["reference_uv"])
    target_outer = trace["target_outer"][outer_to_ref]
    source_area = np.linalg.norm(np.cross(
        outer[outer_faces[:, 1]] - outer[outer_faces[:, 0]],
        outer[outer_faces[:, 2]] - outer[outer_faces[:, 0]]), axis=1)
    target_area = np.linalg.norm(np.cross(
        target_outer[outer_faces[:, 1]] - target_outer[outer_faces[:, 0]],
        target_outer[outer_faces[:, 2]] - target_outer[outer_faces[:, 0]]), axis=1)
    usable_faces = outer_faces[(source_area > 1e-8) & (target_area > 1e-10)]
    lo = np.min(outer[usable_faces], axis=1)
    hi = np.max(outer[usable_faces], axis=1)
    fitted = np.empty_like(trace["source_vertices"])
    distance = np.empty(len(fitted))
    for i, point in enumerate(trace["source_vertices"]):
        distance[i], found = _closest_triangle(point, outer, usable_faces, lo, hi, closest_point_on_triangle)
        face_index, q, weights = found
        face = usable_faces[face_index]
        source_tri = outer[face]
        target_tri = target_outer[face]
        transform = _local_map(*source_tri, *target_tri)
        fitted[i] = np.asarray(weights) @ target_tri + transform @ (point - q)
    report = {"asset": asset_id, "baseline": edge_metrics(garment, baseline, garment_faces),
              "outer_topology": edge_metrics(garment, fitted, garment_faces),
              "source_distance_median": float(np.median(distance)),
              "source_distance_p99": float(np.quantile(distance, .99)),
              "outer_faces": len(outer_faces), "base_info": base_info}
    artifact = ROOT / "artifacts/clothing_audit"
    (artifact / f"experiment_outer_topology_{asset_id}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    with (artifact / f"experiment_outer_topology_{asset_id}.obj").open("w", encoding="utf-8") as out:
        for x, y, z in fitted:
            out.write(f"v {-x:.9f} {z:.9f} {-y:.9f}\n")
        for u, v in uvs:
            out.write(f"vt {u:.9f} {v:.9f}\n")
        for face, uv_face in zip(garment_faces, face_uvs):
            out.write("f " + " ".join(f"{i+1}/{j+1}" for i, j in zip(face[::-1], uv_face[::-1])) + "\n")
    return report


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    for asset in sys.argv[1:] or ["114590471167431", "109837605892174", "133331049150205", "16899958482"]:
        report = run(asset, engine)
        print(json.dumps({key: val for key, val in report.items() if key != "base_info"}, indent=2))
