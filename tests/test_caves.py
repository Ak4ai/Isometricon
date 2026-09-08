"""Testes unitários e invariantes do gerador de cavernas 3D (CaveCarver)."""

from itertools import product

import numpy as np
import pytest

from src.world import BlockType, Chunk3D, ChunkMesher, TerrainGenerator
from src.world.caves import CaveCarver


def test_cave_carver_determinism_and_order_independence():
    positions = list(product((-1, 0), (0,), (-1, 0)))

    # Mesma seed deve produzir exatamente o mesmo resultado
    gen1 = TerrainGenerator(seed=1234, enable_caves=True, cave_chance=1.0)
    region1 = gen1.generate_region(positions)

    gen2 = TerrainGenerator(seed=1234, enable_caves=True, cave_chance=1.0)
    region2 = gen2.generate_region(reversed(positions))

    assert set(region1.keys()) == set(region2.keys())
    for key in region1:
        np.testing.assert_array_equal(region1[key].blocks, region2[key].blocks)


def test_different_seeds_produce_different_caves():
    positions = list(product((-1, 0), (0,), (-1, 0)))

    gen1 = TerrainGenerator(seed=10, enable_caves=True, cave_chance=1.0)
    region1 = gen1.generate_region(positions)

    gen2 = TerrainGenerator(seed=9999, enable_caves=True, cave_chance=1.0)
    region2 = gen2.generate_region(positions)

    # Verifica se os arrays de blocos são diferentes
    different = False
    for key in positions:
        if not np.array_equal(region1[key].blocks, region2[key].blocks):
            different = True
            break
    assert different


def test_caves_carve_air_into_solid_layers():
    positions = [(0, 0, 0)]
    
    # Sem cavernas: tudo sólido até a superfície
    no_caves = TerrainGenerator(seed=42, enable_caves=False).generate_region(positions)[(0, 0, 0)]
    solid_count_before = np.count_nonzero(no_caves.blocks != int(BlockType.AIR))

    # Com cavernas forçadas (chance 1.0)
    with_caves = TerrainGenerator(seed=42, enable_caves=True, cave_chance=1.0).generate_region(positions)[(0, 0, 0)]
    solid_count_after = np.count_nonzero(with_caves.blocks != int(BlockType.AIR))

    # Deve haver menos blocos sólidos devido à escavação de ar
    assert solid_count_after < solid_count_before


def test_caves_preserve_water():
    # Mundo com alto nível do mar para garantir bastante água
    gen = TerrainGenerator(
        seed=77,
        base_height=4,
        amplitude=2,
        sea_level=12,
        enable_caves=True,
        cave_chance=1.0,
    )
    positions = list(product((-1, 0), (0,), (-1, 0)))
    region = gen.generate_region(positions)

    # Nenhuma água deve ser destruída pela caverna
    for chunk in region.values():
        for x in range(16):
            for z in range(16):
                for y in range(16):
                    world_y = chunk.chunk_y * 16 + y
                    # Se este bloco deveria ser água (entre surface e sea_level)
                    surface = gen.get_height(chunk.chunk_x * 16 + x, chunk.chunk_z * 16 + z)
                    if surface < world_y <= gen.sea_level:
                        assert chunk.get_block(x, y, z) == BlockType.WATER


def test_sparse_subterranean_chunks():
    # allow_sparse_depth=True pode criar chunks em Y=-1 quando a caverna aprofunda
    gen_sparse = TerrainGenerator(
        seed=1234,
        base_height=4,
        amplitude=0,
        enable_caves=True,
        cave_chance=1.0,
        allow_sparse_depth=True,
    )
    region = gen_sparse.generate_region([(0, 0, 0)])
    has_negative_y = any(cy < 0 for _, cy, _ in region.keys())

    # Se desceu para Y=-1, o chunk deve conter blocos de ar escavados em meio a rocha
    if has_negative_y:
        sub_chunk = [c for k, c in region.items() if k[1] < 0][0]
        assert np.any(sub_chunk.blocks == int(BlockType.AIR))
        assert np.any(sub_chunk.blocks == int(BlockType.STONE))


def test_disabled_sparse_depth_prevents_negative_chunks():
    gen_no_sparse = TerrainGenerator(
        seed=1234,
        base_height=4,
        amplitude=0,
        enable_caves=True,
        cave_chance=1.0,
        allow_sparse_depth=False,
    )
    region = gen_no_sparse.generate_region([(0, 0, 0)])
    assert all(cy >= 0 for _, cy, _ in region.keys())


def test_caved_chunk_meshing():
    gen = TerrainGenerator(seed=555, enable_caves=True, cave_chance=1.0)
    region = gen.generate_region(list(product((-1, 0), (0,), (-1, 0))))

    mesher = ChunkMesher()
    for chunk in region.values():
        mesh = mesher.build(chunk)
        assert mesh.face_count > 0
        assert mesh.vertices.shape == (mesh.face_count * 4, 11)
        assert mesh.indices.shape == (mesh.face_count * 6,)


@pytest.mark.parametrize("kwargs,error", [
    ({"cave_chance": -0.1}, ValueError),
    ({"cave_chance": 1.1}, ValueError),
    ({"cave_chance": "high"}, TypeError),
    ({"room_chance": -0.5}, ValueError),
    ({"room_chance": 1.5}, ValueError),
    ({"min_length": 0}, ValueError),
    ({"max_length": 10, "min_length": 20}, ValueError),
    ({"min_radius": 0.0}, ValueError),
    ({"max_radius": 1.0, "min_radius": 2.0}, ValueError),
    ({"allow_sparse_depth": "yes"}, TypeError),
])
def test_cave_carver_validation(kwargs, error):
    with pytest.raises(error):
        CaveCarver(**kwargs)


@pytest.mark.parametrize("kwargs,error", [
    ({"enable_caves": "true"}, TypeError),
    ({"cave_chance": 1.5}, ValueError),
    ({"allow_sparse_depth": 1}, TypeError),
])
def test_terrain_generator_cave_validation(kwargs, error):
    with pytest.raises(error):
        TerrainGenerator(**kwargs)
