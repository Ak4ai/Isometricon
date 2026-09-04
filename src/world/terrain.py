"""Terreno por value noise 2D: somente CPU e coordenadas mundiais."""

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import blake2b
from math import floor, isfinite
from numbers import Real

import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D, _coordinate


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
        # Hash estável da stdlib, sem hash() do Python nem estado aleatório global.
        key = f'{self.seed}:{x}:{z}'.encode('ascii')
        value = int.from_bytes(blake2b(key, digest_size=8).digest(), 'big')
        return 2 * (value / (2**64 - 1)) - 1

    def _noise(self, x: float, z: float) -> float:
        ix, iz = floor(x), floor(z)
        u, v = _fade(x - ix), _fade(z - iz)
        a, b = self._lattice_value(ix, iz), self._lattice_value(ix + 1, iz)
        c, d = self._lattice_value(ix, iz + 1), self._lattice_value(ix + 1, iz + 1)
        near, far = a + u * (b - a), c + u * (d - c)
        return near + v * (far - near)

    def get_height(self, world_x: int, world_z: int) -> int:
        """Retorna Y sólido em [base+floor(-amplitude), base+floor(amplitude)]."""
        x, z = _coordinate(world_x), _coordinate(world_z)
        total, weight_sum = 0.0, 0.0
        weight, frequency = 1.0, self.frequency
        for _ in range(self.octaves):
            total += weight * self._noise(x * frequency, z * frequency)
            weight_sum += weight
            weight *= self.persistence
            frequency *= self.lacunarity
        noise = max(-1.0, min(1.0, total / weight_sum))
        return self.base_height + floor(self.amplitude * noise)

    def populate_chunk(self, chunk: Chunk3D) -> None:
        """Substitui todos os voxels, preservando array, coordenadas e AABB.

        Calcula uma altura por coluna X/Z e preenche Y por fatias locais.
        O mundo sólido continua em profundidade, sem piso artificial em Y=0.
        """
        for z in range(chunk.SIZE):
            for x in range(chunk.SIZE):
                world_x, origin_y, world_z = chunk.local_to_world(x, 0, z)
                surface = self.get_height(world_x, world_z)
                column = chunk.blocks[x, :, z]
                column[:] = BlockType.AIR

                def end(world_y: int) -> int:
                    return max(0, min(chunk.SIZE, world_y - origin_y + 1))

                column[:end(surface)] = BlockType.STONE
                column[end(surface - self.dirt_depth - 1):end(surface)] = BlockType.DIRT
                if origin_y <= surface < origin_y + chunk.SIZE:
                    column[surface - origin_y] = (
                        BlockType.DIRT if surface < self.sea_level else BlockType.GRASS
                    )
                column[end(surface):end(self.sea_level)] = BlockType.WATER

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
        return chunks
