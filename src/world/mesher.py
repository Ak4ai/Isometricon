"""Face culling de chunks na CPU, sem dependência de contexto OpenGL."""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from src.world.block import BlockType, BLOCK_COLORS, get_block_color, is_opaque
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


_OPAQUE_LUT = np.zeros(256, dtype=bool)
_OPAQUE_LUT[[int(b) for b in (BlockType.DIRT, BlockType.GRASS, BlockType.STONE, BlockType.WOOD)]] = True

_COLOR_LUT = np.zeros((256, 3), dtype=np.float32)
for _bt, _c in BLOCK_COLORS.items():
    _COLOR_LUT[int(_bt)] = _c


class ChunkMesher:
    """Converte voxels em quads visíveis: O(n) tempo, O(f) memória de saída.

    Cada voxel não AIR consulta até seis vizinhos; somente vizinhos opacos
    descartam faces. WATER/LEAVES geram geometria, mas não ocultam faces,
    inclusive entre dois blocos transparentes do mesmo tipo.
    """

    def __init__(self, atlas: object = None) -> None:
        self.atlas = atlas

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
        blocks = chunk.blocks
        if not np.any(blocks):
            return ChunkMeshData(np.empty((0, 11), dtype=np.float32), np.empty(0, dtype=np.uint32))

        origin_x, origin_y, origin_z = chunk.local_to_world(0, 0, 0)

        padded = np.zeros((18, 18, 18), dtype=bool)
        padded[1:17, 1:17, 1:17] = _OPAQUE_LUT[blocks]

        if neighbor_at is not None:
            y_idx, z_idx = np.where(blocks[15, :, :] != BlockType.AIR)
            for y, z in zip(y_idx, z_idx):
                padded[17, y + 1, z + 1] = is_opaque(neighbor_at(origin_x + 16, origin_y + y, origin_z + z))

            y_idx, z_idx = np.where(blocks[0, :, :] != BlockType.AIR)
            for y, z in zip(y_idx, z_idx):
                padded[0, y + 1, z + 1] = is_opaque(neighbor_at(origin_x - 1, origin_y + y, origin_z + z))

            x_idx, z_idx = np.where(blocks[:, 15, :] != BlockType.AIR)
            for x, z in zip(x_idx, z_idx):
                padded[x + 1, 17, z + 1] = is_opaque(neighbor_at(origin_x + x, origin_y + 16, origin_z + z))

            x_idx, z_idx = np.where(blocks[:, 0, :] != BlockType.AIR)
            for x, z in zip(x_idx, z_idx):
                padded[x + 1, 0, z + 1] = is_opaque(neighbor_at(origin_x + x, origin_y - 1, origin_z + z))

            x_idx, y_idx = np.where(blocks[:, :, 15] != BlockType.AIR)
            for x, y in zip(x_idx, y_idx):
                padded[x + 1, y + 1, 17] = is_opaque(neighbor_at(origin_x + x, origin_y + y, origin_z + 16))

            x_idx, y_idx = np.where(blocks[:, :, 0] != BlockType.AIR)
            for x, y in zip(x_idx, y_idx):
                padded[x + 1, y + 1, 0] = is_opaque(neighbor_at(origin_x + x, origin_y + y, origin_z - 1))

        non_air = (blocks != BlockType.AIR)

        vis = [
            non_air & (~padded[2:18, 1:17, 1:17]),  # +X (0)
            non_air & (~padded[0:16, 1:17, 1:17]),  # -X (1)
            non_air & (~padded[1:17, 2:18, 1:17]),  # +Y (2)
            non_air & (~padded[1:17, 0:16, 1:17]),  # -Y (3)
            non_air & (~padded[1:17, 1:17, 2:18]),  # +Z (4)
            non_air & (~padded[1:17, 1:17, 0:16]),  # -Z (5)
        ]

        total_faces = sum(int(v.sum()) for v in vis)
        if total_faces == 0:
            return ChunkMeshData(np.empty((0, 11), dtype=np.float32), np.empty(0, dtype=np.uint32))

        vertices = np.empty((total_faces * 4, 11), dtype=np.float32)
        indices = np.empty(total_faces * 6, dtype=np.uint32)

        use_atlas = self.atlas is not None and hasattr(self.atlas, "uv_table")
        uv_table = self.atlas.uv_table if use_atlas else None
        color_table = self.atlas.color_table if use_atlas else None

        base_idx = np.arange(total_faces, dtype=np.uint32) * 4
        quad_offsets = np.tile(_QUAD_INDICES, total_faces).reshape(total_faces, 6)
        indices[:] = (quad_offsets + base_idx[:, None]).ravel()

        current_face_idx = 0
        for face in range(6):
            mask = vis[face]
            count = int(mask.sum())
            if count == 0:
                continue
            xs, ys, zs = np.where(mask)
            blk = blocks[xs, ys, zs]

            face_v_start = current_face_idx * 4
            face_v_end = face_v_start + count * 4
            current_face_idx += count

            v_slice = vertices[face_v_start:face_v_end].reshape(count, 4, 11)
            offsets = np.stack([xs, ys, zs], axis=-1)[:, None, :]
            v_slice[:, :, :3] = _CORNERS[face] + offsets
            v_slice[:, :, 3:6] = _NORMALS[face]

            if use_atlas:
                v_slice[:, :, 6:8] = uv_table[blk, face]
                v_slice[:, :, 8:11] = color_table[blk, face][:, None, :]
            else:
                v_slice[:, :, 6:8] = _TOP_UVS if face == 2 else _UVS
                v_slice[:, :, 8:11] = _COLOR_LUT[blk][:, None, :]

        return ChunkMeshData(vertices, indices)
