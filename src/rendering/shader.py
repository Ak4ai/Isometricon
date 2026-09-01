"""Compilador e gerenciador de Shaders GLSL 330 core para PyOpenGL."""

import os
from typing import Sequence, Union
import OpenGL.GL as gl
import numpy as np


class Shader:
    """Carrega, compila e gerencia programas de shaders GLSL."""

    def __init__(self, vertex_path: str, fragment_path: str):
        """Inicializa e compila o programa de shader a partir de arquivos no disco.

        Args:
            vertex_path: Caminho para o arquivo de vertex shader (.vert).
            fragment_path: Caminho para o arquivo de fragment shader (.frag).
        """
        self.vertex_path = vertex_path
        self.fragment_path = fragment_path
        self._uniform_cache: dict[str, int] = {}

        vertex_source = self._read_source(vertex_path)
        fragment_source = self._read_source(fragment_path)

        vert_shader = self._compile_shader(gl.GL_VERTEX_SHADER, vertex_source)
        frag_shader = self._compile_shader(gl.GL_FRAGMENT_SHADER, fragment_source)

        self.program_id = gl.glCreateProgram()
        gl.glAttachShader(self.program_id, vert_shader)
        gl.glAttachShader(self.program_id, frag_shader)
        gl.glLinkProgram(self.program_id)

        if not gl.glGetProgramiv(self.program_id, gl.GL_LINK_STATUS):
            error_log = gl.glGetProgramInfoLog(self.program_id).decode("utf-8")
            gl.glDeleteProgram(self.program_id)
            gl.glDeleteShader(vert_shader)
            gl.glDeleteShader(frag_shader)
            raise RuntimeError(f"Erro ao linkar Shader Program:\n{error_log}")

        # Shaders individuais podem ser liberados após a linkagem bem-sucedida
        gl.glDeleteShader(vert_shader)
        gl.glDeleteShader(frag_shader)

    def _read_source(self, path: str) -> str:
        """Lê o conteúdo de um arquivo de shader."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Arquivo de shader não encontrado: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _compile_shader(self, shader_type: int, source: str) -> int:
        """Compila um shader GLSL individual e verifica erros."""
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)

        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            error_log = gl.glGetShaderInfoLog(shader).decode("utf-8")
            gl.glDeleteShader(shader)
            tipo = "Vertex" if shader_type == gl.GL_VERTEX_SHADER else "Fragment"
            raise RuntimeError(f"Erro ao compilar {tipo} Shader ({self.vertex_path if shader_type == gl.GL_VERTEX_SHADER else self.fragment_path}):\n{error_log}")
        return shader

    def use(self) -> None:
        """Ativa este programa de shader para renderização."""
        gl.glUseProgram(self.program_id)

    def unbind(self) -> None:
        """Desativa o programa de shader."""
        gl.glUseProgram(0)

    def __enter__(self) -> "Shader":
        self.use()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.unbind()

    def get_uniform_location(self, name: str) -> int:
        """Busca e armazena em cache o local da variável uniform pelo nome."""
        if name not in self._uniform_cache:
            loc = gl.glGetUniformLocation(self.program_id, name)
            self._uniform_cache[name] = loc
        return self._uniform_cache[name]

    def set_mat4(self, name: str, matrix: np.ndarray) -> None:
        """Envia uma matriz 4x4 float32 para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl.glUniformMatrix4fv(loc, 1, gl.GL_TRUE, np.ascontiguousarray(matrix, dtype=np.float32))

    def set_mat3(self, name: str, matrix: np.ndarray) -> None:
        """Envia uma matriz 3x3 float32 para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl.glUniformMatrix3fv(loc, 1, gl.GL_TRUE, np.ascontiguousarray(matrix, dtype=np.float32))

    def set_vec4(
        self,
        name: str,
        x: Union[float, Sequence[float], np.ndarray],
        y: float = 0.0,
        z: float = 0.0,
        w: float = 1.0,
    ) -> None:
        """Envia um vetor 4D para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            if isinstance(x, (np.ndarray, list, tuple)):
                gl.glUniform4f(loc, float(x[0]), float(x[1]), float(x[2]), float(x[3]))
            else:
                gl.glUniform4f(loc, float(x), float(y), float(z), float(w))

    def set_vec3(
        self,
        name: str,
        x: Union[float, Sequence[float], np.ndarray],
        y: float = 0.0,
        z: float = 0.0,
    ) -> None:
        """Envia um vetor 3D para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            if isinstance(x, (np.ndarray, list, tuple)):
                gl.glUniform3f(loc, float(x[0]), float(x[1]), float(x[2]))
            else:
                gl.glUniform3f(loc, float(x), float(y), float(z))

    def set_vec2(
        self,
        name: str,
        x: Union[float, Sequence[float], np.ndarray],
        y: float = 0.0,
    ) -> None:
        """Envia um vetor 2D para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            if isinstance(x, (np.ndarray, list, tuple)):
                gl.glUniform2f(loc, float(x[0]), float(x[1]))
            else:
                gl.glUniform2f(loc, float(x), float(y))

    def set_float(self, name: str, value: float) -> None:
        """Envia um valor float para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl.glUniform1f(loc, float(value))

    def set_int(self, name: str, value: int) -> None:
        """Envia um valor inteiro para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl.glUniform1i(loc, int(value))

    def set_bool(self, name: str, value: bool) -> None:
        """Envia um valor booleano para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl.glUniform1i(loc, 1 if value else 0)

    def delete(self) -> None:
        """Libera a memória da GPU ocupada pelo programa de shader."""
        if hasattr(self, "program_id") and self.program_id:
            gl.glDeleteProgram(self.program_id)
            self.program_id = 0
            self._uniform_cache.clear()

    def __del__(self) -> None:
        # Tenta liberar recursos com segurança se o contexto ainda existir
        try:
            self.delete()
        except Exception:
            pass
