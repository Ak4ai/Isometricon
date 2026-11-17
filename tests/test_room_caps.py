"""Testes das tampas: o que o efeito de revelar esconde e as faces que precisam ser geradas (sem OpenGL)."""

import numpy as np
import pytest

from src.rendering.atlas import TextureAtlas
from src.world import BlockType, Schematic
from src.world.room_caps import RAY_START, RAY_STEP, RAY_STEPS, build_caps, hidden_cells
from src.world.room_reveal import INTERIOR, OBJECT, RoomRevealTracker, window_origin
from src.world.structure_layer import StructureLayer
from tests.test_room_reveal import box, world

DOWN = (0.0, -1.0, 0.0)
ISO = tuple(np.array([-1.0, -1.0, -1.0]) / np.sqrt(3.0))


@pytest.fixture(scope="module")
def atlas():
    return TextureAtlas()


def reference_hidden(solid, interior, view_dir, cells):
    """O mesmo que o shader para as ``cells`` dadas: um raio por célula, a partir do centro, passo a passo."""
    shape = np.array(solid.shape)
    direction = np.asarray(view_dir, dtype=np.float64)
    result = []
    for cell in cells:
        found = False
        if solid[tuple(cell)] and not interior[tuple(cell)]:
            for step in range(RAY_STEPS):
                p = np.floor(cell + 0.5 + direction * (RAY_START + RAY_STEP * step)).astype(int)
                if ((p >= 0) & (p < shape)).all() and interior[tuple(p)]:
                    found = True
                    break
        result.append(found)
    return np.array(result)


def room_in(chunks, position, structures=()):
    tracker = RoomRevealTracker()
    return tracker.update(1.0, position, chunks, 1, structures)


def shown_caps(room, vertices, view_dir):
    """As tampas que o shader deixa: a célula dona da face (atrás dela) não sumiu."""
    from src.world.room_caps import cut_cells

    cut = cut_cells(room, view_dir)
    verts = vertices.reshape(-1, 4, 11)
    owners = np.floor(verts[:, :, :3].mean(axis=1) - verts[:, 0, 3:6] * 0.5).astype(int) - np.array(room.origin)
    keep = ~cut[tuple(owners.T)]
    return verts[keep]


@pytest.mark.parametrize("direction", [DOWN, ISO, (0.5, -0.6, 0.62), (-0.8, -0.3, 0.52)])
def test_hidden_cells_match_the_shader_ray_march(direction):
    """O deslocamento inteiro da máscara dá exatamente o resultado do raio por célula."""
    chunks = world(lambda b: box(b, 10, 10, doors=[(0, 0, 3), (0, 1, 3)]))
    room = room_in(chunks, (13.5, 3.0, 13.5))
    interior = room.data == INTERIOR
    direction = np.asarray(direction) / np.linalg.norm(direction)
    hidden = hidden_cells(room.window.solid, interior, direction)
    rng = np.random.default_rng(7)
    near_room = np.argwhere(room.data > 0)                       # a casca e o interior (onde há o que decidir)
    sample = np.concatenate([
        near_room[rng.choice(len(near_room), min(300, len(near_room)), replace=False)],
        np.argwhere(room.window.solid)[rng.choice(int(room.window.solid.sum()), 300, replace=False)],
    ])
    expected = reference_hidden(room.window.solid, interior, direction, sample)
    assert np.array_equal(hidden[tuple(sample.T)], expected)
    assert hidden.any() and expected.any() or direction[1] == 0  # a amostra pega células escondidas de verdade


def test_looking_straight_down_hides_only_the_roof_over_the_room():
    chunks = world(lambda b: box(b, 10, 10))
    room = room_in(chunks, (13.5, 3.0, 13.5))
    hidden = hidden_cells(room.window.solid, room.data == INTERIOR, DOWN)
    ox, oy, oz = room.origin
    assert hidden.sum() == 5 * 5                         # o teto, só sobre o interior de 5x5
    assert hidden[13 - ox, 7 - oy, 13 - oz] and not hidden[10 - ox, 7 - oy, 10 - oz]  # a quina do teto fica


