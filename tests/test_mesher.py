"""Meshing CPU: contagens, geometria, fronteiras e contrato de upload."""

from itertools import product
import subprocess
import sys

import numpy as np
import pytest

from src.world import BlockType, Chunk3D, ChunkMeshData, ChunkMesher, get_block_color, is_opaque


DIRECTIONS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


def assert_mesh(data, faces):
    assert isinstance(data, ChunkMeshData)
    assert data.face_count == faces
    assert data.vertex_count == faces * 4
    assert data.index_count == faces * 6
    assert data.vertices.shape == (faces * 4, 11)
    assert data.indices.shape == (faces * 6,)
    assert data.vertices.dtype == np.float32
    assert data.indices.dtype == np.uint32
    assert data.vertices.flags.c_contiguous
    assert data.indices.flags.c_contiguous
    assert np.isfinite(data.vertices).all()
    if faces:
        assert data.indices.min() == 0
        assert data.indices.max() < data.vertex_count
        assert len(np.unique(data.indices)) == data.vertex_count
        assert np.all((data.vertices[:, 6:8] >= 0) & (data.vertices[:, 6:8] <= 1))
        triangles = data.vertices[data.indices.reshape(-1, 3)]
        crosses = np.cross(triangles[:, 1, :3] - triangles[:, 0, :3],
                           triangles[:, 2, :3] - triangles[:, 0, :3])
        # Área = 1/2, CCW voltado para fora e normal constante por triângulo.
        np.testing.assert_array_equal(crosses, triangles[:, 0, 3:6])
        np.testing.assert_array_equal(triangles[:, 0, 3:6], triangles[:, 1, 3:6])
        np.testing.assert_array_equal(triangles[:, 0, 3:6], triangles[:, 2, 3:6])


def test_empty_and_air_removed():
    chunk = Chunk3D()
    assert_mesh(ChunkMesher().build(chunk), 0)
    chunk.set_block(4, 5, 6, BlockType.STONE)
    chunk.set_block(4, 5, 6, BlockType.AIR)
    assert_mesh(ChunkMesher().build(chunk), 0)


@pytest.mark.parametrize('block', [b for b in BlockType if b != BlockType.AIR])
def test_single_block_geometry_normals_uvs_colors(block):
    chunk = Chunk3D()
    position = np.array([4, 6, 7])
    chunk.set_block(*position, block)
    data = ChunkMesher().build(chunk)
    assert_mesh(data, 6)
    quads = data.vertices.reshape(6, 4, 11)
    assert {tuple(q[0, 3:6]) for q in quads} == set(DIRECTIONS)
    for quad in quads:
        normal = quad[0, 3:6]
        axis = np.flatnonzero(normal)[0]
        expected_plane = position[axis] + (normal[axis] > 0)
        assert np.all(quad[:, axis] == expected_plane)
        assert len(np.unique(quad[:, :3], axis=0)) == 4
        assert np.all(quad[:, :3] >= position)
        assert np.all(quad[:, :3] <= position + 1)
        assert {tuple(uv) for uv in quad[:, 6:8]} == {(0, 0), (1, 0), (1, 1), (0, 1)}
        np.testing.assert_array_equal(quad[:, 8:11],
                                      np.tile(np.float32(get_block_color(block)), (4, 1)))
        # Topo usa UV=(x,z); faces verticais mantêm V crescente em Y.
        if normal[1] == 1:
            np.testing.assert_array_equal(quad[:, 6:8], (quad[:, :3] - position)[:, [0, 2]])
        elif normal[1] == 0:
            np.testing.assert_array_equal(quad[:, 7], quad[:, 1] - position[1])


@pytest.mark.parametrize('axis', range(3))
@pytest.mark.parametrize('count', [2, 3, 8, 16])
def test_line_along_each_axis(axis, count):
    chunk = Chunk3D()
    for i in range(count):
        position = [5, 5, 5]
        position[axis] = i
        chunk.set_block(*position, BlockType.STONE)
    # Seis por bloco menos duas por cada contato: 6N - 2(N-1).
    assert_mesh(ChunkMesher().build(chunk), 4 * count + 2)


@pytest.mark.parametrize('side', [2, 16])
def test_solid_cube(side):
    chunk = Chunk3D()
    chunk.blocks[:side, :side, :side] = BlockType.STONE
    data = ChunkMesher().build(chunk)
    assert_mesh(data, 6 * side * side)
    for quad in data.vertices.reshape(-1, 4, 11):
        normal = quad[0, 3:6]
        axis = np.flatnonzero(normal)[0]
        assert np.all(quad[:, axis] == (side if normal[axis] > 0 else 0))
    if side == 16:
        reduction = 1 - data.face_count / (6 * side ** 3)
        assert reduction == 0.9375
        assert reduction >= 0.70


@pytest.mark.parametrize('axis', range(3))
def test_opposite_borders_do_not_wrap(axis):
    chunk = Chunk3D()
    for edge in (0, 15):
        position = [7, 7, 7]
        position[axis] = edge
        chunk.set_block(*position, BlockType.STONE)
    assert_mesh(ChunkMesher().build(chunk), 12)


@pytest.mark.parametrize('position', list(product((0, 15), repeat=3)))
def test_corner(position):
    chunk = Chunk3D()
    chunk.set_block(*position, BlockType.STONE)
    assert_mesh(ChunkMesher().build(chunk), 6)


