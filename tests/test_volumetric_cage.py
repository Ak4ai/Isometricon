"""Validation of temporary, matched cage closure."""
import numpy as np

from src.clothing.volumetric_cage import close_cage_pair


def test_open_cube_closes_with_same_source_target_topology():
    vertices = np.asarray([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ], dtype=float)
    faces = np.asarray([
        [0, 2, 1], [0, 3, 2],
        [0, 1, 5], [0, 5, 4],
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
    ])
    result = close_cage_pair(vertices, vertices * 2, faces)
    assert result["loop_lengths"] == [4]
    assert result["cap_face_count"] == 2
    assert len(result["faces"]) == 12
    np.testing.assert_allclose(result["source_signed_volume"], 1)
    np.testing.assert_allclose(result["target_signed_volume"], 8)


def test_source_seams_weld_and_target_seam_error_is_reported():
    vertices = np.asarray([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1],
    ], dtype=float)
    faces = np.asarray([
        [0, 2, 1], [0, 3, 2],
        [0, 1, 5], [0, 5, 8],
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
    ])
    target = vertices.copy()
    target[8, 0] += .1
    result = close_cage_pair(vertices, target, faces)
    assert len(result["source_vertices"]) == 8
    assert result["target_seam_spread_max"] >= .05 - 1e-8
