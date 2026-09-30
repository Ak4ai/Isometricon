"""Boots that come with a garment stay rigid below the ankle; long skirts are left alone."""
import numpy as np

from src.clothing.wear_engine import SHOE_RIGID_TOP, RobloxWearEngine


def _strip(x0, x1, z0=-0.02, z1=0.30, n=6):
    """A vertical band of cloth from x0 to x1: vertices and triangles."""
    xs, zs = np.linspace(x0, x1, n), np.linspace(z0, z1, n)
    verts = np.array([[x, 0.0, z] for z in zs for x in xs])
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            faces += [[a, a + 1, a + n], [a + 1, a + n + 1, a + n]]
    return verts, np.array(faces)


def _engine(calls):
    engine = RobloxWearEngine.__new__(RobloxWearEngine)
    engine._fit_shoe_affine = lambda points, trace: (calls.append(len(points)), points + [0, 0, 1.0])[1]
    return engine


def test_long_skirt_hem_is_not_treated_as_boots():
    verts, faces = _strip(-0.25, 0.25)
    calls = []
    out = _engine(calls)._rigid_footwear(verts, faces, verts, trace={})
    np.testing.assert_array_equal(out, verts)
    assert not calls


def test_each_trouser_leg_foot_is_fitted_rigidly():
    left, left_faces = _strip(-0.06, 0.28)  # a wide hem crossing the middle a little
    right, right_faces = _strip(-0.28, -0.08)
    verts = np.vstack([left, right])
    faces = np.vstack([left_faces, right_faces + len(left)])
    calls = []
    out = _engine(calls)._rigid_footwear(verts, faces, verts, trace={})
    assert len(calls) == 2
    below = verts[:, 2] < SHOE_RIGID_TOP
    np.testing.assert_allclose(out[below, 2] - verts[below, 2], 1.0)  # fully rigid
    np.testing.assert_allclose(out[verts[:, 2] > 0.2], verts[verts[:, 2] > 0.2], atol=1e-6)  # above the blend