def test_terrain_caps_cover_the_faces_the_mesher_dropped(atlas):
    """O anel do teto fica à vista, e sua face voltada para o teto escondido ganha tampa."""
    chunks = world(lambda b: box(b, 10, 10))
    room = room_in(chunks, (13.5, 3.0, 13.5))
    caps = build_caps(room, DOWN, atlas, lambda block, face: (0, 0, 1, 1))
    vertices, indices = caps.terrain
    verts = shown_caps(room, vertices, DOWN)
    assert len(verts) == 20                              # 5 células x 4 lados do anel
    assert len(caps.structures[1]) == 0
    normals = verts[:, 0, 3:6]
    assert (np.abs(normals[:, 1]) == 0).all()            # só faces laterais
    # cada tampa é a face de uma célula do anel, voltada para dentro (para o teto escondido)
    ox, oy, oz = room.origin
    centre = np.array([13.5, 7.5, 13.5])
    for quad, normal in zip(verts, normals):
        face_centre = quad[:, :3].mean(axis=0)
        assert np.dot(centre - face_centre, normal) > 0
        assert abs(face_centre[1] - 7.5) < 1e-6          # no nível do teto
    assert indices.max() == len(vertices) - 1


def test_terrain_caps_use_the_block_texture(atlas):
    chunks = world(lambda b: box(b, 10, 10, roof_block=BlockType.DIRT))
    room = room_in(chunks, (13.5, 3.0, 13.5))
    vertices, _ = build_caps(room, DOWN, atlas, lambda b, f: (0, 0, 1, 1)).terrain
    verts = vertices.reshape(-1, 4, 11)
    # o anel do teto agora é terra: as UVs vêm da tabela do atlas para (terra, face)
    faces = {int(np.argmax(np.abs(n))) * 2 + (0 if n.max() > 0 else 1) for n in verts[:, 0, 3:6]}
    for quad in verts:
        n = quad[0, 3:6]
        face = {(1, 0, 0): 0, (-1, 0, 0): 1, (0, 0, 1): 4, (0, 0, -1): 5}[tuple(int(v) for v in n)]
        assert np.allclose(quad[:, 6:8], atlas.uv_table[int(BlockType.DIRT), face])
        assert np.allclose(quad[:, 8:11], atlas.color_table[int(BlockType.DIRT), face])
    assert faces


def test_structure_caps_use_the_schematic_atlas_and_not_the_terrain_one(atlas):
    n = 7
    grid = np.full((5, n, n), "minecraft:air", dtype=object)
    grid[0, :, :] = grid[4, :, :] = "minecraft:stone"
    grid[1:4, 0, :] = grid[1:4, -1, :] = grid[1:4, :, 0] = grid[1:4, :, -1] = "minecraft:stone"
    house = Schematic(n, 5, n, grid, palette={}, name="casa")
    layer = StructureLayer()
    layer.add("casa", house, (10, 3, 10))
    chunks = world(lambda b: None)
    room = room_in(chunks, (13.5, 4.0, 13.5), layer.structures)
    assert room.active

    asked = []

    def structure_uv(block, face):
        asked.append((block, face))
        return (0.25, 0.5, 0.5, 0.75)

    caps = build_caps(room, DOWN, atlas, structure_uv)
    assert len(caps.terrain[1]) == 0 and len(shown_caps(room, caps.structures[0], DOWN)) == 20
    assert {block for block, _ in asked} == {"minecraft:stone"}
    uvs = caps.structures[0].reshape(-1, 11)[:, 6:8]
    assert uvs[:, 0].min() == 0.25 and uvs[:, 0].max() == 0.5 and uvs[:, 1].min() == 0.5 and uvs[:, 1].max() == 0.75


def test_no_caps_outside_a_room_or_without_a_window(atlas):
    chunks = world(lambda b: box(b, 10, 10))
    outside = room_in(chunks, (30.5, 3.0, 30.5))
    caps = build_caps(outside, ISO, atlas, lambda b, f: (0, 0, 1, 1))
    assert len(caps.terrain[1]) == 0 and len(caps.structures[1]) == 0
    inside = room_in(chunks, (13.5, 3.0, 13.5))
    inside.window = None
    assert len(build_caps(inside, ISO, atlas, lambda b, f: (0, 0, 1, 1)).terrain[1]) == 0


