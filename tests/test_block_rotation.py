"""Girar blocos e construções em passos de 90°, com as propriedades de direção girando junto."""

import numpy as np
import pytest

from src.editor.voxel_object import EMPTY, VoxelObject
from src.world.block_rotation import rotate_block_name, rotate_schematic
from src.world.schematic import Schematic
from src.world.shape_showcase import showcase_schematic


@pytest.mark.parametrize("name,turns,expected", [
    ("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]", 1, "minecraft:oak_stairs[facing=north,half=bottom,shape=straight]"),
    ("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]", 2, "minecraft:oak_stairs[facing=west,half=bottom,shape=straight]"),
    ("minecraft:oak_log[axis=x]", 1, "minecraft:oak_log[axis=z]"),
    ("minecraft:oak_log[axis=y]", 1, "minecraft:oak_log[axis=y]"),
    ("minecraft:oak_sign[rotation=0]", 1, "minecraft:oak_sign[rotation=12]"),
    ("minecraft:oak_fence[east=true,north=false,south=false,west=false]", 1, "minecraft:oak_fence[east=false,north=true,south=false,west=false]"),
    ("minecraft:rail[shape=north_south]", 1, "minecraft:rail[shape=east_west]"),
    ("minecraft:rail[shape=ascending_east]", 1, "minecraft:rail[shape=ascending_north]"),
    ("minecraft:rail[shape=south_east]", 1, "minecraft:rail[shape=north_east]"),
    ("minecraft:oak_door[facing=south,half=lower,hinge=left,open=false]", 1, "minecraft:oak_door[facing=east,half=lower,hinge=left,open=false]"),
    ("minecraft:chest[facing=south,type=left]", 1, "minecraft:chest[facing=east,type=left]"),
    ("minecraft:stone", 3, "minecraft:stone"),
])
def test_rotate_block_name(name, turns, expected):
    assert rotate_block_name(name, turns) == expected


def test_four_turns_is_identity_for_every_name_in_the_shape_showcase():
    names = set(showcase_schematic().grid.ravel().tolist())
    for name in names:
        assert rotate_block_name(rotate_block_name(name, 3), 1) == name
        assert rotate_block_name(name, 4) == name


def _random_schematic(seed=3):
    rng = np.random.default_rng(seed)
    w, h, l = 4, 2, 6
    grid = np.full((h, l, w), "minecraft:air", dtype=object)
    grid[rng.random((h, l, w)) < 0.4] = "minecraft:stone"
    return Schematic(w, h, l, grid, {}, "teste")


@pytest.mark.parametrize("turns", [1, 2, 3])
def test_grid_rotation_matches_voxel_object_rotation(turns):
    schematic = _random_schematic()
    obj = VoxelObject((schematic.width, schematic.height, schematic.length), "o")
    stone = obj.add_material((128, 128, 128))
    for y, z, x in np.argwhere(schematic.grid != "minecraft:air"):
        obj.set(int(x), int(y), int(z), stone)
    rotated = rotate_schematic(schematic, turns)
    expected = obj.rotated_y(turns)
    assert (rotated.width, rotated.height, rotated.length) == expected.size
    occupied = {(int(x), int(y), int(z)) for y, z, x in np.argwhere(rotated.grid != "minecraft:air")}
    assert occupied == {(int(x), int(y), int(z)) for x, y, z in np.argwhere(expected.blocks != EMPTY)}


def test_block_on_the_east_edge_facing_east_still_faces_its_edge_after_a_turn():
    grid = np.full((1, 3, 5), "minecraft:air", dtype=object)
    grid[0, 1, 4] = "minecraft:oak_stairs[facing=east,half=bottom,shape=straight]"
    rotated = rotate_schematic(Schematic(5, 1, 3, grid, {}, "t"), 1)
    (y, z, x), = np.argwhere(rotated.grid != "minecraft:air")
    assert z == 0                      # o lado leste foi para o lado norte
    assert "facing=north" in rotated.grid[y, z, x]


@pytest.mark.parametrize("turns", [1, 3])
def test_tints_rotate_with_the_grid(turns):
    w, h, l = 3, 2, 5
    grid = np.empty((h, l, w), dtype=object)
    tints = np.zeros((h, l, w, 3), dtype=np.float32)
    for index, (y, z, x) in enumerate(np.ndindex(h, l, w)):
        grid[y, z, x] = f"minecraft:block_{index}"     # o nome e a cor dizem de qual célula vieram
        tints[y, z, x, 0] = index
    schematic = Schematic(w, h, l, grid, {}, "t")
    schematic.tints = tints
    rotated = rotate_schematic(schematic, turns)
    assert rotated.tints.shape == (rotated.height, rotated.length, rotated.width, 3)
    for y, z, x in np.ndindex(rotated.height, rotated.length, rotated.width):
        assert rotated.grid[y, z, x] == f"minecraft:block_{int(rotated.tints[y, z, x, 0])}"


def test_rotation_keeps_the_original_untouched():
    schematic = _random_schematic()
    before = schematic.grid.copy()
    rotate_schematic(schematic, 1)
    assert (schematic.grid == before).all()
