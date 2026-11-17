"""A malha feita com o cubo 18³ em volta do chunk (``around``) é idêntica à feita bloco a bloco (``neighbor_at``)."""

import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMesher, blocks_around
from src.world.terrain import TerrainGenerator


def world(seed):
    rng = np.random.default_rng(seed)
    chunks = TerrainGenerator(seed=seed, enable_caves=True, vegetation=True).generate_region(
        [(x, 0, z) for x in range(-1, 2) for z in range(-1, 2)])
    kinds = [int(b) for b in BlockType]
    for chunk in chunks.values():            # blocos soltos de todo tipo, água nas bordas
        for _ in range(60):
            x, y, z = rng.integers(0, 16, size=3)
            chunk.blocks[x, y, z] = rng.choice(kinds)
        chunk.blocks[rng.integers(0, 16), 8:12, 15] = int(BlockType.WATER)
        chunk.blocks[0, 8:12, rng.integers(0, 16)] = int(BlockType.WATER)
    levels = {}
    for (cx, cy, cz), chunk in chunks.items():
        for x, y, z in np.argwhere(chunk.blocks == int(BlockType.WATER))[::3]:
            levels[(cx * 16 + int(x), cy * 16 + int(y), cz * 16 + int(z))] = float(rng.uniform(0.0, 1.0))
    return chunks, levels


def neighbor_at(chunks):
    def at(x, y, z):
        chunk = chunks.get((x // 16, y // 16, z // 16))
        return BlockType.AIR if chunk is None else chunk.get_block(x % 16, y % 16, z % 16)
    return at


def test_around_gives_the_same_mesh_as_neighbor_lookups():
    for seed in (1, 7, 4242, 99991):
        chunks, levels = world(seed)
        for ao in (True, False):
            mesher = ChunkMesher(ambient_occlusion=ao)
            for key in ((0, 0, 0), (-1, 0, 1), (1, 0, -1)):
                old = mesher.build(chunks[key], neighbor_at(chunks), levels)
                new = mesher.build(chunks[key], None, levels, around=blocks_around(chunks.get, key))
                assert np.array_equal(old.vertices, new.vertices), (seed, ao, key)
                assert np.array_equal(old.indices, new.indices), (seed, ao, key)


def test_blocks_around_takes_one_layer_from_each_neighbour():
    chunks = {}
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            chunk = Chunk3D(dx, 0, dz)
            chunk.blocks[:] = (dx + 1) * 3 + (dz + 1) + 1
            chunks[(dx, 0, dz)] = chunk
    cube = blocks_around(chunks.get, (0, 0, 0))
    assert cube[1, 5, 1] == 5 and cube[0, 5, 0] == 1 and cube[17, 5, 17] == 9 and cube[0, 5, 9] == 2
    assert (cube[:, 0, :] == 0).all() and (cube[:, 17, :] == 0).all()     # sem chunk em cima nem embaixo: ar
