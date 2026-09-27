"""Contact solve whose samples include the bound garment residual.

This isolates a missing term from earlier shell-only clearance experiments:
actual shirt vertices and face centers are sampled through the prism binding,
so collision corrections can act on the target outer cage that drives them.
The fixed local frame is a linearization around the source-only radial fit;
the final garment is reevaluated with the exact prism code and all metrics.
"""
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
    body_components, body_penetration, distortion, prism_jacobians, seam_report,
)
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.experimental_prism_constraints import PrismShapeConstraints
from src.clothing.experimental_shell_clearance import ClosedBodyUnion, project_shell_clearance
from src.clothing.wrap_layer_fit import _local_map


ROOT_INPUT = ROOT / "artifacts/clothing_audit/radial_frames"
OUT = ROOT / "artifacts/clothing_audit/joint_contact"
CASE = "blocky_133331049150205"


def linked_garment_samples(data, binding, shell):
    """Linearize garment vertices against target outer-cage triangle points."""
    parity = int(data["cage_normal_sign"])
    count = len(data["garment"])
    indices = np.empty((count, 3), dtype=np.int32)
    weights = np.empty((count, 3), dtype=np.float64)
    offsets = np.empty((count, 3), dtype=np.float64)
    for vertex, (face_id, level, bary, residual) in enumerate(zip(
            binding["face_ids"], binding["levels"], binding["bary"], binding["residual"])):
        face = binding["faces"][face_id]
        inner = data["reference_parent"][face]
        outer = data["outer_parent"][face]
        target_inner = data["target_body"][face]
        target_outer = shell[face]
        source_section = (1 - level) * inner + level * outer
        target_section = (1 - level) * target_inner + level * target_outer
        transform = _local_map(*source_section, *target_section, normal_sign=parity)
        if transform is None:
            transform = _local_map(*inner, *target_inner, normal_sign=parity)
        if transform is None:
            transform = _local_map(*outer, *target_outer, normal_sign=parity)
        if transform is None:
            raise ValueError("No valid local frame for bound garment sample")
        indices[vertex] = face
        weights[vertex] = float(level) * bary
        offsets[vertex] = bary @ ((1 - level) * target_inner) + transform @ residual

    # Also constrain triangle centers. Each center depends on the three cage
    # triangles selected by its garment vertices, hence nine shell supports.
    faces = np.asarray(data["garment_faces"], dtype=np.int32)
    center_indices = indices[faces].reshape(-1, 9)
    center_weights = weights[faces].reshape(-1, 9) / 3.0
    center_offsets = offsets[faces].mean(axis=1)
    vertex_indices = np.pad(indices, ((0, 0), (0, 6)), mode="constant")
    vertex_weights = np.pad(weights, ((0, 0), (0, 6)), mode="constant")
    return {
        "indices": np.vstack((vertex_indices, center_indices)),
        "weights": np.vstack((vertex_weights, center_weights)),
        "offsets": np.vstack((offsets, center_offsets)),
    }


