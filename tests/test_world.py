# Testes da fundação voxel: memória, tipos, coordenadas e limites.

from enum import IntEnum
from itertools import product

import numpy as np
import pytest

from src.math.aabb import AABB
from src.world import BLOCK_COLORS, BlockType, Chunk3D, get_block_color


def test_block_ids_and_colors():
    assert issubclass(BlockType, IntEnum)
    assert {block.name: block.value for block in BlockType} == {
        "AIR": 0, "DIRT": 1, "GRASS": 2, "STONE": 3,
        "WATER": 4, "WOOD": 5, "LEAVES": 6,
    }
    assert set(BLOCK_COLORS) == set(BlockType)
    for block in BlockType:
        color = get_block_color(block)
        assert get_block_color(np.uint8(block)) == color
        assert len(color) == 3
        assert all(0.0 <= channel <= 1.0 for channel in color)
        assert np.asarray(color, dtype=np.float32).shape == (3,)
    with pytest.raises(TypeError):
        BLOCK_COLORS[BlockType.AIR] = (1.0, 1.0, 1.0)


def test_empty_chunk_storage():
    chunk = Chunk3D()
    assert (chunk.chunk_x, chunk.chunk_y, chunk.chunk_z) == (0, 0, 0)
    assert chunk.SIZE == 16
    assert isinstance(chunk.blocks, np.ndarray)
    assert chunk.blocks.shape == (16, 16, 16)
    assert chunk.blocks.dtype == np.uint8
    assert chunk.blocks.nbytes == 4096
    assert chunk.blocks.flags.f_contiguous
    assert np.all(chunk.blocks == BlockType.AIR)
    for position in product(range(16), repeat=3):
        assert chunk.get_block(*position) is BlockType.AIR


@pytest.mark.parametrize("block_type", list(BlockType))
@pytest.mark.parametrize("position", [(0, 0, 0), (15, 15, 15), (4, 6, 7)])
def test_get_set_all_types(block_type, position):
    chunk = Chunk3D()
    chunk.set_block(*position, BlockType.STONE)
    chunk.set_block(*position, block_type)
    assert chunk.get_block(*position) is block_type
    assert chunk.blocks[position] == int(block_type)


def test_all_valid_coordinates_and_axis_order():
    chunk = Chunk3D()
    for x, y, z in product(range(16), repeat=3):
        chunk.set_block(x, y, z, (x + 2 * y + 3 * z) % 7)
    for x, y, z in product(range(16), repeat=3):
        expected = (x + 2 * y + 3 * z) % 7
        assert chunk.get_block(x, y, z) == expected
        assert chunk.blocks.ravel(order="F")[x + 16 * (y + 16 * z)] == expected


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("value", [-17, -1, 16, 32])
def test_local_bounds_are_strict(axis, value):
    chunk = Chunk3D()
    position = [0, 0, 0]
    position[axis] = value
    for operation in (chunk.get_block, chunk.local_to_world):
        with pytest.raises(IndexError):
            operation(*position)
    with pytest.raises(IndexError):
        chunk.set_block(*position, BlockType.STONE)
    assert np.all(chunk.blocks == BlockType.AIR)


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("value", [1.5, 1.0, True, np.bool_(False), "1", None])
def test_coordinate_types_are_strict(axis, value):
    position = [0, 0, 0]
    position[axis] = value
    with pytest.raises(TypeError):
        Chunk3D(*position)
    chunk = Chunk3D()
    for operation in (chunk.get_block, chunk.local_to_world, chunk.world_to_local):
        with pytest.raises(TypeError):
            operation(*position)
    with pytest.raises(TypeError):
        chunk.set_block(*position, BlockType.STONE)


@pytest.mark.parametrize("value,error", [
    (-1, ValueError), (7, ValueError), (256, ValueError),
    (1.5, TypeError), (1.0, TypeError), ("1", TypeError),
    (True, TypeError), (np.bool_(True), TypeError), (None, TypeError),
])
def test_invalid_block_ids_do_not_mutate(value, error):
    chunk = Chunk3D()
    chunk.set_block(1, 2, 3, BlockType.WOOD)
    with pytest.raises(error):
        chunk.set_block(1, 2, 3, value)
    assert chunk.get_block(1, 2, 3) is BlockType.WOOD
    with pytest.raises(error):
        get_block_color(value)


def test_numpy_integer_coordinates_and_ids():
    chunk = Chunk3D(np.int64(-1), np.int32(0), np.int64(2))
    chunk.set_block(np.int64(1), np.int32(2), np.uint8(3), np.uint8(6))
    assert chunk.get_block(1, 2, 3) is BlockType.LEAVES
    assert chunk.local_to_world(1, 2, 3) == (-15, 2, 35)


