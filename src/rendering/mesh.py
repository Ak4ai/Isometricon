"""Gerenciamento de malhas e buffers OpenGL (VAO, VBO, EBO)."""

import ctypes
from typing import Optional
import OpenGL.GL as gl
import numpy as np


class Mesh:
    """Representa uma malha 3D com buffers OpenGL gerenciados (VAO, VBO, EBO)."""

    def __init__(
        self,
        vertices: np.ndarray,
        indices: Optional[np.ndarray] = None,
        usage: int = gl.GL_STATIC_DRAW,
    ):
        """Inicializa a malha e faz o upload dos dados para a GPU.

        Layout esperado de cada vértice:
            - Posição (vec3): [x, y, z]           (offset 0,  tamanho 12 bytes)
            - Normal  (vec3): [nx, ny, nz]        (offset 12, tamanho 12 bytes)
            - Cor     (vec3): [r, g, b]           (offset 24, tamanho 12 bytes)
            Stride total = 36 bytes (9 floats).

        Args:
            vertices: Array de floats (1D ou 2D) contendo os atributos dos vértices.
            indices: Array de inteiros sem sinal (uint32) para desenho indexado (opcional).
            usage: Modo de uso dos buffers (ex: GL_STATIC_DRAW, GL_DYNAMIC_DRAW).
        """
        self.usage = usage
        self.vao: int = gl.glGenVertexArrays(1)
        self.vbo: int = gl.glGenBuffers(1)
        self.ebo: Optional[int] = gl.glGenBuffers(1) if indices is not None else None

        self.index_count = 0
        self.vertex_count = 0

        self.update_buffers(vertices, indices)

    def update_buffers(
        self,
        vertices: np.ndarray,
        indices: Optional[np.ndarray] = None,
    ) -> None:
        """Atualiza os dados nos buffers de GPU."""
        v_data = np.ascontiguousarray(vertices, dtype=np.float32)
        self.vertex_count = len(v_data) // 9 if v_data.ndim == 1 else len(v_data)

        gl.glBindVertexArray(self.vao)

        # 1. Upload dos vértices no VBO
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, v_data.nbytes, v_data, self.usage)

        # 2. Upload dos índices no EBO (se fornecidos)
        if indices is not None and len(indices) > 0:
            i_data = np.ascontiguousarray(indices, dtype=np.uint32)
            self.index_count = len(i_data)
            if self.ebo is None:
                self.ebo = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, i_data.nbytes, i_data, self.usage)
        else:
            self.index_count = 0

        # 3. Configurar os ponteiros de atributos de vértices (Layout 330 core)
        stride = 9 * ctypes.sizeof(ctypes.c_float)  # 36 bytes

        # Atributo 0: aPos (vec3)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(
            0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0)
        )

        # Atributo 1: aNormal (vec3)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(
            1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(3 * 4)
        )

        # Atributo 2: aColor (vec3)
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(
            2, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(6 * 4)
        )

        # Desvincular VAO
        gl.glBindVertexArray(0)

    def draw(self) -> None:
        """Desenha a malha utilizando o pipeline OpenGL."""
        gl.glBindVertexArray(self.vao)
        if self.index_count > 0:
            gl.glDrawElements(
                gl.GL_TRIANGLES,
                self.index_count,
                gl.GL_UNSIGNED_INT,
                None,
            )
        elif self.vertex_count > 0:
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self.vertex_count)
        gl.glBindVertexArray(0)

    def delete(self) -> None:
        """Libera os buffers e VAO da memória de GPU."""
        if hasattr(self, "vao") and self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            self.vao = 0
        if hasattr(self, "vbo") and self.vbo:
            gl.glDeleteBuffers(1, [self.vbo])
            self.vbo = 0
        if hasattr(self, "ebo") and self.ebo:
            gl.glDeleteBuffers(1, [self.ebo])
            self.ebo = None

    def __del__(self) -> None:
        try:
            self.delete()
        except Exception:
            pass


class TexturedMesh:
    """Representa uma malha 3D texturizada com suporte a Texture Atlas (Layout: Pos3, Norm3, UV2, Col3 = 44 bytes)."""

    def __init__(
        self,
        vertices: np.ndarray,
        indices: Optional[np.ndarray] = None,
        usage: int = gl.GL_STATIC_DRAW,
    ):
        self.usage = usage
        self.vao: int = gl.glGenVertexArrays(1)
        self.vbo: int = gl.glGenBuffers(1)
        self.ebo: Optional[int] = gl.glGenBuffers(1) if indices is not None else None

        self.index_count = 0
        self.vertex_count = 0

        self.update_buffers(vertices, indices)

    def update_buffers(
        self,
        vertices: np.ndarray,
        indices: Optional[np.ndarray] = None,
    ) -> None:
        """Atualiza os dados nos buffers de GPU."""
        v_data = np.ascontiguousarray(vertices, dtype=np.float32)
        self.vertex_count = len(v_data) // 11 if v_data.ndim == 1 else len(v_data)

        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, v_data.nbytes, v_data, self.usage)

        if indices is not None and len(indices) > 0:
            i_data = np.ascontiguousarray(indices, dtype=np.uint32)
            self.index_count = len(i_data)
            if self.ebo is None:
                self.ebo = gl.glGenBuffers(1)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, i_data.nbytes, i_data, self.usage)
        else:
            self.index_count = 0

        # Layout: Pos(3), Normal(3), TexCoord(2), Color(3) = 11 floats (44 bytes)
        stride = 11 * ctypes.sizeof(ctypes.c_float)

        # Attr 0: aPos (vec3) -> offset 0
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))

        # Attr 1: aNormal (vec3) -> offset 12 bytes
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(3 * 4))

        # Attr 2: aTexCoord (vec2) -> offset 24 bytes
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(6 * 4))

        # Attr 3: aColor (vec3) -> offset 32 bytes
        gl.glEnableVertexAttribArray(3)
        gl.glVertexAttribPointer(3, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8 * 4))

        gl.glBindVertexArray(0)

    def draw(self) -> None:
        """Desenha a malha indexada na GPU."""
        gl.glBindVertexArray(self.vao)
        if self.index_count > 0:
            gl.glDrawElements(gl.GL_TRIANGLES, self.index_count, gl.GL_UNSIGNED_INT, None)
        elif self.vertex_count > 0:
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self.vertex_count)
        gl.glBindVertexArray(0)

    def delete(self) -> None:
        """Libera os buffers de GPU."""
        if hasattr(self, "vao") and self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            self.vao = 0
        if hasattr(self, "vbo") and self.vbo:
            gl.glDeleteBuffers(1, [self.vbo])
            self.vbo = 0
        if hasattr(self, "ebo") and self.ebo:
            gl.glDeleteBuffers(1, [self.ebo])
            self.ebo = None

    def __del__(self) -> None:
        try:
            self.delete()
        except Exception:
            pass
