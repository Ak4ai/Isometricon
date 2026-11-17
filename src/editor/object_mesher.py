"""Malha de um objeto voxel, com cor e textura por voxel.

O layout de vértice é o mesmo do ``TexturedMesh``: posição3, normal3, UV2,
cor3 (11 floats). Cada face recebe a UV do tile do material e a cor do material;
a textura é modulada pela cor no fragment shader.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.editor.material_atlas import MaterialAtlas
from src.editor.voxel_object import EMPTY, VoxelObject

# Mesma convenção do ChunkMesher: CCW visto de fora, em [0, 1]^3.
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
class ObjectMeshData:
    vertices: np.ndarray
    indices: np.ndarray
    face_count: int

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def index_count(self) -> int:
        return len(self.indices)


def build_mesh_data(obj: VoxelObject, atlas: MaterialAtlas) -> ObjectMeshData:
    """Constrói a malha das faces expostas do objeto (sem contexto OpenGL)."""
    if obj.voxel_count == 0:
        return ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)

    blocks = np.asarray(obj.blocks, dtype=np.int32)
    padded = np.full(tuple(size + 2 for size in obj.size), EMPTY, dtype=np.int32)
    padded[1:-1, 1:-1, 1:-1] = blocks
    occupied = blocks != EMPTY

    visible = [
        occupied & (padded[2:, 1:-1, 1:-1] == EMPTY),   # +X
        occupied & (padded[:-2, 1:-1, 1:-1] == EMPTY),  # -X
        occupied & (padded[1:-1, 2:, 1:-1] == EMPTY),   # +Y
        occupied & (padded[1:-1, :-2, 1:-1] == EMPTY),  # -Y
        occupied & (padded[1:-1, 1:-1, 2:] == EMPTY),   # +Z
        occupied & (padded[1:-1, 1:-1, :-2] == EMPTY),  # -Z
    ]
    total_faces = sum(int(mask.sum()) for mask in visible)
    if total_faces == 0:
        return ObjectMeshData(np.empty((0, 11), np.float32), np.empty(0, np.uint32), 0)

    vertices = np.empty((total_faces * 4, 11), dtype=np.float32)
    indices = np.empty(total_faces * 6, dtype=np.uint32)
    base_index = np.arange(total_faces, dtype=np.uint32) * 4
    quad_offsets = np.tile(_QUAD_INDICES, total_faces).reshape(total_faces, 6)
    indices[:] = (quad_offsets + base_index[:, None]).ravel()

    # Tabelas por material, consultadas por face.
    uv_table = np.zeros((len(obj.materials), 6, 4, 2), dtype=np.float32)
    colour_table = np.ones((len(obj.materials), 3), dtype=np.float32)
    for material_index, material in enumerate(obj.materials):
        u0, v0, u1, v1 = atlas.uv_for(material.texture)
        du, dv = u1 - u0, v1 - v0
        for face in range(6):
            base = _TOP_UVS if face == 2 else _UVS
            uv_table[material_index, face, :, 0] = u0 + base[:, 0] * du
            uv_table[material_index, face, :, 1] = v0 + base[:, 1] * dv
        colour_table[material_index] = np.asarray(material.color, dtype=np.float32) / 255.0

    current = 0
    for face in range(6):
        mask = visible[face]
        count = int(mask.sum())
        if not count:
            continue
        xs, ys, zs = np.where(mask)
        materials = blocks[xs, ys, zs]
        start = current * 4
        current += count
        rows = vertices[start:start + count * 4].reshape(count, 4, 11)
        offsets = np.stack((xs, ys, zs), axis=-1)[:, None, :]
        rows[:, :, 0:3] = _CORNERS[face] + offsets
        rows[:, :, 3:6] = _NORMALS[face]
        rows[:, :, 6:8] = uv_table[materials, face]
        rows[:, :, 8:11] = colour_table[materials][:, None, :]

    return ObjectMeshData(vertices, indices, total_faces)
