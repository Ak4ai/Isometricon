"""As cavernas escavadas em numpy dão exatamente os mesmos blocos da escavação bloco a bloco de antes."""

from math import cos, floor, sin

import numpy as np
import pytest

import src.world.caves as caves
from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.terrain import TerrainGenerator


class ScalarCarver(caves.CaveCarver):
    """A escavação original, bloco a bloco (a referência)."""

    def _build_organic_shell(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
    ) -> None:
        """Gera uma camada de pedra esculpida ao redor do túnel apenas no subterrâneo negativo (Y < 0)."""
        max_outer_r = radius + self.shell_thickness + 0.6
        max_outer_sq = max_outer_r * max_outer_r

        min_x = floor(px - max_outer_r)
        max_x = floor(px + max_outer_r)
        min_y = floor(py - max_outer_r)
        max_y = min(-1, floor(py + max_outer_r))  # Apenas Y < 0 (Y >= 0 já possui rocha sólida)
        min_z = floor(pz - max_outer_r)
        max_z = floor(pz + max_outer_r)

        for bx in range(min_x, max_x + 1):
            dx = bx - px
            for bz in range(min_z, max_z + 1):
                dz = bz - pz
                dxz_sq = dx * dx + dz * dz
                if dxz_sq > max_outer_sq:
                    continue

                # Rugosidade orgânica suave baseada na posição do bloco
                roughness = 0.45 * sin(bx * 1.5) * cos(bz * 1.5)
                effective_outer_r = radius + self.shell_thickness + roughness
                effective_outer_sq = effective_outer_r * effective_outer_r

                for by in range(min_y, max_y + 1):
                    dy = by - py
                    dist_sq = dxz_sq + dy * dy
                    if dist_sq > effective_outer_sq:
                        continue

                    cx = bx // Chunk3D.SIZE
                    cy = by // Chunk3D.SIZE
                    cz = bz // Chunk3D.SIZE
                    chunk_key = (cx, cy, cz)

                    # Se a coluna correspondente existe no mapa (cx, 0, cz), instancia chunk subterrâneo
                    if chunk_key not in chunks:
                        if (cx, 0, cz) in chunks:
                            # Inicia 100% como ar; somente a casca receberá pedra!
                            chunks[chunk_key] = Chunk3D(cx, cy, cz)
                        else:
                            continue

                    chunk = chunks[chunk_key]
                    lx = bx % Chunk3D.SIZE
                    ly = by % Chunk3D.SIZE
                    lz = bz % Chunk3D.SIZE

                    # Define como rocha para formar a casca
                    chunk.blocks[lx, ly, lz] = BlockType.STONE

    def _carve_tunnel_air(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None,
    ) -> None:
        """Escava o vazio (AIR) no centro do túnel/salão."""
        r_sq = radius * radius
        min_x = floor(px - radius)
        max_x = floor(px + radius)
        min_y = floor(py - radius)
        max_y = floor(py + radius)
        min_z = floor(pz - radius)
        max_z = floor(pz + radius)

        if not self.allow_sparse_depth and min_y < 1:
            min_y = 1

        has_generator = terrain_generator is not None and hasattr(terrain_generator, "get_height")
        sea = getattr(terrain_generator, "sea_level", 7) if has_generator else 7

        for bx in range(min_x, max_x + 1):
            dx = bx - px
            for bz in range(min_z, max_z + 1):
                dz = bz - pz
                dxz_sq = dx * dx + dz * dz
                if dxz_sq > r_sq:
                    continue

                limit_y = max_y
                if has_generator:
                    surf = terrain_generator.get_height(bx, bz)
                    if surf < sea and limit_y >= surf:
                        limit_y = surf - 1

                for by in range(min_y, limit_y + 1):
                    dy = by - py
                    if dxz_sq + dy * dy > r_sq:
                        continue

                    cx = bx // Chunk3D.SIZE
                    cy = by // Chunk3D.SIZE
                    cz = bz // Chunk3D.SIZE
                    chunk_key = (cx, cy, cz)

                    if chunk_key not in chunks:
                        continue

                    chunk = chunks[chunk_key]
                    lx = bx % Chunk3D.SIZE
                    ly = by % Chunk3D.SIZE
                    lz = bz % Chunk3D.SIZE

                    current = chunk.blocks[lx, ly, lz]
                    if current == BlockType.WATER:
                        continue

                    if current in (BlockType.STONE, BlockType.DIRT, BlockType.GRASS):
                        chunk.blocks[lx, ly, lz] = BlockType.AIR


@pytest.fixture
def scalar_caves(monkeypatch):
    monkeypatch.setattr(caves, "CaveCarver", ScalarCarver)


def region(seed, keys, **config):
    return TerrainGenerator(seed=seed, enable_caves=True, vegetation=True, **config).generate_region(keys)


KEYS = [(x, 0, z) for x in range(-2, 2) for z in range(-1, 2)]


@pytest.mark.parametrize("seed", [0, 3, 21, 4242, 777, 90210, -5])
def test_numpy_caves_match_the_block_by_block_carving(seed, monkeypatch):
    fast = region(seed, KEYS)
    monkeypatch.setattr(caves, "CaveCarver", ScalarCarver)
    slow = region(seed, KEYS)
    assert list(fast) == list(slow)                  # os mesmos chunks, criados na mesma ordem
    for key in slow:
        assert np.array_equal(fast[key].blocks, slow[key].blocks), (seed, key)


def test_without_sparse_depth_and_with_a_tall_world(monkeypatch):
    for config in (dict(allow_sparse_depth=False), dict(base_height=3, sea_level=6, amplitude=9.0)):
        fast = region(11, KEYS, **config)
        monkeypatch.setattr(caves, "CaveCarver", ScalarCarver)
        slow = region(11, KEYS, **config)
        monkeypatch.undo()
        assert list(fast) == list(slow)
        for key in slow:
            assert np.array_equal(fast[key].blocks, slow[key].blocks), (config, key)