def make_comparison(before_path, after_path, output_path):
    images = [Image.open(path).convert("RGB") for path in (before_path, after_path)]
    canvas = Image.new("RGB", (images[0].width, 2 * images[0].height + 48), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), "Controle: radial + prisma", fill="black")
    canvas.paste(images[0], (0, 24))
    y = images[0].height + 24
    draw.text((8, y + 5), "Contato usa vertices e centros da camisa", fill="black")
    canvas.paste(images[1], (0, y + 24))
    canvas.save(output_path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = dict(np.load(ROOT_INPUT / f"{CASE}.npz"))
    frozen = dict(np.load(ROOT_INPUT / f"{CASE}_outputs.npz"))
    reference_report = json.loads((ROOT_INPUT / f"{CASE}.json").read_text(encoding="utf-8"))
    binding = bind_source(data, ROOT_INPUT / f"{CASE}_binding.npz")
    baseline_shell = frozen["radial_previous_shell"].astype(float)
    baseline_mesh = frozen["radial_previous"].astype(float)
    active_faces = binding["faces"][np.unique(binding["face_ids"])]
    components = body_components(data["body"], data["body_faces"])
    closed = [ids for ids, is_closed in components if is_closed]
    body = ClosedBodyUnion(data["body"], data["body_faces"], closed)
    linked = linked_garment_samples(data, binding, baseline_shell)
    # Keep the first contact pass tractable. Every clothing vertex participates;
    # triangle centers remain in the independent final penetration metric.
    linked = {key: value[:len(data["garment"])] for key, value in linked.items()}

    def constraints(x, inverse):
        return PrismShapeConstraints(
            x, inverse, data["reference_parent"], data["outer_parent"],
            data["target_body"], active_faces,
            binding["faces"][binding["face_ids"]], binding["bary"],
            binding["levels"], int(data["cage_normal_sign"]),
        )

    shell, solver_audit = project_shell_clearance(
        data["outer_parent"], baseline_shell, data["projection_faces"],
        active_faces, body,
        margin=float(np.ptp(data["body"][:, 2])) * 1e-4,
        iterations=8, local_steps=True, constraint_factory=constraints,
        linked_samples=linked,
    )
    mesh = evaluate_binding(data, binding, shell)
    shared = np.vstack((data["body"], baseline_mesh, mesh))
    before_image = OUT / f"{CASE}_before.png"
    after_image = OUT / f"{CASE}_after.png"
    before_visibility = depth_preview(data["body"], data["body_faces"], baseline_mesh,
                                      data["garment_faces"], before_image,
                                      shared_garment_vertices=shared)
    after_visibility = depth_preview(data["body"], data["body_faces"], mesh,
                                     data["garment_faces"], after_image,
                                     shared_garment_vertices=shared)
    comparison = OUT / f"{CASE}_comparison.png"
    make_comparison(before_image, after_image, comparison)

    variants = {}
    for label, candidate, candidate_shell, visibility in (
            ("radial_prism", baseline_mesh, baseline_shell, before_visibility),
            ("joint_contact", mesh, shell, after_visibility)):
        samples = np.vstack((candidate, candidate[data["garment_faces"]].mean(axis=1)))
        valid, inverted = binding_jacobians(data, binding, candidate_shell)
        variants[label] = {
            "distortion": distortion(data["garment"], candidate, data["garment_faces"],
                                     float(reference_report["common_metric_scale"])),
            "penetration": body_penetration(samples, data["body"], data["body_faces"]),
            "seams": seam_report(data["outer_parent"], candidate_shell, data["uv_index"]),
            "used_prism_jacobians": prism_jacobians(
                data["reference_parent"], data["outer_parent"], data["target_body"],
                candidate_shell, active_faces, int(data["cage_normal_sign"])),
            "binding_jacobians": {"valid_vertices": int(valid.sum()),
                                  "inverted_vertices": int(inverted.sum())},
            "visibility": visibility,
        }
    report = {
        "case": CASE,
        "method": "shell solve includes bound garment vertices and triangle centers; fixed local-frame linearization",
        "solver": solver_audit,
        "closed_body_components": len(closed),
        "variants": variants,
        "comparison_image": str(comparison.relative_to(ROOT)),
        "limitations": [
            "The clothing residual transform is linearized at the source-only radial fit during contact iterations.",
            "Final garment positions are reevaluated with the exact prism binding before measuring.",
            "Sampled collision and prism guards do not prove continuous non-penetration or universal fit.",
        ],
    }
    (OUT / f"{CASE}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(OUT / f"{CASE}.npz", before_mesh=baseline_mesh,
                        after_mesh=mesh, before_shell=baseline_shell, after_shell=shell)
    concise = {
        label: {
            "edges_over_3x": row["distortion"]["historical_length_mask"]["over_3"],
            "penetration_fraction": row["penetration"]["penetrating_fraction"],
            "prism_inversions": row["used_prism_jacobians"]["inverted_samples"],
            "binding_inversions": row["binding_jacobians"]["inverted_vertices"],
        } for label, row in variants.items()
    }
    print(json.dumps({"solver": {k: v for k, v in solver_audit.items() if k != "history"},
                      "variants": concise, "image": str(comparison.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
