"""HUD de coordenadas em segmentos, independente de fontes externas."""

from __future__ import annotations

import os
import math

import numpy as np
import OpenGL.GL as gl

from src.rendering.shader import Shader


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg",
    "4": "bcfg", "5": "acdfg", "6": "acdefg", "7": "abc",
    "8": "abcdefg", "9": "abcdfg",
}
_SEGMENT_POINTS = {
    "a": ((0, 0), (6, 0)), "b": ((6, 0), (6, 8)),
    "c": ((6, 8), (6, 16)), "d": ((0, 16), (6, 16)),
    "e": ((0, 8), (0, 16)), "f": ((0, 0), (0, 8)),
    "g": ((0, 8), (6, 8)),
}


def _glyph_vertices(char: str, x: float, y: float, scale: float) -> list[tuple[float, float]]:
    if char == "X":
        return [(x, y), (x + 6 * scale, y + 16 * scale),
                (x + 6 * scale, y), (x, y + 16 * scale)]
    if char == "Y":
        return [(x, y), (x + 3 * scale, y + 8 * scale),
                (x + 6 * scale, y), (x + 3 * scale, y + 8 * scale),
                (x + 3 * scale, y + 8 * scale), (x + 3 * scale, y + 16 * scale)]
    if char == "Z":
        return [(x, y), (x + 6 * scale, y),
                (x + 6 * scale, y), (x, y + 16 * scale),
                (x, y + 16 * scale), (x + 6 * scale, y + 16 * scale)]
    if char in _SEGMENTS:
        segments = _SEGMENTS[char]
    elif char == "-":
        segments = "g"
    elif char == ".":
        return [(x + 5 * scale, y + 16 * scale), (x + 6 * scale, y + 16 * scale)]
    else:
        return []

    vertices: list[tuple[float, float]] = []
    for segment in segments:
        (x0, y0), (x1, y1) = _SEGMENT_POINTS[segment]
        vertices.extend([
            (x + x0 * scale, y + y0 * scale),
            (x + x1 * scale, y + y1 * scale),
        ])
    return vertices


class CoordinateOverlayRenderer:
    """Desenha a posição do token no canto superior esquerdo da janela."""

    def __init__(self) -> None:
        self.shader = Shader(
            os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.vert"),
            os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.frag"),
        )
        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.vertex_count = 0
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 2 * 4, None)
        gl.glBindVertexArray(0)

    def _build_vertices(self, position: np.ndarray) -> np.ndarray:
        values = f"X:{position[0]:.1f} Y:{position[1]:.1f} Z:{position[2]:.1f}"
        vertices: list[tuple[float, float]] = []
        cursor_x = 14.0
        cursor_y = 14.0
        scale = 1.25
        for char in values:
            if char == " ":
                cursor_x += 5 * scale
                continue
            vertices.extend(_glyph_vertices(char, cursor_x, cursor_y, scale))
            cursor_x += 9 * scale
        return np.asarray(vertices, dtype=np.float32).reshape(-1, 2)

    def render(self, viewport_width: int, viewport_height: int, position: np.ndarray) -> None:
        vertices = self._build_vertices(position)
        self.vertex_count = len(vertices)
        if self.vertex_count == 0:
            return

        self.shader.use()
        self.shader.set_vec2("u_Viewport", float(viewport_width), float(viewport_height))
        self.shader.set_vec4("u_Color", 0.95, 0.82, 0.30, 1.0)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)
        gl.glDrawArrays(gl.GL_LINES, 0, self.vertex_count)
        gl.glBindVertexArray(0)
        gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST)

    def delete(self) -> None:
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            gl.glDeleteBuffers(1, [self.vbo])
            self.vao = 0
        self.shader.delete()
