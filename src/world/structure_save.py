"""Salvar e recarregar as construções colocadas no terreno.

Cada construção vira um item ``{"entry", "name", "origin", "rotation", "open_doors"}``: a entrada diz de onde refazer
a grade (``src/world/structure_sources.py``), o giro e as portas abertas (células locais da metade de baixo, já na
grade girada) dizem como ela estava. O mundo do menu guarda a lista no save dele (chave ``structures``); o
``--terrain`` sem mundo guarda em ``saves/mundos/mundo_<seed>.json``, o mesmo arquivo dos objetos do Rafael, que é lido
e convertido se ainda estiver no formato antigo.
"""

from __future__ import annotations

import json
import os
from typing import List

import numpy as np

from src.core.game_storage import atomic_json
from src.core.paths import saves_path
from src.world.block_rotation import rotate_schematic
from src.world.doors import is_door, is_open_door, with_open

FORMAT = "isometricon-structures"
VERSION = 2
OLD_FORMAT = "isometricon-world-objects"


def seed_store_path(seed: int) -> str:
    return os.fspath(saves_path("mundos", f"mundo_{int(seed)}.json"))


def _lower_door_cells(grid: np.ndarray):
    """(x, y, z) locais da metade de baixo de cada porta da grade."""
    if not grid.size:
        return []
    doors = np.vectorize(is_door, otypes=[bool])(grid)
    return [(int(x), int(y), int(z)) for y, z, x in np.argwhere(doors)
            if not (y > 0 and doors[y - 1, z, x])]


def to_data(layer) -> List[dict]:
    """A lista para o save: o que for preciso para refazer cada construção como está."""
    items = []
    for placed in layer.structures:
        if placed.entry is None:
            continue   # sem origem conhecida não dá para refazer
        grid = placed.schematic.grid
        open_doors = [list(cell) for cell in _lower_door_cells(grid)
                      if is_open_door(grid[cell[1], cell[2], cell[0]])]
        items.append({"entry": placed.entry, "name": placed.name, "origin": [int(v) for v in placed.origin],
                      "rotation": int(placed.rotation), "open_doors": open_doors})
    for index, item in layer.unavailable:
        items.insert(index, item)
    return items


def _set_doors(grid: np.ndarray, open_cells) -> None:
    wanted = {tuple(int(v) for v in cell) for cell in open_cells}
    for x, y, z in _lower_door_cells(grid):
        opened = (x, y, z) in wanted
        for dy in (0, 1):
            if y + dy < grid.shape[0] and is_door(grid[y + dy, z, x]):
                grid[y + dy, z, x] = with_open(grid[y + dy, z, x], opened)


def restore(tool, items: List[dict]) -> List[str]:
    """Troca o que está no mundo pelas construções de ``items``; devolve avisos das que não deu para refazer.

    Recarregar não conta como mudança (``tool.on_change`` não é chamado): não há o que regravar.
    """
    on_change, tool.on_change = tool.on_change, (lambda: None)
    warnings = []
    try:
        tool.clear()
        for index, item in enumerate(items):
            name = "construção"
            try:
                entry = dict(item["entry"])
                name = str(item.get("name") or entry.get("name") or name)
                entry, schematic = tool.prepare_entry(entry)
                schematic = rotate_schematic(schematic, int(item.get("rotation", 0)))
                _set_doors(schematic.grid, item.get("open_doors", []))
                x, y, z = (int(v) for v in item["origin"])
                origin = (x, y, z)
                schematic.name = name
                mesh = tool._mesh_factory(schematic)
            except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
                warnings.append(f"{name}: não deu para carregar ({error}). A entrada foi preservada.")
                tool.layer.unavailable.append((index, item))
                continue
            placed = tool.layer.add(name, schematic, origin, mesh, rotation=int(item.get("rotation", 0)) % 4, entry=entry)
            tool.on_place(placed)
    finally:
        tool.on_change = on_change
    return warnings


def _from_old(data: dict) -> List[dict]:
    """Os objetos do formato antigo do Rafael como itens novos (o objeto vai inteiro na entrada)."""
    items = []
    for obj in data.get("objects", []):
        name = str(obj.get("name") or obj.get("object", {}).get("name") or "objeto")
        items.append({"entry": {"kind": "object", "object": obj["object"], "name": name}, "name": name,
                      "origin": [int(v) for v in obj.get("position", (0, 0, 0))],
                      "rotation": int(obj.get("rotation", 0)) % 4, "open_doors": []})
    return items


class SeedStore:
    """O arquivo de construções de uma seed, para o ``--terrain`` sem mundo do menu."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)

    def read(self) -> List[dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if data.get("format") == OLD_FORMAT:
                return _from_old(data)
            if data.get("format") == FORMAT and int(data.get("version", -1)) == VERSION:
                return list(data.get("structures", []))
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
        return []

    def write(self, items: List[dict], seed: int | None = None) -> None:
        payload = {"format": FORMAT, "version": VERSION, "structures": items}
        if seed is not None:
            payload["seed"] = int(seed)
        atomic_json(self.path, payload)
