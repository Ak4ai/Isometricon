"""Terreno por value noise 2D: somente CPU e coordenadas mundiais."""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from hashlib import blake2b
from math import floor, isfinite
from numbers import Real

import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D, _coordinate


@lru_cache(maxsize=1 << 16)
def _lattice(seed: int, x: int, z: int) -> float:
    """O valor do ponto (x, z) da grade do ruído: hash estável da stdlib, sem hash() do Python nem estado aleatório
    global. A divisão é entre inteiros (exata, arredondada uma vez): por isso fica em Python, e não em numpy."""
    key = f'{seed}:{x}:{z}'.encode('ascii')
    value = int.from_bytes(blake2b(key, digest_size=8).digest(), 'big')
    return 2 * (value / (2**64 - 1)) - 1


@lru_cache(maxsize=1 << 16)
def _column_height(generator: "TerrainGenerator", x: int, z: int) -> int:
    """``get_height`` guardado por coluna: as cavernas perguntam a mesma coluna a cada passo do túnel."""
    return generator._compute_height(x, z)


def _fade(t: float) -> float:
    """Interpolação quintica com primeira e segunda derivadas nulas nas bordas."""
    return t * t * t * (t * (t * 6 - 15) + 10)


@dataclass(frozen=True)
class TerrainGenerator:
    """Configuração imutável; mesma seed/configuração reproduz o mesmo mundo.

    N = sum(persistence**i * noise(frequency*lacunarity**i * (x,z)))
        / sum(persistence**i), para i em [0, octaves).
    height = base_height + floor(amplitude * clamp(N, -1, 1)).
    A altura identifica o Y do último bloco sólido, não o topo geométrico.
    Consulte README.md para unidades, camadas e limites.
    """

    seed: int = 0
    base_height: int = 8
    amplitude: float = 6.0
    frequency: float = 1 / 24
    octaves: int = 3
    persistence: float = 0.5
    lacunarity: float = 2.0
    dirt_depth: int = 3
    sea_level: int = 7
    enable_caves: bool = False
    cave_chance: float = 0.60
    allow_sparse_depth: bool = True
    vegetation: bool = False   # capim, flores e cogumelos sobre a grama (o jogo liga; os testes antigos não)

    def __post_init__(self) -> None:
        for name in ('seed', 'base_height', 'octaves', 'dirt_depth', 'sea_level'):
            object.__setattr__(self, name, _coordinate(getattr(self, name)))
        for name in ('amplitude', 'frequency', 'persistence', 'lacunarity'):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
                raise TypeError(f'{name} deve ser um número real.')
            if not isfinite(value):
                raise ValueError(f'{name} deve ser finito.')
            object.__setattr__(self, name, float(value))
        for name in ('enable_caves', 'allow_sparse_depth', 'vegetation'):
            value = getattr(self, name)
            if not isinstance(value, (bool, np.bool_)):
                raise TypeError(f'{name} deve ser booleano.')
            object.__setattr__(self, name, bool(value))
        if isinstance(self.cave_chance, (bool, np.bool_)) or not isinstance(self.cave_chance, Real):
            raise TypeError('cave_chance deve ser um número real.')
        if not isfinite(self.cave_chance) or not 0.0 <= self.cave_chance <= 1.0:
            raise ValueError('cave_chance deve estar em [0, 1].')
        object.__setattr__(self, 'cave_chance', float(self.cave_chance))
        if self.amplitude < 0 or self.frequency <= 0:
            raise ValueError('amplitude >= 0 e frequency > 0 são necessárias.')
        if self.octaves < 1 or self.dirt_depth < 0:
            raise ValueError('octaves >= 1 e dirt_depth >= 0 são necessários.')
        if not 0 <= self.persistence <= 1 or self.lacunarity < 1:
            raise ValueError('persistence deve estar em [0,1] e lacunarity >= 1.')
        try:
            highest_frequency = self.frequency * self.lacunarity ** (self.octaves - 1)
        except OverflowError as exc:
            raise ValueError('Frequência das oitavas excede o limite numérico.') from exc
        if not isfinite(highest_frequency):
            raise ValueError('Frequência das oitavas deve ser finita.')


    def _lattice_value(self, x: int, z: int) -> float:
        return _lattice(self.seed, x, z)

    def _noise(self, x: float, z: float) -> float:
        ix, iz = floor(x), floor(z)
        u, v = _fade(x - ix), _fade(z - iz)
        a, b = self._lattice_value(ix, iz), self._lattice_value(ix + 1, iz)
        c, d = self._lattice_value(ix, iz + 1), self._lattice_value(ix + 1, iz + 1)
        near, far = a + u * (b - a), c + u * (d - c)
        return near + v * (far - near)

    def get_height(self, world_x: int, world_z: int) -> int:
        """Retorna Y sólido em [base+floor(-amplitude), base+floor(amplitude)]."""
        return _column_height(self, _coordinate(world_x), _coordinate(world_z))

    def _compute_height(self, x: int, z: int) -> int:
        total, weight_sum = 0.0, 0.0
        weight, frequency = 1.0, self.frequency
        for _ in range(self.octaves):
            total += weight * self._noise(x * frequency, z * frequency)
            weight_sum += weight
            weight *= self.persistence
            frequency *= self.lacunarity
        noise = max(-1.0, min(1.0, total / weight_sum))
        return self.base_height + floor(self.amplitude * noise)

    def heights(self, xs: np.ndarray, zs: np.ndarray) -> np.ndarray:
        """``get_height`` de muitas colunas de uma vez (arrays de inteiros do mesmo formato): a mesma conta, na mesma
        ordem, em float64; só os pontos da grade (poucos por chunk) passam pelo hash."""
        xs, zs = np.broadcast_arrays(np.asarray(xs, dtype=np.int64), np.asarray(zs, dtype=np.int64))
        fx, fz = xs.astype(np.float64), zs.astype(np.float64)
        total = np.zeros(xs.shape, dtype=np.float64)
        weight_sum, weight, frequency = 0.0, 1.0, self.frequency
        for _ in range(self.octaves):
            px, pz = fx * frequency, fz * frequency
            ix, iz = np.floor(px), np.floor(pz)
            u, v = _fade(px - ix), _fade(pz - iz)
            ix, iz = ix.astype(np.int64), iz.astype(np.int64)
            # os quatro cantos de cada ponto; o hash só uma vez por canto distinto
            corners = np.stack([np.stack([ix, iz], -1), np.stack([ix + 1, iz], -1),
                                np.stack([ix, iz + 1], -1), np.stack([ix + 1, iz + 1], -1)]).reshape(-1, 2)
            unique, inverse = np.unique(corners, axis=0, return_inverse=True)
            values = np.array([_lattice(self.seed, int(x), int(z)) for x, z in unique])
            a, b, c, d = values[inverse.reshape(4, *ix.shape)]
            near, far = a + u * (b - a), c + u * (d - c)
            total += weight * (near + v * (far - near))
            weight_sum += weight
            weight *= self.persistence
            frequency *= self.lacunarity
        noise = np.maximum(-1.0, np.minimum(1.0, total / weight_sum))
        return self.base_height + np.floor(self.amplitude * noise).astype(np.int64)

    def populate_chunk(self, chunk: Chunk3D) -> None:
        """Substitui todos os voxels, preservando array, coordenadas e AABB.

        Calcula uma altura por coluna X/Z e preenche Y por fatias locais.
        O mundo sólido continua em profundidade, sem piso artificial em Y=0.
        """
        size = chunk.SIZE
        origin_x, origin_y, origin_z = chunk.local_to_world(0, 0, 0)
        local = np.arange(size, dtype=np.int64)
        surface = self.heights(origin_x + local[:, None], origin_z + local[None, :])[:, None, :]   # [x, 1, z]
        y = (origin_y + local)[None, :, None]                                                         # [1, y, 1]
        blocks = np.full((size, size, size), int(BlockType.AIR), dtype=chunk.blocks.dtype)
        blocks[np.broadcast_to(y <= surface, blocks.shape)] = int(BlockType.STONE)
        blocks[np.broadcast_to((y >= surface - self.dirt_depth) & (y <= surface), blocks.shape)] = int(BlockType.DIRT)
        top = np.where(surface < self.sea_level, int(BlockType.DIRT), int(BlockType.GRASS))
        at_top = np.broadcast_to(y == surface, blocks.shape)
        blocks[at_top] = np.broadcast_to(top, blocks.shape)[at_top]
        blocks[np.broadcast_to((y > surface) & (y <= self.sea_level), blocks.shape)] = int(BlockType.WATER)
        chunk.blocks[...] = blocks

    def generate_region(
        self, positions: Iterable[tuple[int, int, int]],
    ) -> dict[tuple[int, int, int], Chunk3D]:
        """Gera uma coleção finita de (chunk_x, chunk_y, chunk_z), sem streaming.

        Retorna chunks por coordenada; posições repetidas são ignoradas.
        Cada chamada cria armazenamento independente.
        """
        chunks = {}
        for position in positions:
            key = tuple(_coordinate(value) for value in position)
            if len(key) != 3:
                raise ValueError('Cada posição deve conter chunk_x, chunk_y e chunk_z.')
            if key not in chunks:
                chunk = Chunk3D(*key)
                self.populate_chunk(chunk)
                chunks[key] = chunk
        if self.enable_caves and chunks:
            from src.world.caves import CaveCarver
            carver = CaveCarver(
                seed=self.seed,
                cave_chance=self.cave_chance,
                allow_sparse_depth=self.allow_sparse_depth,
            )
            carver.carve_region(chunks, self)
        if self.vegetation and chunks:
            self.plant_vegetation(chunks)
        return chunks

    def _plant_roll(self, xs: np.ndarray, zs: np.ndarray) -> np.ndarray:
        """Um número estável em [0, 1) por coluna (x, z), da seed: a mesma planta volta no mesmo lugar."""
        h = (xs.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)) ^ (zs.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F))
        h ^= np.uint64((self.seed * 0x165667B19E3779F9 + 0x27D4EB2F) & 0xFFFFFFFFFFFFFFFF)
        h ^= h >> np.uint64(31)
        h *= np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(27)
        h *= np.uint64(0x94D049BB133111EB)
        h ^= h >> np.uint64(31)
        return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)

    def plant_vegetation(self, chunks: dict) -> None:
        """Põe capim, flores e cogumelos no ar logo acima da grama, nos chunks dados (depois das cavernas)."""
        size = Chunk3D.SIZE
        # (limite acumulado, planta): 14% capim, 1,5% papoula, 1,5% dente-de-leão, 0,4% de cada cogumelo
        table = ((0.140, BlockType.SHORT_GRASS), (0.155, BlockType.POPPY), (0.170, BlockType.DANDELION),
                 (0.174, BlockType.RED_MUSHROOM), (0.178, BlockType.BROWN_MUSHROOM))
        with np.errstate(over='ignore'):
            for (cx, cy, cz), chunk in chunks.items():
                grass = np.argwhere(chunk.blocks == int(BlockType.GRASS))
                if len(grass) == 0:
                    continue
                rolls = self._plant_roll(grass[:, 0] + cx * size, grass[:, 2] + cz * size)
                limits = np.array([limit for limit, _ in table])
                picks = np.searchsorted(limits, rolls, side='right')
                for (lx, ly, lz), pick in zip(grass, picks):
                    if pick >= len(table):
                        continue
                    target, ty = chunk, int(ly) + 1
                    if ty >= size:
                        target, ty = chunks.get((cx, cy + 1, cz)), 0
                        if target is None:
                            continue
                    if target.blocks[lx, ty, lz] == int(BlockType.AIR):
                        target.blocks[lx, ty, lz] = int(table[pick][1])

