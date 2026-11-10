"""Mundo estático jogável a partir de um mapa salvo no editor.

Renderiza o volume base e as construções, e implementa ``get_block_at`` para o
token/colisão. É o caminho de ``--terrain --map=arquivo.json``.
"""

from __future__ import annotations

import os

import numpy as np
import OpenGL.GL as gl

from src.editor.map_project import MapProject
from src.editor.material_atlas import MaterialAtlas
from src.editor.object_mesher import ObjectMeshData, build_mesh_data
from src.math import mat4_translate
from src.rendering.mesh import TexturedMesh
from src.world import BlockType


class MapWorld:
    def __init__(self, path: str | os.PathLike, create_gl: bool = True) -> None:
        self.project = MapProject.load(path)
        self.create_gl = create_gl
        self.atlas = MaterialAtlas(create_gl=create_gl)
        self.mesh: TexturedMesh | None = None
        self.mesh_data: ObjectMeshData | None = None
        self.object_meshes: list[tuple[object, TexturedMesh | None]] = []
        if create_gl:
            self._rebuild()

    @property
    def size(self) -> tuple[int, int, int]:
        return self.project.size

    def _rebuild(self) -> None:
        self.mesh_data = build_mesh_data(self.project.base, self.atlas)
        if self.mesh_data.vertex_count:
            self.mesh = TexturedMesh(self.mesh_data.vertices.flatten(), self.mesh_data.indices)
        for index, placed in enumerate(self.project.objects):
            data = build_mesh_data(placed.rendered_object(), self.atlas)
            mesh = TexturedMesh(data.vertices.flatten(), data.indices) if data.vertex_count else None
            self.object_meshes.append((placed, mesh))

    # Contrato mínimo de mundo para o token / raycast.
    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        return BlockType.STONE if self.project.occupied(int(x), int(y), int(z)) else BlockType.AIR

    def get_top_solid_block(self, x: int, z: int) -> int:
        for y in range(self.size[1] - 1, -1, -1):
            if self.project.occupied(int(x), int(y), int(z)):
                return y
        return -1

    def get_height(self, x: float, z: float) -> int:
        return max(0, self.get_top_solid_block(int(np.floor(x)), int(np.floor(z))))

    def spawn_position(self) -> tuple[float, float, float]:
        x = self.size[0] // 2
        z = self.size[2] // 2
        top = self.get_top_solid_block(x, z)
        return float(x) + 0.5, float(top) + 1.0, float(z) + 0.5

    def render(self, shader, model: np.ndarray) -> None:
        if not self.create_gl:
            return
        shader.use()
        shader.set_mat4("u_Model", model)
        shader.set_bool("u_Skinned", False)
        shader.set_bool("u_UndergroundMode", False)
        shader.set_bool("u_WaterMode", False)
        shader.set_int("u_CutawayPass", 0)
        shader.set_float("u_Vitiligo", 0.0)
        shader.set_int("u_Underwear", 0)
        shader.set_float("u_Alpha", 1.0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.atlas.texture_id)
        shader.set_int("u_TextureAtlas", 0)
        if self.mesh is not None:
            self.mesh.draw()
        for placed, mesh in self.object_meshes:
            if mesh is not None:
                shader.set_mat4("u_Model", model @ mat4_translate(*placed.position))
                mesh.draw()

    def delete(self) -> None:
        if self.mesh is not None:
            self.mesh.delete()
            self.mesh = None
        for _, mesh in self.object_meshes:
            if mesh is not None:
                mesh.delete()
        self.object_meshes.clear()
        self.atlas.delete()
