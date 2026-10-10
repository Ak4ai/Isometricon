"""Testes unitários da câmera isométrica."""

import math

import numpy as np
import pytest

from src.camera import IsometricCamera
from src.math import mat4_rotate_y, transform_point, transform_vector, vec3


VIEWPORT = (1280, 720)


def project_point(
    camera: IsometricCamera,
    model: np.ndarray,
    point: np.ndarray,
) -> np.ndarray:
    """Projeta um ponto lógico até NDC com as matrizes usadas pelo renderer."""
    projection = camera.get_projection_matrix(*VIEWPORT)
    view = camera.get_view_matrix()
    return transform_point(projection @ view @ model, point)


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


def test_camera_follows_token_target():
    """O foco acompanha a posição do token sem saltar instantaneamente."""
    camera = IsometricCamera()
    target = vec3(4.0, -6.0, 8.0)

    camera.follow_target(target, 1.0 / 60.0)

    assert np.all(camera.target != target)
    assert np.linalg.norm(target - camera.target) < np.linalg.norm(target)


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
    camera = IsometricCamera(target=vec3(2.0, 14.0, -3.0))

    camera.pan_screen(
        100.0,
        50.0,
    )

    assert np.isclose(
        camera.target[1],
        14.0,
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


@pytest.mark.parametrize(
    "focus",
    [
        vec3(18.5, 7.0, 34.25),
        vec3(-27.75, 12.0, -19.5),
    ],
)
def test_board_rotation_keeps_nonzero_focus_fixed(focus):
    """O target deve ser o pivô em todos os quatro estados e após 360°."""
    camera = IsometricCamera(target=focus)

    for _ in range(5):
        transformed_focus = transform_point(camera.get_model_matrix(), focus)
        np.testing.assert_allclose(transformed_focus, focus, atol=1e-5)
        camera.rotate_right()


@pytest.mark.parametrize(
    "focus",
    [
        vec3(18.5, 7.0, 34.25),
        vec3(-27.75, 12.0, -19.5),
    ],
)
def test_focus_projection_is_stable_across_board_rotations(focus):
    """View e Model devem projetar o mesmo foco no mesmo ponto da tela."""
    camera = IsometricCamera(target=focus, ortho_size=4.5)
    initial_projection = project_point(camera, camera.get_model_matrix(), focus)

    for _ in range(4):
        camera.rotate_right()
        rotated_projection = project_point(camera, camera.get_model_matrix(), focus)
        np.testing.assert_allclose(rotated_projection, initial_projection, atol=1e-5)


def test_animated_rotation_keeps_focus_fixed_at_intermediate_angle():
    """O pivô deve permanecer fixo também durante a interpolação Q/E."""
    focus = vec3(23.5, 9.0, -41.25)
    camera = IsometricCamera(target=focus, ortho_size=4.5)
    initial_projection = project_point(camera, camera.get_animated_model_matrix(), focus)

    camera.rotate_right()
    camera.update(0.05)

    assert np.isclose(camera.current_rotation, 45.0)
    animated_model = camera.get_animated_model_matrix()
    np.testing.assert_allclose(transform_point(animated_model, focus), focus, atol=1e-5)
    np.testing.assert_allclose(
        project_point(camera, animated_model, focus),
        initial_projection,
        atol=1e-5,
    )


def test_animated_full_rotation_returns_to_initial_model():
    """Quatro passos animados devem completar 360° sem drift no Model."""
    camera = IsometricCamera(target=vec3(-48.5, 15.0, 63.25))
    initial_model = camera.get_animated_model_matrix()

    for _ in range(4):
        camera.rotate_right()
        camera.update(1.0)

    assert camera.board_rotation_degrees == 0
    assert np.isclose(camera.current_rotation, 360.0)
    np.testing.assert_allclose(camera.get_animated_model_matrix(), initial_model, atol=1e-5)


def test_rotation_pivot_tracks_target_after_pan_follow_and_zoom():
    """Mudanças legítimas do target devem atualizar o pivô sem depender do zoom."""
    camera = IsometricCamera(target=vec3(12.0, 8.0, -6.0), ortho_size=4.5)
    camera.rotate_right()
    camera.update(0.05)

    camera.pan_screen(80.0, -35.0)
    panned_target = camera.get_target()
    np.testing.assert_allclose(
        transform_point(camera.get_animated_model_matrix(), panned_target),
        panned_target,
        atol=1e-5,
    )

    # Equivale ao target atualizado pelo token-follow após o gesto de pan.
    camera.set_target(-22.5, 11.0, 31.75)
    followed_target = camera.get_target()
    before_zoom = project_point(camera, camera.get_animated_model_matrix(), followed_target)
    camera.zoom_in()
    after_zoom = project_point(camera, camera.get_animated_model_matrix(), followed_target)

    np.testing.assert_allclose(
        transform_point(camera.get_animated_model_matrix(), followed_target),
        followed_target,
        atol=1e-5,
    )
    np.testing.assert_allclose(after_zoom[:2], before_zoom[:2], atol=1e-5)


def test_screen_pan_direction_is_stable_during_board_rotation():
    """O Model pivotado não deve rotacionar a resposta visual do pan."""
    focus = vec3(12.0, 8.0, -6.0)
    reference_point = vec3(15.0, 8.0, -2.0)

    def projected_pan_delta(angle: float) -> np.ndarray:
        camera = IsometricCamera(target=focus, ortho_size=4.5)
        camera.current_rotation = angle
        before = project_point(camera, camera.get_animated_model_matrix(), reference_point)
        camera.pan_screen(80.0, -35.0)
        after = project_point(camera, camera.get_animated_model_matrix(), reference_point)
        return after[:2] - before[:2]

    expected_delta = projected_pan_delta(0.0)
    for angle in (45.0, 90.0, 180.0, 270.0):
        np.testing.assert_allclose(projected_pan_delta(angle), expected_delta, atol=1e-5)


@pytest.mark.parametrize(
    "focus",
    [
        vec3(0.0, 0.0, 0.0),
        vec3(-137.5, 9.0, -88.25),
    ],
)
@pytest.mark.parametrize("quarter_turns", [0, 1, 2, 3, 4])
def test_movement_directions_cancel_discrete_board_rotation(focus, quarter_turns):
    """As direções lógicas devem manter o mesmo resultado visual após o Model."""
    camera = IsometricCamera(target=focus)
    base_forward = camera._forward_direction()
    base_right = camera._right_direction()

    for _ in range(quarter_turns):
        camera.rotate_right()

    movement_forward, movement_right = camera.get_movement_directions()
    board_rotation = mat4_rotate_y(math.radians(camera.board_rotation_degrees))

    np.testing.assert_allclose(
        transform_vector(board_rotation, movement_forward),
        base_forward,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        transform_vector(board_rotation, movement_right),
        base_right,
        atol=1e-6,
    )
    assert np.isclose(np.linalg.norm(movement_forward), 1.0)
    assert np.isclose(np.linalg.norm(movement_right), 1.0)


def test_movement_directions_ignore_animated_rotation():
    """O controle usa o estado discreto, sem girar durante a interpolação."""
    camera = IsometricCamera()
    camera.rotate_right()
    expected = camera.get_movement_directions()

    for animated_angle in (0.0, 22.5, 45.0, 89.0):
        camera.current_rotation = animated_angle
        actual = camera.get_movement_directions()
        np.testing.assert_allclose(actual[0], expected[0], atol=1e-6)
        np.testing.assert_allclose(actual[1], expected[1], atol=1e-6)


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


def test_camera_foreground_not_clipped_by_near_plane():
    """Objetos no primeiro plano (frente do target / parte inferior da tela) não devem ser cortados pelo near plane."""
    camera = IsometricCamera()
    view = camera.get_view_matrix()

    # Um ponto a 20 unidades à frente do target (em direção à câmera)
    offset = camera._camera_position() - camera.target
    offset_dir = offset / np.linalg.norm(offset)

    foreground_point = camera.target + offset_dir * 20.0
    view_pos = transform_point(view, foreground_point)

    # No espaço de visualização OpenGL, a câmera olha para -Z.
    # Pontos à frente da câmera devem ter Z negativo e magnitude > near.
    assert view_pos[2] < -camera.near
