"""Face culling de chunks na CPU, sem dependência de contexto OpenGL."""

from dataclasses import dataclass
from collections.abc import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from src.world.block import (
    BlockType, BLOCK_COLORS, CUBE_LUT, SHAPED_BLOCK_NAMES, SHAPED_LUT, get_block_color, is_opaque,
)
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


# Brilho do vértice conforme quantos blocos opacos o cercam na frente da face (0 a 3), como na
# iluminação suave do Minecraft: o canto de uma parede ou de um degrau escurece, o campo aberto não.
_AO_BRIGHTNESS = np.array([1.0, 0.82, 0.64, 0.46], dtype=np.float32)
_FLIPPED_INDICES = np.array([1, 2, 3, 3, 0, 1], dtype=np.uint32)


def _vertex_ao(padded: NDArray[np.bool_], xs, ys, zs, face: int) -> NDArray[np.float32]:
    """Brilho (count, 4) dos quatro vértices de cada face visível, pela oclusão ambiente.

    Para cada vértice olham-se as duas células vizinhas à frente da face e a do canto entre elas;
    com as duas laterais ocupadas o canto já não importa (nível 3).
    """
    normal = np.array(_NORMALS[face], dtype=np.int64)
    axis = int(np.argmax(np.abs(normal)))
    t1, t2 = [a for a in range(3) if a != axis]
    base = np.stack([xs, ys, zs], axis=1).astype(np.int64) + 1 + normal  # a célula à frente, em coords do padded

    def occupied(d1: int, d2: int):
        cell = base.copy()
        cell[:, t1] += d1
        cell[:, t2] += d2
        return padded[cell[:, 0], cell[:, 1], cell[:, 2]]

    brightness = np.empty((len(xs), 4), dtype=np.float32)
    for k in range(4):
        corner = _CORNERS[face][k]
        s1 = 1 if corner[t1] > 0.5 else -1
        s2 = 1 if corner[t2] > 0.5 else -1
        side1, side2, diagonal = occupied(s1, 0), occupied(0, s2), occupied(s1, s2)
        level = np.where(side1 & side2, 3, side1.astype(np.int64) + side2.astype(np.int64) + diagonal.astype(np.int64))
        brightness[:, k] = _AO_BRIGHTNESS[level]
    return brightness


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


def _shaped_template(block: BlockType, atlas: object) -> NDArray[np.float32]:
    """Os vértices (4n, 11) da forma do bloco na célula (0, 0, 0): cada grupo de 4 é um quad.

    A forma é a mesma das construções (``block_shapes.shape_for`` com o nome do Minecraft do bloco); a UV vem do
    atlas do terreno. Sem atlas, a cor é a cor base do bloco.
    """
    from src.world.block_shapes import FACES, Quad, box_face_quad, parse_block, quad_vertices, shape_for

    name = SHAPED_BLOCK_NAMES[block]
    base, _ = parse_block(name)
    use_atlas = atlas is not None and hasattr(atlas, "flipped_rect")
    color = (1.0, 1.0, 1.0) if use_atlas else BLOCK_COLORS[block]
    corner = np.zeros(3, dtype=np.float32)
    quads = []
    for part in shape_for(name) or ():
        rect = atlas.flipped_rect(part.texture or base) if use_atlas else (0.0, 1.0, 1.0, 0.0)
        if isinstance(part, Quad):
            quads.append(quad_vertices(part, corner, rect, color))
        else:
            for face in range(len(FACES)):
                quad = box_face_quad(part, face, corner, rect)
                quad[:, 8:11] = color
                quads.append(quad)
    if not quads:
        return np.empty((0, 11), dtype=np.float32)
    return np.concatenate(quads).astype(np.float32)


