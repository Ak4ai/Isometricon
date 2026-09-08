import numpy as np

import pytest

from src.math.aabb import AABB
from src.integration import VoxelGridProvider
from src.world import BlockType, Chunk3D


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
