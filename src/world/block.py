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
    # Enfeites sem volume de cubo: desenhados com a forma do bloco (cruz, placa, haste), não barram ninguém
    SHORT_GRASS = 7
    POPPY = 8
    DANDELION = 9
    RED_MUSHROOM = 10
    BROWN_MUSHROOM = 11
    TORCH = 12
    # A escada de mão encosta na parede oposta ao lado para onde ela "olha" (como no Minecraft):
    # LADDER_NORTH olha para o norte (-z) e está presa no bloco do sul (+z).
    LADDER_NORTH = 13
    LADDER_SOUTH = 14
    LADDER_EAST = 15
    LADDER_WEST = 16
    FIRE = 17


BLOCK_COLORS: Mapping[BlockType, tuple[float, float, float]] = MappingProxyType({
    BlockType.AIR: (0.0, 0.0, 0.0),
    BlockType.DIRT: (0.55, 0.35, 0.20),
    BlockType.GRASS: (0.30, 0.65, 0.20),
    BlockType.STONE: (0.50, 0.50, 0.50),
    BlockType.WATER: (0.20, 0.40, 0.85),
    BlockType.WOOD: (0.45, 0.28, 0.12),
    BlockType.LEAVES: (0.20, 0.50, 0.15),
    BlockType.SHORT_GRASS: (0.38, 0.76, 0.24),
    BlockType.POPPY: (0.80, 0.15, 0.12),
    BlockType.DANDELION: (0.95, 0.85, 0.20),
    BlockType.RED_MUSHROOM: (0.80, 0.20, 0.18),
    BlockType.BROWN_MUSHROOM: (0.60, 0.45, 0.33),
    BlockType.TORCH: (1.0, 0.85, 0.45),
    BlockType.LADDER_NORTH: (0.60, 0.45, 0.25),
    BlockType.LADDER_SOUTH: (0.60, 0.45, 0.25),
    BlockType.LADDER_EAST: (0.60, 0.45, 0.25),
    BlockType.LADDER_WEST: (0.60, 0.45, 0.25),
    BlockType.FIRE: (1.0, 0.55, 0.10),
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


# Nome do bloco equivalente do Minecraft: a forma vem de ``block_shapes.shape_for`` (a mesma das construções)
SHAPED_BLOCK_NAMES: Mapping[BlockType, str] = MappingProxyType({
    BlockType.SHORT_GRASS: "short_grass",
    BlockType.POPPY: "poppy",
    BlockType.DANDELION: "dandelion",
    BlockType.RED_MUSHROOM: "red_mushroom",
    BlockType.BROWN_MUSHROOM: "brown_mushroom",
    BlockType.TORCH: "torch",
    BlockType.LADDER_NORTH: "ladder[facing=north]",
    BlockType.LADDER_SOUTH: "ladder[facing=south]",
    BlockType.LADDER_EAST: "ladder[facing=east]",
    BlockType.LADDER_WEST: "ladder[facing=west]",
    BlockType.FIRE: "fire",
})

# Para onde a escada de mão "olha"; a parede em que ela está presa fica do lado oposto
LADDER_FACING: Mapping[BlockType, str] = MappingProxyType({
    BlockType.LADDER_NORTH: "north",
    BlockType.LADDER_SOUTH: "south",
    BlockType.LADDER_EAST: "east",
    BlockType.LADDER_WEST: "west",
})
LADDER_BY_FACING: Mapping[str, BlockType] = MappingProxyType({v: k for k, v in LADDER_FACING.items()})

# Direção (x, z) de quem está na escada até a parede em que ela está presa
_LADDER_WALL = {"north": (0, 1), "south": (0, -1), "east": (-1, 0), "west": (1, 0)}

_PASSABLE_BLOCKS = frozenset({BlockType.AIR, BlockType.WATER, *SHAPED_BLOCK_NAMES})


def is_shaped(block_type: BlockType | int) -> bool:
    """O bloco não é um cubo: o malhador desenha a forma dele (cruz, tocha, escada de mão)."""
    return _as_block_type(block_type) in SHAPED_BLOCK_NAMES


def is_solid(block_type: BlockType | int) -> bool:
    """O personagem não atravessa o bloco (tudo menos ar, água e os enfeites)."""
    return _as_block_type(block_type) not in _PASSABLE_BLOCKS


def is_ladder(block_type: BlockType | int) -> bool:
    return _as_block_type(block_type) in LADDER_FACING


def ladder_wall_direction(block_type: BlockType | int) -> tuple[int, int]:
    """(dx, dz) da célula da escada até o bloco em que ela está presa."""
    return _LADDER_WALL[LADDER_FACING[_as_block_type(block_type)]]


# Por ID (uint8): é um cubo desenhado como cubo (tudo menos ar e os blocos com forma)
CUBE_LUT = np.zeros(256, dtype=bool)
CUBE_LUT[[int(b) for b in BlockType if b is not BlockType.AIR and b not in SHAPED_BLOCK_NAMES]] = True
# Por ID (uint8): é um bloco com forma (planta, tocha, escada de mão, fogo)
SHAPED_LUT = np.zeros(256, dtype=bool)
SHAPED_LUT[[int(b) for b in SHAPED_BLOCK_NAMES]] = True
