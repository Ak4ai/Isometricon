"""O relevo calculado em numpy (``heights`` e ``populate_chunk``) é idêntico à conta coluna a coluna de antes."""

from math import floor

import numpy as np
import pytest

from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.terrain import TerrainGenerator, _fade, _lattice

CONFIGS = [
    dict(seed=0), dict(seed=4242), dict(seed=-77, octaves=5, persistence=0.7, lacunarity=2.5),
    dict(seed=123456789, amplitude=11.0, frequency=1 / 9, base_height=20, sea_level=18, dirt_depth=0),
    dict(seed=31, amplitude=0.0), dict(seed=8, frequency=0.37, octaves=1),
]


def scalar_height(g, x, z):
    """A conta original de ``get_height``, um ponto por vez."""
    total, weight_sum, weight, frequency = 0.0, 0.0, 1.0, g.frequency
    for _ in range(g.octaves):
        px, pz = x * frequency, z * frequency
        ix, iz = floor(px), floor(pz)
        u, v = _fade(px - ix), _fade(pz - iz)
        a, b = _lattice(g.seed, ix, iz), _lattice(g.seed, ix + 1, iz)
        c, d = _lattice(g.seed, ix, iz + 1), _lattice(g.seed, ix + 1, iz + 1)
        near, far = a + u * (b - a), c + u * (d - c)
        total += weight * (near + v * (far - near))
        weight_sum += weight
        weight *= g.persistence
        frequency *= g.lacunarity
    return g.base_height + floor(g.amplitude * max(-1.0, min(1.0, total / weight_sum)))


def scalar_chunk(g, chunk):
    """O ``populate_chunk`` original, coluna a coluna."""
    for z in range(chunk.SIZE):
        for x in range(chunk.SIZE):
            world_x, origin_y, world_z = chunk.local_to_world(x, 0, z)
            surface = scalar_height(g, world_x, world_z)
            column = chunk.blocks[x, :, z]
            column[:] = BlockType.AIR

            def end(world_y):
                return max(0, min(chunk.SIZE, world_y - origin_y + 1))

            column[:end(surface)] = BlockType.STONE
            column[end(surface - g.dirt_depth - 1):end(surface)] = BlockType.DIRT
            if origin_y <= surface < origin_y + chunk.SIZE:
                column[surface - origin_y] = BlockType.DIRT if surface < g.sea_level else BlockType.GRASS
            column[end(surface):end(g.sea_level)] = BlockType.WATER


@pytest.mark.parametrize("config", CONFIGS)
def test_heights_match_the_scalar_formula(config):
    g = TerrainGenerator(**config)
    rng = np.random.default_rng(1)
    xs = rng.integers(-5000, 5000, size=3000)
    zs = rng.integers(-5000, 5000, size=3000)
    fast = g.heights(xs, zs)
    assert [int(h) for h in fast] == [scalar_height(g, int(x), int(z)) for x, z in zip(xs, zs)]
    assert [g.get_height(int(x), int(z)) for x, z in zip(xs[:300], zs[:300])] == [int(h) for h in fast[:300]]


@pytest.mark.parametrize("config", CONFIGS)
def test_chunks_match_the_column_by_column_fill(config):
    g = TerrainGenerator(**config)
    for key in ((0, 0, 0), (-3, 0, 5), (7, -1, -2), (2, 1, 2), (-40, 0, -41)):
        fast, slow = Chunk3D(*key), Chunk3D(*key)
        g.populate_chunk(fast)
        scalar_chunk(g, slow)
        assert np.array_equal(fast.blocks, slow.blocks), key
