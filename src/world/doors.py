"""Portas das construções: achar a que está ao alcance do jogador e abri-la ou fechá-la (sem OpenGL).

Uma porta do Minecraft ocupa duas células (``half=lower`` embaixo, ``half=upper`` em cima) e guarda o estado em
``open``. Abrir troca ``open`` nas duas metades; a porta aberta não barra o personagem (ver
``block_shapes.collides``), então a colisão, os cômodos e a malha da construção precisam ser refeitos.
"""

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from src.world.block_shapes import parse_block

REACH = 1.8          # distância horizontal (blocos) do centro do jogador ao centro da porta
VERTICAL_REACH = 1   # a metade de baixo da porta pode estar até 1 bloco acima ou abaixo dos pés


def is_door(block_name: str) -> bool:
    base, _ = parse_block(block_name)
    return base.endswith("_door") and not base.endswith("trapdoor")


def is_open_door(block_name: str) -> bool:
    if not is_door(block_name):
        return False
    _, props = parse_block(block_name)
    return props.get("open", "false") == "true"


def with_open(block_name: str, opened: bool) -> str:
    """O mesmo bloco com ``open`` trocado, mantendo a ordem das outras propriedades."""
    value = "true" if opened else "false"
    head, bracket, rest = block_name.partition("[")
    if not bracket:
        return f"{block_name}[open={value}]"
    props = [p for p in rest.rstrip("]").split(",") if p]
    for i, prop in enumerate(props):
        if prop.split("=", 1)[0].strip() == "open":
            props[i] = f"open={value}"
            break
    else:
        props.append(f"open={value}")
    return f"{head}[{','.join(props)}]"


@dataclass(frozen=True)
class DoorRef:
    """Uma porta numa construção: a construção e a célula (local) da metade de baixo."""

    structure: object        # PlacedStructure
    local: Tuple[int, int, int]

    @property
    def world(self) -> Tuple[int, int, int]:
        ox, oy, oz = self.structure.origin
        x, y, z = self.local
        return ox + x, oy + y, oz + z

    @property
    def is_open(self) -> bool:
        x, y, z = self.local
        return is_open_door(self.structure.schematic.grid[y, z, x])

    def cells(self):
        """As células do mundo ocupadas pela porta (as duas metades, se a de cima existir)."""
        wx, wy, wz = self.world
        out = [(wx, wy, wz)]
        x, y, z = self.local
        grid = self.structure.schematic.grid
        if y + 1 < grid.shape[0] and is_door(grid[y + 1, z, x]):
            out.append((wx, wy + 1, wz))
        return out


def find_door(structures: Iterable, position, reach: float = REACH) -> Optional[DoorRef]:
    """A porta mais próxima ao alcance de quem está em ``position`` (pés), ou ``None``."""
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
                    name = schematic.grid[ly, lz, lx]
                    if not is_door(name):
                        continue
                    if parse_block(name)[1].get("half", "lower") == "upper":
                        continue
                    dx, dz = ox + lx + 0.5 - px, oz + lz + 0.5 - pz
                    distance = dx * dx + dz * dz
                    if distance <= best_distance:
                        best, best_distance = DoorRef(placed, (lx, ly, lz)), distance
    return best


def door_at(structures: Iterable, cell) -> Optional[DoorRef]:
    """A porta que ocupa a célula ``cell`` (mundo), pela metade de baixo, ou ``None`` (o bloco sob o cursor)."""
    x, y, z = (int(v) for v in cell)
    for placed in structures:
        schematic = placed.schematic
        ox, oy, oz = placed.origin
        lx, ly, lz = x - ox, y - oy, z - oz
        if not (0 <= lx < schematic.width and 0 <= ly < schematic.height and 0 <= lz < schematic.length):
            continue
        name = schematic.grid[ly, lz, lx]
        if not is_door(name):
            continue
        if parse_block(name)[1].get("half", "lower") == "upper" and ly > 0 and is_door(schematic.grid[ly - 1, lz, lx]):
            ly -= 1
        return DoorRef(placed, (lx, ly, lz))
    return None


def toggle_door(door: DoorRef) -> bool:
    """Abre a porta fechada ou fecha a aberta (as duas metades). Devolve o estado novo (True = aberta)."""
    opened = not door.is_open
    grid = door.structure.schematic.grid
    x, y, z = door.local
    grid[y, z, x] = with_open(grid[y, z, x], opened)
    if y + 1 < grid.shape[0] and is_door(grid[y + 1, z, x]):
        grid[y + 1, z, x] = with_open(grid[y + 1, z, x], opened)
    door.structure.refresh()
    return opened
