"""Radial outer cage + prism binding used by the runtime WrapLayer fit."""
import numpy as np

from src.clothing.radial_prism_fit import fit_radial_prism


def _octahedron(scale=1.0):
    vertices = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float) * scale
    faces = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),
                      (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    return vertices, faces


def _trace(target_offset=np.zeros(3)):
    inner, faces = _octahedron(1.0)
    outer, _ = _octahedron(1.3)
    return {"reference_parent": inner, "outer_parent": outer, "target_body": inner + target_offset,
            "projection_faces": faces, "cage_normal_sign": 1}


def _garment():
    # A small triangle strip between the cages plus one vertex hanging outside them.
    points = np.array([(0.6, 0.35, 0.35), (0.35, 0.6, 0.35), (0.35, 0.35, 0.6),
                       (0.9, 0.9, 0.4)])  # ~0.5 outside the outer cage face x+y+z=1.3
    faces = np.array([(0, 1, 2), (0, 2, 3)])
    return points, faces


def test_identity_target_keeps_the_garment_in_place():
    points, faces = _garment()
    fitted, audit = fit_radial_prism(points, faces, _trace())
    np.testing.assert_allclose(fitted, points, atol=1e-9)
    assert audit["hanging_vertices"] == 1


def test_translated_body_moves_bound_and_hanging_parts_together():
    offset = np.array([0.2, -0.1, 0.5])
    points, faces = _garment()
    fitted, _ = fit_radial_prism(points, faces, _trace(offset))
    np.testing.assert_allclose(fitted, points + offset, atol=1e-9)


def test_loose_hanging_piece_follows_the_nearest_bound_point_rigidly():
    offset = np.array([0.2, -0.1, 0.5])
    points, faces = _garment()
    # A separate two-triangle bow, not connected to the garment, hanging outside the cages.
    bow = np.array([(0.9, 0.9, 0.6), (1.0, 0.9, 0.6), (0.9, 1.0, 0.6), (1.0, 1.0, 0.7)])
    all_points = np.vstack((points, bow))
    all_faces = np.vstack((faces, np.array([(4, 5, 6), (5, 7, 6)])))
    fitted, audit = fit_radial_prism(all_points, all_faces, _trace(offset))
    assert audit["hanging_vertices"] == 5
    np.testing.assert_allclose(fitted, all_points + offset, atol=1e-9)
