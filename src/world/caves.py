"""Geração determinística de cavernas 3D (Cave Carvers) com casca orgânica para terrenos voxel."""

from dataclasses import dataclass
from hashlib import blake2b
from math import cos, floor, isfinite, sin
from numbers import Real
import threading
import time

import numpy as np

from src.world.block import SURFACE_BLOCKS, BlockType
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
        """Gera uma camada de pedra esculpida ao redor do túnel apenas no subterrâneo negativo (Y < 0).

        Em numpy, com o mesmo resultado da versão bloco a bloco: as mesmas contas na mesma ordem (o seno e o cosseno
        da rugosidade saem do ``math``, um por linha e coluna, para não mudar nem o último dígito), e os chunks
        novos entram no dicionário na ordem em que a varredura x, z, y os encontraria."""
        max_outer_r = radius + self.shell_thickness + 0.6
        max_outer_sq = max_outer_r * max_outer_r

        min_x = floor(px - max_outer_r)
        max_x = floor(px + max_outer_r)
        min_y = floor(py - max_outer_r)
        max_y = min(-1, floor(py + max_outer_r))  # Apenas Y < 0 (Y >= 0 já possui rocha sólida)
        min_z = floor(pz - max_outer_r)
        max_z = floor(pz + max_outer_r)
        if max_y < min_y or max_x < min_x or max_z < min_z:
            return

        bxs = np.arange(min_x, max_x + 1)
        bzs = np.arange(min_z, max_z + 1)
        bys = np.arange(min_y, max_y + 1)
        dx = (bxs - px)[:, None]
        dz = (bzs - pz)[None, :]
        dxz_sq = dx * dx + dz * dz                                                    # [x, z]
        # Rugosidade orgânica suave baseada na posição do bloco
        sin_x = np.array([sin(int(bx) * 1.5) for bx in bxs])
        cos_z = np.array([cos(int(bz) * 1.5) for bz in bzs])
        roughness = (0.45 * sin_x)[:, None] * cos_z[None, :]
        effective_outer_r = radius + self.shell_thickness + roughness
        effective_outer_sq = effective_outer_r * effective_outer_r
        dy = bys - py
        dist_sq = dxz_sq[:, :, None] + (dy * dy)[None, None, :]                       # [x, z, y]
        inside = (dxz_sq <= max_outer_sq)[:, :, None] & (dist_sq <= effective_outer_sq[:, :, None])
        ix, iz, iy = np.nonzero(inside)                                               # na ordem x, z, y
        if len(ix) == 0:
            return
        _stamp(chunks, bxs[ix], bys[iy], bzs[iz], int(BlockType.STONE), create=True)

    def _carve_tunnel_air(
        self,
        px: float,
        py: float,
        pz: float,
        radius: float,
        chunks: dict[tuple[int, int, int], Chunk3D],
        terrain_generator: object | None,
    ) -> None:
        """Escava o vazio (AIR) no centro do túnel/salão (em numpy, com o mesmo resultado bloco a bloco)."""
        r_sq = radius * radius
        min_x = floor(px - radius)
        max_x = floor(px + radius)
        min_y = floor(py - radius)
        max_y = floor(py + radius)
        min_z = floor(pz - radius)
        max_z = floor(pz + radius)

        if not self.allow_sparse_depth and min_y < 1:
            min_y = 1
        if max_y < min_y:
            return

        has_generator = terrain_generator is not None and hasattr(terrain_generator, "get_height")
        sea = getattr(terrain_generator, "sea_level", 7) if has_generator else 7

        bxs = np.arange(min_x, max_x + 1)
        bzs = np.arange(min_z, max_z + 1)
        bys = np.arange(min_y, max_y + 1)
        dx = (bxs - px)[:, None]
        dz = (bzs - pz)[None, :]
        dxz_sq = dx * dx + dz * dz                                                    # [x, z]
        columns = dxz_sq <= r_sq
        limit_y = np.full(dxz_sq.shape, max_y, dtype=np.int64)
        if has_generator and columns.any():
            cx, cz = np.nonzero(columns)
            # get_height guarda cada coluna (o túnel volta às mesmas a cada passo)
            surf = np.array([terrain_generator.get_height(int(bxs[i]), int(bzs[k])) for i, k in zip(cx, cz)],
                            dtype=np.int64)
            lowered = (surf < sea) & (max_y >= surf)
            limit_y[cx[lowered], cz[lowered]] = surf[lowered] - 1
        dy = bys - py
        inside = (columns[:, :, None] & (bys[None, None, :] <= limit_y[:, :, None])
                  & (dxz_sq[:, :, None] + (dy * dy)[None, None, :] <= r_sq))
        ix, iz, iy = np.nonzero(inside)
        if len(ix) == 0:
            return
        _stamp(chunks, bxs[ix], bys[iy], bzs[iz], int(BlockType.AIR), create=False,
               only=_CARVABLE)


# o que o túnel abre: a pedra, o arenito e o chão de cima de qualquer bioma
_CARVABLE = tuple(sorted({int(BlockType.STONE), int(BlockType.SANDSTONE), *(int(b) for b in SURFACE_BLOCKS)}))


def _stamp(chunks, xs, ys, zs, value, *, create, only=None) -> None:
    """Põe ``value`` nas células (xs, ys, zs) do mundo, chunk por chunk. ``create``: cria o chunk que falta (só se
    a coluna (cx, 0, cz) existe), na ordem em que as células o encontram; ``only``: troca só esses blocos."""
    size = Chunk3D.SIZE
    kx, ky, kz = xs // size, ys // size, zs // size
    x0, y0, z0 = int(kx.min()), int(ky.min()), int(kz.min())
    ny, nz = int(ky.max()) - y0 + 1, int(kz.max()) - z0 + 1
    code = ((kx - x0) * ny + (ky - y0)) * nz + (kz - z0)       # um número por chunk (a caixa é de poucos chunks)
    unique, first, inverse = np.unique(code, return_index=True, return_inverse=True)
    for group in np.argsort(first, kind="stable"):
        c = int(unique[group])
        key = (x0 + c // (ny * nz), y0 + (c // nz) % ny, z0 + c % nz)
        chunk = chunks.get(key)
        if chunk is None:
            if not create or (key[0], 0, key[2]) not in chunks:
                continue
            chunk = chunks[key] = Chunk3D(*key)    # inicia 100% como ar; somente a casca recebe pedra
        cells = inverse == group
        lx, ly, lz = xs[cells] % size, ys[cells] % size, zs[cells] % size
        if only is None:
            chunk.blocks[lx, ly, lz] = value
        else:
            current = chunk.blocks[lx, ly, lz]
            hit = np.isin(current, only)
            chunk.blocks[lx[hit], ly[hit], lz[hit]] = value
