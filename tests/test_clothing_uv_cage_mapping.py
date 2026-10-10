"""Tests for binding Roblox reference and edited target cages by UV coordinates."""
from pathlib import Path

import numpy as np
import pytest

from src.clothing.wear_engine import (
    BODY_CAGES,
    _align_target_faces_by_uv,
    load_r15_cages,
)


def _part(faces, face_uvs):
    return {
        "faces": np.asarray(faces, dtype=np.int32),
        "face_uvs": np.asarray(face_uvs, dtype=np.float64),
    }


def test_target_triangles_are_paired_by_uv_not_vertex_or_face_order():
    source = _part(
        [[0, 1, 2], [0, 2, 3]],
        [
            [[0, 0], [1, 0], [1, 1]],
            [[0, 0], [1, 1], [0, 1]],
        ],
    )
    # Target vertices and triangles are both reordered. Its face UVs retain identity.
    target = _part(
        [[0, 1, 3], [2, 0, 1]],
        [
            [[1, 1], [0, 0], [0, 1]],
            [[1, 0], [1, 1], [0, 0]],
        ],
    )

    aligned = _align_target_faces_by_uv(source, target, "Synthetic")

    np.testing.assert_array_equal(aligned, [[1, 2, 0], [1, 0, 3]])


def test_missing_uv_binding_fails_instead_of_using_indices():
    source = {"faces": np.asarray([[0, 1, 2]]), "face_uvs": None}
    target = _part([[0, 1, 2]], [[[0, 0], [1, 0], [0, 1]]])

    with pytest.raises(ValueError, match="UV coordinates are required"):
        _align_target_faces_by_uv(source, target, "NoUV")


@pytest.mark.parametrize("body", sorted(BODY_CAGES))
def test_exported_r15_reference_and_body_cages_pair_by_uv_for_all_parts(body):
    root = Path(__file__).resolve().parents[1]
    source = load_r15_cages(str(root / "assets/models/roblox_reference_cages.obj"), is_source_cage=True)
    target = load_r15_cages(str(root / "assets/models" / BODY_CAGES[body]))
    body_parts = [
        "Head", "UpperTorso", "LowerTorso",
        "LeftUpperArm", "LeftLowerArm", "LeftHand",
        "RightUpperArm", "RightLowerArm", "RightHand",
        "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
        "RightUpperLeg", "RightLowerLeg", "RightFoot",
    ]

    assert len(body_parts) == 15
    for name in body_parts:
        aligned = _align_target_faces_by_uv(source[name], target[name], name)
        assert aligned.shape == source[name]["faces"].shape
        assert aligned.shape == target[name]["faces"].shape
        assert np.all(aligned >= 0)
        assert np.all(aligned < len(target[name]["verts"]))


def test_body_cages_share_the_body_uv_points():
    """The male cage is the female cage's topology and UVs on the male body."""
    from src.clothing.wrap_layer_fit import _unique_uv_positions

    root = Path(__file__).resolve().parents[1]
    uvs = {body: _unique_uv_positions(load_r15_cages(str(root / "assets/models" / path)))[0]
           for body, path in BODY_CAGES.items()}
    np.testing.assert_allclose(uvs["male"], uvs["female"], atol=1e-3)
