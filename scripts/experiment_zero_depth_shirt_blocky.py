"""Causal diagnostic: directly move only penetrating t=0 shirt vertices.

This does not alter either cage or the production/runtime fit. It asks whether
the zero-depth subset itself accounts for measurable Blocky shirt penetration.
The direct projection is intentionally unsmoothed; quality metrics expose the
cost of treating those vertices as free garment variables.
"""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_canonical_radial import bind_source
from scripts.radial_validation_metrics import body_penetration, distortion
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.experimental_shell_clearance import ClosedBodyUnion

INPUT = ROOT / "artifacts/clothing_audit/radial_frames"
OUT = ROOT / "artifacts/clothing_audit/zero_depth_diagnostic"
CASE = "blocky_133331049150205"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(np.load(INPUT / f"{CASE}.npz"))
    frozen = dict(np.load(INPUT / f"{CASE}_outputs.npz"))
    reference = json.loads((INPUT / f"{CASE}.json").read_text(encoding="utf-8"))
    binding = bind_source(data, INPUT / f"{CASE}_binding.npz")
    base = frozen["radial_previous"].astype(float)
    faces = np.asarray(data["garment_faces"], int)
    body_faces = np.asarray(data["body_faces"], int)
    body_vertices = np.asarray(data["body"], float)
    common_scale = float(reference["common_metric_scale"])

    components = []
    for ids, closed in __import__("scripts.radial_validation_metrics", fromlist=["body_components"]).body_components(body_vertices, body_faces):
        if closed:
            components.append(ids)
    body = ClosedBodyUnion(body_vertices, body_faces, components)
    _, penetrating, depth = body_penetration(base, body_vertices, body_faces, return_samples=True)
    zero = np.asarray(binding["levels"]) <= 1e-8
    zero_penetrating = zero & penetrating

    # Diagnostic counterfactual: take only penetrating zero-depth garment
    # vertices to a nearby exposed body boundary. Other garment points are fixed.
    candidate = base.copy()
    margin = float(np.ptp(body_vertices[:, 2])) * 1e-4
    if zero_penetrating.any():
        candidate[zero_penetrating] = body.exterior_targets(base[zero_penetrating], margin)

    samples_before = np.vstack((base, base[faces].mean(axis=1)))
    samples_after = np.vstack((candidate, candidate[faces].mean(axis=1)))
    penetration_before = body_penetration(samples_before, body_vertices, body_faces)
    penetration_after = body_penetration(samples_after, body_vertices, body_faces)
    edge = distortion(data["garment"], candidate, faces, common_scale)
    base_edge = distortion(data["garment"], base, faces, common_scale)
    tri_before = np.cross(base[faces][:, 1] - base[faces][:, 0], base[faces][:, 2] - base[faces][:, 0])
    tri_after = np.cross(candidate[faces][:, 1] - candidate[faces][:, 0], candidate[faces][:, 2] - candidate[faces][:, 0])
    inversions = int(np.count_nonzero(np.einsum("ij,ij->i", tri_before, tri_after) <= 0))

    baseline_png = OUT / f"{CASE}_baseline.png"
    diagnostic_png = OUT / f"{CASE}_zero_depth_pushed.png"
    shared = np.vstack((body_vertices, base, candidate))
    vis_before = depth_preview(body_vertices, body_faces, base, faces, baseline_png,
                               shared_garment_vertices=shared)
    vis_after = depth_preview(body_vertices, body_faces, candidate, faces, diagnostic_png,
                              shared_garment_vertices=shared)

    report = {
        "case": CASE,
        "method": "Only penetrating garment vertices with prism depth <= 1e-8 are directly projected to the nearest exposed body boundary; cages and all other garment vertices remain fixed.",
        "zero_depth_vertices": int(zero.sum()),
        "penetrating_garment_vertices": int(penetrating.sum()),
        "penetrating_zero_depth_vertices": int(zero_penetrating.sum()),
        "zero_depth_share_of_penetrating_vertices": float(zero_penetrating.sum() / max(1, penetrating.sum())),
        "penetration_before_vertices_plus_face_centers": penetration_before,
        "penetration_after_vertices_plus_face_centers": penetration_after,
        "edge_distortion_before": base_edge,
        "edge_distortion_after": edge,
        "face_orientation_inversions_vs_baseline": inversions,
        "visibility_before": vis_before,
        "visibility_after": vis_after,
        "images": [str(baseline_png.relative_to(ROOT)), str(diagnostic_png.relative_to(ROOT))],
        "limitations": [
            "This is a causal diagnostic, not a proposed deformation algorithm: zero-depth points are projected independently without continuity regularization.",
            "Only vertices are projected; face-center penetration is measured independently and may remain.",
            "The frozen radial+prism baseline and fixture are unchanged.",
        ],
    }
    (OUT / f"{CASE}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(OUT / f"{CASE}.npz", baseline=base, zero_depth_diagnostic=candidate,
                        zero_depth=zero, penetrating_baseline=penetrating)
    print(json.dumps({
        "zero_depth_vertices": int(zero.sum()),
        "penetrating_zero_depth_vertices": int(zero_penetrating.sum()),
        "all_penetrating_vertices": int(penetrating.sum()),
        "penetration_before": penetration_before["penetrating_fraction"],
        "penetration_after": penetration_after["penetrating_fraction"],
        "edges_over_3_before": base_edge["historical_length_mask"]["over_3"],
        "edges_over_3_after": edge["historical_length_mask"]["over_3"],
        "face_orientation_inversions": inversions,
        "report": str((OUT / f"{CASE}.json").relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
