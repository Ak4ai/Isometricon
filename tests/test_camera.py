"""Testes unitários da câmera isométrica."""

import math

import numpy as np
import pytest

from src.camera import IsometricCamera
from src.math import transform_point, vec3


def test_camera_default_angles():
    """A câmera deve iniciar com os ângulos isométricos padrão."""
    camera = IsometricCamera()

    assert np.isclose(camera.yaw_degrees, 45.0)

    expected_pitch = math.degrees(
        math.asin(math.tan(math.radians(30.0)))
    )

    assert np.isclose(
        camera.pitch_degrees,
        expected_pitch,
        atol=1e-6,
    )


def test_camera_default_target():
    """O target inicial deve ser a origem."""
    camera = IsometricCamera()

    assert np.allclose(
        camera.target,
        vec3(0.0, 0.0, 0.0),
    )


def test_camera_view_matrix_shape_and_type():
    """A View Matrix deve estar pronta para ser enviada ao OpenGL."""
    camera = IsometricCamera()

    view = camera.get_view_matrix()

    assert view.shape == (4, 4)
    assert view.dtype == np.float32
    assert view.flags.c_contiguous


def test_camera_isometric_view_points_towards_target():
    """O target deve estar à frente da câmera no view space."""
    camera = IsometricCamera()

    view = camera.get_view_matrix()

    target_view = transform_point(
        view,
        camera.target,
    )

    # O target deve estar no eixo Z negativo do view space.
    assert target_view[2] < 0.0

    # Como a câmera olha exatamente para o target,
    # ele deve estar centralizado em X/Y.
    assert np.isclose(target_view[0], 0.0, atol=1e-5)
    assert np.isclose(target_view[1], 0.0, atol=1e-5)


def test_camera_projection_is_orthographic():
    """A projeção deve ser ortográfica."""
    camera = IsometricCamera(
        ortho_size=2.0,
    )

    projection = camera.get_projection_matrix(
        1280,
        720,
    )

    assert projection.shape == (4, 4)
    assert projection.dtype == np.float32
    assert projection.flags.c_contiguous

    # Em uma matriz ortográfica OpenGL, w permanece 1.
    assert np.isclose(projection[3, 3], 1.0)

    # Não existe o componente típico da projeção perspectiva.
    assert np.isclose(projection[3, 2], 0.0)


def test_camera_projection_preserves_aspect_ratio():
    """A largura da projeção deve considerar o aspect ratio."""
    camera = IsometricCamera(
        ortho_size=2.0,
    )

    projection = camera.get_projection_matrix(
        1280,
        720,
    )

    aspect = 1280.0 / 720.0

    expected_x = 1.0 / (2.0 * aspect)
    expected_y = 1.0 / 2.0

    assert np.isclose(
        projection[0, 0],
        expected_x,
        atol=1e-6,
    )

    assert np.isclose(
        projection[1, 1],
        expected_y,
        atol=1e-6,
    )


def test_projection_rejects_invalid_dimensions():
    """Dimensões inválidas devem gerar ValueError."""
    camera = IsometricCamera()

    with pytest.raises(ValueError):
        camera.get_projection_matrix(0, 720)

    with pytest.raises(ValueError):
        camera.get_projection_matrix(1280, 0)

    with pytest.raises(ValueError):
        camera.get_projection_matrix(-1280, 720)


def test_zoom_in_decreases_ortho_size():
    """Zoom positivo deve aproximar a câmera."""
    camera = IsometricCamera(
        ortho_size=10.0,
    )

    initial = camera.ortho_size

    camera.zoom_in()

    assert camera.ortho_size < initial


def test_zoom_out_increases_ortho_size():
    """Zoom negativo deve afastar a câmera."""
    camera = IsometricCamera(
        ortho_size=10.0,
    )

    initial = camera.ortho_size

    camera.zoom_out()

    assert camera.ortho_size > initial


def test_zoom_respects_minimum_limit():
    """Zoom não pode ultrapassar o limite mínimo."""
    camera = IsometricCamera(
        ortho_size=1.0,
    )

    for _ in range(100):
        camera.zoom_in(10.0)

    assert camera.ortho_size == camera.MIN_ORTHO_SIZE


def test_zoom_respects_maximum_limit():
    """Zoom não pode ultrapassar o limite máximo."""
    camera = IsometricCamera(
        ortho_size=1.0,
    )

    for _ in range(100):
        camera.zoom_out(10.0)

    assert camera.ortho_size == camera.MAX_ORTHO_SIZE


