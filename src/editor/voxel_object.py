"""Modelo de dados de um objeto/mapa voxel.

O editor não altera o formato de ``Chunk3D``: um objeto é uma grade própria
(``blocks``) cujo valor é um índice na paleta de materiais (``-1`` = vazio).
Cada material combina uma cor RGB com o nome de um tile de textura. A cena
resultante é renderizada como uma malha comum, com a mesma iluminação e o
mesmo shader do terreno.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

FORMAT = "isometricon-voxel-object"
VERSION = 1
MAX_DIM = 64
MAX_MATERIALS = 512
EMPTY = -1


def _dimension(value: int, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} deve ser inteiro.")
    value = int(value)
    if not 1 <= value <= MAX_DIM:
        raise ValueError(f"{name} deve estar entre 1 e {MAX_DIM}.")
    return value


def _colour(value: Sequence[int]) -> tuple[int, int, int]:
    values = tuple(int(component) for component in value)
    if len(values) != 3 or any(component < 0 or component > 255 for component in values):
        raise ValueError("A cor deve ter três componentes entre 0 e 255.")
    return values  # type: ignore[return-value]


@dataclass(frozen=True)
class VoxelMaterial:
    """Cor e textura de um voxel. ``texture`` é o nome do tile no atlas."""

    color: tuple[int, int, int]
    texture: str = "white_concrete"

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", _colour(self.color))
        texture = str(self.texture).strip()
        if not texture:
            texture = "white_concrete"
        object.__setattr__(self, "texture", texture)

    def to_dict(self) -> dict:
        return {"color": list(self.color), "texture": self.texture}

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelMaterial":
        if not isinstance(data, dict):
            raise ValueError("Material inválido.")
        return cls(tuple(data.get("color", (255, 255, 255))), str(data.get("texture", "white_concrete")))


class VoxelObject:
    """Grade tridimensional de voxels com paleta de materiais e serialização."""

    def __init__(
        self,
        size: tuple[int, int, int] = (16, 16, 16),
        name: str = "objeto",
        kind: str = "object",
        materials: Iterable[VoxelMaterial] | None = None,
        blocks: np.ndarray | None = None,
    ) -> None:
        if len(tuple(size)) != 3:
            raise ValueError("size deve ter três dimensões.")
        self.size = tuple(_dimension(value, "size") for value in size)  # type: ignore[assignment]
        self.name = str(name)
        self.kind = str(kind)
        self.blocks = np.full(self.size, EMPTY, dtype=np.int16)
        self.materials: list[VoxelMaterial] = []
        self._material_lookup: dict[tuple[tuple[int, int, int], str], int] = {}
        if materials is not None:
            for material in materials:
                self.add_material(material)
        if blocks is not None:
            data = np.asarray(blocks)
            if data.shape != self.size:
                raise ValueError(f"blocks deve ter shape {self.size}.")
            if not np.issubdtype(data.dtype, np.integer):
                raise TypeError("blocks deve ter dtype inteiro.")
            if np.any(data < EMPTY) or np.any(data >= len(self.materials)):
                raise ValueError("blocks contém índices de material inválidos.")
            self.blocks = np.array(data, dtype=np.int16, copy=True)

    # ------------------------------------------------------------------
    # Dimensões e paleta
    # ------------------------------------------------------------------
    def add_material(self, material: VoxelMaterial | tuple[int, int, int], texture: str | None = None) -> int:
        """Acrescenta (ou reutiliza) um material e devolve seu índice."""
        if not isinstance(material, VoxelMaterial):
            material = VoxelMaterial(material, texture or "white_concrete")
        key = (material.color, material.texture)
        if key in self._material_lookup:
            return self._material_lookup[key]
        if len(self.materials) >= MAX_MATERIALS:
            raise ValueError(f"Um objeto aceita no máximo {MAX_MATERIALS} materiais.")
        index = len(self.materials)
        self.materials.append(material)
        self._material_lookup[key] = index
        return index

    def material_index(self, color: Sequence[int], texture: str) -> int:
        """Índice do material (cor, textura), criando-o se necessário."""
        return self.add_material(VoxelMaterial(_colour(color), texture))

    def material(self, index: int) -> VoxelMaterial:
        if not 0 <= int(index) < len(self.materials):
            raise IndexError("Índice de material fora da paleta.")
        return self.materials[int(index)]

    # ------------------------------------------------------------------
    # Acesso aos voxels
    # ------------------------------------------------------------------
    def _check(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        coordinates = (int(x), int(y), int(z))
        for value, limit in zip(coordinates, self.size):
            if not 0 <= value < limit:
                raise IndexError(f"Coordenada fora do objeto: {coordinates}.")
        return coordinates

    def in_bounds(self, x: int, y: int, z: int) -> bool:
        return all(0 <= int(value) < limit for value, limit in zip((x, y, z), self.size))

    def get(self, x: int, y: int, z: int) -> int:
        return int(self.blocks[self._check(x, y, z)])

    def set(self, x: int, y: int, z: int, material_index: int) -> None:
        coordinates = self._check(x, y, z)
        material_index = int(material_index)
        if material_index != EMPTY and not 0 <= material_index < len(self.materials):
            raise IndexError("Índice de material fora da paleta.")
        self.blocks[coordinates] = material_index

    def clear(self, x: int, y: int, z: int) -> None:
        self.set(x, y, z, EMPTY)

    def is_empty(self) -> bool:
        return not bool(np.any(self.blocks != EMPTY))

    @property
    def voxel_count(self) -> int:
        return int(np.count_nonzero(self.blocks != EMPTY))

    def bounds(self) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
        """Menor e maior canto ocupado, em coordenadas de voxel (inclusivo)."""
        occupied = np.argwhere(self.blocks != EMPTY)
        if not len(occupied):
            return None
        low = tuple(int(value) for value in occupied.min(axis=0))
        high = tuple(int(value) for value in occupied.max(axis=0))
        return low, high  # type: ignore[return-value]

    def copy(self) -> "VoxelObject":
        clone = VoxelObject(self.size, self.name, self.kind, materials=self.materials)
        clone.blocks = self.blocks.copy()
        clone._material_lookup = dict(self._material_lookup)
        return clone

    # ------------------------------------------------------------------
    # Redimensionamento, rotação e colagem
    # ------------------------------------------------------------------
    def resize(self, new_size: tuple[int, int, int]) -> "VoxelObject":
        """Redimensiona preservando a região de interseção."""
        size = tuple(_dimension(value, "size") for value in new_size)  # type: ignore[assignment]
        blocks = np.full(size, EMPTY, dtype=np.int16)
        common = tuple(min(old, new) for old, new in zip(self.size, size))
        blocks[: common[0], : common[1], : common[2]] = self.blocks[
            : common[0], : common[1], : common[2]
        ]
        self.size = size
        self.blocks = blocks
        return self

    def rotated_y(self, quarter_turns: int = 1) -> "VoxelObject":
        """Cópia girada em torno do eixo Y, em passos de 90°."""
        turns = int(quarter_turns) % 4
        if turns == 0:
            return self.copy()
        sx, sy, sz = self.size
        if turns == 1:
            size = (sz, sy, sx)
            rotate = lambda x, y, z: (z, y, sx - 1 - x)
        elif turns == 2:
            size = (sx, sy, sz)
            rotate = lambda x, y, z: (sx - 1 - x, y, sz - 1 - z)
        else:
            size = (sz, sy, sx)
            rotate = lambda x, y, z: (sz - 1 - z, y, x)
        result = VoxelObject(size, self.name, self.kind, materials=self.materials)
        for x, y, z in np.argwhere(self.blocks != EMPTY):
            material = int(self.blocks[x, y, z])
            nx, ny, nz = rotate(int(x), int(y), int(z))
            result.blocks[nx, ny, nz] = material
        return result

    def blit(self, other: "VoxelObject", offset: tuple[int, int, int] = (0, 0, 0), quarter_turns: int = 0) -> int:
        """Cola outro objeto nesta grade, girado, sem sair dos limites."""
        source = other.rotated_y(quarter_turns)
        ox, oy, oz = (int(value) for value in offset)
        placed = 0
        for x, y, z in np.argwhere(source.blocks != EMPTY):
            tx, ty, tz = ox + int(x), oy + int(y), oz + int(z)
            if not self.in_bounds(tx, ty, tz):
                continue
            material = source.material(int(source.blocks[x, y, z]))
            self.blocks[tx, ty, tz] = self.material_index(material.color, material.texture)
            placed += 1
        return placed

    # ------------------------------------------------------------------
    # Serialização
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        occupied = np.argwhere(self.blocks != EMPTY)
        voxels = [
            [int(x), int(y), int(z), int(self.blocks[x, y, z])]
            for x, y, z in occupied
        ]
        return {
            "format": FORMAT,
            "version": VERSION,
            "kind": self.kind,
            "name": self.name,
            "size": list(self.size),
            "materials": [material.to_dict() for material in self.materials],
            "voxels": voxels,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoxelObject":
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ValueError("Arquivo não é um objeto voxel do Isometricon.")
        if int(data.get("version", -1)) != VERSION:
            raise ValueError("Versão de objeto voxel não suportada.")
        size = tuple(data.get("size", ()))
        if len(size) != 3:
            raise ValueError("Objeto sem as três dimensões.")
        materials = [VoxelMaterial.from_dict(item) for item in data.get("materials", [])]
        obj = cls(size, str(data.get("name", "objeto")), str(data.get("kind", "object")), materials=materials)  # type: ignore[arg-type]
        for entry in data.get("voxels", []):
            if not isinstance(entry, (list, tuple)) or len(entry) != 4:
                raise ValueError("Voxel inválido no arquivo.")
            x, y, z, material = (int(value) for value in entry)
            obj.set(x, y, z, material)
        return obj

    def save(self, path: str | os.PathLike, *, atomic: bool = True) -> str:
        """Grava JSON; por padrão usa arquivo temporário e troca atômica."""
        destination = os.fspath(path)
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=1)
        if atomic:
            temporary = destination + ".tmp"
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        else:
            with open(destination, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
        return destination

    @classmethod
    def load(cls, path: str | os.PathLike) -> "VoxelObject":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data)
