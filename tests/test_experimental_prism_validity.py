import numpy as np
from src.clothing.experimental_prism_validity import determinant_bounds
from src.clothing.experimental_prism_constraints import determinants


def test_straight_wedge_and_reflection():
    low = np.array([[[0., 0, 0], [1, 0, 0], [0, 1, 0]]])
    high = low + [0, 0, 2]
    lo, hi, _, _ = determinant_bounds(low, high)
    np.testing.assert_allclose([lo, hi], 2)
    lo, hi, _, _ = determinant_bounds(low * [-1, 1, 1], high * [-1, 1, 1])
    np.testing.assert_allclose([lo, hi], -2)


def test_detects_fold_between_previous_sampling_levels():
    # det = (t - .2)^2 - .01: positive at 0, .5, 1 but negative at .2.
    low = np.array([[[0., 0, 0], [-.2, .1, 0], [.1, -.2, 0]]])
    high = np.array([[[0., 0, 1], [.8, .1, 1], [.1, .8, 1]]])
    for t in (0., .5, 1.):
        assert determinants(low, high, np.array([[1., 0, 0]]), np.array([t]))[0] > 0
    lo, hi, _, depth = determinant_bounds(low, high)
    np.testing.assert_allclose(lo, -.01)
    np.testing.assert_allclose(hi, .63)
    np.testing.assert_allclose(depth, .2)


def test_bounds_enclose_random_samples_and_scale_cubically():
    rng = np.random.default_rng(42)
    low, high = rng.normal(size=(2, 40, 3, 3))
    lo, hi, corner, depth = determinant_bounds(low, high)
    witness = determinants(low, high, np.eye(3)[corner], depth)
    np.testing.assert_allclose(witness, lo, atol=1e-13)
    for _ in range(50):
        bary = rng.dirichlet([1, 1, 1], size=40)
        sampled = determinants(low, high, bary, rng.random(40))
        assert np.all(sampled >= lo - 1e-13)
        assert np.all(sampled <= hi + 1e-13)
    scaled = determinant_bounds(low * 3, high * 3)
    np.testing.assert_allclose(scaled[0], lo * 27, atol=1e-12)
    np.testing.assert_allclose(scaled[1], hi * 27, atol=1e-12)
