"""Compare source-only and source+target radial influence sets on Blocky.

Consumes the frozen official Blocky shirt fixture from ``radial_frames``.
Writes only under ``artifacts/clothing_audit/bidirectional_radial`` and never
changes the production runtime.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_canonical_radial_results import binding_jacobians
from scripts.experiment_canonical_radial import bind_source, evaluate_binding
from scripts.radial_validation_metrics import (
    body_penetration, distortion, prism_jacobians, seam_report,
)
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.experimental_bidirectional_radial import transfer_outer_cage_bidirectional_radial


INPUT = ROOT / "artifacts/clothing_audit/radial_frames"
OUT = ROOT / "artifacts/clothing_audit/bidirectional_radial"
CASE = "blocky_133331049150205"


def comparison_sheet(before_path: Path, after_path: Path, output_path: Path):
    images = [Image.open(p).convert("RGB") for p in (before_path, after_path)]
    sheet = Image.new("RGB", (images[0].width, images[0].height * 2 + 48), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 5), "Radial atual: centros na cage fonte", fill="black")
    sheet.paste(images[0], (0, 24))
    y = images[0].height + 24
    draw.text((8, y + 5), "Experimento: centros na cage fonte e destino", fill="black")
    sheet.paste(images[1], (0, y + 24))
    sheet.save(output_path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(np.load(INPUT / f"{CASE}.npz"))
    saved = dict(np.load(INPUT / f"{CASE}_outputs.npz"))
    previous_report = json.loads((INPUT / f"{CASE}.json").read_text(encoding="utf-8"))

    binding_path = INPUT / f"{CASE}_binding.npz"
    binding = bind_source(data, binding_path)
    used_faces = binding["faces"][np.unique(binding["face_ids"])]
    baseline_shell = saved["radial_previous_shell"].astype(float)
    baseline_mesh = saved["radial_previous"].astype(float)

    shell, influence_audit = transfer_outer_cage_bidirectional_radial(
        data["reference_parent"], data["outer_parent"], data["target_body"],
        data["projection_faces"], parity=int(data["cage_normal_sign"]),
        radius_factor=1.0, bulk_scale=float(previous_report["legacy"]["bulk_scale"]),
        return_audit=True,
    )
    mesh = evaluate_binding(data, binding, shell)

    shared = np.vstack((data["body"], baseline_mesh, mesh))
    image_before = OUT / f"{CASE}_source_only.png"
    image_after = OUT / f"{CASE}_source_and_target.png"
    before_visibility = depth_preview(data["body"], data["body_faces"], baseline_mesh,
                                      data["garment_faces"], image_before,
                                      shared_garment_vertices=shared)
    after_visibility = depth_preview(data["body"], data["body_faces"], mesh,
                                     data["garment_faces"], image_after,
                                     shared_garment_vertices=shared)
    comparison = OUT / f"{CASE}_comparison.png"
    comparison_sheet(image_before, image_after, comparison)

    variants = {}
    for label, candidate_mesh, candidate_shell, visibility in (
        ("source_only", baseline_mesh, baseline_shell, before_visibility),
        ("source_and_target", mesh, shell, after_visibility),
    ):
        samples = np.vstack((candidate_mesh,
                             candidate_mesh[data["garment_faces"]].mean(axis=1)))
        valid, inverted = binding_jacobians(data, binding, candidate_shell)
        variants[label] = {
            "distortion": distortion(data["garment"], candidate_mesh,
                                     data["garment_faces"],
                                     previous_report["common_metric_scale"]),
            "penetration": body_penetration(samples, data["body"], data["body_faces"]),
            "shell_center_penetration": body_penetration(
                candidate_shell[used_faces].mean(axis=1), data["body"], data["body_faces"]),
            "seams": seam_report(data["outer_parent"], candidate_shell, data["uv_index"]),
            "used_prism_jacobians": prism_jacobians(
                data["reference_parent"], data["outer_parent"], data["target_body"],
                candidate_shell, used_faces, int(data["cage_normal_sign"])),
            "binding_jacobians": {"valid_vertices": int(valid.sum()),
                                  "inverted_vertices": int(inverted.sum())},
            "visibility": visibility,
            "image": str((image_before if label == "source_only" else image_after).relative_to(ROOT)),
        }

    report = {
        "case": CASE,
        "source_fixture": str((INPUT / f"{CASE}.npz").relative_to(ROOT)),
        "method": "same source-only radial transfer plus proximity centers on destination cage",
        "patent_scope": "approximation of US20250265799A1 claims 1-6/16-20; private Roblox implementation unknown",
        "influences": influence_audit,
        "variants": variants,
        "comparison_image": str(comparison.relative_to(ROOT)),
    }
    (OUT / f"{CASE}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(OUT / f"{CASE}.npz", before_mesh=baseline_mesh,
                        after_mesh=mesh, before_shell=baseline_shell, after_shell=shell)
    concise = {
        name: {
            "edges_over_3x": row["distortion"]["historical_length_mask"]["over_3"],
            "penetration_fraction": row["penetration"]["penetrating_fraction"],
            "inverted_prism_samples": row["used_prism_jacobians"]["inverted_samples"],
            "inverted_binding_vertices": row["binding_jacobians"]["inverted_vertices"],
            "visibility": {view: round(stats["visible_fraction"], 4)
                           for view, stats in row["visibility"].items()},
        }
        for name, row in variants.items()
    }
    print(json.dumps({"influences": influence_audit, "comparison": concise,
                      "image": str(comparison.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