class ChunkMesher:
    """Converte voxels em quads visíveis: O(n) tempo, O(f) memória de saída.

    Cada voxel não AIR consulta até seis vizinhos; somente vizinhos opacos
    descartam faces. WATER/LEAVES geram geometria, mas não ocultam faces dos
    outros blocos. Entre duas águas não há face: a água é desenhada
    translúcida, e uma face interna seria uma camada a mais no meio dela.
    """

    def __init__(self, atlas: object = None, ambient_occlusion: bool = False) -> None:
        """``ambient_occlusion`` escurece, por vértice, os cantos entre blocos (embutido na cor do vértice)."""
        self.atlas = atlas
        self.ambient_occlusion = ambient_occlusion
        self._templates: dict[int, NDArray[np.float32]] = {}

    def _shaped_geometry(self, blocks: NDArray) -> tuple[NDArray[np.float32], int]:
        """Os vértices das plantas, tochas, escadas de mão e fogo do chunk, e quantos quads são."""
        parts = []
        for block_id in np.unique(blocks[SHAPED_LUT[blocks]]):
            block_id = int(block_id)
            if block_id not in self._templates:
                self._templates[block_id] = _shaped_template(BlockType(block_id), self.atlas)
            template = self._templates[block_id]
            if len(template) == 0:
                continue
            xs, ys, zs = np.where(blocks == block_id)
            offsets = np.stack([xs, ys, zs], axis=-1).astype(np.float32)
            cells = np.repeat(template[None, :, :], len(xs), axis=0)
            cells[:, :, :3] += offsets[:, None, :]
            parts.append(cells.reshape(-1, 11))
        if not parts:
            return np.empty((0, 11), dtype=np.float32), 0
        vertices = np.concatenate(parts)
        return vertices, len(vertices) // 4

    @staticmethod
    def _water_corner_height(blocks, origin_x, origin_y, origin_z, cx, y, cz, neighbor_at, water_levels) -> float:
        """Altura (0..1) do canto (cx, cz) do topo da água na camada ``y``: a média das quatro células em volta que
        são água; cheia se alguma delas tem água logo acima (a superfície encosta na água de cima sem degrau)."""
        water = int(BlockType.WATER)

        def block_at(lx: int, ly: int, lz: int) -> int:
            if 0 <= lx < 16 and 0 <= ly < 16 and 0 <= lz < 16:
                return int(blocks[lx, ly, lz])
            if neighbor_at is None:
                return int(BlockType.AIR)
            return int(neighbor_at(origin_x + lx, origin_y + ly, origin_z + lz))

        total, count = 0.0, 0
        for lx in (cx - 1, cx):
            for lz in (cz - 1, cz):
                if block_at(lx, y, lz) != water:
                    continue
                if block_at(lx, y + 1, lz) == water:
                    return 1.0
                level = water_levels.get((origin_x + lx, origin_y + y, origin_z + lz), 1.0)
                total += min(max(float(level), 0.05), 1.0)
                count += 1
        return total / count if count else 1.0

    def build(
        self,
        chunk: Chunk3D,
        neighbor_at: Callable[[int, int, int], BlockType | int] | None = None,
        water_levels: Mapping[tuple[int, int, int], float] | None = None,
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
        water = int(BlockType.WATER)
        padded_water = np.zeros((18, 18, 18), dtype=bool)
        padded_water[1:17, 1:17, 1:17] = blocks == water

        def shell(i: int, j: int, k: int, value) -> None:
            """Um vizinho de fora do chunk: se esconde faces (opaco) e se é água."""
            padded[i, j, k] = is_opaque(value)
            padded_water[i, j, k] = int(value) == water

        if neighbor_at is not None and self.ambient_occlusion:
            # o AO também olha as arestas e os cantos do cubo de 18³: a casca inteira vem do mundo
            for i in range(-1, 17):
                for j in range(-1, 17):
                    for k in range(-1, 17):
                        if 0 <= i < 16 and 0 <= j < 16 and 0 <= k < 16:
                            continue
                        shell(i + 1, j + 1, k + 1, neighbor_at(origin_x + i, origin_y + j, origin_z + k))
        elif neighbor_at is not None:
            y_idx, z_idx = np.where(blocks[15, :, :] != BlockType.AIR)
            for y, z in zip(y_idx, z_idx):
                shell(17, y + 1, z + 1, neighbor_at(origin_x + 16, origin_y + y, origin_z + z))

            y_idx, z_idx = np.where(blocks[0, :, :] != BlockType.AIR)
            for y, z in zip(y_idx, z_idx):
                shell(0, y + 1, z + 1, neighbor_at(origin_x - 1, origin_y + y, origin_z + z))

            x_idx, z_idx = np.where(blocks[:, 15, :] != BlockType.AIR)
            for x, z in zip(x_idx, z_idx):
                shell(x + 1, 17, z + 1, neighbor_at(origin_x + x, origin_y + 16, origin_z + z))

            x_idx, z_idx = np.where(blocks[:, 0, :] != BlockType.AIR)
            for x, z in zip(x_idx, z_idx):
                shell(x + 1, 0, z + 1, neighbor_at(origin_x + x, origin_y - 1, origin_z + z))

            x_idx, y_idx = np.where(blocks[:, :, 15] != BlockType.AIR)
            for x, y in zip(x_idx, y_idx):
                shell(x + 1, y + 1, 17, neighbor_at(origin_x + x, origin_y + y, origin_z + 16))

            x_idx, y_idx = np.where(blocks[:, :, 0] != BlockType.AIR)
            for x, y in zip(x_idx, y_idx):
                shell(x + 1, y + 1, 0, neighbor_at(origin_x + x, origin_y + y, origin_z - 1))

        non_air = CUBE_LUT[blocks]   # os blocos com forma saem à parte (_shaped_geometry)
        is_water = padded_water[1:17, 1:17, 1:17]
        neighbours = (
            np.s_[2:18, 1:17, 1:17],  # +X (0)
            np.s_[0:16, 1:17, 1:17],  # -X (1)
            np.s_[1:17, 2:18, 1:17],  # +Y (2)
            np.s_[1:17, 0:16, 1:17],  # -Y (3)
            np.s_[1:17, 1:17, 2:18],  # +Z (4)
            np.s_[1:17, 1:17, 0:16],  # -Z (5)
        )
        # a face some atrás de um vizinho opaco, e a da água também atrás de outra água
        vis = [non_air & ~padded[n] & ~(is_water & padded_water[n]) for n in neighbours]

        cube_faces = sum(int(v.sum()) for v in vis)
        shaped_vertices, shaped_quads = self._shaped_geometry(blocks)
        total_faces = cube_faces + shaped_quads
        if total_faces == 0:
            return ChunkMeshData(np.empty((0, 11), dtype=np.float32), np.empty(0, dtype=np.uint32))

        vertices = np.empty((total_faces * 4, 11), dtype=np.float32)
        if shaped_quads:
            vertices[cube_faces * 4:] = shaped_vertices
        indices = np.empty(total_faces * 6, dtype=np.uint32)

        use_atlas = self.atlas is not None and hasattr(self.atlas, "uv_table")
        uv_table = self.atlas.uv_table if use_atlas else None
        color_table = self.atlas.color_table if use_atlas else None

        base_idx = np.arange(total_faces, dtype=np.uint32) * 4
        quad_offsets = np.tile(_QUAD_INDICES, total_faces).reshape(total_faces, 6)
        indices[:] = (quad_offsets + base_idx[:, None]).ravel()

        flip = np.zeros(total_faces, dtype=bool)
        current_face_idx = 0
        corner_heights: dict[tuple[int, int, int], float] = {}
        for face in range(6):
            mask = vis[face]
            count = int(mask.sum())
            if count == 0:
                continue
            xs, ys, zs = np.where(mask)
            blk = blocks[xs, ys, zs]

            face_v_start = current_face_idx * 4
            face_v_end = face_v_start + count * 4
            quad_start = current_face_idx
            current_face_idx += count

            v_slice = vertices[face_v_start:face_v_end].reshape(count, 4, 11)
            offsets = np.stack([xs, ys, zs], axis=-1)[:, None, :]
            v_slice[:, :, :3] = _CORNERS[face] + offsets
            v_slice[:, :, 3:6] = _NORMALS[face]

            if water_levels is not None and np.any(blk == BlockType.WATER):
                # a superfície inclina como no Minecraft: cada canto do topo tem a altura média das águas que o tocam
                for i in np.flatnonzero(blk == BlockType.WATER):
                    y = int(ys[i])
                    for corner in range(4):
                        if v_slice[i, corner, 1] <= y:
                            continue                       # vértice de baixo: fica no chão do bloco
                        cx, cz = int(round(float(v_slice[i, corner, 0]))), int(round(float(v_slice[i, corner, 2])))
                        key = (cx, y, cz)
                        if key not in corner_heights:
                            corner_heights[key] = self._water_corner_height(
                                blocks, origin_x, origin_y, origin_z, cx, y, cz, neighbor_at, water_levels)
                        v_slice[i, corner, 1] = y + corner_heights[key]

            if use_atlas:
                v_slice[:, :, 6:8] = uv_table[blk, face]
                v_slice[:, :, 8:11] = color_table[blk, face][:, None, :]
            else:
                v_slice[:, :, 6:8] = _TOP_UVS if face == 2 else _UVS
                v_slice[:, :, 8:11] = _COLOR_LUT[blk][:, None, :]

            if self.ambient_occlusion:
                ao = _vertex_ao(padded, xs, ys, zs, face)
                ao[blk == int(BlockType.WATER)] = 1.0  # a água não ganha canto escuro
                v_slice[:, :, 8:11] *= ao[:, :, None]
                # divide o quad pela diagonal dos vértices mais escuros: o degradê não vira uma costura torta
                flip[quad_start:quad_start + count] = (ao[:, 0] + ao[:, 2]) > (ao[:, 1] + ao[:, 3])

        if flip.any():
            quads = indices.reshape(total_faces, 6)
            first = (np.arange(total_faces, dtype=np.uint32) * 4)[flip][:, None]
            quads[flip] = first + _FLIPPED_INDICES

        return ChunkMeshData(vertices, indices)