def test_caps_are_cheap_enough_to_rebuild_when_the_camera_turns(atlas):
    import time

    chunks = world(lambda b: box(b, 10, 10))
    room = room_in(chunks, (13.5, 3.0, 13.5))
    start = time.perf_counter()
    for _ in range(10):
        build_caps(room, ISO, atlas, lambda b, f: (0, 0, 1, 1))
    assert (time.perf_counter() - start) / 10 < 0.05    # bem abaixo de um quadro de folga


def _iso_room(extra=None):
    def build(b):
        box(b, 10, 10)                                   # paredes x/z = 10 e 16, interior 11..15, teto y = 7
        if extra:
            extra(b)
    return room_in(world(build), (13.5, 3.0, 13.5))


def test_cut_cells_keep_the_back_walls_and_cut_the_front_ones():
    """Como o shader: com o centro do cômodo, a parede do fundo fica inteira e a da frente (lado da câmera) some."""
    from src.world.room_caps import cut_cells

    room = _iso_room()
    ox, oy, oz = room.origin
    cut = cut_cells(room, ISO, center=(13.5, 13.5))
    assert not cut[10 - ox, 4 - oy, 13 - oz] and not cut[13 - ox, 4 - oy, 10 - oz]   # fundo
    assert cut[16 - ox, 4 - oy, 13 - oz] and cut[13 - ox, 4 - oy, 16 - oz]           # frente
    assert cut[13 - ox, 7 - oy, 13 - oz]                                             # o teto sobre o espaço


def test_cut_cells_follow_the_story_cut_above_the_ceiling():
    """Acima do teto do andar some a frente e, no fundo, o que está sobre o cômodo; em cima das paredes do fundo fica
    (escurecido pelo shader)."""
    from src.world.room_caps import StoryCut, cut_cells

    def upstairs(b):
        b[10, 8, 10] = BlockType.STONE                   # canto do fundo, no andar de cima
        b[16, 8, 16] = BlockType.STONE                   # canto da frente
    room = _iso_room(upstairs)
    ox, oy, oz = room.origin
    story = StoryCut(cut_y=7, feet_y=3, center=(13.5, 13.5), radius=12.0)
    cut = cut_cells(room, ISO, story=story)
    assert cut[16 - ox, 8 - oy, 16 - oz]
    assert not cut[10 - ox, 8 - oy, 10 - oz]             # o canto do fundo do andar de cima fica
    assert not cut[10 - ox, 4 - oy, 13 - oz]             # a parede do fundo do andar continua


def test_story_cut_leaves_an_eave_along_the_back_walls():
    """Beiral: do teto do cômodo sobra a laje em cima das paredes do fundo e mais um bloco para dentro, reta de uma
    ponta à outra; o resto da laje e o que está acima dela sobre o cômodo somem."""
    from src.world.room_caps import StoryCut, cut_cells

    def upstairs(b):
        b[11, 8, 13] = BlockType.STONE                   # algo do andar de cima, junto da parede do fundo
        b[10, 8, 13] = BlockType.STONE                   # a parede do andar de cima, em cima da parede do fundo
    room = _iso_room(upstairs)
    ox, oy, oz = room.origin
    cut = cut_cells(room, ISO, story=StoryCut(cut_y=7, feet_y=3, center=(13.5, 13.5), radius=24.0))
    # a aba: um bloco à frente de cada parede do fundo, por toda a parede, até a parede da frente
    assert not any(cut[11 - ox, 7 - oy, z - oz] for z in range(11, 16))
    assert not any(cut[x - ox, 7 - oy, 11 - oz] for x in range(11, 16))
    # a laje em cima das próprias paredes do fundo fica, de um vértice ao outro
    assert not any(cut[10 - ox, 7 - oy, z - oz] for z in range(10, 17))
    assert not any(cut[x - ox, 7 - oy, 10 - oz] for x in range(10, 17))
    # a laje em cima das paredes da frente some (a quina da frente e o meio delas)
    assert cut[16 - ox, 7 - oy, 16 - oz] and cut[16 - ox, 7 - oy, 13 - oz] and cut[13 - ox, 7 - oy, 16 - oz]
    # a dois blocos da parede e no meio, a laje some
    assert cut[12 - ox, 7 - oy, 13 - oz] and cut[13 - ox, 7 - oy, 13 - oz] and cut[13 - ox, 7 - oy, 12 - oz]
    # acima da laje, sobre o cômodo (tapa a vista) some; em cima da parede do fundo fica (escurecido no shader)
    assert cut[11 - ox, 8 - oy, 13 - oz]
    assert not cut[10 - ox, 8 - oy, 13 - oz]


