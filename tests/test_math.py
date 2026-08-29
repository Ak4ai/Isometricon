import numpy as np
from src.math.vector import vec3, normalize, dot, cross

def test_vector_operations():
    v = vec3(3.0, 0.0, 0.0)
    v_norm = normalize(v)
    assert np.allclose(v_norm, np.array([1.0, 0.0, 0.0]))

    u = vec3(1.0, 0.0, 0.0)
    w = vec3(0.0, 1.0, 0.0)
    assert dot(u, w) == 0.0

    z = cross(u, w)
    assert np.allclose(z, np.array([0.0, 0.0, 1.0]))