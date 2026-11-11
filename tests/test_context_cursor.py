"""O cursor de contexto (as formas de cada modo, o rótulo) e a mira do personagem para o cursor."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

from src.interactive.context_cursor import (
    AIM_DEAD_ZONE, SCALE, CursorMode, _Canvas, aim_point, classify, cursor_image, door_in_reach, face_toward,
    prompt_image, pulse,
)
from src.world.doors import door_at, find_door, toggle_door
from tests.test_doors import wall_with_door


def pixel(image, x, y):
    """A cor no pixel de interface (x, y) relativo ao centro do cursor."""
    h = _Canvas.HALF
    return image.getpixel(((x + h) * SCALE + SCALE // 2, (y + h) * SCALE + SCALE // 2))


def test_the_mode_follows_what_is_under_the_cursor():
    hit = SimpleNamespace(block=(0, 0, 0))
    assert classify(None) is CursorMode.WALK
    assert classify(hit) is CursorMode.MINE
    assert classify(hit, door=object()) is CursorMode.INTERACT


def test_the_cross_has_a_black_outline_and_the_mode_colour_inside():
    image = cursor_image(CursorMode.WALK)
    assert pixel(image, 0, 0) == CursorMode.WALK.color
    assert pixel(image, 3, 0) == CursorMode.WALK.color and pixel(image, 0, -3) == CursorMode.WALK.color
    assert pixel(image, 4, 0) == (0, 0, 0, 255) and pixel(image, 0, 4) == (0, 0, 0, 255)
    assert pixel(image, 6, 0)[3] == 0       # andar: nada em volta


@pytest.mark.parametrize("mode, spot", [
    (CursorMode.MINE, (-6, 0)),      # colchete do lado esquerdo
    (CursorMode.INTERACT, (0, -6)),  # ponto de cima do losango
    (CursorMode.ATTACK, (7, 7)),     # canto de baixo à direita
    (CursorMode.BUILD, (-6, -6)),    # canto de cima à esquerda
])
def test_each_mode_draws_its_shape_around_the_cross(mode, spot):
    image = cursor_image(mode)
    assert pixel(image, *spot) == mode.color
    assert pixel(cursor_image(CursorMode.WALK), *spot)[3] == 0


def test_interact_and_attack_pulse_outwards():
    assert pulse(0.0) in (0, 1) and {pulse(t / 10) for t in range(20)} == {0, 1}
    assert pixel(cursor_image(CursorMode.INTERACT, grow=1), 0, -7) == CursorMode.INTERACT.color
    assert pixel(cursor_image(CursorMode.INTERACT, grow=0), 0, -8)[3] == 0


def test_the_prompt_shows_the_key_and_the_verb():
    image = prompt_image("E", "Abrir")
    colours = {tuple(c) for c in np.asarray(image).reshape(-1, 4).tolist()}
    assert (181, 181, 181, 255) in colours                    # a borda da tecla
    assert any(c[:3] == CursorMode.INTERACT.color[:3] for c in colours)  # o verbo, dourado
    assert image.width > prompt_image("E", "A").width


def test_the_aim_is_the_hit_point_or_the_ground_plane_under_the_cursor():
    hit = SimpleNamespace(point=np.array([3.0, 5.0, 4.0]))
    np.testing.assert_allclose(aim_point(hit, None, 0.0), (3.0, 5.0, 4.0))
    ray = SimpleNamespace(origin=np.array([0.0, 10.0, 0.0]), direction=np.array([0.6, -0.8, 0.0]))
    np.testing.assert_allclose(aim_point(None, ray, 2.0), (6.0, 2.0, 0.0))
    up = SimpleNamespace(origin=np.array([0.0, 10.0, 0.0]), direction=np.array([0.0, 1.0, 0.0]))
    assert aim_point(None, up, 2.0) is None                    # o raio não chega ao chão


def test_the_character_turns_smoothly_towards_the_cursor():
    position = (0.0, 0.0, 0.0)
    target = (5.0, 0.0, 0.0)                                   # a +x: yaw de 90 graus
    yaw = face_toward(0.0, position, target, 0.06)
    assert yaw == pytest.approx(math.pi / 4, abs=1e-6)         # meia-vida: metade do caminho
    for _ in range(60):
        yaw = face_toward(yaw, position, target, 1 / 60)
    assert yaw == pytest.approx(math.pi / 2, abs=1e-3)
    # pelo lado mais curto: de 170 graus para -170 gira 20, não 340
    turned = face_toward(math.radians(170), position, (math.sin(math.radians(-170)), 0, math.cos(math.radians(-170))), 10)
    assert math.cos(turned - math.radians(-170)) == pytest.approx(1.0, abs=1e-6)
    # com o cursor em cima do personagem, não gira
    assert face_toward(1.0, position, (AIM_DEAD_ZONE / 2, 0.0, 0.0), 1.0) == 1.0
    assert face_toward(1.0, position, None, 1.0) == 1.0


def test_the_door_under_the_cursor_is_found_by_either_half():
    layer, placed = wall_with_door()
    lower = door_at(layer.structures, (12, 3, 10))
    upper = door_at(layer.structures, (12, 4, 10))
    assert lower is not None and lower == upper == find_door(layer.structures, (12.5, 3.0, 11.5))
    assert door_at(layer.structures, (11, 3, 10)) is None      # a parede
    assert door_at(layer.structures, (40, 3, 10)) is None      # fora da construção
    toggle_door(lower)
    assert door_at(layer.structures, (12, 4, 10)) == lower     # aberta também


def test_the_door_under_the_cursor_opens_only_within_reach():
    layer, placed = wall_with_door()
    door = door_at(layer.structures, (12, 3, 10))
    assert door_in_reach(door, (12.5, 3.0, 12.5))
    assert not door_in_reach(door, (12.5, 3.0, 16.5))          # longe
    assert not door_in_reach(door, (12.5, 9.0, 11.5))          # dois andares acima
    assert not door_in_reach(None, (12.5, 3.0, 11.5))


def test_the_cursor_fades_out_when_the_mouse_rests():
    from src.interactive.context_cursor import CURSOR_FADE, CURSOR_IDLE, cursor_opacity
    assert cursor_opacity(0.0) == 1.0
    assert cursor_opacity(CURSOR_IDLE - CURSOR_FADE) == pytest.approx(1.0)
    assert 0.0 < cursor_opacity(CURSOR_IDLE - CURSOR_FADE / 2) < 1.0
    assert cursor_opacity(CURSOR_IDLE) == 0.0 and cursor_opacity(60.0) == 0.0


def test_the_visible_surface_skips_what_the_room_cut_hides():
    """Um teto escondido entre a câmera e o chão: o raio recomeça no chão visto e acha o chão, não o teto."""
    from src.interaction.raycast import Ray, raycast_voxels
    from src.interactive.context_cursor import SKY, raycast_visible
    from src.world.block import BlockType

    class Lookup:
        def get_block_at(self, x, y, z):
            if y == 5 or y == 0:                       # o teto (cortado na tela) e o chão
                return BlockType.STONE
            return BlockType.AIR

    ray = Ray(np.array([0.5, 10.0, 0.5], dtype=np.float32), np.array([0.0, -1.0, 0.0], dtype=np.float32))
    assert raycast_voxels(ray, Lookup()).block == (0, 5, 0)          # sem a superfície: o teto
    hit = raycast_visible(ray, Lookup(), np.array([0.5, 1.0, 0.5]), raycast_voxels)
    assert hit.block == (0, 0, 0) and hit.normal == (0, 1, 0)
    assert hit.distance == pytest.approx(9.0, abs=1e-6)
    assert raycast_visible(ray, Lookup(), SKY, raycast_voxels) is None
    assert raycast_visible(ray, Lookup(), None, raycast_voxels).block == (0, 5, 0)