@pytest.mark.parametrize("position,local,world", [
    ((2, 0, 3), (4, 6, 7), (36, 6, 55)),
    ((0, 0, 0), (15, 15, 15), (15, 15, 15)),
    ((-2, -1, -3), (4, 6, 7), (-28, -10, -41)),
    ((-1, -1, -1), (15, 15, 15), (-1, -1, -1)),
])
def test_coordinate_conversion(position, local, world):
    chunk = Chunk3D(*position)
    assert chunk.local_to_world(*local) == world
    assert chunk.world_to_local(*world) == local


@pytest.mark.parametrize("axis", range(3))
def test_adjacent_chunks_have_distinct_cells(axis):
    position = [0, 0, 0]
    position[axis] = -1
    left = Chunk3D(*position)
    right = Chunk3D()
    last = [0, 0, 0]
    last[axis] = 15
    world = left.local_to_world(*last)
    assert world[axis] == -1
    assert left.world_to_local(*world) == tuple(last)
    with pytest.raises(IndexError):
        right.world_to_local(*world)
    with pytest.raises(IndexError):
        left.world_to_local(0, 0, 0)
    assert right.world_to_local(0, 0, 0) == (0, 0, 0)
    assert left.get_bounding_box().max[axis] == right.get_bounding_box().min[axis]


@pytest.mark.parametrize("position,minimum,maximum", [
    ((0, 0, 0), (0, 0, 0), (16, 16, 16)),
    ((2, 1, 3), (32, 16, 48), (48, 32, 64)),
    ((-2, -1, -3), (-32, -16, -48), (-16, 0, -32)),
])
def test_chunk_aabb(position, minimum, maximum):
    chunk = Chunk3D(*position)
    bounds = chunk.get_bounding_box()
    assert isinstance(bounds, AABB)
    np.testing.assert_array_equal(bounds.min, minimum)
    np.testing.assert_array_equal(bounds.max, maximum)
    for vector in bounds:
        assert vector.shape == (3,)
        assert vector.dtype == np.float32
    np.testing.assert_array_equal(bounds.max - bounds.min, (16, 16, 16))
    bounds.min[:] = 999
    np.testing.assert_array_equal(chunk.get_bounding_box().min, minimum)


def test_chunks_are_independent():
    first, second = Chunk3D(), Chunk3D()
    assert not np.shares_memory(first.blocks, second.blocks)
    first.set_block(0, 0, 0, BlockType.DIRT)
    second.set_block(15, 15, 15, BlockType.WOOD)
    assert second.get_block(0, 0, 0) is BlockType.AIR
    assert first.get_block(15, 15, 15) is BlockType.AIR


@pytest.mark.parametrize("dtype", [np.uint8, np.int16, np.int64, np.uint64])
def test_initial_array_is_validated_and_copied(dtype):
    source = (np.arange(4096).reshape(16, 16, 16) % 7).astype(dtype)
    # Inclui entrada não contígua; os eixos lógicos não podem ser trocados.
    source = source.transpose(2, 0, 1)
    first, second = Chunk3D(blocks=source), Chunk3D(blocks=source)
    np.testing.assert_array_equal(first.blocks, source)
    assert first.blocks.dtype == np.uint8
    assert first.blocks.nbytes == 4096
    assert first.blocks.flags.f_contiguous
    assert not np.shares_memory(first.blocks, source)
    assert not np.shares_memory(first.blocks, second.blocks)
    source[:] = BlockType.STONE
    first.set_block(0, 0, 0, BlockType.WOOD)
    assert second.get_block(0, 0, 0) is BlockType.AIR


@pytest.mark.parametrize("shape", [(4096,), (16, 16), (16, 256, 16), (0, 16, 16)])
def test_initial_array_rejects_shape(shape):
    with pytest.raises(ValueError):
        Chunk3D(blocks=np.zeros(shape, dtype=np.uint8))


@pytest.mark.parametrize("dtype", [np.float32, np.float64, bool, object, str, complex])
def test_initial_array_rejects_non_integer_dtype(dtype):
    with pytest.raises(TypeError):
        Chunk3D(blocks=np.zeros((16, 16, 16), dtype=dtype))


@pytest.mark.parametrize("value", [-1, 7, 255, 256, 257])
def test_initial_array_rejects_invalid_values_before_conversion(value):
    blocks = np.zeros((16, 16, 16), dtype=np.int64)
    blocks[4, 6, 7] = value
    with pytest.raises(ValueError):
        Chunk3D(blocks=blocks)


def test_initial_data_requires_ndarray():
    with pytest.raises(TypeError):
        Chunk3D(blocks=[[[0]]])
