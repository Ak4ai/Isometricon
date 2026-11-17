import numpy as np

import pytest

from src.math.aabb import AABB
from src.integration import VoxelGridProvider
from src.world import BlockType, Chunk3D, TerrainGenerator, WorldManager


def make_chunk(
    chunk_x: int = 0,
    chunk_y: int = 0,
    chunk_z: int = 0,
) -> Chunk3D:
    return Chunk3D(chunk_x, chunk_y, chunk_z)


def test_get_block_at_uses_global_coordinates():
    chunk = make_chunk()
    chunk.set_block(2, 3, 4, BlockType.STONE)

    provider = VoxelGridProvider({(0, 0, 0): chunk})

    assert provider.get_block_at(2, 3, 4) is BlockType.STONE
    assert provider.get_block_at(2, 3, 3) is BlockType.AIR


def test_get_block_at_resolves_chunk_boundaries():
    left = make_chunk(0, 0, 0)
    right = make_chunk(1, 0, 0)

    left.set_block(15, 2, 4, BlockType.DIRT)
    right.set_block(0, 2, 4, BlockType.GRASS)

    provider = VoxelGridProvider({
        (0, 0, 0): left,
        (1, 0, 0): right,
    })

    assert provider.get_block_at(15, 2, 4) is BlockType.DIRT
    assert provider.get_block_at(16, 2, 4) is BlockType.GRASS


def test_get_block_at_supports_negative_coordinates():
    chunk = make_chunk(-1, 0, -1)
    chunk.set_block(15, 2, 15, BlockType.STONE)

    provider = VoxelGridProvider({
        (-1, 0, -1): chunk,
    })

    assert provider.get_block_at(-1, 2, -1) is BlockType.STONE
    assert provider.get_block_at(0, 2, -1) is BlockType.AIR


def test_missing_chunk_returns_air():
    provider = VoxelGridProvider()

    assert provider.get_block_at(100, 10, -50) is BlockType.AIR


def test_is_solid_matches_non_air_contract():
    chunk = make_chunk()
    chunk.set_block(1, 2, 3, BlockType.WATER)
    chunk.set_block(4, 5, 6, BlockType.STONE)

    provider = VoxelGridProvider({(0, 0, 0): chunk})

    assert provider.is_solid(1, 2, 3)
    assert provider.is_solid(4, 5, 6)
    assert not provider.is_solid(0, 0, 0)


def test_top_solid_block():
    chunk = make_chunk()
    chunk.set_block(5, 2, 7, BlockType.STONE)
    chunk.set_block(5, 8, 7, BlockType.DIRT)
    chunk.set_block(5, 11, 7, BlockType.GRASS)

    provider = VoxelGridProvider({(0, 0, 0): chunk})

    assert provider.get_top_solid_block(5, 7) == 11
    assert provider.get_top_solid_block(0, 0) == -1


def test_top_solid_block_across_y_chunks():
    lower = make_chunk(0, 0, 0)
    upper = make_chunk(0, 1, 0)

    lower.set_block(3, 15, 4, BlockType.STONE)
    upper.set_block(3, 0, 4, BlockType.GRASS)

    provider = VoxelGridProvider({
        (0, 0, 0): lower,
        (0, 1, 0): upper,
    })

    assert provider.get_top_solid_block(3, 4) == 16


def test_top_solid_block_uses_loaded_dynamic_world_chunks():
    generator = TerrainGenerator(seed=27, enable_caves=False)
    manager = WorldManager(
        generator=generator,
        render_distance=0,
        create_gl_meshes=False,
        async_loading=False,
    )
    try:
        manager.load_initial_region(-1.0, -1.0)
        provider = VoxelGridProvider(block_lookup=manager.neighbor_at)

        expected_y = max(generator.get_height(-1, -1), generator.sea_level)
        assert provider.get_top_solid_block(-1, -1) == expected_y

        manager.update(32.0, -1.0)
        assert provider.get_block_at(-1, expected_y, -1) is BlockType.AIR
        assert provider.get_top_solid_block(-1, -1) == -1
    finally:
        manager.delete()


def test_block_bounding_box():
    provider = VoxelGridProvider()

    bounds = provider.get_block_bounding_box(-2, 5, 8)

    assert isinstance(bounds, AABB)

    np.testing.assert_array_equal(
        bounds.min,
        np.array([-2, 5, 8], dtype=np.float32),
    )

    np.testing.assert_array_equal(
        bounds.max,
        np.array([-1, 6, 9], dtype=np.float32),
    )


def test_bounding_box_does_not_depend_on_block_existence():
    provider = VoxelGridProvider()

    air_box = provider.get_block_bounding_box(10, 20, 30)

    assert tuple(air_box.min) == (10.0, 20.0, 30.0)
    assert tuple(air_box.max) == (11.0, 21.0, 31.0)


@pytest.mark.parametrize(
    "method,args",
    [
        ("get_block_at", (1.5, 0, 0)),
        ("get_block_at", (0, 1.5, 0)),
        ("get_block_at", (0, 0, 1.5)),
        ("is_solid", (True, 0, 0)),
        ("get_block_bounding_box", (0, False, 0)),
    ],
)
def test_global_queries_validate_coordinates(method, args):
    provider = VoxelGridProvider()

    with pytest.raises(TypeError):
        getattr(provider, method)(*args)


def _column_provider(blocks):
    """Um provedor cuja coluna (qualquer x, z) tem os blocos de ``blocks`` (y -> BlockType); o resto é ar."""
    from src.integration.voxel_grid import VoxelGridProvider
    return VoxelGridProvider(block_lookup=lambda x, y, z: blocks.get(y, BlockType.AIR))


def test_swimming_in_a_lake_is_not_underground():
    # chão até y=5, lago de y=6 a y=8: nadando em y=7 o topo "sólido" sem a água é o chão, abaixo do jogador
    lake = {**{y: BlockType.STONE for y in range(0, 6)}, **{y: BlockType.WATER for y in range(6, 9)}}
    provider = _column_provider(lake)
    assert provider.get_top_solid_block(0, 0) == 8                    # com a água, a coluna "cobre" o jogador
    assert provider.get_top_solid_block(0, 0, skip_water=True) == 5   # sem ela, o jogador está acima do chão
    assert 7.0 > provider.get_top_solid_block(0, 0, skip_water=True) + 0.25


def test_a_cave_under_a_lake_is_still_underground():
    # caverna em y=3..4 com teto de pedra em y=5, e o lago por cima: o teto cobre o jogador
    cave = {**{y: BlockType.STONE for y in (0, 1, 2, 5)}, **{y: BlockType.WATER for y in (6, 7, 8)}}
    provider = _column_provider(cave)
    top = provider.get_top_solid_block(0, 0, skip_water=True)
    assert top == 5 and 3.0 < top + 0.25
