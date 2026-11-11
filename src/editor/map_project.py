"""Projeto de mapa: volume base + objetos voxel posicionados/rotacionados.

O mapa guarda o que é editado diretamente (``base``) e as construções colocadas
como entidades independentes. Assim é possível selecionar, mover, girar,
duplicar e excluir uma construção sem apagar o terreno/base embaixo dela.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from src.editor.voxel_object import EMPTY, VoxelObject

FORMAT = "isometricon-voxel-map"
VERSION = 1


def _position(value) -> tuple[int, int, int]:
    if len(tuple(value)) != 3:
        raise ValueError("A posição deve ter três coordenadas.")
    return tuple(int(component) for component in value)  # type: ignore[return-value]


@dataclass
class PlacedObject:
    """Uma construção no mapa, com posição e rotação em passos de 90°."""

    object: VoxelObject
    position: tuple[int, int, int] = (0, 0, 0)
    rotation: int = 0
    name: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.object, VoxelObject):
            raise TypeError("object deve ser um VoxelObject.")
        self.position = _position(self.position)
        self.rotation = int(self.rotation) % 4
        if not self.name:
            self.name = self.object.name or "objeto"

    def rendered_object(self) -> VoxelObject:
        return self.object.rotated_y(self.rotation)

    def bounds(self) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
        rendered = self.rendered_object()
        local = rendered.bounds()
        if local is None:
            return None
        low, high = local
        return (
            (self.position[0] + low[0], self.position[1] + low[1], self.position[2] + low[2]),
            (self.position[0] + high[0], self.position[1] + high[1], self.position[2] + high[2]),
        )

    def local_cell(self, x: int, y: int, z: int) -> tuple[int, int, int] | None:
        """Converte uma célula do mundo na célula local, se estiver dentro do objeto."""
        px, py, pz = self.position
        wx, wy, wz = int(x) - px, int(y) - py, int(z) - pz
        sx, sy, sz = self.object.size
        turns = self.rotation % 4
        if turns == 0:
            local = (wx, wy, wz)
        elif turns == 1:
            local = (sx - 1 - wz, wy, wx)
        elif turns == 2:
            local = (sx - 1 - wx, wy, sz - 1 - wz)
        else:
            local = (wz, wy, sz - 1 - wx)
        if not all(0 <= value < limit for value, limit in zip(local, (sx, sy, sz))):
            return None
        return local

    def occupies(self, x: int, y: int, z: int) -> bool:
        local = self.local_cell(x, y, z)
        return local is not None and self.object.get(*local) >= 0

    def copy(self) -> "PlacedObject":
        return PlacedObject(self.object.copy(), self.position, self.rotation, self.name, self.source)

    def to_dict(self) -> dict:
        return {
            "object": self.object.to_dict(),
            "position": list(self.position),
            "rotation": self.rotation,
            "name": self.name,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlacedObject":
        if not isinstance(data, dict) or "object" not in data:
            raise ValueError("Objeto colocado inválido.")
        return cls(VoxelObject.from_dict(data["object"]), _position(data.get("position", (0, 0, 0))),
                   int(data.get("rotation", 0)), str(data.get("name", "")), str(data.get("source", "")))


class MapProject:
    """Volume base editável + lista de objetos colocados."""

    def __init__(self, base: VoxelObject | None = None, objects: Iterable[PlacedObject] | None = None,
                 name: str = "mapa") -> None:
        self.base = base if base is not None else VoxelObject((16, 16, 16), name, "map")
        self.base.kind = "map"
        self.objects: list[PlacedObject] = [item.copy() if isinstance(item, PlacedObject) else item for item in (objects or [])]
        self.name = name or self.base.name

    @property
    def size(self) -> tuple[int, int, int]:
        return self.base.size

    def copy(self) -> "MapProject":
        return MapProject(self.base.copy(), [item.copy() for item in self.objects], self.name)

    def add_object(self, obj: VoxelObject, position: tuple[int, int, int], rotation: int = 0,
                   name: str = "") -> PlacedObject:
        placed = PlacedObject(obj.copy(), position, rotation, name or obj.name)
        self.objects.append(placed)
        return placed

    def remove_object(self, index: int) -> PlacedObject:
        return self.objects.pop(index)

    def object_at(self, x: int, y: int, z: int) -> int | None:
        for index in range(len(self.objects) - 1, -1, -1):
            if self.objects[index].occupies(x, y, z):
                return index
        return None

    def occupied(self, x: int, y: int, z: int) -> bool:
        if self.base.in_bounds(x, y, z) and self.base.get(x, y, z) >= 0:
            return True
        return self.object_at(x, y, z) is not None

    @property
    def voxel_count(self) -> int:
        return self.base.voxel_count + sum(item.object.voxel_count for item in self.objects)

    def resize(self, new_size: tuple[int, int, int]) -> "MapProject":
        self.base.resize(new_size)
        return self

    def to_dict(self) -> dict:
        return {
            "format": FORMAT,
            "version": VERSION,
            "name": self.name,
            "size": list(self.base.size),
            "base": self.base.to_dict(),
            "objects": [item.to_dict() for item in self.objects],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapProject":
        if not isinstance(data, dict):
            raise ValueError("Mapa inválido.")
        # Compatibilidade: um arquivo de objeto/mapa antigo vira o volume base.
        if data.get("format") != FORMAT:
            base = VoxelObject.from_dict(data)
            base.kind = "map"
            return cls(base, [], base.name)
        if int(data.get("version", -1)) != VERSION:
            raise ValueError("Versão de mapa não suportada.")
        base = VoxelObject.from_dict(data.get("base", {}))
        base.kind = "map"
        objects = [PlacedObject.from_dict(item) for item in data.get("objects", [])]
        return cls(base, objects, str(data.get("name", "mapa")))

    def save(self, path: str | os.PathLike) -> str:
        destination = os.fspath(path)
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=1)
        temporary = destination + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        return destination

    @classmethod
    def load(cls, path: str | os.PathLike) -> "MapProject":
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
