"""Construções (schematics) colocadas no mundo, por cima do terreno.

Não alteram os chunks: a camada só responde "tem bloco sólido aqui?" para a colisão e o
raycast, por meio de ``wrap_lookup``, e guarda onde cada construção está. O desenho é feito
à parte (ver ``src/interactive/schematic_tool.py``).
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

from src.world.block import BlockType
from src.world.schematic import Schematic

BlockLookup = Callable[[int, int, int], BlockType]


@dataclass
class PlacedStructure:
    """Uma construção fixada no mundo; ``origin`` é a célula do canto mínimo (x, y, z)."""

    name: str
    schematic: Schematic
    origin: Tuple[int, int, int]
    mesh: object = None  # malha para desenhar (TexturedMesh), quando já existe
    _solid: np.ndarray = field(init=False, repr=False)

    revision: int = field(init=False, default=0)  # sobe quando um bloco muda (porta aberta ou fechada)

    def __post_init__(self) -> None:
        self._load_masks()

    def _load_masks(self) -> None:
        self._solid = self.schematic.solid_mask          # indexados [y, z, x]
        self._occupied = self.schematic.occupied_mask
        self._culls = self.schematic.full_cube_mask

    def refresh(self) -> None:
        """Relê as máscaras depois de a grade mudar; a colisão e os cômodos passam a ver o bloco novo."""
        self.schematic.invalidate_masks()
        self._load_masks()
        self.revision += 1

    def bounds(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Células (mínima, máxima) ocupadas pela caixa da construção, inclusive."""
        ox, oy, oz = self.origin
        s = self.schematic
        return (ox, oy, oz), (ox + s.width - 1, oy + s.height - 1, oz + s.length - 1)

    def is_solid_at(self, x: int, y: int, z: int) -> bool:
        ox, oy, oz = self.origin
        lx, ly, lz = x - ox, y - oy, z - oz
        s = self.schematic
        if 0 <= lx < s.width and 0 <= ly < s.height and 0 <= lz < s.length:
            return bool(self._solid[ly, lz, lx])
        return False


class StructureLayer:
    """Conjunto das construções colocadas; consultado pela colisão como se fossem terreno."""

    def __init__(self) -> None:
        self.structures: List[PlacedStructure] = []

    def __len__(self) -> int:
        return len(self.structures)

    def add(self, name: str, schematic: Schematic, origin: Tuple[int, int, int], mesh: object = None) -> PlacedStructure:
        placed = PlacedStructure(name, schematic, (int(origin[0]), int(origin[1]), int(origin[2])), mesh)
        self.structures.append(placed)
        return placed

    def remove_last(self) -> Optional[PlacedStructure]:
        return self.structures.pop() if self.structures else None

    def clear(self) -> List[PlacedStructure]:
        removed, self.structures = self.structures, []
        return removed

    def solid_at(self, x: int, y: int, z: int) -> bool:
        return any(s.is_solid_at(x, y, z) for s in self.structures)

    def wrap_lookup(self, base: BlockLookup) -> BlockLookup:
        """Devolve um ``block_lookup`` que enxerga o terreno e as construções (sólidas = pedra)."""

        def lookup(x: int, y: int, z: int) -> BlockType:
            if self.structures and self.solid_at(x, y, z):
                return BlockType.STONE
            return base(x, y, z)

        return lookup
