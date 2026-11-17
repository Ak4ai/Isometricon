"""O contorno de relevo vetorizado é idêntico ao caminho antigo, coluna por coluna."""

import numpy as np
import pytest

import src.interactive.grid_overlay as grid_overlay
from src.interactive.grid_overlay import CONTOUR_WIDTH, SURFACE_EPSILON
from src.world import BlockType, Chunk3D


def random_chunks(seed, keys):
    rng = np.random.default_rng(seed)
    blocks = np.array([BlockType.AIR, BlockType.STONE, BlockType.GRASS, BlockType.DIRT,
                       BlockType.WATER, BlockType.LEAVES], dtype=np.uint8)
    chunks = {}
    for key in keys:
        c = Chunk3D(*key)
        c.blocks[...] = rng.choice(blocks, size=c.blocks.shape, p=[0.7, 0.1, 0.08, 0.05, 0.04, 0.03])
        chunks[key] = c
    return chunks


def old_ribbons(chunks, width=CONTOUR_WIDTH, epsilon=SURFACE_EPSILON):
    triangles = []
    for x0, y, z0, x1, _, z1, ix, iz in grid_overlay._relief_segments_sparse(chunks, epsilon):
        a, b = (x0, y, z0), (x1, y, z1)
        a2, b2 = (x0 + ix * width, y, z0 + iz * width), (x1 + ix * width, y, z1 + iz * width)
        triangles += [a, b, b2, a, b2, a2]
    return np.asarray(triangles, dtype=np.float32).reshape(-1, 3)


@pytest.mark.parametrize('seed,keys', [
    (1, [(0, 0, 0)]),
    (2, [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0) for z in (-2, -1, 0)]),
    (3, [(0, 0, 0), (1, 0, 0), (0, 1, 1)]),            # buraco: coluna (1, 1) faltando
    (4, [(5, -1, -7), (6, -1, -7), (5, 0, -6)]),
])
def test_dense_relief_matches_column_loop(seed, keys):
    chunks = random_chunks(seed, keys)
    expected = grid_overlay._relief_segments_sparse(chunks, SURFACE_EPSILON)
    assert grid_overlay._relief_segments(chunks, SURFACE_EPSILON) == expected
    got = grid_overlay.build_relief_contour_ribbons(chunks)
    want = old_ribbons(chunks)
    assert got.dtype == np.float32 and np.array_equal(got, want)
    lines = grid_overlay.build_relief_contour_vertices(chunks)
    assert np.array_equal(lines, np.asarray([s[:6] for s in expected], dtype=np.float32).reshape(-1, 3))


def test_far_islands_use_the_sparse_path():
    chunks = random_chunks(5, [(0, 0, 0), (40, 0, 40)])
    assert grid_overlay._surface_height_grid(chunks) is None
    assert grid_overlay._relief_segments(chunks, SURFACE_EPSILON) == \
        grid_overlay._relief_segments_sparse(chunks, SURFACE_EPSILON)
