"""Check whether cached clothing cages can form a closed deformation domain."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import (
    _nearest_uv_indices, read_wrap_layer, retarget_garment_with_wrap_layer,
)
from src.clothing.volumetric_cage import close_cage_pair


def audit(engine, asset_id):
    directory = ROOT / "assets/models/clothing"
    cache = directory / "wrap_cages"
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    garment_obj = next(directory.glob(f"*_{asset_id}.obj"))
    garment, _, _, _ = engine.load_obj(str(garment_obj))
    trace = {}
    _, fit = retarget_garment_with_wrap_layer(
        engine, garment, str(rbxm), cache, binding_audit=trace)
    wrap = read_wrap_layer(rbxm)
    outer, outer_faces, outer_uv, _ = engine.load_obj(str(cache / (wrap["cage_id"] + ".obj")))
    outer = np.asarray(outer, dtype=np.float64)
    outer_faces = np.asarray(outer_faces, dtype=np.int32)
    outer_to_ref = _nearest_uv_indices(np.asarray(outer_uv), trace["reference_uv"])
    target_outer = trace["target_outer"][outer_to_ref]
    target_body = trace["target_body"][outer_to_ref]
    _, seam_ids = np.unique(np.round(outer, 5), axis=0, return_inverse=True)
    seam_counts = np.bincount(seam_ids)
    uv_parts = {}
    for part_name, part in engine.body_cages.items():
        if part_name.endswith("Forearm"):
            continue
        for uv in part["face_uvs"].reshape(-1, 2):
            uv_parts[tuple(np.round(uv, 5))] = part_name

    def seam_stats(positions, details=False):
        centers = np.stack([np.bincount(seam_ids, weights=positions[:, axis]) / seam_counts
                            for axis in range(3)], axis=1)
        spread = np.zeros(len(centers))
        np.maximum.at(spread, seam_ids, np.linalg.norm(positions - centers[seam_ids], axis=1))
        result = {"max_m": float(spread.max(initial=0)),
                  "groups_over_2cm": int(np.count_nonzero(spread > .02))}
        if details:
            result["largest"] = []
            for group in np.argsort(spread)[-8:][::-1]:
                members = np.flatnonzero(seam_ids == group)
                unique_uvs = np.unique(np.round(np.asarray(outer_uv)[members], 5), axis=0)
                body_uvs = np.unique(np.round(trace["target_uv"][trace["uv_index"][outer_to_ref[members]]], 5), axis=0)
                result["largest"].append({
                    "source_center": np.mean(outer[members], axis=0).round(4).tolist(),
                    "spread_m": round(float(spread[group]), 5),
                    "body_spread_m": round(float(np.linalg.norm(
                        target_body[members] - target_body[members].mean(axis=0), axis=1).max()), 5),
                    "parts": sorted({uv_parts.get(tuple(uv), "unknown") for uv in body_uvs}),
                    "uvs": unique_uvs.round(5).tolist(),
                    "body_uvs": body_uvs.round(5).tolist(),
                })
        return result
    def seam_spread(positions):
        centers = np.stack([np.bincount(seam_ids, weights=positions[:, axis]) / seam_counts
                            for axis in range(3)], axis=1)
        spread = np.zeros(len(centers))
        np.maximum.at(spread, seam_ids, np.linalg.norm(positions - centers[seam_ids], axis=1))
        return spread
    body_spread = seam_spread(target_body)
    outer_spread = seam_spread(target_outer)
    seam_classes = {
        "body_continuous_shell_broken_over_2cm": int(np.count_nonzero(
            (body_spread <= .005) & (outer_spread > .02))),
        "body_broken_over_2cm": int(np.count_nonzero(body_spread > .02)),
        "shell_additional_gap_over_2cm": int(np.count_nonzero(
            outer_spread - body_spread > .02)),
    }
    # Diagnostic only: identical source points whose body locations already
    # coincide ought to share one shell location. Do not move anatomical gaps.
    shell_harmonized = target_outer.copy()
    body_continuous = body_spread <= .005
    shell_centers = np.stack([
        np.bincount(seam_ids, weights=target_outer[:, axis]) / seam_counts
        for axis in range(3)], axis=1)
    harmonize_mask = body_continuous[seam_ids] & (seam_counts[seam_ids] > 1)
    shell_harmonized[harmonize_mask] = shell_centers[seam_ids[harmonize_mask]]
    result = close_cage_pair(outer, target_outer, outer_faces,
                             source_uv=np.asarray(outer_uv),
                             target_stitch_tolerance=float("inf"))
    try:
        close_cage_pair(outer, target_outer, outer_faces, source_uv=np.asarray(outer_uv))
        strict_status = "closed"
    except ValueError as exc:
        strict_status = str(exc)
    return {"asset": asset_id, "raw_outer_vertices": len(outer),
            "raw_outer_faces": len(outer_faces),
            "welded_vertices": len(result["source_vertices"]),
            "closed_faces": len(result["faces"]),
            "loop_lengths": result["loop_lengths"],
            "cap_face_count": result["cap_face_count"],
            "cap_plane_error_max": result["cap_plane_error_max"],
            "target_seam_spread_max": result["target_seam_spread_max"],
            "target_seam_groups_over_2cm": result["target_seam_groups_over_2cm"],
            "body_seam_stats": seam_stats(target_body),
            "outer_seam_stats": seam_stats(target_outer, details=True),
            "seam_classes": seam_classes,
            "harmonized_shell_seam_stats": seam_stats(shell_harmonized),
            "largest_target_seams": result["largest_target_seams"],
            "strict_target_continuity": strict_status,
            "source_signed_volume": result["source_signed_volume"],
            "target_signed_volume": result["target_signed_volume"],
            "fit": fit}


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    items = sys.argv[1:] or ["114590471167431", "109837605892174",
                             "133331049150205", "72628400373948", "16899958482"]
    reports = []
    for asset in items:
        try:
            report = audit(engine, asset)
        except Exception as exc:
            report = {"asset": asset, "error": str(exc)}
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    out = ROOT / "artifacts/clothing_audit/VOLUMETRIC_CAGE_READINESS.json"
    out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
