"""Invariantes do terreno e integração CPU, sem janela ou contexto gráfico."""

from dataclasses import FrozenInstanceError
from itertools import product
from math import floor
import os
import subprocess
import sys

import numpy as np
import pytest

from src.world import BlockType, Chunk3D, ChunkMesher, TerrainGenerator


@pytest.mark.parametrize('seed', [0, -1234, 1234])
def test_determinism_and_order(seed):
    positions = list(product((-1, 0), (-1, 0, 1), (-1, 0)))
    first = TerrainGenerator(seed).generate_region(positions)
    second = TerrainGenerator(seed).generate_region(reversed(positions))
    for key in positions:
        np.testing.assert_array_equal(first[key].blocks, second[key].blocks)
        assert not np.shares_memory(first[key].blocks, second[key].blocks)
    assert TerrainGenerator(seed).get_height(20, -15) == TerrainGenerator(seed).get_height(20, -15)


def test_different_seeds_and_natural_relief():
    positions = list(product(range(-64, 65, 4), repeat=2))
    first = [TerrainGenerator(0).get_height(*p) for p in positions]
    second = [TerrainGenerator(1).get_height(*p) for p in positions]
    assert first != second
    assert min(first) < TerrainGenerator().sea_level < max(first)
    assert len(set(first)) >= 5


@pytest.mark.parametrize('amplitude', [0, 0.5, 6, 24.5])
def test_height_integer_and_normalized_bounds(amplitude):
    generator = TerrainGenerator(-5, base_height=-3, amplitude=amplitude, octaves=5)
    for x, z in product(range(-50, 51, 7), repeat=2):
        height = generator.get_height(x, z)
        assert type(height) is int
        assert -3 + floor(-amplitude) <= height <= -3 + floor(amplitude)


@pytest.mark.parametrize('surface,sea', [(8, 7), (7, 7), (4, 7), (19, 22), (-8, -5)])
@pytest.mark.parametrize('chunk_y', [-2, -1, 0, 1, 2])
def test_layers_and_vertical_chunks(surface, sea, chunk_y):
    generator = TerrainGenerator(0, base_height=surface, amplitude=0, sea_level=sea)
    chunk = Chunk3D(-1, chunk_y, 2)
    original_array = chunk.blocks
    bounds = chunk.get_bounding_box()
    assert np.all(chunk.blocks == BlockType.AIR)
    generator.populate_chunk(chunk)
    for y in range(16):
        world_y = chunk_y * 16 + y
        if world_y > max(surface, sea):
            expected = BlockType.AIR
        elif world_y > surface:
            expected = BlockType.WATER
        elif world_y == surface:
            expected = BlockType.DIRT if surface < sea else BlockType.GRASS
        elif world_y >= surface - 3:
            expected = BlockType.DIRT
        else:
            expected = BlockType.STONE
        assert np.all(chunk.blocks[:, y, :] == expected)
    assert chunk.blocks is original_array
    assert chunk.blocks.shape == (16, 16, 16)
    assert chunk.blocks.dtype == np.uint8
    assert chunk.blocks.flags.f_contiguous
    np.testing.assert_array_equal(chunk.get_bounding_box().min, bounds.min)
    np.testing.assert_array_equal(chunk.get_bounding_box().max, bounds.max)


@pytest.mark.parametrize('depth', [0, 1, 5, 20])
def test_configurable_dirt_depth_and_repopulation(depth):
    generator = TerrainGenerator(base_height=10, amplitude=0, dirt_depth=depth)
    chunk = Chunk3D()
    chunk.blocks[:] = BlockType.WOOD
    generator.populate_chunk(chunk)
    assert np.all(chunk.blocks[:, 10, :] == BlockType.GRASS)
    assert np.all(chunk.blocks[:, 11:, :] == BlockType.AIR)
    assert np.count_nonzero(chunk.blocks[0, :10, 0] == BlockType.DIRT) == min(depth, 10)
    before = chunk.blocks.copy()
    generator.populate_chunk(chunk)
    np.testing.assert_array_equal(before, chunk.blocks)


