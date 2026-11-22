"""A malha das construções leva a cor de cada célula (``schematic.tints``), como as tampas dos cortes."""

import numpy as np

from src.world.schematic import Schematic
from src.world.structure_mesher import StructureMesher


def uv(name, face):
    return (0.0, 0.0, 1.0, 1.0)


def two_cubes(name="minecraft:white_concrete"):
    grid = np.full((1, 1, 2), name, dtype=object)
    return Schematic(2, 1, 1, grid, {}, "t")


def test_each_cube_takes_its_cell_colour():
    schematic = two_cubes()
    schematic.tints = np.zeros((1, 1, 2, 3), dtype=np.float32)
    schematic.tints[0, 0, 0] = (1.0, 0.0, 0.0)
    schematic.tints[0, 0, 1] = (0.0, 0.0, 1.0)
    vertices, _ = StructureMesher.build_arrays(schematic, uv, center=False)
    v = vertices.reshape(-1, 11)
    left = v[v[:, 0] < 0.5]                 # faces da célula x = 0 (o centro está em 0, o meio da junta em 0,5)
    right = v[v[:, 0] > 0.5]
    assert np.allclose(left[:, 8:11], (1.0, 0.0, 0.0))
    assert np.allclose(right[:, 8:11], (0.0, 0.0, 1.0))


def test_shaped_blocks_take_the_cell_colour_too():
    schematic = two_cubes("minecraft:oak_slab[type=bottom]")
    schematic.tints = np.full((1, 1, 2, 3), 0.5, dtype=np.float32)
    vertices, _ = StructureMesher.build_arrays(schematic, uv, center=False)
    assert np.allclose(vertices.reshape(-1, 11)[:, 8:11], 0.5)


def test_without_tints_the_colour_stays_white():
    vertices, _ = StructureMesher.build_arrays(two_cubes(), uv, center=False)
    assert np.allclose(vertices.reshape(-1, 11)[:, 8:11], 1.0)
