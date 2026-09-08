"""Geração determinística de cavernas 3D (Cave Carvers) para terrenos voxel."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import blake2b
from math import cos, floor, isfinite, sin
from numbers import Real

import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D, _coordinate


@dataclass(frozen=True)
class CaveCarver:
    """Escavador procedural de cavernas baseado em vermes 3D determinísticos (estilo Minecraft).

    Gera túneis e salões subterrâneos a partir da seed global do mundo,
    preservando corpos d'água e suportando chunks subterrâneos esparsos.
    """

    seed: int = 0
    cave_chance: float = 0.60
    min_length: int = 25
    max_length: int = 50
    min_radius: float = 1.4
    max_radius: float = 2.6
    room_chance: float = 0.10
    allow_sparse_depth: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", _coordinate(self.seed))
        object.__setattr__(self, "min_length", _coordinate(self.min_length))
        object.__setattr__(self, "max_length", _coordinate(self.max_length))

        for name in ("cave_chance", "min_radius", "max_radius", "room_chance"):
            val = getattr(self, name)
            if isinstance(val, (bool, np.bool_)) or not isinstance(val, Real):
                raise TypeError(f"{name} deve ser um número real.")
            if not isfinite(val):
                raise ValueError(f"{name} deve ser finito.")
            object.__setattr__(self, name, float(val))

        for name in ("allow_sparse_depth",):
            val = getattr(self, name)
            if not isinstance(val, (bool, np.bool_)):
                raise TypeError(f"{name} deve ser booleano.")
            object.__setattr__(self, name, bool(val))

        if not 0.0 <= self.cave_chance <= 1.0:
            raise ValueError("cave_chance deve estar no intervalo [0.0, 1.0].")
        if not 0.0 <= self.room_chance <= 1.0:
            raise ValueError("room_chance deve estar no intervalo [0.0, 1.0].")
        if self.min_length < 1 or self.max_length < self.min_length:
            raise ValueError("min_length >= 1 e max_length >= min_length são necessários.")
        if self.min_radius <= 0.0 or self.max_radius < self.min_radius:
            raise ValueError("min_radius > 0 e max_radius >= min_radius são necessários.")

    def _chunk_seed(self, chunk_x: int, chunk_z: int) -> int:
        """Deriva uma seed determinística de 64 bits para a coluna de chunks."""
        key = f"{self.seed}:cave:{chunk_x}:{chunk_z}".encode("ascii")
        return int.from_bytes(blake2b(key, digest_size=8).digest(), "big")

    def carve_region(
        self,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None = None,
    ) -> None:
        """Escava cavernas através de uma região de chunks de forma contínua e determinística.

        A ordem de avaliação é ordenada pelas coordenadas horizontais (chunk_x, chunk_z),
        garantindo independência de ordem de inserção no dicionário.
        """
        if not chunks:
            return

        columns = sorted(set((cx, cz) for cx, _, cz in chunks.keys()))
        for cx, cz in columns:
            self._carve_column(cx, cz, chunks, terrain_generator)

    def _carve_column(
        self,
        chunk_x: int,
        chunk_z: int,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None,
    ) -> None:
        rng = np.random.default_rng(self._chunk_seed(chunk_x, chunk_z))

        if rng.random() > self.cave_chance:
            return

        # Número de túneis originados neste chunk (1 a 2)
        num_caves = int(rng.integers(1, 3))
        for _ in range(num_caves):
            start_lx = int(rng.integers(2, Chunk3D.SIZE - 2))
            start_lz = int(rng.integers(2, Chunk3D.SIZE - 2))
            world_x = chunk_x * Chunk3D.SIZE + start_lx
            world_z = chunk_z * Chunk3D.SIZE + start_lz

            # Consulta altura da superfície local
            if terrain_generator is not None and hasattr(terrain_generator, "get_height"):
                surface_y = terrain_generator.get_height(world_x, world_z)
                sea_level = getattr(terrain_generator, "sea_level", 7)
            else:
                surface_y = 8
                sea_level = 7

            # 35% de chance de o túnel começar como uma entrada visível na superfície
            is_surface_entrance = (rng.random() < 0.35) and (surface_y >= sea_level)
            if is_surface_entrance:
                start_y = float(surface_y)
                pitch = float(rng.uniform(-0.6, -0.2))  # Mergulha para dentro da terra
            else:
                start_y = float(rng.integers(max(1, surface_y - 8), max(2, surface_y - 1)))
                pitch = float(rng.uniform(-0.25, 0.15))

            yaw = float(rng.uniform(0.0, 2.0 * np.pi))
            length = int(rng.integers(self.min_length, self.max_length + 1))

            curr_pos = np.array([world_x, start_y, world_z], dtype=np.float64)

            for step in range(length):
                # Determina raio: salão esférico ou túnel padrão
                if rng.random() < self.room_chance:
                    radius = float(rng.uniform(2.8, 4.0))
                else:
                    radius = float(rng.uniform(self.min_radius, self.max_radius))

                self._carve_sphere(curr_pos[0], curr_pos[1], curr_pos[2], radius, chunks, terrain_generator)

                # Avança na direção (passos de 0.8 blocos para sobreposição contínua)
                step_size = 0.8
                curr_pos[0] += cos(yaw) * cos(pitch) * step_size
                curr_pos[1] += sin(pitch) * step_size
                curr_pos[2] += sin(yaw) * cos(pitch) * step_size

                # Variação angular suave a cada passo
                yaw += float(rng.normal(0.0, 0.22))
                pitch += float(rng.normal(0.0, 0.12))
                pitch = float(np.clip(pitch, -0.65, 0.45))

    def _carve_sphere(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None,
    ) -> None:
        r_sq = radius * radius
        min_x = floor(px - radius)
        max_x = floor(px + radius)
        min_y = floor(py - radius)
        max_y = floor(py + radius)
        min_z = floor(pz - radius)
        max_z = floor(pz + radius)

        # Se não permitirmos profundidade negativa esparsa, não escavamos abaixo de Y=1
        if not self.allow_sparse_depth and min_y < 1:
            min_y = 1

        for bx in range(min_x, max_x + 1):
            dx = bx - px
            for bz in range(min_z, max_z + 1):
                dz = bz - pz
                dxz_sq = dx * dx + dz * dz
                if dxz_sq > r_sq:
                    continue

                for by in range(min_y, max_y + 1):
                    dy = by - py
                    if dxz_sq + dy * dy > r_sq:
                        continue

                    cx = bx // Chunk3D.SIZE
                    cy = by // Chunk3D.SIZE
                    cz = bz // Chunk3D.SIZE
                    chunk_key = (cx, cy, cz)

                    if chunk_key not in chunks:
                        # Se for chunk subterrâneo negativo e sparse depth estiver habilitado
                        if self.allow_sparse_depth and cy < 0 and (cx, 0, cz) in chunks:
                            new_chunk = Chunk3D(cx, cy, cz)
                            new_chunk.blocks[:] = BlockType.STONE
                            chunks[chunk_key] = new_chunk
                        else:
                            continue

                    chunk = chunks[chunk_key]
                    lx = bx % Chunk3D.SIZE
                    ly = by % Chunk3D.SIZE
                    lz = bz % Chunk3D.SIZE

                    current = chunk.blocks[lx, ly, lz]
                    # Preserva oceanos, lagos e água
                    if current == BlockType.WATER:
                        continue

                    # Proteção: não perfura fundo de rios/lagos para evitar água suspensa
                    if terrain_generator is not None and hasattr(terrain_generator, "get_height"):
                        surf = terrain_generator.get_height(bx, bz)
                        sea = getattr(terrain_generator, "sea_level", 7)
                        if surf < sea and by >= surf:
                            continue

                    if current in (BlockType.STONE, BlockType.DIRT, BlockType.GRASS):
                        chunk.blocks[lx, ly, lz] = BlockType.AIR
