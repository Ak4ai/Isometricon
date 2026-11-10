"""Descobre o espaço fechado em que o jogador está (cômodo, caverna) para revelá-lo.

Sem OpenGL. A cada recálculo:

1. copia para uma janela de 48x32x48 células o que é sólido (chunks do terreno e construções);
2. marca as células com "teto" (algo estrutural acima delas) e separa o ar coberto do ar aberto ao céu;
3. inunda o ar coberto a partir do jogador (o fluxo para onde o céu começa, que é o lado de fora);
4. decide se é um espaço fechado de verdade: um alpendre ou uma marquise abrem para o céu demais;
5. devolve uma máscara: 255 no espaço do jogador, 128 na casca de 1 bloco de sólido ao redor, 0 no resto.

O shader usa a máscara para escurecer o que está fora e remover o que tapa a vista do espaço.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from scipy import ndimage

from src.world.block import BlockType
from src.world.chunk import Chunk3D

WINDOW = (48, 32, 48)          # células em x, y, z
BELOW_PLAYER = 10              # células da janela abaixo do pé do jogador
MIN_SPACE_CELLS = 6            # um vão menor que isso não é cômodo
ENTER_EXPOSURE = 0.20          # fração do espaço aberta ao céu: abaixo disso passa a ser "dentro"
RETAIN_EXPOSURE = 0.35         # e só deixa de ser "dentro" acima disto (histerese)
INTERIOR = 255
SHELL = 128

# Blocos que não contam como teto (a copa de uma árvore não faz um cômodo)
_NOT_ROOF = (int(BlockType.LEAVES),)
_PASSABLE = (int(BlockType.AIR), int(BlockType.WATER))

_FACE_STRUCTURE = ndimage.generate_binary_structure(3, 1)  # vizinhança de 6 faces


@dataclass
class RoomMask:
    """Resultado de um cálculo: a máscara e o que se sabe sobre o espaço."""

    origin: Tuple[int, int, int]   # célula do mundo do canto (0, 0, 0) da janela
    data: np.ndarray               # uint8 [x, y, z]
    active: bool                   # o jogador está num espaço fechado
    cells: int                     # células de ar do espaço do jogador
    exposure: float                # fração delas aberta ao céu


def window_origin(position) -> Tuple[int, int, int]:
    """Canto mínimo da janela: o jogador fica no meio de x/z e com algumas células abaixo."""
    x, y, z = (int(np.floor(float(v))) for v in position)
    return x - WINDOW[0] // 2, y - BELOW_PLAYER, z - WINDOW[2] // 2


def extract_window(
    origin: Tuple[int, int, int],
    chunks: Dict[Tuple[int, int, int], Chunk3D],
    structures: Iterable = (),
) -> Tuple[np.ndarray, np.ndarray]:
    """Devolve (sólido, teto) da janela, ambos bool [x, y, z].

    Sólido é o que o personagem não atravessa (tudo menos ar e água); teto é o sólido que fecha
    um espaço por cima (sólido sem a folhagem). Abaixo de y = 0 é o chão do mundo, sólido.
    """
    ox, oy, oz = origin
    sx, sy, sz = WINDOW
    blocks = np.zeros(WINDOW, dtype=np.uint8)
    size = Chunk3D.SIZE
    for (cx, cy, cz), chunk in chunks.items():
        x0, y0, z0 = cx * size, cy * size, cz * size
        lo = (max(ox, x0), max(oy, y0), max(oz, z0))
        hi = (min(ox + sx, x0 + size), min(oy + sy, y0 + size), min(oz + sz, z0 + size))
        if any(h <= l for l, h in zip(lo, hi)):
            continue
        src = chunk.blocks[lo[0] - x0:hi[0] - x0, lo[1] - y0:hi[1] - y0, lo[2] - z0:hi[2] - z0]
        blocks[lo[0] - ox:hi[0] - ox, lo[1] - oy:hi[1] - oy, lo[2] - oz:hi[2] - oz] = src

    solid = ~np.isin(blocks, _PASSABLE)
    roof = solid & ~np.isin(blocks, _NOT_ROOF)

    floor_rows = max(0, min(sy, -oy))  # as camadas com y < 0
    if floor_rows:
        solid[:, :floor_rows, :] = True
        roof[:, :floor_rows, :] = True

    for placed in structures:
        (bx0, by0, bz0), (bx1, by1, bz1) = placed.bounds()
        lo = (max(ox, bx0), max(oy, by0), max(oz, bz0))
        hi = (min(ox + sx, bx1 + 1), min(oy + sy, by1 + 1), min(oz + sz, bz1 + 1))
        if any(h <= l for l, h in zip(lo, hi)):
            continue
        # a máscara da construção é [y, z, x]; a janela é [x, y, z]
        part = placed._solid[lo[1] - by0:hi[1] - by0, lo[2] - bz0:hi[2] - bz0, lo[0] - bx0:hi[0] - bx0]
        part = part.transpose(2, 0, 1)
        sel = (slice(lo[0] - ox, hi[0] - ox), slice(lo[1] - oy, hi[1] - oy), slice(lo[2] - oz, hi[2] - oz))
        solid[sel] |= part
        roof[sel] |= part
    return solid, roof


def _covered(roof: np.ndarray) -> np.ndarray:
    """True nas células com teto em algum ponto acima delas (dentro da janela)."""
    from_here_up = np.logical_or.accumulate(roof[:, ::-1, :], axis=1)[:, ::-1, :]
    covered = np.zeros_like(roof)
    covered[:, :-1, :] = from_here_up[:, 1:, :]
    return covered


def compute_room(
    solid: np.ndarray,
    roof: np.ndarray,
    origin: Tuple[int, int, int],
    position,
    was_active: bool = False,
) -> RoomMask:
    """Calcula a máscara do espaço em que o jogador (posição dos pés) está."""
    mask = np.zeros(WINDOW, dtype=np.uint8)
    outside = RoomMask(origin, mask, False, 0, 1.0)

    cell = [int(np.floor(float(v))) - o for v, o in zip(position, origin)]
    if not all(0 <= c < s for c, s in zip(cell, WINDOW)):
        return outside
    # o pé pode estar dentro do bloco do piso: sobe até achar ar
    while cell[1] < WINDOW[1] - 1 and solid[cell[0], cell[1], cell[2]]:
        cell[1] += 1
    seed = tuple(cell)
    if solid[seed]:
        return outside

    covered = _covered(roof)
    air = ~solid
    if not covered[seed]:
        return outside  # céu aberto sobre a cabeça: ao ar livre

    # o espaço é o ar com teto ligado ao jogador; o ar sem teto é o lado de fora e para a inundação
    labels, _ = ndimage.label(air & covered, structure=_FACE_STRUCTURE)
    space = labels == labels[seed]
    cells = int(space.sum())

    sky_air = air & ~covered
    leaks = space & ndimage.binary_dilation(sky_air, structure=_FACE_STRUCTURE)
    exposure = float(leaks.sum()) / max(cells, 1)

    limit = RETAIN_EXPOSURE if was_active else ENTER_EXPOSURE
    active = cells >= MIN_SPACE_CELLS and exposure < limit

    if active:
        shell = ndimage.binary_dilation(space, structure=_FACE_STRUCTURE) & solid
        mask[shell] = SHELL
        mask[space] = INTERIOR
    return RoomMask(origin, mask, active, cells, exposure)


class RoomRevealTracker:
    """Recalcula a máscara quando preciso (o jogador mudou de célula, ou o mundo mudou)."""

    MIN_INTERVAL = 0.25  # segundos entre recálculos do mesmo estado

    def __init__(self) -> None:
        self.mask: Optional[RoomMask] = None
        self.version = 0  # sobe a cada máscara nova (o renderizador reenvia à GPU)
        self._key = None
        self._age = 0.0

    @property
    def active(self) -> bool:
        return self.mask is not None and self.mask.active

    def reset(self) -> None:
        self.mask, self._key = None, None
        self.version += 1

    def update(self, dt: float, position, chunks, world_revision: int, structures=()) -> RoomMask:
        """Devolve a máscara atual, recalculando se o jogador ou o mundo mudou."""
        structures = list(structures)
        cell = tuple(int(np.floor(float(v))) for v in position)
        key = (cell, world_revision, tuple((id(s), s.origin) for s in structures))
        self._age += dt
        if self.mask is not None and key == self._key:
            return self.mask
        if self.mask is not None and self._age < self.MIN_INTERVAL and key[1:] == self._key[1:]:
            return self.mask  # só andou: espera o intervalo mínimo
        origin = window_origin(position)
        solid, roof = extract_window(origin, chunks, structures)
        self.mask = compute_room(solid, roof, origin, position, was_active=self.active)
        self._key, self._age = key, 0.0
        self.version += 1
        return self.mask
