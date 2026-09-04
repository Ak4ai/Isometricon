"""Face culling de chunks na CPU, sem dependência de contexto OpenGL."""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from src.world.block import BlockType, get_block_color, is_opaque
from src.world.chunk import Chunk3D


# Vértices CCW vistos de fora, em [0, 1]³. UVs preservam a orientação
# do cubo texturizado de main.py (inclusive o topo).
_NORMALS = (
    (1, 0, 0), (-1, 0, 0), (0, 1, 0),
    (0, -1, 0), (0, 0, 1), (0, 0, -1),
)
_CORNERS = np.array([
    [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)],  # +X
    [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],  # -X
    [(0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)],  # +Y
    [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],  # -Y
    [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],  # +Z
    [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)],  # -Z
], dtype=np.float32)
_UVS = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=np.float32)
_TOP_UVS = np.array([(0, 1), (1, 1), (1, 0), (0, 0)], dtype=np.float32)
_QUAD_INDICES = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)


@dataclass
class ChunkMeshData:
    """Arrays C-contíguos: vertices (V, 11) float32; indices (I,) uint32.

    Layout TexturedMesh: posição3, normal3, UV2, cor3 (44 bytes).
    Posições locais: a célula (x, y, z) ocupa [x, x+1] × [y, y+1] × [z, z+1].
    O renderer aplica a translação da origem do chunk em u_Model.
    """

    vertices: NDArray[np.float32]
    indices: NDArray[np.uint32]

    @property
    def face_count(self) -> int:
        return self.index_count // 6

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def index_count(self) -> int:
        return len(self.indices)


class ChunkMesher:
    """Converte voxels em quads visíveis: O(n) tempo, O(f) memória de saída.

    Cada voxel não AIR consulta até seis vizinhos; somente vizinhos opacos
    descartam faces. WATER/LEAVES geram geometria, mas não ocultam faces,
    inclusive entre dois blocos transparentes do mesmo tipo.
    """

    def build(
        self,
        chunk: Chunk3D,
        neighbor_at: Callable[[int, int, int], BlockType | int] | None = None,
    ) -> ChunkMeshData:
        """Gera a malha sem alterar o chunk nem alocar recursos de GPU.

        Exterior é AIR por padrão. neighbor_at, quando fornecido, recebe
        coordenadas MUNDIAIS somente fora do chunk e retorna um ID válido.
        O chamador deve retornar AIR para chunks desconhecidos e reconstruir
        malhas afetadas quando vizinhos mudarem. Erros do callback propagam.
        """
        size = chunk.SIZE
        origin_x, origin_y, origin_z = chunk.local_to_world(0, 0, 0)
        faces = []
        # X varia mais rápido, acompanhando o armazenamento Fortran do chunk.
        for z in range(size):
            for y in range(size):
                for x in range(size):
                    block = chunk.get_block(x, y, z)
                    if block == BlockType.AIR:
                        continue
                    for face, (dx, dy, dz) in enumerate(_NORMALS):
                        nx, ny, nz = x + dx, y + dy, z + dz
                        if 0 <= nx < size and 0 <= ny < size and 0 <= nz < size:
                            neighbor = chunk.get_block(nx, ny, nz)
                        elif neighbor_at is not None:
                            neighbor = neighbor_at(
                                origin_x + nx, origin_y + ny, origin_z + nz,
                            )
                        else:
                            neighbor = BlockType.AIR
                        if not is_opaque(neighbor):
                            faces.append((x, y, z, face, block))

        # Uma descrição por face, sem objetos por vértice. Alocação exata,
        # inclusive para saída vazia; quatro vértices e seis índices por quad.
        vertices = np.empty((len(faces) * 4, 11), dtype=np.float32)
        indices = np.empty(len(faces) * 6, dtype=np.uint32)
        for i, (x, y, z, face, block) in enumerate(faces):
            base = i * 4
            quad = vertices[base:base + 4]
            quad[:, :3] = _CORNERS[face] + (x, y, z)
            quad[:, 3:6] = _NORMALS[face]
            quad[:, 6:8] = _TOP_UVS if face == 2 else _UVS
            quad[:, 8:11] = get_block_color(block)
            indices[i * 6:i * 6 + 6] = _QUAD_INDICES + base
        return ChunkMeshData(vertices, indices)
