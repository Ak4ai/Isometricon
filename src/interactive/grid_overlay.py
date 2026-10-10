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
_LOCAL_Y = np.arange(Chunk3D.SIZE, dtype=np.int32)[None, :, None]
_SURFACE_LUT = np.zeros(256, dtype=bool)
_SURFACE_LUT[[int(block) for block in TACTICAL_SURFACE_BLOCKS]] = True
_BLOCKER_LUT = np.zeros(256, dtype=bool)
_BLOCKER_LUT[[int(block) for block in TACTICAL_SURFACE_BLOCKERS]] = True
_NO_HEIGHT = np.iinfo(np.int32).min


def _build_sparse_surface_grid_vertices(
    chunks: Mapping[tuple[int, int, int], Chunk3D],
    epsilon: float,
) -> np.ndarray:
    """Constrói a grade sem alocar a área entre regiões muito distantes."""

    heights: dict[tuple[int, int], int] = {}
    blocker_heights: dict[tuple[int, int], int] = {}

    for (chunk_x, chunk_y, chunk_z), chunk in chunks.items():
        origin_x = chunk_x * Chunk3D.SIZE
        origin_y = chunk_y * Chunk3D.SIZE
        origin_z = chunk_z * Chunk3D.SIZE
        for mask, target in (
            (_SURFACE_LUT[chunk.blocks], heights),
            (_BLOCKER_LUT[chunk.blocks], blocker_heights),
        ):
            if not mask.any():
                continue
            local_heights = np.where(mask, _LOCAL_Y, -1).max(axis=1)
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


def _grid_edges(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    *,
    x_offset: int = 0,
    z_offset: int = 0,
) -> np.ndarray:
    """Converte vetores de início/fim em pares de vértices ``GL_LINES``."""

    return np.column_stack(
        (x, y, z, x + x_offset, y, z + z_offset)
    ).astype(np.float32, copy=False).reshape(-1, 2, 3)


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

    chunk_columns = {(chunk_x, chunk_z) for chunk_x, _, chunk_z in chunks}
    min_chunk_x = min(chunk_x for chunk_x, _ in chunk_columns)
    max_chunk_x = max(chunk_x for chunk_x, _ in chunk_columns)
    min_chunk_z = min(chunk_z for _, chunk_z in chunk_columns)
    max_chunk_z = max(chunk_z for _, chunk_z in chunk_columns)
    width = (max_chunk_x - min_chunk_x + 1) * Chunk3D.SIZE
    depth = (max_chunk_z - min_chunk_z + 1) * Chunk3D.SIZE

    # O streaming mantém uma região contígua. Para consumidores que forneçam
    # ilhas muito distantes, preservar o caminho esparso evita uma matriz
    # proporcional à distância entre elas.
    if width * depth > len(chunk_columns) * Chunk3D.SIZE**2 * 4:
        return _build_sparse_surface_grid_vertices(chunks, epsilon)

    heights = np.full((width, depth), _NO_HEIGHT, dtype=np.int32)
    blocker_heights = np.full((width, depth), _NO_HEIGHT, dtype=np.int32)
    for (chunk_x, chunk_y, chunk_z), chunk in chunks.items():
        start_x = (chunk_x - min_chunk_x) * Chunk3D.SIZE
        start_z = (chunk_z - min_chunk_z) * Chunk3D.SIZE
        area = np.s_[
            start_x:start_x + Chunk3D.SIZE,
            start_z:start_z + Chunk3D.SIZE,
        ]
        origin_y = chunk_y * Chunk3D.SIZE
        for lookup, target in (
            (_SURFACE_LUT, heights),
            (_BLOCKER_LUT, blocker_heights),
        ):
            mask = lookup[chunk.blocks]
            if mask.any():
                local_heights = np.where(mask, _LOCAL_Y, -1).max(axis=1)
                world_heights = np.where(
                    local_heights >= 0,
                    np.maximum(local_heights + origin_y, -1),
                    _NO_HEIGHT,
                )
                np.maximum(target[area], world_heights, out=target[area])

    valid = (heights != _NO_HEIGHT) & (blocker_heights <= heights)
    local_x, local_z = np.nonzero(valid)
    if len(local_x) == 0:
        return np.empty((0, 3), dtype=np.float32)

    x = local_x.astype(np.float32) + np.float32(min_chunk_x * Chunk3D.SIZE)
    z = local_z.astype(np.float32) + np.float32(min_chunk_z * Chunk3D.SIZE)
    y = (
        heights[local_x, local_z].astype(np.float64) + 1.0 + float(epsilon)
    ).astype(np.float32)

    same_height_east = np.zeros_like(valid)
    same_height_east[:-1, :] = (
        valid[:-1, :] & valid[1:, :] & (heights[:-1, :] == heights[1:, :])
    )
    same_height_south = np.zeros_like(valid)
    same_height_south[:, :-1] = (
        valid[:, :-1] & valid[:, 1:] & (heights[:, :-1] == heights[:, 1:])
    )
    keep_east = ~same_height_east[local_x, local_z]
    keep_south = ~same_height_south[local_x, local_z]

    edges = [
        _grid_edges(x, y, z, x_offset=1),
        _grid_edges(x, y, z, z_offset=1),
        _grid_edges(x[keep_east] + 1, y[keep_east], z[keep_east], z_offset=1),
        _grid_edges(x[keep_south], y[keep_south], z[keep_south] + 1, x_offset=1),
    ]
    return np.concatenate(edges, axis=0).reshape(-1, 3)


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
        self._pending_chunk_revision: int | None = None
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

    def should_sync(self, revision: int) -> bool:
        """Coalesce revisões consecutivas até que uma persista por dois frames."""

        if not self.needs_sync(revision):
            self._pending_chunk_revision = None
            return False
        if revision == self._pending_chunk_revision:
            return True
        self._pending_chunk_revision = revision
        return False

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
        self._pending_chunk_revision = None
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
