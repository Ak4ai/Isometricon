"""Caixa delimitadora do objeto selecionado (GL_LINES, shader da grade)."""

from __future__ import annotations

import os

import numpy as np
import OpenGL.GL as gl

from src.math import mat4_scale, mat4_translate
from src.rendering.shader import Shader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SelectionBoxRenderer:
    def __init__(self) -> None:
        self.shader = Shader(os.path.join(PROJECT_ROOT, "assets", "shaders", "grid.vert"),
                             os.path.join(PROJECT_ROOT, "assets", "shaders", "grid.frag"))
        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        vertices = np.array([
            0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1,
            0, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1,
        ], dtype=np.float32)
        edges = np.array([
            0, 1, 1, 2, 2, 3, 3, 0,
            4, 5, 5, 6, 6, 7, 7, 4,
            0, 4, 1, 5, 2, 6, 3, 7,
        ], dtype=np.uint32)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, None)
        self.ebo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, edges.nbytes, edges, gl.GL_STATIC_DRAW)
        gl.glBindVertexArray(0)
        self.index_count = len(edges)

    def render(self, projection: np.ndarray, view: np.ndarray, model: np.ndarray,
               low: tuple[int, int, int], high: tuple[int, int, int],
               colour: tuple[float, float, float] = (1.0, 0.85, 0.25)) -> None:
        size = tuple(max(1, high[i] - low[i] + 1) for i in range(3))
        final_model = model @ mat4_translate(float(low[0]), float(low[1]), float(low[2])) @ mat4_scale(*size)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDepthMask(gl.GL_FALSE)
        self.shader.use()
        self.shader.set_mat4("u_Model", final_model)
        self.shader.set_mat4("u_View", view)
        self.shader.set_mat4("u_Projection", projection)
        self.shader.set_vec4("u_GridColor", *colour, 1.0)
        gl.glBindVertexArray(self.vao)
        gl.glDrawElements(gl.GL_LINES, self.index_count, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)

    def delete(self) -> None:
        gl.glDeleteVertexArrays(1, [self.vao])
        gl.glDeleteBuffers(2, [self.vbo, self.ebo])
        self.shader.delete()
