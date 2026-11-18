"""Baús das construções: achar o que está ao alcance do jogador (sem OpenGL).

Os baús vêm do ``.schem`` como blocos ``minecraft:chest[...]``, ``trapped_chest`` ou ``ender_chest``. Abrir um baú não
muda a construção (ainda não há inventário): ``ChestRef`` só diz qual baú é, para a interface saber qual está aberto.
"""

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from src.world.block_shapes import parse_block

REACH = 1.8           # distância horizontal (blocos) do centro do jogador ao centro do baú
VERTICAL_REACH = 1    # o baú pode estar até 1 bloco acima ou abaixo dos pés
CHEST_BLOCKS = ("chest", "trapped_chest", "ender_chest")


def is_chest(block_name: str) -> bool:
    base, _ = parse_block(block_name)
    return base in CHEST_BLOCKS or base.endswith("_copper_chest") or base == "copper_chest"


@dataclass(frozen=True)
class ChestRef:
    """Um baú numa construção: a construção e a célula (local) dele."""

    structure: object        # PlacedStructure
    local: Tuple[int, int, int]

    @property
    def world(self) -> Tuple[int, int, int]:
        ox, oy, oz = self.structure.origin
        x, y, z = self.local
        return ox + x, oy + y, oz + z

    @property
    def name(self) -> str:
        x, y, z = self.local
        return str(self.structure.schematic.grid[y, z, x])

    @property
    def kind(self) -> str:
        return parse_block(self.name)[0]


def find_chest(structures: Iterable, position, reach: float = REACH) -> Optional[ChestRef]:
    """O baú mais próximo ao alcance de quem está em ``position`` (pés), ou ``None``."""
    px, py, pz = (float(v) for v in position)
    foot = int(py // 1)
    best, best_distance = None, reach * reach
    for placed in structures:
        schematic = placed.schematic
        ox, oy, oz = placed.origin
        x0, x1 = int(px - reach) - ox, int(px + reach) + 1 - ox
        z0, z1 = int(pz - reach) - oz, int(pz + reach) + 1 - oz
        for ly in range(foot - VERTICAL_REACH - oy, foot + VERTICAL_REACH + 1 - oy):
            if not 0 <= ly < schematic.height:
                continue
            for lz in range(max(z0, 0), min(z1, schematic.length)):
                for lx in range(max(x0, 0), min(x1, schematic.width)):
                    if not is_chest(schematic.grid[ly, lz, lx]):
                        continue
                    dx, dz = ox + lx + 0.5 - px, oz + lz + 0.5 - pz
                    distance = dx * dx + dz * dz
                    if distance <= best_distance:
                        best, best_distance = ChestRef(placed, (lx, ly, lz)), distance
    return best


def distance_to(ref, position) -> float:
    """Distância horizontal (blocos) de ``position`` ao centro da célula de ``ref.world`` (baú ou porta)."""
    wx, _, wz = ref.world
    return float(((wx + 0.5 - float(position[0])) ** 2 + (wz + 0.5 - float(position[2])) ** 2) ** 0.5)