def test_eave_ignores_furniture_and_steps_on_the_floor():
    """Um móvel ou degrau no chão é chão do cômodo: a laje em volta dele não vira beiral."""
    from src.world.room_caps import StoryCut, _eave

    def chest(b):
        b[13, 3, 13] = BlockType.STONE                   # um bloco solto no meio do chão
    room = _iso_room(chest)
    ox, oy, oz = room.origin
    assert room.data[13 - ox, 3 - oy, 13 - oz] == OBJECT
    flat = np.array(ISO)[[0, 2]] / np.linalg.norm(np.array(ISO)[[0, 2]])
    over, eave = _eave(room.data, room.origin, StoryCut(cut_y=7, feet_y=3, center=(13.5, 13.5), radius=24.0), flat)
    assert over[13 - ox, 7 - oy, 13 - oz]                # o bloco solto é chão do cômodo
    assert not any(eave[x - ox, 7 - oy, z - oz] for x in (12, 13, 14) for z in (12, 13, 14))
    assert eave[11 - ox, 7 - oy, 13 - oz] and eave[10 - ox, 7 - oy, 13 - oz] and not over[10 - ox, 7 - oy, 13 - oz]


def test_caps_close_the_faces_left_open_by_the_cuts(atlas):
    """Com a parede da frente cortada, os blocos atrás dela ganham as faces que o mesher tinha descartado."""
    room = _iso_room()
    caps = build_caps(room, ISO, atlas, lambda block, face: (0.0, 0.0, 1.0, 1.0), center=(13.5, 13.5))
    assert caps.terrain is not None and len(caps.terrain[0]) > 0


def test_stairs_and_furniture_in_the_front_half_are_not_cut():
    """Degraus e móveis (o espaço logo acima deles) não são parede: ficam, mesmo na metade da frente do cômodo."""
    from src.world.room_caps import StoryCut, cut_cells
    from src.world.room_reveal import OBJECT, story_center, story_ceiling

    def two_floors(b):
        b[5:16, 3:13, 5:16] = BlockType.STONE
        b[6:15, 3:7, 6:15] = BlockType.AIR               # térreo y 3..6, laje em y = 7
        b[6:15, 8:12, 6:15] = BlockType.AIR              # andar de cima, telhado em y = 12
        b[7:11, 7, 12:14] = BlockType.AIR                # só a abertura da escada
        for i, x in enumerate(range(7, 11)):
            b[x, 3:4 + i, 12:14] = BlockType.STONE       # degraus de y = 3 a 6
        b[13, 3, 13] = BlockType.WOOD                    # um móvel na frente
    position = (11.5, 3.0, 8.5)
    room = room_in(world(two_floors), position)
    ox, oy, oz = room.origin
    assert room.data[10 - ox, 6 - oy, 12 - oz] == OBJECT
    assert room.data[14 - ox, 4 - oy, 15 - oz] != OBJECT          # a parede da frente continua parede
    ceiling = story_ceiling(room, position)
    center = story_center(room, 3, ceiling)
    cut = cut_cells(room, ISO, story=StoryCut(ceiling, 3, center, 12.0), center=center)
    steps = [(x, y, z) for i, x in enumerate(range(7, 11)) for y in range(3, 4 + i) for z in (12, 13)]
    assert not any(cut[x - ox, y - oy, z - oz] for x, y, z in steps)
    assert not cut[13 - ox, 3 - oy, 13 - oz]
    assert cut[14 - ox, 4 - oy, 15 - oz]