@pytest.mark.parametrize('first,second,faces', [
    (BlockType.DIRT, BlockType.GRASS, 10),
    (BlockType.STONE, BlockType.WOOD, 10),
    (BlockType.STONE, BlockType.WATER, 11),
    (BlockType.LEAVES, BlockType.STONE, 11),
    (BlockType.WATER, BlockType.WATER, 12),
    (BlockType.LEAVES, BlockType.LEAVES, 12),
    (BlockType.WATER, BlockType.LEAVES, 12),
])
def test_mixed_types_and_transparency(first, second, faces):
    chunk = Chunk3D()
    chunk.set_block(5, 5, 5, first)
    chunk.set_block(6, 5, 5, second)
    data = ChunkMesher().build(chunk)
    assert_mesh(data, faces)
    for block, neighbor in ((first, second), (second, first)):
        color = np.float32(get_block_color(block))
        actual = np.count_nonzero(np.all(data.vertices[:, 8:11] == color, axis=1))
        multiplier = 2 if first == second else 1
        assert actual == multiplier * (6 - int(is_opaque(neighbor))) * 4


@pytest.mark.parametrize('block,opaque', [
    (BlockType.AIR, False), (BlockType.DIRT, True), (BlockType.GRASS, True),
    (BlockType.STONE, True), (BlockType.WATER, False), (BlockType.WOOD, True),
    (BlockType.LEAVES, False),
])
def test_opacity_policy(block, opaque):
    assert is_opaque(block) is opaque
    assert is_opaque(np.uint8(block)) is opaque


@pytest.mark.parametrize('value,error', [
    (-1, ValueError), (7, ValueError), (256, ValueError),
    (1.0, TypeError), (True, TypeError), (np.bool_(False), TypeError),
    ('1', TypeError), (None, TypeError),
])
def test_opacity_validation(value, error):
    with pytest.raises(error):
        is_opaque(value)


@pytest.mark.parametrize('direction', DIRECTIONS)
@pytest.mark.parametrize('neighbor,faces', [(BlockType.STONE, 5), (BlockType.AIR, 6),
                                          (BlockType.WATER, 6), (BlockType.LEAVES, 6)])
def test_external_callback_world_coordinates(direction, neighbor, faces):
    chunk = Chunk3D(-2, 1, -3)
    axis = next(i for i, d in enumerate(direction) if d)
    position = [7, 7, 7]
    position[axis] = 15 if direction[axis] > 0 else 0
    chunk.set_block(*position, BlockType.STONE)
    calls = []

    def lookup(x, y, z):
        calls.append((x, y, z))
        return neighbor

    data = ChunkMesher().build(chunk, neighbor_at=lookup)
    assert_mesh(data, faces)
    world = chunk.local_to_world(*position)
    assert calls == [tuple(world[i] + direction[i] for i in range(3))]
    assert np.all(data.vertices[:, :3] >= position)
    assert np.all(data.vertices[:, :3] <= np.array(position) + 1)


def test_callback_only_outside_and_errors_propagate():
    chunk = Chunk3D()

    def unavailable(*position):
        raise RuntimeError('lookup failed')

    assert_mesh(ChunkMesher().build(chunk, unavailable), 0)
    chunk.set_block(7, 7, 7, BlockType.STONE)
    assert_mesh(ChunkMesher().build(chunk, unavailable), 6)
    chunk.set_block(0, 0, 0, BlockType.STONE)
    with pytest.raises(RuntimeError, match='lookup failed'):
        ChunkMesher().build(chunk, unavailable)
    with pytest.raises(ValueError):
        ChunkMesher().build(chunk, lambda *p: 255)


def test_adjacent_full_chunks_remove_shared_boundary():
    left, right = Chunk3D(-1, 0, 0), Chunk3D()
    left.blocks[:] = right.blocks[:] = BlockType.STONE

    def lookup(x, y, z):
        for chunk in (left, right):
            try:
                return chunk.get_block(*chunk.world_to_local(x, y, z))
            except IndexError:
                pass
        return BlockType.AIR

    for chunk in (left, right):
        assert_mesh(ChunkMesher().build(chunk, lookup), 5 * 16 * 16)


def test_rebuild_is_independent_and_does_not_mutate_chunk():
    chunk = Chunk3D()
    chunk.set_block(1, 2, 3, BlockType.GRASS)
    original = chunk.blocks.copy()
    mesher = ChunkMesher()
    first, second = mesher.build(chunk), mesher.build(chunk)
    np.testing.assert_array_equal(first.vertices, second.vertices)
    np.testing.assert_array_equal(first.indices, second.indices)
    first.vertices[:] = 0
    first.indices[:] = 0
    assert_mesh(second, 6)
    np.testing.assert_array_equal(chunk.blocks, original)
    assert chunk.blocks.dtype == np.uint8
    assert chunk.blocks.flags.f_contiguous
    chunk.blocks[:] = BlockType.AIR
    assert_mesh(mesher.build(chunk), 0)


def test_cpu_meshing_imports_without_opengl_or_glfw():
    code = '''
import sys
sys.modules['OpenGL'] = None
sys.modules['glfw'] = None
from src.world import Chunk3D, ChunkMesher
assert ChunkMesher().build(Chunk3D()).face_count == 0
'''
    subprocess.run([sys.executable, '-c', code], check=True)
