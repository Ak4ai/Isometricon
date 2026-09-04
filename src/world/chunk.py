# Armazenamento compacto de voxels em chunks de 16³ células.

from operator import index
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from src.math.aabb import AABB
from src.math.vector import vec3
from src.world.block import BlockType, _as_block_type


def _coordinate(value: int) -> int:
    # Aceita inteiros Python/NumPy, sem truncar floats ou aceitar booleanos.
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("Coordenadas devem ser inteiras, não booleanas.")
    return index(value)


class Chunk3D:
    # Chunk lógico com eixos [x, y, z] e 4096 bytes de voxels.
    #
    # Coordenadas locais pertencem a [0, SIZE); fora disso, IndexError.
    # Coordenadas não inteiras geram TypeError. O array usa ordem Fortran:
    # o deslocamento linear é x + SIZE * (y + SIZE * z), conforme a arquitetura.
    # Use get_block/set_block para acesso validado; blocks expõe o ndarray
    # para consumo em lote, e sua edição direta deve preservar shape/dtype/IDs.

    SIZE: ClassVar[int] = 16

    def __init__(
        self,
        chunk_x: int = 0,
        chunk_y: int = 0,
        chunk_z: int = 0,
        blocks: np.ndarray | None = None,
    ) -> None:
        # Cria AIR ou copia um array inteiro 16³ com IDs válidos.
        #
        # Outros dtypes inteiros são convertidos após validar os valores.
        # Floats, bools e objetos são rejeitados com TypeError; shape ou IDs
        # inválidos geram ValueError. A entrada nunca compartilha memória.
        self.chunk_x = _coordinate(chunk_x)
        self.chunk_y = _coordinate(chunk_y)
        self.chunk_z = _coordinate(chunk_z)
        shape = (self.SIZE, self.SIZE, self.SIZE)
        self.blocks: NDArray[np.uint8]
        if blocks is None:
            self.blocks = np.zeros(shape, dtype=np.uint8, order="F")
        else:
            if not isinstance(blocks, np.ndarray):
                raise TypeError("blocks deve ser um np.ndarray.")
            if blocks.shape != shape:
                raise ValueError(f"blocks deve ter shape {shape}.")
            if not np.issubdtype(blocks.dtype, np.integer):
                raise TypeError("blocks deve ter dtype inteiro.")
            if not np.isin(blocks, [int(block) for block in BlockType]).all():
                raise ValueError("blocks contém IDs de BlockType inválidos.")
            self.blocks = np.array(blocks, dtype=np.uint8, order="F", copy=True)

    def _local_coordinates(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        # Valida cada eixo antes da indexação NumPy.
        coordinates = (_coordinate(x), _coordinate(y), _coordinate(z))
        if any(value < 0 or value >= self.SIZE for value in coordinates):
            raise IndexError(f"Coordenadas locais fora do chunk: {coordinates}.")
        return coordinates

    def get_block(self, x: int, y: int, z: int) -> BlockType:
        # Consulta um voxel local em O(1), retornando o membro de BlockType.
        return BlockType(int(self.blocks[self._local_coordinates(x, y, z)]))

    def set_block(self, x: int, y: int, z: int, block_type: BlockType | int) -> None:
        # Altera um voxel local em O(1); rejeita IDs inválidos antes da escrita.
        coordinates = self._local_coordinates(x, y, z)
        self.blocks[coordinates] = _as_block_type(block_type)

    def local_to_world(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        # Converte uma célula local válida para sua coordenada inteira no mundo.
        x, y, z = self._local_coordinates(x, y, z)
        return (
            self.chunk_x * self.SIZE + x,
            self.chunk_y * self.SIZE + y,
            self.chunk_z * self.SIZE + z,
        )

    def world_to_local(self, x: int, y: int, z: int) -> tuple[int, int, int]:
        # Converte célula do mundo; IndexError se pertencer a outro chunk.
        #
        # Um futuro provedor pode localizar o chunk com world // SIZE e a célula
        # local com world % SIZE, inclusive para coordenadas negativas.
        return self._local_coordinates(
            _coordinate(x) - self.chunk_x * self.SIZE,
            _coordinate(y) - self.chunk_y * self.SIZE,
            _coordinate(z) - self.chunk_z * self.SIZE,
        )

    def get_bounding_box(self) -> AABB:
        # Retorna min/max em vec3 float32; max é o limite externo do chunk.
        #
        # A posse das células usa [min, max), evitando sobreposição de chunks.
        # As conversões lógicas mantêm inteiros; estes vetores são geométricos,
        # com a mesma precisão float32 do módulo matemático existente.
        x, y, z = self.local_to_world(0, 0, 0)
        return AABB(vec3(x, y, z), vec3(x + self.SIZE, y + self.SIZE, z + self.SIZE))
