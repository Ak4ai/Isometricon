"""Uma imagem 2D desenhada sobre a cena, em pixels da janela (painéis de interface)."""
from __future__ import annotations

import ctypes
import os
from typing import Any

import numpy as np
import OpenGL.GL as gl

from src.math.matrix import mat4_ortho
from src.rendering.shader import Shader

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class HudQuad:
    """Textura RGBA com um quad do seu tamanho; ``set_image`` troca a imagem, ``draw`` a posiciona."""

    def __init__(self) -> None:
        self.shader = Shader(os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.vert"),
                             os.path.join(PROJECT_ROOT, "assets", "shaders", "hud.frag"))
        self.size = (0, 0)
        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.ebo = gl.glGenBuffers(1)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, 16 * 4, None, gl.GL_DYNAMIC_DRAW)
        indices = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, gl.GL_STATIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 16, None)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 16, ctypes.c_void_p(8))
        gl.glBindVertexArray(0)
        self.texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

    def set_image(self, image: Any) -> None:
        """Envia uma imagem PIL RGBA como textura."""
        data = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        self.size = (image.width, image.height)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, image.width, image.height, 0,
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)

    def draw(self, x: float, y: float, window_width: int, window_height: int) -> None:
        """Desenha a imagem com o canto superior esquerdo em (x, y), por cima da cena."""
        w, h = self.size
        if not w or not h:
            return
        vertices = np.array([x, y, 0.0, 0.0,  x + w, y, 1.0, 0.0,  x + w, y + h, 1.0, 1.0,  x, y + h, 0.0, 1.0],
                            dtype=np.float32)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDepthMask(gl.GL_FALSE)
        self.shader.use()
        self.shader.set_mat4("u_Projection", mat4_ortho(0.0, float(window_width), float(window_height), 0.0, -1.0, 1.0))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture)
        self.shader.set_int("u_Texture", 0)
        gl.glBindVertexArray(self.vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferSubData(gl.GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)
        gl.glDrawElements(gl.GL_TRIANGLES, 6, gl.GL_UNSIGNED_INT, None)
        gl.glBindVertexArray(0)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_BLEND)

    def delete(self) -> None:
        gl.glDeleteVertexArrays(1, [self.vao])
        gl.glDeleteBuffers(2, [self.vbo, self.ebo])
        gl.glDeleteTextures(1, [self.texture])
