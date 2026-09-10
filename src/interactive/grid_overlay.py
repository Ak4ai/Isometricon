"""Overlay de grade tática que acompanha a superfície dos chunks carregados."""

from __future__ import annotations

import os
from collections.abc import Mapping
from time import perf_counter

import numpy as np
import OpenGL.GL as gl

from src.interaction.surface import TACTICAL_SURFACE_BLOCKS, TACTICAL_SURFACE_BLOCKERS
from src.rendering.shader import Shader
from src.world import Chunk3D


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SURFACE_EPSILON = 0.002


def build_surface_grid_vertices(
    chunks: Mapping[tuple[int, int, int], Chunk3D],
    *,
    epsilon: float = SURFACE_EPSILON,
) -> np.ndarray:
    """Constrói segmentos ``GL_LINES`` sobre as células táticas carregadas.

    Cada contorno permanece horizontal na altura da própria célula. Em uma
    borda entre alturas diferentes os dois contornos são preservados; assim não
    há uma linha diagonal atravessando a face lateral de um voxel. Segmentos
    idênticos em terreno plano são compartilhados.
    """

    if not chunks:
        return np.empty((0, 3), dtype=np.float32)

    support_values = np.fromiter(TACTICAL_SURFACE_BLOCKS, dtype=np.uint8)
    blocker_values = np.fromiter(TACTICAL_SURFACE_BLOCKERS, dtype=np.uint8)
    heights: dict[tuple[int, int], int] = {}
    blocker_heights: dict[tuple[int, int], int] = {}

    for (chunk_x, chunk_y, chunk_z), chunk in chunks.items():
        walkable = np.isin(chunk.blocks, support_values)
        origin_x = chunk_x * Chunk3D.SIZE
        origin_y = chunk_y * Chunk3D.SIZE
        origin_z = chunk_z * Chunk3D.SIZE
        local_y = np.arange(Chunk3D.SIZE, dtype=np.int32)[None, :, None]
        for mask, target in ((walkable, heights), (np.isin(chunk.blocks, blocker_values), blocker_heights)):
            if not mask.any():
                continue
            local_heights = np.where(mask, local_y, -1).max(axis=1)
            for local_x, local_z in np.argwhere(local_heights >= 0):
                position = (origin_x + int(local_x), origin_z + int(local_z))
                height = origin_y + int(local_heights[local_x, local_z])
                target[position] = max(target.get(position, -1), height)

    segments: set[tuple[tuple[float, float, float], tuple[float, float, float]]] = set()
    for (x, z), height in heights.items():
        if blocker_heights.get((x, z), -1) > height:
            continue
        y = float(height + 1) + float(epsilon)
        corners = ((float(x), y, float(z)), (float(x + 1), y, float(z)),
                   (float(x + 1), y, float(z + 1)), (float(x), y, float(z + 1)))
        for start, end in zip(corners, corners[1:] + corners[:1]):
            segments.add((start, end) if start <= end else (end, start))

    if not segments:
        return np.empty((0, 3), dtype=np.float32)
    return np.asarray(
        [point for segment in sorted(segments) for point in segment], dtype=np.float32
    ).reshape(-1, 3)


class GridOverlayRenderer:
    """Mantém um VBO dedicado e desenha a grade em uma única chamada."""

    def __init__(self, *, color: tuple[float, float, float, float] = (0.06, 0.08, 0.11, 0.72)) -> None:
        self.shader = Shader(
            os.path.join(PROJECT_ROOT, "assets", "shaders", "grid.vert"),
            os.path.join(PROJECT_ROOT, "assets", "shaders", "grid.frag"),
        )
        self.color = color
        self.visible = True
        self.vertex_count = 0
        self._chunk_revision = -1
        self.last_rebuild_cpu_ms = 0.0
        self.last_render_cpu_ms = 0.0

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, 0, None, gl.GL_DYNAMIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 3 * 4, None)
        gl.glBindVertexArray(0)

    def set_visible(self, visible: bool) -> None:
        self.visible = bool(visible)

    def toggle_visibility(self) -> bool:
        self.visible = not self.visible
        return self.visible

    def needs_sync(self, revision: int) -> bool:
        """Indica se é necessário obter o snapshot do WorldManager neste frame."""
        return self.visible and revision != self._chunk_revision

    def sync_chunks(self, chunks: Mapping[tuple[int, int, int], Chunk3D], revision: int) -> bool:
        """Atualiza o VBO somente quando o streaming alterou os chunks lógicos."""

        if not self.needs_sync(revision):
            return False
        started = perf_counter()
        vertices = build_surface_grid_vertices(chunks)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)
        self.vertex_count = len(vertices)
        self._chunk_revision = revision
        self.last_rebuild_cpu_ms = (perf_counter() - started) * 1000.0
        return True

    def render(self, projection: np.ndarray, view: np.ndarray, model: np.ndarray) -> int:
        """Desenha a grade com depth test ativo; retorna os vértices submetidos."""

        if not self.visible or self.vertex_count == 0:
            self.last_render_cpu_ms = 0.0
            return 0
        started = perf_counter()
        self.shader.use()
        self.shader.set_mat4("u_Projection", projection)
        self.shader.set_mat4("u_View", view)
        self.shader.set_mat4("u_Model", model)
        self.shader.set_vec4("u_GridColor", *self.color)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glLineWidth(1.0)
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_LINES, 0, self.vertex_count)
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        self.last_render_cpu_ms = (perf_counter() - started) * 1000.0
        return self.vertex_count

    def delete(self) -> None:
        if getattr(self, "vao", 0):
            gl.glDeleteVertexArrays(1, [self.vao])
            gl.glDeleteBuffers(1, [self.vbo])
            self.vao = 0
        self.shader.delete()
