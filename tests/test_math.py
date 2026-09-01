"""Testes unitários para o módulo matemático de vetores e matrizes 4x4."""

import numpy as np
import pytest

from src.math import (
    cross,
    distance,
    dot,
    length,
    mat4_identity,
    mat4_inverse,
    mat4_look_at,
    mat4_multiply,
    mat4_ortho,
    mat4_perspective,
    mat4_rotate,
    mat4_rotate_x,
    mat4_rotate_y,
    mat4_rotate_z,
    mat4_scale,
    mat4_translate,
    normalize,
    transform_point,
    transform_vector,
    vec2,
    vec3,
    vec4,
)


def test_vector_creation_and_types():
    v2 = vec2(1.0, 2.0)
    assert v2.shape == (2,)
    assert v2.dtype == np.float32
    assert np.allclose(v2, [1.0, 2.0])

    v3 = vec3(1.0, 2.0, 3.0)
    assert v3.shape == (3,)
    assert v3.dtype == np.float32
    assert np.allclose(v3, [1.0, 2.0, 3.0])

    v4 = vec4(1.0, 2.0, 3.0, 4.0)
    assert v4.shape == (4,)
    assert v4.dtype == np.float32
    assert np.allclose(v4, [1.0, 2.0, 3.0, 4.0])


def test_vector_algebra():
    v = vec3(3.0, 0.0, 4.0)
    assert length(v) == 5.0

    v_norm = normalize(v)
    assert np.isclose(length(v_norm), 1.0)
    assert np.allclose(v_norm, [0.6, 0.0, 0.8])

    # Vetor nulo não gera divisão por zero
    zero_v = vec3(0.0, 0.0, 0.0)
    assert np.allclose(normalize(zero_v), [0.0, 0.0, 0.0])

    # Dot product
    u = vec3(1.0, 0.0, 0.0)
    w = vec3(0.0, 1.0, 0.0)
    assert dot(u, w) == 0.0
    assert dot(u, u) == 1.0

    # Cross product
    z = cross(u, w)
    assert np.allclose(z, [0.0, 0.0, 1.0])

    # Distance
    p1 = vec3(1.0, 2.0, 3.0)
    p2 = vec3(4.0, 2.0, 7.0)
    assert np.isclose(distance(p1, p2), 5.0)


def test_mat4_identity():
    ident = mat4_identity()
    assert ident.shape == (4, 4)
    assert ident.dtype == np.float32
    assert np.allclose(ident, np.eye(4, dtype=np.float32))
    assert ident.flags.c_contiguous


def test_mat4_translate():
    t = mat4_translate(10.0, -5.0, 2.5)
    assert t.shape == (4, 4)
    assert t.dtype == np.float32

    point = vec3(1.0, 2.0, 3.0)
    transformed = transform_point(t, point)
    assert np.allclose(transformed, [11.0, -3.0, 5.5])

    # Vetores direcionais não sofrem translação
    vector = vec3(1.0, 2.0, 3.0)
    transformed_vec = transform_vector(t, vector)
    assert np.allclose(transformed_vec, [1.0, 2.0, 3.0])


def test_mat4_scale():
    s = mat4_scale(2.0, 3.0, 0.5)
    assert s.shape == (4, 4)
    assert s.dtype == np.float32

    point = vec3(4.0, 2.0, 10.0)
    transformed = transform_point(s, point)
    assert np.allclose(transformed, [8.0, 6.0, 5.0])


def test_mat4_rotations():
    half_pi = np.pi / 2.0

    # Rotação X: (0, 1, 0) rotacionado 90° em torno de X vira (0, 0, 1)
    rx = mat4_rotate_x(half_pi)
    p_x = transform_point(rx, vec3(0.0, 1.0, 0.0))
    assert np.allclose(p_x, [0.0, 0.0, 1.0], atol=1e-6)

    # Rotação Y: (1, 0, 0) rotacionado 90° em torno de Y vira (0, 0, -1)
    ry = mat4_rotate_y(half_pi)
    p_y = transform_point(ry, vec3(1.0, 0.0, 0.0))
    assert np.allclose(p_y, [0.0, 0.0, -1.0], atol=1e-6)

    # Rotação Z: (1, 0, 0) rotacionado 90° em torno de Z vira (0, 1, 0)
    rz = mat4_rotate_z(half_pi)
    p_z = transform_point(rz, vec3(1.0, 0.0, 0.0))
    assert np.allclose(p_z, [0.0, 1.0, 0.0], atol=1e-6)

    # Rotação por eixo arbitrário (eixo Y)
    r_axis = mat4_rotate(half_pi, vec3(0.0, 1.0, 0.0))
    p_axis = transform_point(r_axis, vec3(1.0, 0.0, 0.0))
    assert np.allclose(p_axis, [0.0, 0.0, -1.0], atol=1e-6)


