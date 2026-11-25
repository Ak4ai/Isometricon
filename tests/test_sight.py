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


def test_leaves_alone_do_not_open_the_corridor():
    # a copa de um pinheiro entre o personagem e a câmera: quem a abre é o buraco das folhas (no shader), não o
    # corredor, que cortaria também o tronco e o chão. A cobertura que o corredor olha é o sólido sem a folhagem.
    from src.world.block import BlockType
    from src.world.chunk import Chunk3D
    from src.world.room_reveal import extract_window_cells, window_origin
    from src.world.sight import sight_cover
    chunk = Chunk3D(0, 0, 0)
    chunk.blocks[:, :5, :] = int(BlockType.STONE)
    for d in range(1, 4):
        chunk.blocks[10 + d, 6 + d, 10 + d] = int(BlockType.SPRUCE_LEAVES)   # na linha até a câmera
    feet = FEET
    origin = window_origin(feet)
    cells = extract_window_cells(origin, {(0, 0, 0): chunk})
    assert sight_needed(cells.solid, origin, feet, TOWARD_CAMERA)            # com as folhas, abriria
    assert not sight_needed(sight_cover(cells), origin, feet, TOWARD_CAMERA)
    chunk.blocks[12, 7, 12] = int(BlockType.SPRUCE_LOG)                     # um tronco no caminho ainda abre
    cells = extract_window_cells(origin, {(0, 0, 0): chunk})
    assert sight_needed(sight_cover(cells), origin, feet, TOWARD_CAMERA)


def test_the_leaf_hole_keeps_its_size_on_screen():
    # o raio é uma fração da meia-altura visível (ortho_size): afastar a câmera aumenta o buraco no mundo, aproximar
    # diminui, e na tela ele fica do mesmo tamanho; de muito perto não fica menor que o personagem
    from src.world.sight import LEAF_HOLE_MIN, leaf_hole_radius
    assert leaf_hole_radius(20.0) == 2 * leaf_hole_radius(10.0)
    assert leaf_hole_radius(10.0) > leaf_hole_radius(8.0)
    assert leaf_hole_radius(0.5) == LEAF_HOLE_MIN


def test_tronco_longe_rumo_a_camera_tambem_tapa():
    """Uma árvore alta longe do personagem (fora da janela em volta dele) ainda tapa a vista: o raio segue nos chunks."""
    from src.world.block import BlockType
    from src.world.chunk import Chunk3D
    from src.world.sight import sight_blocked_world
    chunks = {}

    def put(x, y, z, block):
        key = (x // 16, y // 16, z // 16)
        chunks.setdefault(key, Chunk3D(*key)).blocks[x % 16, y % 16, z % 16] = int(block)
    for y in range(0, 40):
        put(30, y, 30, BlockType.SEQUOIA_LOG)                  # 30 blocos na diagonal, 40 de altura
    d = (1.0, 0.816, 1.0)
    assert sight_blocked_world(chunks.get, (0.5, 1.1, 0.5), d, 0.0, 120.0)
    assert not sight_blocked_world(chunks.get, (0.5, 1.1, 0.5), (1.0, 0.816, -1.0), 0.0, 120.0)
    for y in range(0, 40):
        put(30, y, 30, BlockType.SPRUCE_LEAVES)               # folha não tapa (abre pelo buraco das folhas)
    assert not sight_blocked_world(chunks.get, (0.5, 1.1, 0.5), d, 0.0, 120.0)
