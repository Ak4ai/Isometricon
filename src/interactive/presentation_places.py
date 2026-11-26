"""Os lugares aonde a apresentação leva o personagem: construções de teste e uma caverna do terreno.

Alguns slides mostram a câmera dentro de um cômodo ou ao lado da vitrine de formas de bloco. O ``main.py`` põe a
construção num pedaço plano e seco do terreno perto do começo (``choose_site``), acha um ponto de pé dentro dela
(``find_floor_spot``) ou numa caverna já carregada (``find_cave_spot``) e leva o personagem até lá. Nada aqui usa
OpenGL nem o mundo de verdade: as funções recebem quem responde se uma célula é sólida, molhada ou qual a altura.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Optional, Sequence, Tuple

Cell = Tuple[int, int, int]
Spot = Tuple[float, float, float]
Solid = Callable[[int, int, int], bool]

CAVE = "caverna"
# o nome que aparece no cartão -> o que a apresentação abre (um .schem da pasta, a vitrine ou a caverna)
ENTRIES = {
    "sala-andar": {"kind": "schem", "name": "sala-andar"},
    "house-medieval": {"kind": "schem", "name": "house-medieval"},
    "formas": {"kind": "formas"},
}


def choose_site(height_at: Callable[[int, int], int], wet: Callable[[int, int], bool], home: Sequence[float],
                size: Tuple[int, int], taken: Iterable[Tuple[Cell, Cell]] = (), near: float = 20.0,
                far: float = 64.0, step: int = 4) -> Cell:
    """O canto mínimo (x, y, z) de uma construção de ``size`` (largura, comprimento) num chão plano e seco.

    Procura em volta de ``home``, entre ``near`` e ``far`` blocos, longe das caixas ``taken``; fica com o chão
    menos acidentado e, no empate, o mais perto. A base vai um bloco acima do ponto mais alto do recorte."""
    width, length = size
    hx, hz = int(math.floor(home[0])), int(math.floor(home[2]))
    taken = list(taken)
    best = None
    reach = int(far)
    for dz in range(-reach, reach + 1, step):
        for dx in range(-reach, reach + 1, step):
            distance = math.hypot(dx, dz)
            if distance < near or distance > far:
                continue
            x0, z0 = hx + dx - width // 2, hz + dz - length // 2
            if any(x0 - 3 <= b[1][0] and b[0][0] <= x0 + width + 3 and z0 - 3 <= b[1][2] and b[0][2] <= z0 + length + 3
                   for b in taken):
                continue
            samples = [(x0 + i * (width - 1) // 3, z0 + j * (length - 1) // 3) for i in range(4) for j in range(4)]
            if any(wet(x, z) for x, z in samples):
                continue
            heights = [height_at(x, z) for x, z in samples]
            score = (max(heights) - min(heights), distance)
            if best is None or score < best[0]:
                best = (score, (x0, max(heights) + 1, z0))
    if best is None:
        return (hx + int(near), height_at(hx + int(near), hz) + 1, hz)
    return best[1]


def find_floor_spot(solid: Solid, lo: Cell, hi: Cell, roofed: bool = True) -> Optional[Spot]:
    """Onde ficar de pé dentro da caixa ``lo``..``hi`` (inclusive): chão sólido, duas células de ar e, com
    ``roofed``, algo sólido acima dentro da caixa. O andar mais baixo; nele, o mais perto do meio da caixa."""
    cx, cz = (lo[0] + hi[0]) / 2.0, (lo[2] + hi[2]) / 2.0
    for y in range(lo[1] + 1, hi[1]):
        best = None
        for z in range(lo[2] + 1, hi[2]):
            for x in range(lo[0] + 1, hi[0]):
                if not solid(x, y - 1, z) or solid(x, y, z) or solid(x, y + 1, z):
                    continue
                if roofed and not any(solid(x, top, z) for top in range(y + 2, hi[1] + 1)):
                    continue
                d = (x + 0.5 - cx) ** 2 + (z + 0.5 - cz) ** 2
                if best is None or d < best[0]:
                    best = (d, (x + 0.5, float(y), z + 0.5))
        if best is not None:
            return best[1]
    return None


def find_cave_spot(solid: Solid, surface: Callable[[int, int], int], home: Sequence[float], radius: int = 40,
                   step: int = 2, min_air: int = 60) -> Optional[Spot]:
    """Um ponto de pé numa caverna perto de ``home``: ar com chão, coberto pelo terreno, num vão largo.

    Mede o vão contando o ar numa caixa 7 x 4 x 7 em volta; fica com o maior (``min_air`` no mínimo) e, no
    empate, o mais perto."""
    hx, hz = int(math.floor(home[0])), int(math.floor(home[2]))
    best = None
    for dz in range(-radius, radius + 1, step):
        for dx in range(-radius, radius + 1, step):
            x, z = hx + dx, hz + dz
            top = surface(x, z)
            for y in range(top - 4, top - 48, -1):
                if solid(x, y - 1, z) and not solid(x, y, z) and not solid(x, y + 1, z):
                    air = sum(1 for ay in range(y, y + 4) for az in range(z - 3, z + 4) for ax in range(x - 3, x + 4)
                              if not solid(ax, ay, az))
                    score = (air, -math.hypot(dx, dz))
                    if air >= min_air and (best is None or score > best[0]):
                        best = (score, (x + 0.5, float(y), z + 0.5))
                    break   # só o primeiro chão abaixo da superfície em cada coluna
    return None if best is None else best[1]
