import numpy as np

from src.clothing.experimental_bidirectional_radial import (
    transfer_outer_cage_bidirectional_radial,
)
from src.clothing.multi_influence_shell import transfer_outer_cage_radial


def _tetrahedron():
    inner = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    outer = inner * 1.18 + np.array([-.04, -.04, -.04])
    target = inner @ np.array([[1.1, .15, 0.], [0., .85, .1], [0., 0., 1.05]])
    return inner, outer, target, faces


def test_bidirectional_radial_preserves_identity_and_reports_both_center_sets():
    inner, outer, _, faces = _tetrahedron()
    fitted, audit = transfer_outer_cage_bidirectional_radial(
        inner, outer, inner, faces, parity=1, bulk_scale=1., return_audit=True,
    )
    np.testing.assert_allclose(fitted, outer, atol=1e-12)
    assert audit["source_center_queries"] == len(inner)
    assert audit["target_center_queries"] == len(inner)
    assert audit["outer_vertices_receiving_target_influence"] == len(outer)


def test_target_centers_change_transfer_vs_source_only_control():
    inner, outer, target, faces = _tetrahedron()
    target[3] += [.3, -.2, .4]
    source_only = transfer_outer_cage_radial(
        inner, outer, target, faces, parity=1, bulk_scale=1., radius_factor=8.,
    )
    both_centers = transfer_outer_cage_bidirectional_radial(
        inner, outer, target, faces, parity=1, bulk_scale=1., radius_factor=8.,
    )
    assert np.isfinite(both_centers).all()
    assert np.max(np.linalg.norm(both_centers - source_only, axis=1)) > 1e-6