def test_pan_moves_target_on_xz_plane():
    """Pan direto deve alterar somente X/Z."""
    camera = IsometricCamera()

    initial = camera.target.copy()

    camera.pan(
        3.0,
        -5.0,
    )

    assert np.isclose(
        camera.target[0],
        initial[0] + 3.0,
    )

    assert np.isclose(
        camera.target[2],
        initial[2] - 5.0,
    )

    assert np.isclose(
        camera.target[1],
        initial[1],
    )


def test_screen_pan_keeps_target_on_xz_plane():
    """Pan pelo mouse não deve modificar a altura do target."""
    camera = IsometricCamera()

    camera.pan_screen(
        100.0,
        50.0,
    )

    assert np.isclose(
        camera.target[1],
        0.0,
    )


def test_screen_pan_changes_target():
    """Movimento do mouse deve mover o ponto focal."""
    camera = IsometricCamera()

    initial = camera.target.copy()

    camera.pan_screen(
        100.0,
        50.0,
    )

    assert not np.allclose(
        camera.target,
        initial,
    )


def test_initial_board_rotation():
    """O tabuleiro começa sem rotação."""
    camera = IsometricCamera()

    assert camera.board_rotation_degrees == 0


def test_rotate_right_by_90_degrees():
    """E deve girar 90° para a direita."""
    camera = IsometricCamera()

    camera.rotate_right()

    assert camera.board_rotation_degrees == 90


def test_rotate_left_by_90_degrees():
    """Q deve girar 90° para a esquerda."""
    camera = IsometricCamera()

    camera.rotate_left()

    assert camera.board_rotation_degrees == 270


def test_four_right_rotations_return_to_zero():
    """Quatro rotações de 90° devem retornar à posição inicial."""
    camera = IsometricCamera()

    for _ in range(4):
        camera.rotate_right()

    assert camera.board_rotation_degrees == 0


def test_four_left_rotations_return_to_zero():
    """Quatro rotações anti-horárias devem retornar à posição inicial."""
    camera = IsometricCamera()

    for _ in range(4):
        camera.rotate_left()

    assert camera.board_rotation_degrees == 0


def test_rotation_model_matrix():
    """A matriz do tabuleiro deve representar a rotação atual."""
    camera = IsometricCamera()

    camera.rotate_right()

    model = camera.get_model_matrix()

    assert model.shape == (4, 4)
    assert model.dtype == np.float32
    assert model.flags.c_contiguous

    # X positivo após rotação Y de +90° deve apontar para -Z.
    transformed = transform_point(
        model,
        vec3(1.0, 0.0, 0.0),
    )

    assert np.allclose(
        transformed,
        [0.0, 0.0, -1.0],
        atol=1e-6,
    )


def test_handle_scroll_zoom_in():
    """Scroll positivo deve aproximar."""
    camera = IsometricCamera(
        ortho_size=10.0,
    )

    initial = camera.ortho_size

    camera.handle_scroll(
        0.0,
        1.0,
    )

    assert camera.ortho_size < initial


def test_handle_scroll_zoom_out():
    """Scroll negativo deve afastar."""
    camera = IsometricCamera(
        ortho_size=10.0,
    )

    initial = camera.ortho_size

    camera.handle_scroll(
        0.0,
        -1.0,
    )

    assert camera.ortho_size > initial


def test_handle_key_q():
    """Tecla Q deve rotacionar para a esquerda."""
    camera = IsometricCamera()

    consumed = camera.handle_key(
        ord("Q"),
        1,
    )

    assert consumed is True
    assert camera.board_rotation_degrees == 270


def test_handle_key_e():
    """Tecla E deve rotacionar para a direita."""
    camera = IsometricCamera()

    consumed = camera.handle_key(
        ord("E"),
        1,
    )

    assert consumed is True
    assert camera.board_rotation_degrees == 90


def test_handle_key_ignores_release():
    """Release não deve causar rotação."""
    camera = IsometricCamera()

    consumed = camera.handle_key(
        ord("E"),
        0,
    )

    assert consumed is False
    assert camera.board_rotation_degrees == 0


def test_reset_rotation():
    """Reset deve retornar para 0°."""
    camera = IsometricCamera()

    camera.rotate_right()
    camera.rotate_right()

    camera.reset_rotation()

    assert camera.board_rotation_degrees == 0


def test_invalid_ortho_size():
    """ortho_size negativo deve ser rejeitado."""
    with pytest.raises(ValueError):
        IsometricCamera(ortho_size=0.0)

    with pytest.raises(ValueError):
        IsometricCamera(ortho_size=-1.0)


def test_invalid_clip_planes():
    """Planos de clipping inválidos devem ser rejeitados."""
    with pytest.raises(ValueError):
        IsometricCamera(
            near=0.0,
            far=100.0,
        )

    with pytest.raises(ValueError):
        IsometricCamera(
            near=10.0,
            far=5.0,
        )