@pytest.mark.parametrize('axis', [0, 2])
@pytest.mark.parametrize('boundary', [-16, 0, 16])
def test_world_coordinates_at_adjacent_borders(axis, boundary, monkeypatch):
    generator = TerrainGenerator(base_height=8, amplitude=5, sea_level=-20)
    positions = []
    for coordinate in (boundary // 16 - 1, boundary // 16):
        p = [0, 0, 0]
        p[axis] = coordinate
        positions.append(tuple(p))
    calls = []
    real_height = TerrainGenerator.get_height

    def record(self, x, z):
        calls.append((x, z))
        return real_height(self, x, z)

    monkeypatch.setattr(TerrainGenerator, 'get_height', record)
    region = generator.generate_region(positions)
    expected_calls = []
    for chunk in region.values():
        for z, x in product(range(16), repeat=2):
            wx, _, wz = chunk.local_to_world(x, 0, z)
            expected_calls.append((wx, wz))
            height = real_height(generator, wx, wz)
            assert chunk.get_block(x, height, z) == BlockType.GRASS
            assert chunk.get_block(x, height + 1, z) == BlockType.AIR
    assert calls == expected_calls  # Exactly one height evaluation per column.
    for other in range(16):
        a, b = [other, other], [other, other]
        a[axis // 2], b[axis // 2] = boundary - 1, boundary
        assert tuple(a) in calls and tuple(b) in calls
        # Normalized octave noise has bounded slope; integer steps are expected.
        assert abs(real_height(generator, *a) - real_height(generator, *b)) <= 2


def test_noise_is_continuous_across_negative_and_positive_lattice_edges():
    generator = TerrainGenerator(1234)
    for edge in (-2, -1, 0, 1, 2):
        assert abs(generator._noise(edge - 1e-6, 0.37) - generator._noise(edge + 1e-6, 0.37)) < 1e-5
        assert abs(generator._noise(0.37, edge - 1e-6) - generator._noise(0.37, edge + 1e-6)) < 1e-5


def test_region_mesh_indices_geometry_and_neighbor_culling():
    chunks = TerrainGenerator(1234).generate_region(product((-1, 0), (0,), (-1, 0)))

    def lookup(x, y, z):
        chunk = chunks.get((x // 16, y // 16, z // 16))
        return BlockType.AIR if chunk is None else chunk.get_block(*chunk.world_to_local(x, y, z))

    for chunk in chunks.values():
        before = chunk.blocks.copy()
        mesh = ChunkMesher().build(chunk, lookup)
        assert 0 < mesh.face_count < ChunkMesher().build(chunk).face_count
        assert mesh.vertices.shape == (mesh.face_count * 4, 11)
        assert mesh.vertices.dtype == np.float32
        assert mesh.indices.dtype == np.uint32
        assert mesh.vertices.flags.c_contiguous and mesh.indices.flags.c_contiguous
        assert mesh.indices.min() == 0
        assert mesh.indices.max() < mesh.vertex_count
        assert np.isfinite(mesh.vertices).all()
        assert np.all((mesh.vertices[:, :3] >= 0) & (mesh.vertices[:, :3] <= 16))
        triangles = mesh.vertices[mesh.indices.reshape(-1, 3)]
        np.testing.assert_array_equal(
            np.cross(triangles[:, 1, :3] - triangles[:, 0, :3],
                     triangles[:, 2, :3] - triangles[:, 0, :3]), triangles[:, 0, 3:6])
        np.testing.assert_array_equal(chunk.blocks, before)


def test_cpu_only_and_reproducible_across_processes():
    code = '''
import sys
sys.modules['OpenGL'] = None
sys.modules['glfw'] = None
from src.world import TerrainGenerator, Chunk3D
from hashlib import sha256
chunk = Chunk3D(-1, 0, 2)
TerrainGenerator(-1234).populate_chunk(chunk)
print(sha256(chunk.blocks.tobytes()).hexdigest())
'''
    results = [subprocess.check_output([sys.executable, '-c', code],
               env={**os.environ, 'PYTHONHASHSEED': value}) for value in ('0', '42')]
    assert results[0] == results[1]


@pytest.mark.parametrize('kwargs,error', [
    ({'seed': True}, TypeError), ({'seed': 1.5}, TypeError),
    ({'octaves': 0}, ValueError), ({'octaves': 1.5}, TypeError),
    ({'dirt_depth': -1}, ValueError), ({'base_height': 1.5}, TypeError),
    ({'sea_level': False}, TypeError), ({'frequency': 0}, ValueError),
    ({'amplitude': -1}, ValueError), ({'amplitude': float('nan')}, ValueError),
    ({'frequency': float('inf')}, ValueError), ({'persistence': -0.1}, ValueError),
    ({'persistence': 1.1}, ValueError), ({'lacunarity': 0.5}, ValueError),
    ({'lacunarity': 1e308, 'octaves': 3}, ValueError),
    ({'amplitude': True}, TypeError), ({'frequency': '1'}, TypeError),
])
def test_invalid_configuration(kwargs, error):
    with pytest.raises(error):
        TerrainGenerator(**kwargs)


def test_numpy_integers_and_immutable_configuration():
    generator = TerrainGenerator(np.int64(-1), base_height=np.int32(8))
    assert generator.get_height(np.int32(20), np.int64(-15)) == generator.get_height(20, -15)
    with pytest.raises(FrozenInstanceError):
        generator.seed = 7
    for coordinate in (True, 1.2, '2'):
        with pytest.raises(TypeError):
            generator.get_height(coordinate, 0)


def test_region_empty_and_duplicate_positions():
    generator = TerrainGenerator()
    assert generator.generate_region([]) == {}
    assert len(generator.generate_region([(0, 0, 0), (0, 0, 0)])) == 1


@pytest.mark.parametrize('position', [(), (0,), (0, 0), (0, 0, 0, 0)])
def test_region_requires_three_coordinates(position):
    with pytest.raises(ValueError):
        TerrainGenerator().generate_region([position])


def test_zero_persistence_matches_single_octave():
    single = TerrainGenerator(45, octaves=1)
    multiple = TerrainGenerator(45, octaves=5, persistence=0)
    for position in product(range(-20, 21, 3), repeat=2):
        assert single.get_height(*position) == multiple.get_height(*position)
