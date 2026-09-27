"""Offline test of piecewise R15 affine shell transfer; no runtime change."""
from collections import defaultdict
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle
from src.clothing.wrap_layer_fit import _local_map, _nearest_uv_indices, retarget_garment_with_wrap_layer
from scripts.experiment_wrap_binding import edge_metrics


def part_affine_shell(engine, trace):
    uv_index = trace["uv_index"]
    target_uv = trace["target_uv"]
    reference = trace["reference_parent"]
    target = trace["target_body"]
    outer = trace["outer_parent"]
    output = np.zeros_like(outer, dtype=np.float64)
    weights = np.zeros(len(outer), dtype=np.float64)
    diagnostics = {}
    for name, part in engine.r15_female_cages.items():
        if name.endswith("Forearm"):
            continue
        uv = np.asarray([u for face in part["face_uvs"] for u in face])
        ids = np.unique(_nearest_uv_indices(uv, target_uv))
        vertex_indices = np.where(np.isin(uv_index, ids))[0]
        # One representative per UV avoids weighting duplicated FileMesh vertices.
        representatives = np.unique(uv_index[vertex_indices], return_index=True)[1]
        fit_indices = vertex_indices[representatives]
        if len(fit_indices) < 4:
            continue
        design = np.column_stack((reference[fit_indices], np.ones(len(fit_indices))))
        transform, _, _, _ = np.linalg.lstsq(design, target[fit_indices], rcond=None)
        mapped_ref = design @ transform
        residual = np.linalg.norm(mapped_ref - target[fit_indices], axis=1)
        diagnostics[name] = {"n": len(fit_indices), "ref_error_p99": float(np.quantile(residual, .99))}
        # Keep each UV pinned to the exact target body cage. Only transport
        # the authored inner-to-outer offset through the part's linear map.
        mapped_outer = target[vertex_indices] + (outer[vertex_indices] - reference[vertex_indices]) @ transform[:3]
        output[vertex_indices] += mapped_outer
        weights[vertex_indices] += 1
    if np.any(weights == 0):
        raise ValueError(f"Unmapped outer-cage vertices: {int(np.count_nonzero(weights == 0))}")
    return output / weights[:, None], diagnostics


def deform_visible(trace, outer_target):
    result = np.empty_like(trace["source_vertices"])
    for i, point in enumerate(trace["source_vertices"]):
        face = trace["projection_faces"][trace["face_indices"][i]]
        source_tri = trace["source_outer"][face]
        target_tri = outer_target[face]
        q, u, v, w = closest_point_on_triangle(point, *source_tri)
        transform = _local_map(*source_tri, *target_tri)
        result[i] = np.array([u, v, w]) @ target_tri + transform @ (point - q)
    return result


def run(asset_id, engine):
    directory = ROOT / "assets/models/clothing"
    obj = next(directory.glob(f"*_{asset_id}.obj"))
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    vertices, faces, uvs, face_uvs = engine.load_obj(str(obj))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, vertices, str(rbxm), directory / "wrap_cages", binding_audit=trace)
    outer_target, part_diagnostics = part_affine_shell(engine, trace)
    fitted = deform_visible(trace, outer_target)
    report = {"asset": asset_id,
              "baseline_visible": edge_metrics(vertices, baseline, faces),
              "part_affine_visible": edge_metrics(vertices, fitted, faces),
              "baseline_outer": edge_metrics(trace["source_outer"], trace["target_outer"],
                                             trace["projection_faces"], minimum_source_length=.01),
              "part_affine_outer": edge_metrics(trace["source_outer"], outer_target,
                                                trace["projection_faces"], minimum_source_length=.01),
              "part_reference_fit": part_diagnostics}
    artifact = ROOT / "artifacts/clothing_audit"
    (artifact / f"experiment_part_affine_{asset_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (artifact / f"experiment_part_affine_{asset_id}.obj").open("w", encoding="utf-8") as out:
        for x, y, z in fitted:
            out.write(f"v {-x:.9f} {z:.9f} {-y:.9f}\n")
        for u, v in uvs:
            out.write(f"vt {u:.9f} {v:.9f}\n")
        for face, uv_face in zip(faces, face_uvs):
            out.write("f " + " ".join(f"{i+1}/{j+1}" for i, j in zip(face[::-1], uv_face[::-1])) + "\n")
    return report


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    for asset in sys.argv[1:] or ["16185652164", "72628400373948", "133331049150205", "16899958482"]:
        report = run(asset, engine)
        print(json.dumps({k: v for k, v in report.items() if k != "part_reference_fit"}, indent=2))
