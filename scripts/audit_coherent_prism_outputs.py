"""Audit visible garment seams and folds in saved coherent-prism results."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.experimental_coherent_prism import _groups
from src.clothing.experimental_canonical_radial import canonical_cages, normal_frames
from scripts.experiment_coherent_prism import CASES, INPUT, OUT


def aligned_seams(source, faces, fitted, body_height):
    """Distance between coincident, similarly oriented UV-split garment copies."""
    _, members = _groups(source, faces)
    radii = []
    for ids in members:
        if len(ids) < 2:
            continue
        points = fitted[ids]
        radii.append(float(np.linalg.norm(points - points.mean(axis=0), axis=1).max()))
    radii = np.asarray(radii)
    return dict(groups=len(radii), max_over_body_height=float(radii.max(initial=0) / body_height),
                over_1e_minus_3=int(np.count_nonzero(radii / body_height > 1e-3)),
                p95_over_body_height=float(np.quantile(radii, .95) / body_height) if len(radii) else 0.0)


def newly_reversed_faces(data, binding, faces, baseline, candidate):
    a = baseline[faces]
    b = candidate[faces]
    normal_a = np.cross(a[:, 1] - a[:, 0], a[:, 2] - a[:, 0])
    normal_b = np.cross(b[:, 1] - b[:, 0], b[:, 2] - b[:, 0])
    len_a = np.linalg.norm(normal_a, axis=1)
    len_b = np.linalg.norm(normal_b, axis=1)
    valid = (len_a > 1e-10) & (len_b > 1e-10)
    reverse = valid & (np.einsum("ij,ij->i", normal_a, normal_b) < 0)
    reference, _, target, canonical_faces, inverse = canonical_cages(
        data["reference_parent"], data["outer_parent"], data["target_body"],
        data["projection_faces"], data["uv_index"])
    parity = int(data["cage_normal_sign"])
    frames, _ = normal_frames(reference, target, canonical_faces, parity)
    vertex_frames = frames[inverse][binding["faces"][binding["face_ids"]]].mean(axis=1)
    src = data["garment"][faces]
    source_normal = np.cross(src[:, 1]-src[:, 0], src[:, 2]-src[:, 0])
    expected = parity * np.einsum("ni,nij->nj", source_normal, vertex_frames[faces].mean(axis=1))
    dot_before = np.einsum("ij,ij->i", normal_a, expected)
    dot_after = np.einsum("ij,ij->i", normal_b, expected)
    corrective = reverse & (dot_before < 0) & (dot_after > 0)
    harmful = reverse & ~corrective
    return dict(relative_to_baseline=int(reverse.sum()),
                corrected_existing_orientation=int(corrective.sum()),
                harmful_new_reversals=int(harmful.sum()),
                harmful_indices=np.flatnonzero(harmful).tolist())


def main():
    path = OUT / "SUMMARY.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    for case in CASES:
        data = np.load(INPUT / f"{case}.npz")
        binding = np.load(INPUT / f"{case}_binding.npz")
        outputs = np.load(OUT / f"{case}.npz")
        height = float(np.ptp(data["body"][:, 2]))
        faces = data["garment_faces"]
        baseline, candidate = outputs["baseline"], outputs["candidate"]
        report["cases"][case]["garment_seams"] = {
            name: aligned_seams(data["garment"], faces, mesh, height)
            for name, mesh in (("radial_prism", baseline), ("coherent_candidate", candidate))
        }
        report["cases"][case]["face_reversals"] = newly_reversed_faces(data, binding, faces, baseline, candidate)
        report["cases"][case].pop("new_face_reversals", None)
        print(case, "reversals", report["cases"][case]["face_reversals"],
              "seams", report["cases"][case]["garment_seams"], flush=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