def test_mat4_look_at():
    eye = vec3(0.0, 0.0, 5.0)
    target = vec3(0.0, 0.0, 0.0)
    up = vec3(0.0, 1.0, 0.0)

    view = mat4_look_at(eye, target, up)
    assert view.shape == (4, 4)
    assert view.dtype == np.float32

    # A posição da câmera no espaço de visão deve se transformar para a origem (0, 0, 0)
    p_eye = transform_point(view, eye)
    assert np.allclose(p_eye, [0.0, 0.0, 0.0], atol=1e-6)

    # O ponto target (0,0,0) fica a 5 unidades à frente (Z negativo no OpenGL view space)
    p_target = transform_point(view, target)
    assert np.allclose(p_target, [0.0, 0.0, -5.0], atol=1e-6)


def test_mat4_ortho():
    left, right = -10.0, 10.0
    bottom, top = -5.0, 5.0
    near, far = 0.1, 100.0

    ortho = mat4_ortho(left, right, bottom, top, near, far)
    assert ortho.shape == (4, 4)
    assert ortho.dtype == np.float32

    # O centro do frustum (x=0, y=0, z=-near no view space)
    p_center_near = transform_point(ortho, vec3(0.0, 0.0, -near))
    assert np.allclose(p_center_near, [0.0, 0.0, -1.0], atol=1e-5)

    # Ponto no far plane (z=-far no view space)
    p_center_far = transform_point(ortho, vec3(0.0, 0.0, -far))
    assert np.allclose(p_center_far, [0.0, 0.0, 1.0], atol=1e-5)

    # Canto superior direito no near plane (x=right, y=top, z=-near)
    p_corner = transform_point(ortho, vec3(right, top, -near))
    assert np.allclose(p_corner, [1.0, 1.0, -1.0], atol=1e-5)

    # Erro para dimensões nulas
    with pytest.raises(ValueError):
        mat4_ortho(5.0, 5.0, -5.0, 5.0, 1.0, 10.0)


def test_mat4_perspective():
    persp = mat4_perspective(np.radians(60.0), 16.0 / 9.0, 0.1, 100.0)
    assert persp.shape == (4, 4)
    assert persp.dtype == np.float32

    with pytest.raises(ValueError):
        mat4_perspective(0.0, 1.0, 0.1, 100.0)

    with pytest.raises(ValueError):
        mat4_perspective(np.radians(60.0), 1.0, -1.0, 100.0)


def test_mat4_inverse_and_multiply():
    t = mat4_translate(2.0, 3.0, 4.0)
    r = mat4_rotate_y(0.5)
    s = mat4_scale(1.5, 1.5, 1.5)

    model = mat4_multiply(t, r, s)
    inv_model = mat4_inverse(model)

    ident = mat4_multiply(model, inv_model)
    assert np.allclose(ident, mat4_identity(), atol=1e-5)


def test_mat4_gl_buffer_ready():
    """Garante que todas as matrizes retornadas são np.float32 e contíguas para glUniformMatrix4fv."""
    mats = [
        mat4_identity(),
        mat4_translate(1.0, 2.0, 3.0),
        mat4_scale(1.0, 1.0, 1.0),
        mat4_rotate_x(1.0),
        mat4_rotate_y(1.0),
        mat4_rotate_z(1.0),
        mat4_rotate(1.0, vec3(1.0, 0.0, 0.0)),
        mat4_look_at(vec3(0, 0, 5), vec3(0, 0, 0), vec3(0, 1, 0)),
        mat4_ortho(-10, 10, -10, 10, 0.1, 100),
        mat4_perspective(np.radians(45), 1.0, 0.1, 100),
    ]

    for m in mats:
        assert m.dtype == np.float32
        assert m.shape == (4, 4)
        assert m.flags.c_contiguous