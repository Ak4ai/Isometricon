"""Geração determinística de cavernas 3D (Cave Carvers) com casca orgânica para terrenos voxel."""

from dataclasses import dataclass
from hashlib import blake2b
from math import cos, floor, isfinite, sin
from numbers import Real
import threading
import time

import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D, _coordinate

_BACKGROUND_YIELD_INTERVAL = 1
_BACKGROUND_YIELD_SECONDS = 0.0005


def _yield_to_main_thread() -> None:
    """Cede o GIL entre etapas do carver quando a geração roda em background."""
    if threading.current_thread() is not threading.main_thread():
        time.sleep(_BACKGROUND_YIELD_SECONDS)


@dataclass(frozen=True)
class CaveCarver:
    """Escavador procedural de cavernas baseado em vermes 3D determinísticos (estilo Minecraft).

    Gera túneis e salões subterrâneos a partir da seed global do mundo,
    preservando corpos d'água e criando uma casca rochosa orgânica no subterrâneo
    profundo (sem preencher o chunk todo de pedra).
    """

    seed: int = 0
    cave_chance: float = 0.60
    min_length: int = 25
    max_length: int = 50
    min_radius: float = 1.4
    max_radius: float = 2.6
    room_chance: float = 0.10
    allow_sparse_depth: bool = True
    shell_thickness: float = 2.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", _coordinate(self.seed))
        object.__setattr__(self, "min_length", _coordinate(self.min_length))
        object.__setattr__(self, "max_length", _coordinate(self.max_length))

        for name in ("cave_chance", "min_radius", "max_radius", "room_chance", "shell_thickness"):
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
        if self.shell_thickness < 1.0:
            raise ValueError("shell_thickness deve ser >= 1.0.")

    def _chunk_seed(self, chunk_x: int, chunk_z: int) -> int:
        """Deriva uma seed determinística de 64 bits para a coluna de chunks."""
        key = f"{self.seed}:cave:{chunk_x}:{chunk_z}".encode("ascii")
        return int.from_bytes(blake2b(key, digest_size=8).digest(), "big")

    def carve_region(
        self,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None = None,
    ) -> None:
        """Escava cavernas através de uma região de chunks de forma contínua e determinística."""
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

        num_caves = int(rng.integers(1, 3))
        for _ in range(num_caves):
            start_lx = int(rng.integers(2, Chunk3D.SIZE - 2))
            start_lz = int(rng.integers(2, Chunk3D.SIZE - 2))
            world_x = chunk_x * Chunk3D.SIZE + start_lx
            world_z = chunk_z * Chunk3D.SIZE + start_lz

            if terrain_generator is not None and hasattr(terrain_generator, "get_height"):
                surface_y = terrain_generator.get_height(world_x, world_z)
                sea_level = getattr(terrain_generator, "sea_level", 7)
            else:
                surface_y = 8
                sea_level = 7

            is_surface_entrance = (rng.random() < 0.35) and (surface_y >= sea_level)
            if is_surface_entrance:
                start_y = float(surface_y)
                pitch = float(rng.uniform(-0.6, -0.2))
            else:
                start_y = float(rng.integers(max(1, surface_y - 8), max(2, surface_y - 1)))
                pitch = float(rng.uniform(-0.25, 0.15))

            yaw = float(rng.uniform(0.0, 2.0 * np.pi))
            length = int(rng.integers(self.min_length, self.max_length + 1))

            curr_pos = np.array([world_x, start_y, world_z], dtype=np.float64)

            # Rastreia as esferas da caverna para o processo em duas etapas:
            # 1) Casca de rocha orgânica no subterrâneo profundo (cy < 0)
            # 2) Escavação do ar do túnel
            spheres: list[tuple[float, float, float, float]] = []

            for step in range(length):
                if rng.random() < self.room_chance:
                    radius = float(rng.uniform(2.8, 4.0))
                else:
                    radius = float(rng.uniform(self.min_radius, self.max_radius))

                spheres.append((curr_pos[0], curr_pos[1], curr_pos[2], radius))

                step_size = 0.8
                curr_pos[0] += cos(yaw) * cos(pitch) * step_size
                curr_pos[1] += sin(pitch) * step_size
                curr_pos[2] += sin(yaw) * cos(pitch) * step_size

                yaw += float(rng.normal(0.0, 0.22))
                pitch += float(rng.normal(0.0, 0.12))
                pitch = float(np.clip(pitch, -0.65, 0.45))

            # Passo 1: Construir a casca orgânica ao redor das cavernas que descem para Y < 0
            if self.allow_sparse_depth:
                for sphere_index, (px, py, pz, radius) in enumerate(spheres, start=1):
                    if py - radius - self.shell_thickness < 0:
                        self._build_organic_shell(px, py, pz, radius, chunks)
                    if sphere_index % _BACKGROUND_YIELD_INTERVAL == 0:
                        _yield_to_main_thread()

            # Passo 2: Escavar o ar no interior de todas as esferas do túnel
            for sphere_index, (px, py, pz, radius) in enumerate(spheres, start=1):
                self._carve_tunnel_air(px, py, pz, radius, chunks, terrain_generator)
                if sphere_index % _BACKGROUND_YIELD_INTERVAL == 0:
                    _yield_to_main_thread()

    def _build_organic_shell(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
    ) -> None:
        """Gera uma camada de pedra esculpida ao redor do túnel apenas no subterrâneo negativo (Y < 0)."""
        max_outer_r = radius + self.shell_thickness + 0.6
        max_outer_sq = max_outer_r * max_outer_r

        min_x = floor(px - max_outer_r)
        max_x = floor(px + max_outer_r)
        min_y = floor(py - max_outer_r)
        max_y = min(-1, floor(py + max_outer_r))  # Apenas Y < 0 (Y >= 0 já possui rocha sólida)
        min_z = floor(pz - max_outer_r)
        max_z = floor(pz + max_outer_r)

        for bx in range(min_x, max_x + 1):
            dx = bx - px
            for bz in range(min_z, max_z + 1):
                dz = bz - pz
                dxz_sq = dx * dx + dz * dz
                if dxz_sq > max_outer_sq:
                    continue

                # Rugosidade orgânica suave baseada na posição do bloco
                roughness = 0.45 * sin(bx * 1.5) * cos(bz * 1.5)
                effective_outer_r = radius + self.shell_thickness + roughness
                effective_outer_sq = effective_outer_r * effective_outer_r

                for by in range(min_y, max_y + 1):
                    dy = by - py
                    dist_sq = dxz_sq + dy * dy
                    if dist_sq > effective_outer_sq:
                        continue

                    cx = bx // Chunk3D.SIZE
                    cy = by // Chunk3D.SIZE
                    cz = bz // Chunk3D.SIZE
                    chunk_key = (cx, cy, cz)

                    # Se a coluna correspondente existe no mapa (cx, 0, cz), instancia chunk subterrâneo
                    if chunk_key not in chunks:
                        if (cx, 0, cz) in chunks:
                            # Inicia 100% como ar; somente a casca receberá pedra!
                            chunks[chunk_key] = Chunk3D(cx, cy, cz)
                        else:
                            continue

                    chunk = chunks[chunk_key]
                    lx = bx % Chunk3D.SIZE
                    ly = by % Chunk3D.SIZE
                    lz = bz % Chunk3D.SIZE

                    # Define como rocha para formar a casca
                    chunk.blocks[lx, ly, lz] = BlockType.STONE

    def _carve_tunnel_air(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None,
    ) -> None:
        """Escava o vazio (AIR) no centro do túnel/salão."""
        r_sq = radius * radius
        min_x = floor(px - radius)
        max_x = floor(px + radius)
        min_y = floor(py - radius)
        max_y = floor(py + radius)
        min_z = floor(pz - radius)
        max_z = floor(pz + radius)

        if not self.allow_sparse_depth and min_y < 1:
            min_y = 1

        has_generator = terrain_generator is not None and hasattr(terrain_generator, "get_height")
        sea = getattr(terrain_generator, "sea_level", 7) if has_generator else 7

        for bx in range(min_x, max_x + 1):
            dx = bx - px
            for bz in range(min_z, max_z + 1):
                dz = bz - pz
                dxz_sq = dx * dx + dz * dz
                if dxz_sq > r_sq:
                    continue

                limit_y = max_y
                if has_generator:
                    surf = terrain_generator.get_height(bx, bz)
                    if surf < sea and limit_y >= surf:
                        limit_y = surf - 1

                for by in range(min_y, limit_y + 1):
                    dy = by - py
                    if dxz_sq + dy * dy > r_sq:
                        continue

                    cx = bx // Chunk3D.SIZE
                    cy = by // Chunk3D.SIZE
                    cz = bz // Chunk3D.SIZE
                    chunk_key = (cx, cy, cz)

                    if chunk_key not in chunks:
                        continue

                    chunk = chunks[chunk_key]
                    lx = bx % Chunk3D.SIZE
                    ly = by % Chunk3D.SIZE
                    lz = bz % Chunk3D.SIZE

                    current = chunk.blocks[lx, ly, lz]
                    if current == BlockType.WATER:
                        continue

                    if current in (BlockType.STONE, BlockType.DIRT, BlockType.GRASS):
                        chunk.blocks[lx, ly, lz] = BlockType.AIR
