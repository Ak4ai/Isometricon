"""Os objetos voxel do editor vistos como construções, para a revelação de cômodo do jogo (sem OpenGL).

O rastreador de cômodos (``src/world/room_reveal.py``) lê "construções" (``PlacedStructure``): uma grade de nomes de
bloco por cima do terreno. Um objeto do editor é uma grade de índices de material (cor mais textura). ``object_structure``
traduz de um para o outro, só para esse cálculo: cada voxel vira um bloco com o nome da textura dele
(``minecraft:white_concrete``) e a cor vai em ``schematic.tints`` (as tampas dos cortes leem). O desenho dos objetos
continua sendo o do editor; as construções criadas aqui nunca são desenhadas nem usadas na colisão.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import numpy as np

from src.editor.voxel_object import EMPTY, VoxelObject
from src.world.schematic import Schematic
from src.world.structure_layer import PlacedStructure

AIR = "minecraft:air"


def object_schematic(obj: VoxelObject, name: str = "objeto") -> Schematic:
    """O objeto como ``Schematic``: cada voxel vira o bloco com o nome da textura dele e a cor vai em ``tints``."""
    sx, sy, sz = obj.size
    grid = np.full((sy, sz, sx), AIR, dtype=object)
    tints = np.ones((sy, sz, sx, 3), dtype=np.float32)
    lights = np.zeros((sy, sz, sx), dtype=np.uint8)
    cells = np.argwhere(obj.blocks != EMPTY)            # (n, 3): x, y, z
    if len(cells):
        names = np.array([f"minecraft:{material.texture}" for material in obj.materials], dtype=object)
        colours = np.array([[c / 255.0 for c in material.color] for material in obj.materials], dtype=np.float32)
        index = obj.blocks[cells[:, 0], cells[:, 1], cells[:, 2]].astype(np.int64)
        x, y, z = cells[:, 0], cells[:, 1], cells[:, 2]
        grid[y, z, x] = names[index]
        tints[y, z, x] = colours[index]
        lights[y, z, x] = np.array([material.light for material in obj.materials], dtype=np.uint8)[index]
    schematic = Schematic(sx, sy, sz, grid, {}, name)
    schematic.tints = tints
    schematic.lights = lights
    return schematic


def object_structure(obj: VoxelObject, origin: Tuple[int, int, int], name: str = "objeto") -> PlacedStructure:
    """O objeto (já girado) na posição ``origin`` como uma construção com as mesmas células ocupadas."""
    return PlacedStructure(name, object_schematic(obj, name), (int(origin[0]), int(origin[1]), int(origin[2])))


class ObjectStructureCache:
    """Guarda as construções dos objetos colocados e só refaz a de um objeto que mudou de lugar ou de giro.

    Devolve sempre os mesmos objetos enquanto nada muda: o rastreador de cômodos reconhece a construção por identidade
    e só recalcula o cômodo quando ela muda.
    """

    def __init__(self) -> None:
        self._entries: Dict[int, Tuple[tuple, PlacedStructure]] = {}

    def structures(self, placed_objects: Iterable) -> List[PlacedStructure]:
        out: List[PlacedStructure] = []
        live = set()
        for placed in placed_objects:
            key = (tuple(placed.position), int(placed.rotation), id(placed.object))
            entry = self._entries.get(id(placed))
            if entry is None or entry[0] != key:
                entry = (key, object_structure(placed.rendered_object(), placed.position, placed.name))
                self._entries[id(placed)] = entry
            live.add(id(placed))
            out.append(entry[1])
        for stale in set(self._entries) - live:
            del self._entries[stale]
        return out

    def clear(self) -> None:
        self._entries.clear()
