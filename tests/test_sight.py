"""Testes de quando o corredor da câmera precisa abrir (o personagem está encoberto)."""

import numpy as np

from src.world.sight import CHEST, HEAD, sight_blocked, sight_needed

# a câmera isométrica olha de cima, de +x +y +z; do personagem para a câmera é (1, 1, 1) normalizado
TOWARD_CAMERA = (1.0, 1.0, 1.0)
SHAPE = (24, 24, 24)
ORIGIN = (0, 0, 0)
FEET = (10.5, 5.0, 10.5)   # em pé sobre o chão (y = 4 é o último bloco sólido)


def ground():
    solid = np.zeros(SHAPE, dtype=bool)
    solid[:, :5, :] = True
    return solid


def test_open_ground_never_needs_the_corridor():
    assert not sight_needed(ground(), ORIGIN, FEET, TOWARD_CAMERA)


def test_a_one_block_step_in_front_hides_only_the_legs_and_does_not_open():
    solid = ground()
    solid[11, 5, 11] = True       # um degrau de 1 bloco na frente (em direção à câmera)
    assert not sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)


def test_a_wall_that_covers_the_chest_opens_it():
    solid = ground()
    solid[12:14, 5:9, 12:14] = True   # uma parede alta no caminho
    assert sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)


def test_standing_in_a_pit_with_a_high_front_edge_opens_it():
    """O caso da imagem: o personagem num buraco, com a borda da frente mais alta que ele."""
    solid = ground()
    solid[11:14, 5:8, 11:14] = True   # a borda do buraco, 3 blocos acima dos pés, logo à frente
    assert sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)


def test_something_behind_the_character_does_not_count():
    solid = ground()
    solid[8:10, 5:9, 8:10] = True     # atrás dele, longe da câmera
    assert not sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)


def test_the_block_the_character_stands_in_does_not_count():
    solid = ground()
    solid[10, 5, 10] = True           # a célula dos pés
    assert not sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)


def test_the_head_line_alone_is_enough_and_out_of_window_is_ignored():
    solid = ground()
    # só na linha da cabeça (a do peito passa um pouco por baixo, na diagonal): um bloco mais alto logo à frente
    solid[12, 9, 12] = True
    assert sight_blocked(solid, ORIGIN, (FEET[0], FEET[1] + HEAD, FEET[2]), TOWARD_CAMERA)
    assert not sight_blocked(solid, ORIGIN, (FEET[0], FEET[1] + CHEST, FEET[2]), TOWARD_CAMERA)
    assert sight_needed(solid, ORIGIN, FEET, TOWARD_CAMERA)                           # basta uma das duas
    assert not sight_blocked(solid, ORIGIN, (FEET[0], FEET[1] + CHEST, FEET[2]), (0.0, 0.0, 0.0))
    assert not sight_blocked(solid, ORIGIN, (200.0, 200.0, 200.0), TOWARD_CAMERA)   # fora da janela


def test_the_world_offset_of_the_window_is_respected():
    solid = ground()
    solid[12:14, 5:9, 12:14] = True
    assert sight_needed(solid, (100, 0, -50), (110.5, 5.0, -39.5), TOWARD_CAMERA)
    assert not sight_needed(solid, (0, 0, 0), (110.5, 5.0, -39.5), TOWARD_CAMERA)
