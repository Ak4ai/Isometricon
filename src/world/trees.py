"""As árvores da taiga: pinheiros altos e, mais raras, sequoias gigantes, sempre no mesmo lugar para a mesma seed.

O mapa é dividido em células de ``CELL`` x ``CELL`` blocos; cada célula sorteia (pela seed) se tem árvore, de que tipo,
onde ela fica dentro da célula, a altura e a variação da copa. Cada chunk olha só as células que podem encostar nele
(com a margem da maior copa) e escreve só os próprios voxels: gerar um chunk sozinho ou junto dos vizinhos dá os mesmos
blocos. As árvores passam da camada de chunks do chão: na taiga cada coluna tem mais camadas (``column_layers``).

As duas formas têm o tronco nu embaixo e a copa só no alto, em andares irregulares (galhos curtos para lados sorteados,
largos embaixo e afinando até a ponta), em vez de um cone perfeito.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Tuple

import numpy as np

from src.world.block import FOLIAGE, LYING_LOGS, BlockType

if TYPE_CHECKING:
    from src.world.chunk import Chunk3D
    from src.world.terrain import TerrainGenerator

CELL = 11                # uma árvore no máximo por célula de 11 x 11 blocos
TREE_CHANCE = 0.62       # chance de uma célula ter árvore (vezes a densidade da vegetação)
SEQUOIA_CHANCE = 0.2     # das árvores, quantas são sequoias
PINE = 0
SEQUOIA = 1
PINE_HEIGHT = (14, 20)
SEQUOIA_HEIGHT = (26, 36)
MARGIN = 8               # o quanto a copa (ou a raiz) sai do tronco, no máximo, em x e z
ROOT_DEPTH = 3           # o tronco desce até 3 blocos abaixo da base (só no ar): não flutua em chão torto
MAX_TOP = SEQUOIA_HEIGHT[1] + 3   # o voxel mais alto acima da base, no pior caso

Tree = Tuple[int, int, int, int, int, int, int]   # x, y da base, z, tipo, altura, largura do tronco, variação


def _trunk_cells(width: int) -> List[Tuple[int, int]]:
    lo = -((width - 1) // 2)
    return [(dx, dz) for dx in range(lo, lo + width) for dz in range(lo, lo + width)]


def _trunk_center(width: int) -> float:
    return -((width - 1) // 2) + (width - 1) / 2.0


def _disc(voxels: Dict, rng: np.random.Generator, y: int, radius: float, center: float, rough: float = 0.7) -> None:
    """Uma camada de folhas em volta do tronco: um círculo de borda irregular (cada canto sorteia se entra)."""
    if radius <= 0.2:
        return
    reach = int(np.ceil(radius + 1))
    for dx in range(-reach, reach + 2):
        for dz in range(-reach, reach + 2):
            d = np.hypot(dx - center, dz - center)
            if d <= radius + rng.uniform(-rough, 0.35):
                voxels.setdefault((dx, y, dz), BlockType.SPRUCE_LEAVES)


def _blob(voxels: Dict, rng: np.random.Generator, x: float, y: int, z: float, radius: float) -> None:
    """Um tufo redondo de folhas na ponta de um galho."""
    r = int(np.ceil(radius))
    for dy in range(-1, 2):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if np.hypot(dx, dz) + abs(dy) * 1.3 <= radius + rng.uniform(-0.5, 0.3):
                    voxels.setdefault((int(round(x)) + dx, y + dy, int(round(z)) + dz), BlockType.SPRUCE_LEAVES)


def _branch(voxels: Dict, rng: np.random.Generator, y: int, length: float, center: float, log: BlockType):
    """Um galho deitado saindo reto para um dos quatro lados (sorteado), o tronco virado no eixo dele; devolve onde
    ele termina. Reto, e não na diagonal: na diagonal o galho vira degraus com os anéis de lado."""
    dx, dz = ((1, 0), (-1, 0), (0, 1), (0, -1))[int(rng.integers(0, 4))]
    lying = LYING_LOGS[log]["x" if dx else "z"]
    side = int(rng.integers(0, 2))                    # num tronco largo, sai de uma das colunas do meio
    x, z = int(np.floor(center)) + (side if not dx else 0), int(np.floor(center)) + (side if not dz else 0)
    if center == int(center):
        x, z = int(center), int(center)
    placed = 0
    while placed < int(round(length)):
        x, z = x + dx, z + dz
        if voxels.get((x, y, z)) in (BlockType.SPRUCE_LOG, BlockType.SEQUOIA_LOG):
            continue                                   # ainda dentro do tronco
        voxels[(x, y, z)] = lying
        placed += 1
    ex, ez = float(x), float(z)
    return ex, ez


def _drop_loose_leaves(voxels: Dict) -> None:
    """Tira as folhas que não encostam (pela face, de folha em folha) em nenhum tronco ou galho: nada flutua."""
    seen = {p for p, b in voxels.items() if b != BlockType.SPRUCE_LEAVES}
    frontier = list(seen)
    while frontier:
        x, y, z = frontier.pop()
        for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
            if n not in seen and voxels.get(n) == BlockType.SPRUCE_LEAVES:
                seen.add(n)
                frontier.append(n)
    for p in [p for p in voxels if p not in seen]:
        del voxels[p]


@lru_cache(maxsize=256)
def tree_shape(kind: int, height: int, width: int, variant: int) -> np.ndarray:
    """Os voxels ``[dx, dy, dz, bloco]`` (int16) de uma árvore, a partir da base do tronco (dy = 0 em cima do chão)."""
    rng = np.random.default_rng((kind, height, width, variant))
    log = BlockType.SEQUOIA_LOG if kind == SEQUOIA else BlockType.SPRUCE_LOG
    center = _trunk_center(width)
    voxels: Dict[Tuple[int, int, int], BlockType] = {}
    for dx, dz in _trunk_cells(width):                           # o tronco antes: os galhos saem da borda dele
        for y in range(height):
            voxels[(dx, y, dz)] = log

    if kind == PINE:
        base = int(round(height * 0.32))
        r_max = 3.4 + 0.9 * (width - 1)
        phase = int(rng.integers(0, 3))
        for y in range(height - 1, base - 1, -1):
            t = (y - base) / max(1, height - base)              # 0 no pé da copa, 1 na ponta
            radius = r_max * (1.0 - t) ** 0.85 + 0.6
            row = (y + phase) % 3
            if row == 0:                                        # um andar cheio, com galho quando é largo
                _disc(voxels, rng, y, radius, center)
                if radius >= 2.8:
                    _branch(voxels, rng, y, radius * 0.5, center, log)
            elif row == 1:
                _disc(voxels, rng, y, radius * 0.62, center, rough=0.5)
            else:                                               # entre andares, só um anel junto do tronco
                _disc(voxels, rng, y, 0.9 + 0.5 * (width - 1), center, rough=0.2)
        for y in range(height, height + 2):                     # a ponta
            _disc(voxels, rng, y, 0.6 if y == height else 0.2, center, rough=0.0)
        voxels.setdefault((0, height + 2, 0), BlockType.SPRUCE_LEAVES)
    else:
        base = int(round(height * 0.52))
        r_max = 3.6 + 0.7 * (width - 1)
        for y in range(height, base - 1, -1):
            t = (y - base) / max(1, height - base)
            # copa arredondada: afina na ponta e também um pouco no pé
            radius = r_max * (1.0 - t) ** 0.65 * min(1.0, 0.6 + 2.2 * t) + 0.5
            _disc(voxels, rng, y, radius * 0.55, center, rough=0.4)          # o miolo da copa
            if (y - base) % 3 == 0 and radius > 1.6:                          # galho com um tufo na ponta
                for _ in range(1 + int(radius > 3.0)):
                    ex, ez = _branch(voxels, rng, y, radius * 0.75, center, log)
                    _blob(voxels, rng, ex, y + 1, ez, 1.4 + 0.25 * radius)
        for y in range(height, height + 3):                     # a ponta, presa no tronco
            voxels.setdefault((0, y, 0), BlockType.SPRUCE_LEAVES)
        # alguns tocos de galho seco no tronco nu, e a base alargada em raízes
        for _ in range(int(rng.integers(1, 4))):
            _branch(voxels, rng, int(rng.integers(int(height * 0.3), base)), 1.5, center, log)
        cells = set(_trunk_cells(width))
        ring = {(dx + ox, dz + oz) for dx, dz in cells for ox, oz in ((1, 0), (-1, 0), (0, 1), (0, -1))} - cells
        for dx, dz in sorted(ring):
            top = int(rng.integers(-1, 3))                     # cada raiz sobe 0 a 2 blocos pelo tronco
            for y in range(-ROOT_DEPTH, top):
                voxels[(dx, y, dz)] = log

    for dx, dz in _trunk_cells(width):                           # o tronco por cima de tudo
        for y in range(-ROOT_DEPTH, height):
            voxels[(dx, y, dz)] = log
    _drop_loose_leaves(voxels)
    out = np.array([(dx, dy, dz, int(b)) for (dx, dy, dz), b in voxels.items()], dtype=np.int16)
    out.flags.writeable = False
    return out


def _trees_near(generator: "TerrainGenerator", x0: int, z0: int, x1: int, z1: int) -> List[Tree]:
    """As árvores cujas copas podem cair em [x0, x1) x [z0, z1)."""
    m = MARGIN
    gx = np.arange((x0 - m) // CELL, (x1 + m) // CELL + 1)
    gz = np.arange((z0 - m) // CELL, (z1 + m) // CELL + 1)
    gx, gz = np.meshgrid(gx, gz, indexing="ij")
    gx, gz = gx.ravel(), gz.ravel()
    rolls = [replace(generator, seed=generator.seed + k)._plant_roll(gx, gz) for k in (2, 3, 4, 5, 6, 7)]
    chance = TREE_CHANCE * generator.vegetation_density
    trees = []
    for i in np.nonzero(rolls[0] < chance)[0]:
        x = int(gx[i]) * CELL + int(rolls[1][i] * CELL)
        z = int(gz[i]) * CELL + int(rolls[2][i] * CELL)
        size = float(rolls[3][i])
        if rolls[4][i] < SEQUOIA_CHANCE:
            kind, (lo, hi) = SEQUOIA, SEQUOIA_HEIGHT
            height = lo + int(size * (hi - lo + 1))
            width = 4 if size > 0.5 else 2
        else:
            kind, (lo, hi) = PINE, PINE_HEIGHT
            height = lo + int(size * (hi - lo + 1))
            width = 2 if size > 0.7 else 1
        if width > 1:
            # o tronco grosso começa numa coordenada par: os quadrados 2 x 2 dele viram toras com a textura junta
            # (src/world/mesher.joined_logs)
            lo = -((width - 1) // 2)
            x -= (x + lo) % 2
            z -= (z + lo) % 2
        if not (x0 - m <= x < x1 + m and z0 - m <= z < z1 + m):
            continue
        ground = generator.get_height(x, z)
        if ground < generator.sea_level:
            continue                                  # embaixo d'água não nasce árvore
        trees.append((x, ground + 1, z, kind, height, width, int(rolls[5][i] * 64)))
    return trees


def stamp_trees(generator: "TerrainGenerator", chunks: Dict[Tuple[int, int, int], "Chunk3D"]) -> None:
    """Põe as árvores nos chunks dados. A folha só ocupa ar; o tronco ocupa ar ou folha (de outra árvore)."""
    from src.world.chunk import Chunk3D
    size = Chunk3D.SIZE
    if generator.vegetation_density <= 0:
        return
    foliage = np.array([int(b) for b in FOLIAGE])
    air = int(BlockType.AIR)
    logs = np.array([int(b) for b in LYING_LOGS] + [int(b) for d in LYING_LOGS.values() for b in d.values()])
    for (cx, cy, cz), chunk in chunks.items():
        x0, y0, z0 = cx * size, cy * size, cz * size
        for x, y, z, kind, height, width, variant in _trees_near(generator, x0, z0, x0 + size, z0 + size):
            if y + MAX_TOP < y0 or y - ROOT_DEPTH >= y0 + size:
                continue
            shape = tree_shape(kind, height, width, variant)
            lx = shape[:, 0].astype(np.int64) + (x - x0)
            ly = shape[:, 1].astype(np.int64) + (y - y0)
            lz = shape[:, 2].astype(np.int64) + (z - z0)
            inside = (lx >= 0) & (lx < size) & (ly >= 0) & (ly < size) & (lz >= 0) & (lz < size)
            if not inside.any():
                continue
            lx, ly, lz, block = lx[inside], ly[inside], lz[inside], shape[inside, 3].astype(np.uint8)
            current = chunk.blocks[lx, ly, lz]
            ok = (current == air) | (np.isin(block, logs) & np.isin(current, foliage))
            chunk.blocks[lx[ok], ly[ok], lz[ok]] = block[ok]

