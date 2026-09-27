"""Geometric invariants for the experimental multi-influence shell."""
import numpy as np

from src.clothing.multi_influence_shell import transfer_outer_cage, transfer_outer_cage_radial


def _fixture():
    reference = np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, 0.5, 1.)], dtype=float)
    faces = np.array([(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], dtype=int)
    outer = reference + np.array([(0, 0, -.2), (.1, 0, -.1), (.1, .1, -.2), (0, .1, -.1), (0, 0, .3)])
    return reference, outer, faces


def test_identity_preserves_authored_outer_cage():
    reference, outer, faces = _fixture()
    np.testing.assert_allclose(transfer_outer_cage(reference, outer, reference, faces,
                                                   bulk_scale=1), outer, atol=1e-12)


def test_rigid_rotation_and_translation_preserve_authored_shell():
    reference, outer, faces = _fixture()
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    translation = np.array([3., -2., 4.])
    result = transfer_outer_cage(reference, outer, reference @ rotation.T + translation,
                                 faces, bulk_scale=1)
    np.testing.assert_allclose(result, outer @ rotation.T + translation, atol=1e-12)


def test_reflection_preserves_authored_shell_with_explicit_parity():
    reference, outer, faces = _fixture()
    reflection = np.diag([-1., 1., 1.])
    result = transfer_outer_cage(reference, outer, reference @ reflection.T,
                                 faces, parity=-1, bulk_scale=1)
    np.testing.assert_allclose(result, outer @ reflection.T, atol=1e-12)


def test_radial_transfer_preserves_identity_rotation_and_reflection():
    reference, outer, faces = _fixture()
    np.testing.assert_allclose(transfer_outer_cage_radial(reference, outer, reference, faces,
                                                          bulk_scale=1), outer, atol=1e-12)
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    moved = reference @ rotation.T + [3., 2., 1.]
    np.testing.assert_allclose(transfer_outer_cage_radial(reference, outer, moved, faces,
                                                          bulk_scale=1),
                               outer @ rotation.T + [3., 2., 1.], atol=1e-12)
    reflection = np.diag([-1., 1., 1.])
    np.testing.assert_allclose(transfer_outer_cage_radial(reference, outer,
                                                          reference @ reflection.T, faces,
                                                          parity=-1, bulk_scale=1),
                               outer @ reflection.T, atol=1e-12)
    np.testing.assert_allclose(transfer_outer_cage_radial(reference, outer,
                                                          reference * 2, faces),
                               outer * 2, atol=1e-12)


def test_radial_transfer_couples_touching_outer_seam_across_disconnected_charts():
    reference = np.array([(0., 0., 0.), (1., 0., 0.), (0., 1., 0.),
                          (2., 0., 0.), (3., 0., 0.), (3., 1., 0.)])
    outer = reference.copy()
    outer[1] = outer[3] = [1.5, 0., 0.]
    target = reference.copy()
    target[:3, 2] += .4
    target[3:, 2] -= .4
    faces = np.array([(0, 1, 2), (3, 4, 5)])
    result, audit = transfer_outer_cage_radial(reference, outer, target, faces,
                                               bulk_scale=1, return_audit=True)
    np.testing.assert_allclose(result[1], result[3], atol=1e-12)
    assert audit["outer_vertices_with_multiple_influences"] >= 2
