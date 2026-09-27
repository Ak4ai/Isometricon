import numpy as np
import pytest
from src.clothing.experimental_refined_reference import RefinedReferenceField


SOURCE = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
FACES = np.array([[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]])


@pytest.mark.parametrize('level', [0, 2])
@pytest.mark.parametrize('parity', [1, -1])
def test_exact_similarity_including_outside_points(level, parity):
    rotation = np.array([[0., -1, 0], [1, 0, 0], [0, 0, parity]])
    target = 2.3*SOURCE@rotation.T+[3, -2, 1]
    field = RefinedReferenceField(SOURCE, target, FACES, np.arange(4), parity, level)
    points = np.array([[.2, .3, .1], [2, -3, .4], *SOURCE])
    np.testing.assert_allclose(field.evaluate(points), 2.3*points@rotation.T+[3, -2, 1], atol=1e-12)


def test_reindex_and_duplicate_storage_invariance():
    target = SOURCE.copy(); target[3] += [.4, .2, .7]
    points = np.random.default_rng(3).normal(size=(20, 3))
    original = RefinedReferenceField(SOURCE, target, FACES, np.arange(4)).evaluate(points)
    ids = FACES[::-1].ravel()
    field = RefinedReferenceField(SOURCE[ids], target[ids], np.arange(12).reshape(-1, 3), ids)
    np.testing.assert_allclose(field.evaluate(points), original, atol=1e-12)


def test_continuity_across_face_boundary_and_coincident_queries():
    target = SOURCE.copy(); target[3] += [.4, .2, .7]
    field = RefinedReferenceField(SOURCE, target, FACES, np.arange(4))
    point = np.array([.5, 0, 0])
    pair = field.evaluate(np.array([point, point, point+[0, 1e-8, -1e-8]]))
    np.testing.assert_array_equal(pair[0], pair[1])
    assert np.linalg.norm(pair[2]-pair[0]) < 1e-6
