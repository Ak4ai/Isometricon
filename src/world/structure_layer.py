"""Construções (schematics) colocadas no mundo, por cima do terreno.

Não alteram os chunks: a camada só responde "tem bloco sólido aqui?" para a colisão e o
raycast, por meio de ``wrap_lookup``, e guarda onde cada construção está. O desenho é feito
à parte (ver ``src/interactive/schematic_tool.py``).
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

from src.world.block import LADDER_BY_FACING, BlockType
from src.world.block_shapes import parse_block
from src.world.schematic import Schematic

BlockLookup = Callable[[int, int, int], BlockType]


@dataclass
class PlacedStructure:
    """Uma construção fixada no mundo; ``origin`` é a célula do canto mínimo (x, y, z)."""

    name: str
    schematic: Schematic
    origin: Tuple[int, int, int]
    mesh: object = None  # malha para desenhar (TexturedMesh), quando já existe
    rotation: int = 0    # voltas de 90° já aplicadas à grade (ver ``src/world/block_rotation.py``)
    entry: Optional[dict] = None  # de onde veio (``src/world/structure_sources.py``), para salvar e refazer
    _solid: np.ndarray = field(init=False, repr=False)

    revision: int = field(init=False, default=0)  # sobe quando um bloco muda (porta aberta ou fechada)

    def __post_init__(self) -> None:
        self._load_masks()

    def _load_masks(self) -> None:
        self._solid = self.schematic.solid_mask          # indexados [y, z, x]
        self._occupied = self.schematic.occupied_mask
        self._culls = self.schematic.full_cube_mask
        self._ladders = self._find_ladders()

    def _find_ladders(self) -> dict:
        """Células locais (x, y, z) das escadas de mão, com o BlockType da escada (pela direção dela)."""
        ladders = {}
        grid = self.schematic.grid
        names = {}
        for y, z, x in np.argwhere(self._occupied & ~self._solid):
            name = grid[y, z, x]
            if name not in names:
                base, props = parse_block(str(name))
                names[name] = LADDER_BY_FACING.get(props.get("facing", "north")) if base == "ladder" else None
            if names[name] is not None:
                ladders[(int(x), int(y), int(z))] = names[name]
        return ladders

    def ladder_at(self, x: int, y: int, z: int) -> Optional[BlockType]:
        """A escada de mão na célula do mundo, ou ``None``."""
        if not self._ladders:
            return None
        ox, oy, oz = self.origin
        return self._ladders.get((x - ox, y - oy, z - oz))

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

    def occupies(self, x: int, y: int, z: int) -> bool:
        """Se a célula do mundo tem um bloco desta construção (sólido ou não: porta, planta, escada de mão)."""
        ox, oy, oz = self.origin
        lx, ly, lz = x - ox, y - oy, z - oz
        s = self.schematic
        if 0 <= lx < s.width and 0 <= ly < s.height and 0 <= lz < s.length:
            return bool(self._occupied[ly, lz, lx])
        return False

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

    def add(self, name: str, schematic: Schematic, origin: Tuple[int, int, int], mesh: object = None, *,
            rotation: int = 0, entry: Optional[dict] = None) -> PlacedStructure:
        placed = PlacedStructure(name, schematic, (int(origin[0]), int(origin[1]), int(origin[2])), mesh,
                                 int(rotation) % 4, entry)
        self.structures.append(placed)
        return placed

    def remove(self, placed: PlacedStructure) -> bool:
        """Tira essa construção (pela identidade); False se ela não está na camada."""
        for index, item in enumerate(self.structures):
            if item is placed:
                del self.structures[index]
                return True
        return False

    def structure_at(self, x: int, y: int, z: int) -> Optional[PlacedStructure]:
        """A construção com um bloco nessa célula; a colocada por último ganha."""
        for placed in reversed(self.structures):
            if placed.occupies(int(x), int(y), int(z)):
                return placed
        return None

    def remove_last(self) -> Optional[PlacedStructure]:
        return self.structures.pop() if self.structures else None

    def clear(self) -> List[PlacedStructure]:
        removed, self.structures = self.structures, []
        return removed

    def solid_at(self, x: int, y: int, z: int) -> bool:
        return any(s.is_solid_at(x, y, z) for s in self.structures)

    def wrap_lookup(self, base: BlockLookup) -> BlockLookup:
        """Devolve um ``block_lookup`` que enxerga o terreno e as construções (sólidas = pedra; as escadas de mão
        das construções voltam como a escada do terreno com a mesma direção, para o personagem subir nelas)."""

        def lookup(x: int, y: int, z: int) -> BlockType:
            if self.structures:
                if self.solid_at(x, y, z):
                    return BlockType.STONE
                for placed in self.structures:
                    ladder = placed.ladder_at(x, y, z)
                    if ladder is not None:
                        return ladder
            return base(x, y, z)

        return lookup
