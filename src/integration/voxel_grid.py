from __future__ import annotations
from collections.abc import Callable, Mapping
from numbers import Integral
import numpy as np
from src.math.aabb import AABB
from src.math.vector import vec3
from src.world import BlockType, Chunk3D

def _coordinate(value: int) -> int:
    # Valida coordenadas inteiras sem aceitar bool.
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("Coordenadas devem ser inteiras, não booleanas.")
    if not isinstance(value, Integral):
        raise TypeError("Coordenadas devem ser inteiras.")
    return int(value)

class VoxelGridProvider:
    """
    Interface espacial do Motor do Mundo para a Equipe B.
    Expõe consultas em coordenadas globais sem expor diretamente a
    organização interna dos chunks.
    Chunks ausentes são tratados como AIR.
    """
    def __init__(
        self,
        chunks: Mapping[tuple[int, int, int], Chunk3D] | None = None,
        *,
        block_lookup: Callable[[int, int, int], BlockType] | None = None,
    ) -> None:
        self._chunks: dict[tuple[int, int, int], Chunk3D] = {}
        self._block_lookup = block_lookup
        if chunks is not None:
            for position, chunk in chunks.items():
                self.add_chunk(position, chunk)
    @property
    def chunks(self) -> Mapping[tuple[int, int, int], Chunk3D]:
        # Acesso somente-leitura à coleção de chunks
        return self._chunks
    def add_chunk(
        self,
        position: tuple[int, int, int],
        chunk: Chunk3D,
    ) -> None:
        # Registra um chunk na grade global
        if len(position) != 3:
            raise ValueError(
                "A posição do chunk deve conter exatamente três coordenadas."
            )
        chunk_position = tuple(_coordinate(value) for value in position)
        if not isinstance(chunk, Chunk3D):
            raise TypeError("chunk deve ser uma instância de Chunk3D.")
        if (
            chunk.chunk_x,
            chunk.chunk_y,
            chunk.chunk_z,
        ) != chunk_position:
            raise ValueError(
                "A posição informada não corresponde à posição do Chunk3D."
            )
        self._chunks[chunk_position] = chunk
    def _locate_chunk(
        self,
        world_x: int,
        world_y: int,
        world_z: int,
    ) -> tuple[Chunk3D | None, tuple[int, int, int]]:
        """
        Converte coordenada global em chunk + coordenada local.
        A divisão inteira de Python preserva corretamente coordenadas
        negativas: world = -1 -> chunk = -1, local = 15
        """
        x = _coordinate(world_x)
        y = _coordinate(world_y)
        z = _coordinate(world_z)
        size = Chunk3D.SIZE
        chunk_position = (
            x // size,
            y // size,
            z // size,
        )
        local_position = (
            x % size,
            y % size,
            z % size,
        )
        return self._chunks.get(chunk_position), local_position

    def get_block_at(
        self,
        world_x: int,
        world_y: int,
        world_z: int,
    ) -> BlockType:
        # Valida sempre antes de delegar a uma fonte dinâmica.
        world_x = _coordinate(world_x)
        world_y = _coordinate(world_y)
        world_z = _coordinate(world_z)
        if self._block_lookup is not None:
            return BlockType(self._block_lookup(world_x, world_y, world_z))
        # Coordenadas fora de chunks carregados retornam AIR.
        chunk, local = self._locate_chunk(
            world_x,
            world_y,
            world_z,
        )
        if chunk is None:
            return BlockType.AIR
        return chunk.get_block(*local)
    # Alias compatível diretamente com a especificação TypeScript.
    getBlockAt = get_block_at
    def is_solid(
        self,
        world_x: int,
        world_y: int,
        world_z: int,
    ) -> bool:
        
        # Indica se existe um bloco na coordenada
	# Conforme INTEGRATION_SPEC.md, sólido para a interface de interação significa qualquer célula diferente de AIR 
        return self.get_block_at(
            world_x,
            world_y,
            world_z,
        ) != BlockType.AIR
    # Alias compatível com a especificação.
    isSolid = is_solid
    def get_top_solid_block(
        self,
        world_x: int,
        world_z: int,
    ) -> int:
        # Retorna o maior Y sólido existente na coluna X/Z
	# A busca utiliza somente chunks carregados, caso não exista nenhum bloco sólido na coluna, retorna -1
        x = _coordinate(world_x)
        z = _coordinate(world_z)
        best_y: int | None = None
        for chunk in self._chunks.values():
            chunk_x_min = chunk.chunk_x * Chunk3D.SIZE
            chunk_x_max = chunk_x_min + Chunk3D.SIZE
            chunk_z_min = chunk.chunk_z * Chunk3D.SIZE
            chunk_z_max = chunk_z_min + Chunk3D.SIZE
            if not chunk_x_min <= x < chunk_x_max:
                continue
            if not chunk_z_min <= z < chunk_z_max:
                continue
            local_x = x - chunk_x_min
            local_z = z - chunk_z_min
            column = chunk.blocks[local_x, :, local_z]
            solid_indices = np.flatnonzero(
                column != int(BlockType.AIR)
            )
            if solid_indices.size == 0:
                continue
            local_y = int(solid_indices[-1])
            world_y = chunk.chunk_y * Chunk3D.SIZE + local_y
            if best_y is None or world_y > best_y:
                best_y = world_y
        return -1 if best_y is None else best_y
    # Alias compatível com a especificação.
    getTopSolidBlock = get_top_solid_block
    def get_block_bounding_box(
        self,
        world_x: int,
        world_y: int,
        world_z: int,
    ) -> AABB:
        # Retorna a AABB unitária do voxel nas coordenadas globais.
        # Um bloco ocupa: [x, x+1] × [y, y+1] × [z, z+1]
        x = _coordinate(world_x)
        y = _coordinate(world_y)
        z = _coordinate(world_z)
        return AABB(
            vec3(x, y, z),
            vec3(x + 1, y + 1, z + 1),
        )
    # Alias compatível com a especificação.
    getBlockBoundingBox = get_block_bounding_box
