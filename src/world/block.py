# Tipos lógicos de voxel e cores base, independentes de materiais e texturas.

from enum import IntEnum
from operator import index
from types import MappingProxyType
from typing import Mapping

import numpy as np


class BlockType(IntEnum):
    # Identificadores estáveis armazenáveis em um único np.uint8.

    AIR = 0
    DIRT = 1
    GRASS = 2
    STONE = 3
    WATER = 4
    WOOD = 5
    LEAVES = 6


BLOCK_COLORS: Mapping[BlockType, tuple[float, float, float]] = MappingProxyType({
    BlockType.AIR: (0.0, 0.0, 0.0),
    BlockType.DIRT: (0.55, 0.35, 0.20),
    BlockType.GRASS: (0.30, 0.65, 0.20),
    BlockType.STONE: (0.50, 0.50, 0.50),
    BlockType.WATER: (0.20, 0.40, 0.85),
    BlockType.WOOD: (0.45, 0.28, 0.12),
    BlockType.LEAVES: (0.20, 0.50, 0.15),
})


def _as_block_type(value: BlockType | int) -> BlockType:
    # Valida o ID antes de converter para uint8, evitando overflow/truncamento.
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("O tipo de bloco deve ser um inteiro, não booleano.")
    return BlockType(index(value))


def get_block_color(block_type: BlockType | int) -> tuple[float, float, float]:
    # Retorna RGB em [0, 1] para os atributos de cor do pipeline atual.
    #
    # A cor de AIR é apenas um fallback; não representa opacidade ou solidez.
    # IDs desconhecidos geram ValueError; valores não inteiros geram TypeError.
    return BLOCK_COLORS[_as_block_type(block_type)]


_OPAQUE_BLOCKS = frozenset({
    BlockType.DIRT, BlockType.GRASS, BlockType.STONE, BlockType.WOOD,
})


def is_opaque(block_type: BlockType | int) -> bool:
    """Indica oclusão completa de faces, não solidez para colisão.

    AIR, WATER e LEAVES não ocluem. A política é lógica e independente
    do alfa da textura; não configura blending nem materiais na GPU.
    IDs e tipos inválidos seguem a validação de get_block_color.
    """
    return _as_block_type(block_type) in _OPAQUE_BLOCKS
