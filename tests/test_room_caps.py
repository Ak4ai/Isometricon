"""Testes das tampas: o que o efeito de revelar esconde e as faces que precisam ser geradas (sem OpenGL)."""

import numpy as np
import pytest

from src.rendering.atlas import TextureAtlas
from src.world import BlockType, Schematic
from src.world.room_caps import RAY_START, RAY_STEP, RAY_STEPS, build_caps, hidden_cells
from src.world.room_reveal import INTERIOR, RoomRevealTracker, window_origin
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
    assert len(indices) // 6 == 20                       # 5 células x 4 lados do anel
    assert len(caps.structures[1]) == 0
    verts = vertices.reshape(-1, 4, 11)
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
    assert len(caps.terrain[1]) == 0 and len(caps.structures[1]) // 6 == 20
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
