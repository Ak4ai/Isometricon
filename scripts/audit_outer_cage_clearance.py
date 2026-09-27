"""Compare authored and transferred outer-cage offsets from their body cage.

Signed offsets are evaluated in each cage's own outward-normal frame; this
avoids comparing source and target XYZ directions directly. Diagnostic only.
"""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS
from scripts.experiment_chart_blend import load_body_for_preview
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def outward_vertex_normals(vertices, faces):
    triangles = vertices[faces]
    face_normal = np.cross(triangles[:, 1] - triangles[:, 0],
                           triangles[:, 2] - triangles[:, 0])
    volume = np.einsum("ij,ij->i", triangles[:, 0], face_normal).sum() / 6
    face_normal *= 1 if volume > 0 else -1
    normals = np.zeros_like(vertices, dtype=np.float64)
    np.add.at(normals, faces.reshape(-1), np.repeat(face_normal, 3, axis=0))
    length = np.linalg.norm(normals, axis=1)
    valid = length > 1e-12
    normals[valid] /= length[valid, None]
    return normals, valid


def offset_report(trace, preview_body=None, asset=None):
    faces = trace["projection_faces"]
    source_body = trace["reference_parent"]
    source_outer = trace["outer_parent"]
    target_body = trace["target_body"]
    target_outer = trace["reference_order_target_outer"]
    source_normal, source_valid = outward_vertex_normals(source_body, faces)
    target_normal, target_valid = outward_vertex_normals(target_body, faces)
    valid = source_valid & target_valid
    source_offset = np.einsum("ij,ij->i", source_outer - source_body, source_normal)
    target_offset = np.einsum("ij,ij->i", target_outer - target_body, target_normal)
    # Count only sign differences where both offsets are distinguishable from
    # numerical noise; touching/near-zero offsets are reported separately.
    substantial = valid & (np.abs(source_offset) > 1e-3) & (np.abs(target_offset) > 1e-3)
    changed = substantial & (source_offset * target_offset < 0)
    source_positive = substantial & (source_offset > 0)
    source_negative = substantial & (source_offset < 0)
    source_extent = np.ptp(source_body, axis=0)
    target_extent = np.ptp(target_body, axis=0)
    report = {
        "valid_vertices": int(valid.sum()),
        "substantial_vertices": int(substantial.sum()),
        "source_positive_target_negative": int(np.count_nonzero(changed & source_positive)),
        "source_negative_target_positive": int(np.count_nonzero(changed & source_negative)),
        "source_offset_quantiles": np.quantile(source_offset[valid], [.01, .5, .99]).tolist(),
        "target_offset_quantiles": np.quantile(target_offset[valid], [.01, .5, .99]).tolist(),
        "body_extent_ratio_lateral_vertical_depth": [
            float(target_extent[0] / source_extent[0]),
            float(target_extent[2] / source_extent[1]),
            float(target_extent[1] / source_extent[2])],
        "source_to_target_sign_preservation": float(np.mean(
            np.sign(source_offset[substantial]) == np.sign(target_offset[substantial])))
        if np.any(substantial) else None,
    }
    if preview_body is not None:
        threshold = float(np.quantile(np.abs(source_offset[valid]), .99) * .1)
        expanded = np.any(np.abs(source_offset[faces]) > threshold, axis=1)
        selected_faces = faces[expanded]
        body_vertices, body_faces = preview_body
        image_path = ROOT / f"artifacts/clothing_audit/outer_cage_{asset}.png"
        report["expanded_cage_faces"] = int(len(selected_faces))
        report["expanded_cage_preview"] = str(image_path.relative_to(ROOT))
        report["expanded_cage_visibility"] = depth_preview(
            body_vertices, body_faces, target_outer, selected_faces, image_path)
        # The source reference and outer cage are in Roblox XYZ (Y vertical,
        # Z depth). Convert both to the engine's XYZ only for visualization.
        source_display_body = source_body[:, [0, 2, 1]] * [1, -1, 1]
        source_display_outer = source_outer[:, [0, 2, 1]] * [1, -1, 1]
        source_path = ROOT / f"artifacts/clothing_audit/source_outer_cage_{asset}.png"
        report["source_expanded_cage_preview"] = str(source_path.relative_to(ROOT))
        depth_preview(source_display_body, faces, source_display_outer,
                      selected_faces, source_path)
    return report


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    preview_body = None
    if "--preview" in sys.argv:
        preview_body = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report = {}
    for asset in ASSETS:
        vertices, _, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        retarget_garment_with_wrap_layer(
            engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        report[asset] = offset_report(trace, preview_body, asset)
    path = ROOT / "artifacts/clothing_audit/WRAP_OUTER_CAGE_CLEARANCE.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
