"""A construção fixada tira o terreno da caixa dela; removida, o terreno volta."""

import numpy as np

from src.world import BlockType
from src.world.manager import WorldManager
from src.world.terrain import TerrainGenerator


def manager():
    world = WorldManager(TerrainGenerator(seed=350665, enable_caves=False), render_distance=1,
                         create_gl_meshes=False)
    world.load_initial_region(0.5, 0.5)
    return world


def solid_in(world, lo, hi):
    return sum(world.neighbor_at(x, y, z) is not BlockType.AIR
               for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1) for z in range(lo[2], hi[2] + 1))


def test_clearing_a_box_removes_the_terrain_inside_only():
    world = manager()
    lo, hi = (-3, 4, -3), (3, 12, 3)
    assert solid_in(world, lo, hi) > 0
    outside_before = solid_in(world, (5, 4, 5), (8, 12, 8))
    world.clear_box(lo, hi)
    assert solid_in(world, lo, hi) == 0
    assert solid_in(world, (5, 4, 5), (8, 12, 8)) == outside_before
    assert world.neighbor_at(0, 3, 0) is not BlockType.AIR      # abaixo da caixa fica


def test_regenerated_chunks_keep_the_cut():
    world = manager()
    lo, hi = (-3, 4, -3), (3, 12, 3)
    world.clear_box(lo, hi)
    fresh = world.generator.generate_region([(0, 0, 0), (-1, 0, -1)])
    world._apply_clearings(fresh)
    chunk = fresh[(0, 0, 0)]
    assert not np.any(chunk.blocks[0:4, 4:13, 0:4] != int(BlockType.AIR))


def test_restoring_brings_the_terrain_back_and_keeps_other_cuts():
    world = manager()
    first, second = ((-3, 4, -3), (3, 12, 3)), ((5, 4, 5), (8, 12, 8))
    before = solid_in(world, *first)
    world.clear_box(*first)
    world.clear_box(*second)
    world.restore_box(*first)
    assert solid_in(world, *first) == before
    assert solid_in(world, *second) == 0
    world.restore_box(*first)                                   # de novo: nada a fazer
    assert solid_in(world, *first) == before
