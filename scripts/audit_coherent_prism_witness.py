"""Explain why the guarded coherent binder leaves the jeans waist witness."""
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.experimental_coherent_prism import _evaluate_face
from src.clothing.experimental_canonical_radial import canonical_cages, normal_frames


def main():
    case = "female_109837605892174"
    base = ROOT / "artifacts/clothing_audit/radial_frames"
    data = np.load(base / f"{case}.npz")
    bind = np.load(base / f"{case}_binding.npz")
    old = np.load(base / f"{case}_outputs.npz")
    mesh = old["radial_previous"]
    face_ids = bind["face_ids"]
    faces = data["garment_faces"]
    source_face = int(face_ids[734])
    proposed_face = int(face_ids[737])
    output, residual = _evaluate_face(
        data["garment"][734], proposed_face, data["reference_parent"],
        data["outer_parent"], data["target_body"], old["radial_previous_shell"],
        bind["faces"], int(data["cage_normal_sign"]))
    incident = np.flatnonzero(np.any(faces == 734, axis=1))
    before = mesh[faces[incident]]
    after = before.copy()
    after[faces[incident] == 734] = output
    cross = lambda tri: np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n0, n1 = cross(before), cross(after)
    dot = np.einsum("ij,ij->i", n0, n1)
    reversal = dot <= 0
    print("vertex", 734, "original prism", source_face, "proposed prism", proposed_face)
    print("original", mesh[734], "proposed", output, "displacement", np.linalg.norm(output-mesh[734]))
    print("residual", residual, "incident triangles", len(incident),
          "reversals if moved alone", int(reversal.sum()))
    print("reversed face ids", incident[reversal].tolist())
    print("reversed triangles", faces[incident[reversal]].tolist())
    reference, _, target, cage_faces, inverse = canonical_cages(
        data["reference_parent"], data["outer_parent"], data["target_body"],
        data["projection_faces"], data["uv_index"])
    frames, _ = normal_frames(reference, target, cage_faces, int(data["cage_normal_sign"]))
    vertex_frames = frames[inverse][bind["faces"][face_ids]].mean(axis=1)
    original_normal = cross(data["garment"][faces[incident]])
    expected_frame = vertex_frames[faces[incident]].mean(axis=1)
    expected = int(data["cage_normal_sign"]) * np.einsum("ni,nij->nj", original_normal, expected_frame)
    print("baseline orientation sign of reversing faces",
          np.sign(np.einsum("ij,ij->i", expected, n0))[reversal].tolist())
    print("proposed orientation sign of reversing faces",
          np.sign(np.einsum("ij,ij->i", expected, n1))[reversal].tolist())
    print("nearest edge pair source", np.linalg.norm(data["garment"][734]-data["garment"][737]),
          "old", np.linalg.norm(mesh[734]-mesh[737]),
          "proposed", np.linalg.norm(output-mesh[737]))


if __name__ == "__main__":
    main()
