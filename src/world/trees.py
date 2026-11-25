"""Os pinheiros da taiga: a forma de cada árvore e onde elas nascem, sempre no mesmo lugar para a mesma seed.

O mapa é dividido em células de ``CELL`` x ``CELL`` blocos; cada célula sorteia (pela seed) se tem árvore, onde ela
fica dentro da célula e a altura do tronco. Cada chunk olha só as células que podem encostar nele (com a margem da
copa) e escreve só os próprios voxels: gerar um chunk sozinho ou junto dos vizinhos dá os mesmos blocos.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Tuple

import numpy as np

from src.world.block import FOLIAGE, BlockType

if TYPE_CHECKING:
    from src.world.chunk import Chunk3D
    from src.world.terrain import TerrainGenerator

CELL = 7                 # uma árvore no máximo por célula de 7 x 7 blocos
TREE_CHANCE = 0.55       # chance de uma célula ter árvore (vezes a densidade da vegetação)
MIN_HEIGHT, MAX_HEIGHT = 6, 10
CROWN_RADIUS = 3
LOWEST_LEAVES = 2        # a copa começa duas células acima do chão

Voxel = Tuple[int, int, int, BlockType]


@lru_cache(maxsize=16)
def spruce_shape(height: int) -> Tuple[Voxel, ...]:
    """Os voxels (dx, dy, dz, bloco) de um pinheiro com tronco de ``height`` blocos, a partir da base do tronco.

    A copa é um cone: uma folha no topo e, descendo, camadas que alternam raio 1 com um raio que cresce até 3
    (os cantos das camadas largas cortados, para ficar redonda)."""
    voxels: List[Voxel] = [(0, y, 0, BlockType.SPRUCE_LOG) for y in range(height)]
    voxels.append((0, height, 0, BlockType.SPRUCE_LEAVES))
    for k, y in enumerate(range(height - 1, LOWEST_LEAVES - 1, -1), start=1):
        radius = 1 if k % 2 else min(CROWN_RADIUS, 1 + k // 2)
        for dz in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if (dx, dz) == (0, 0) or (radius >= 2 and abs(dx) == abs(dz) == radius):
                    continue
                voxels.append((dx, y, dz, BlockType.SPRUCE_LEAVES))
    return tuple(voxels)


def _trees_near(generator: "TerrainGenerator", x0: int, z0: int, x1: int, z1: int) -> List[Tuple[int, int, int, int]]:
    """As árvores (x, y da base, z, altura) cujas copas podem cair em [x0, x1) x [z0, z1)."""
    m = CROWN_RADIUS
    gx = np.arange((x0 - m) // CELL, (x1 + m) // CELL + 1)
    gz = np.arange((z0 - m) // CELL, (z1 + m) // CELL + 1)
    gx, gz = np.meshgrid(gx, gz, indexing="ij")
    gx, gz = gx.ravel(), gz.ravel()
    rolls = [replace(generator, seed=generator.seed + k)._plant_roll(gx, gz) for k in (2, 3, 4, 5)]
    chance = TREE_CHANCE * generator.vegetation_density
    trees = []
    for i in np.nonzero(rolls[0] < chance)[0]:
        x = int(gx[i]) * CELL + int(rolls[1][i] * CELL)
        z = int(gz[i]) * CELL + int(rolls[2][i] * CELL)
        if not (x0 - m <= x < x1 + m and z0 - m <= z < z1 + m):
            continue
        ground = generator.get_height(x, z)
        if ground < generator.sea_level:
            continue                                  # embaixo d'água não nasce pinheiro
        height = MIN_HEIGHT + int(rolls[3][i] * (MAX_HEIGHT - MIN_HEIGHT + 1))
        trees.append((x, ground + 1, z, height))
    return trees


def stamp_spruces(generator: "TerrainGenerator", chunks: Dict[Tuple[int, int, int], "Chunk3D"]) -> None:
    """Põe os pinheiros nos chunks dados. A folha só ocupa ar; o tronco ocupa ar ou folha (de outra árvore)."""
    from src.world.chunk import Chunk3D
    size = Chunk3D.SIZE
    if generator.vegetation_density <= 0:
        return
    foliage = [int(b) for b in FOLIAGE]
    air = int(BlockType.AIR)
    for (cx, cy, cz), chunk in chunks.items():
        x0, y0, z0 = cx * size, cy * size, cz * size
        for x, y, z, height in _trees_near(generator, x0, z0, x0 + size, z0 + size):
            if y + height + 1 <= y0 or y >= y0 + size:
                continue
            for dx, dy, dz, block in spruce_shape(height):
                lx, ly, lz = x + dx - x0, y + dy - y0, z + dz - z0
                if not (0 <= lx < size and 0 <= ly < size and 0 <= lz < size):
                    continue
                current = chunk.blocks[lx, ly, lz]
                if current == air or (block == BlockType.SPRUCE_LOG and current in foliage):
                    chunk.blocks[lx, ly, lz] = int(block)
