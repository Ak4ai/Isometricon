"""Sistema de renderização de destaque (Highlight) para blocos do grid no Isometricon."""

import math
import os
from typing import Optional, Tuple

import numpy as np
import OpenGL.GL as gl

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

from src.rendering.shader import Shader




class BlockHighlightRenderer:
    """Renderiza um efeito de destaque reluzente sobre um bloco da grade 3D."""

    def __init__(self) -> None:
        vert_path = os.path.join(PROJECT_ROOT, "assets", "shaders", "highlight.vert")
        frag_path = os.path.join(PROJECT_ROOT, "assets", "shaders", "highlight.frag")

        self.shader = Shader(vert_path, frag_path)
        self._init_mesh()

    def _init_mesh(self) -> None:
        """Cria uma malha unitária [0, 1]³ contendo as faces e linhas de contorno."""
        # Vértices de um cubo unitário [0, 1]³
        vertices = np.array([
            # Top face (Y = 1.0)
            0.0, 1.0, 0.0,
            1.0, 1.0, 0.0,
            1.0, 1.0, 1.0,
            0.0, 1.0, 1.0,
            # Bottom face (Y = 0.0)
            0.0, 0.0, 0.0,
            1.0, 0.0, 0.0,
            1.0, 0.0, 1.0,
            0.0, 0.0, 1.0,
        ], dtype=np.float32)

        # Índices para faces sólidas / preenchimento translúcido
        # Focamos principalmente no topo e laterais
        face_indices = np.array([
            # Top face
            0, 1, 2,  2, 3, 0,
            # Front face (+Z)
            3, 2, 6,  6, 7, 3,
            # Back face (-Z)
            1, 0, 4,  4, 5, 1,
            # Left face (-X)
            0, 3, 7,  7, 4, 0,
            # Right face (+X)
            2, 1, 5,  5, 6, 2,
        ], dtype=np.uint32)

        # Índices para linhas de contorno (wireframe brilhante)
        line_indices = np.array([
            # Top square
            0, 1,  1, 2,  2, 3,  3, 0,
            # Bottom square
            4, 5,  5, 6,  6, 7,  7, 4,
            # Vertical pillars
            0, 4,  1, 5,  2, 6,  3, 7,
        ], dtype=np.uint32)

        self.vao = gl.glGenVertexArrays(1)
        self.vbo = gl.glGenBuffers(1)
        self.ebo_faces = gl.glGenBuffers(1)
        self.ebo_lines = gl.glGenBuffers(1)

        gl.glBindVertexArray(self.vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_faces)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, face_indices.nbytes, face_indices, gl.GL_STATIC_DRAW)

        # Attr 0: aPos (vec3)
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 3 * 4, None)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_lines)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, line_indices.nbytes, line_indices, gl.GL_STATIC_DRAW)

        gl.glBindVertexArray(0)

        self.face_count = len(face_indices)
        self.line_count = len(line_indices)

    def render(
        self,
        view_matrix: np.ndarray,
        projection_matrix: np.ndarray,
        model_matrix: np.ndarray,
        block_x: int,
        block_y: int,
        block_z: int,
        time: float = 0.0,
        base_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> None:
        """Renderiza o destaque reluzente no bloco com pulsação suave em branco."""
        # Pulso harmônico de brilho: oscila entre 0.40 e 0.85
        pulse = 0.60 + 0.35 * math.sin(time * 6.0)

        r, g, b = base_color

        self.shader.use()
        self.shader.set_mat4("u_View", view_matrix)
        self.shader.set_mat4("u_Projection", projection_matrix)
        self.shader.set_mat4("u_Model", model_matrix)
        self.shader.set_vec3("u_BlockPosition", float(block_x), float(block_y), float(block_z))

        # Configura blending aditivo/translúcido
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
        gl.glDepthMask(gl.GL_FALSE)  # Não grava no depth buffer para overlay translúcido limpo

        gl.glBindVertexArray(self.vao)

        # 1. Desenha as faces superiores/laterais com brilho suave
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_faces)
        face_alpha = 0.45 * pulse
        self.shader.set_vec4("u_HighlightColor", r, g, b, face_alpha)
        gl.glDrawElements(gl.GL_TRIANGLES, self.face_count, gl.GL_UNSIGNED_INT, None)

        # 2. Desenha a borda da caixa com linhas brancas bem luminosas
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ebo_lines)
        line_alpha = 0.85 * pulse
        self.shader.set_vec4("u_HighlightColor", r, g, b, line_alpha)
        gl.glDrawElements(gl.GL_LINES, self.line_count, gl.GL_UNSIGNED_INT, None)

        # Restaura estado OpenGL
        gl.glDepthMask(gl.GL_TRUE)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_BLEND)
        gl.glBindVertexArray(0)


    def delete(self) -> None:
        """Libera os recursos OpenGL alocados."""
        if hasattr(self, "vao") and self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
            gl.glDeleteBuffers(1, [self.vbo])
            gl.glDeleteBuffers(1, [self.ebo_faces])
            gl.glDeleteBuffers(1, [self.ebo_lines])
            self.vao = 0
        if hasattr(self, "shader") and self.shader:
            self.shader.delete()
