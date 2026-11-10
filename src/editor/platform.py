"""Renderizador da plataforma de edição (shader próprio, um único draw)."""

from __future__ import annotations

import ctypes
import os

import numpy as np
import OpenGL.GL as gl

from src.math import mat4_scale, mat4_translate
from src.rendering.shader import Shader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PlatformRenderer:
    """Desenha a superfície, a grade e a borda da área de edição."""

    def __init__(self) -> None:
        self.shader = Shader(
            os.path.join(PROJECT_ROOT, "assets", "shaders", "platform.vert"),
            os.path.join(PROJECT_ROOT, "assets", "shaders", "platform.frag"),
        )
        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.ebo = gl.glGenBuffers(1)
        vertices = np.array([
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            1.0, 0.0, 1.0,
            0.0, 0.0, 1.0,
        ], dtype=np.float32)
        indices = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 12, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)

    def render(self, projection: np.ndarray, view: np.ndarray, model: np.ndarray,
               size: tuple[int, int], cursor: tuple[int, int] | None, time: float,
               show_grid: bool = True) -> None:
        width, depth = float(size[0]), float(size[1])
        platform_model = model @ mat4_translate(0.0, -0.01, 0.0) @ mat4_scale(width, 1.0, depth)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_FALSE)
        self.shader.use()
        self.shader.set_mat4("u_Model", platform_model)
        self.shader.set_mat4("u_View", view)
        self.shader.set_mat4("u_Projection", projection)
        self.shader.set_vec2("u_Size", width, depth)
        self.shader.set_vec4("u_BaseColor", 0.075, 0.100, 0.140, 0.72)
        self.shader.set_vec4("u_LineColor", 0.45, 0.68, 0.82, 0.95)
        self.shader.set_vec4("u_BorderColor", 1.0, 0.76, 0.22, 1.0)
        self.shader.set_vec4("u_CursorColor", 1.0, 0.95, 0.40, 0.72)
        if cursor is None:
            self.shader.set_vec2("u_Cursor", -100.0, -100.0)
            self.shader.set_float("u_CursorOn", 0.0)
        else:
            self.shader.set_vec2("u_Cursor", float(cursor[0]), float(cursor[1]))
            self.shader.set_float("u_CursorOn", 1.0)
        self.shader.set_float("u_GridOn", 1.0 if show_grid else 0.0)
        self.shader.set_float("u_Time", float(time))
        gl.glBindVertexArray(self.vao)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def delete(self) -> None:
        gl.glDeleteVertexArrays(1, [self.vao])
        gl.glDeleteBuffers(2, [self.vbo, self.ebo])
        self.shader.delete()
