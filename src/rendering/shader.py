"""Compilador e gerenciador de Shaders GLSL 330 core para PyOpenGL."""

import os
from typing import Dict, Sequence, Tuple, Union
import OpenGL.GL as gl
import numpy as np


class Shader:
    """Carrega, compila e gerencia programas de shaders GLSL."""

    # Unidade de textura fixa de samplers adicionais do shader do mundo (u_RoomMask: máscara 3D do espaço)
    EXTRA_SAMPLER_UNITS = {"u_RoomMask": 2, "u_ShadowMask": 3, "u_ShadowShapeIds": 12}

    def __init__(self, vertex_path: str, fragment_path: str):
        """Inicializa e compila o programa de shader a partir de arquivos no disco.

        Args:
            vertex_path: Caminho para o arquivo de vertex shader (.vert).
            fragment_path: Caminho para o arquivo de fragment shader (.frag).
        """
        self.vertex_path = vertex_path
        self.fragment_path = fragment_path
        self._uniform_cache: dict[str, int] = {}
        self.defines: Tuple[str, ...] = ()
        self._variants: Dict[Tuple[str, ...], Tuple[int, dict]] = {}
        self.program_id = self._build(())
        self._variants[()] = (self.program_id, self._uniform_cache)

    @staticmethod
    def _with_defines(source: str, defines: Tuple[str, ...]) -> str:
        """O código com ``#define`` de cada nome logo depois do ``#version`` (a primeira linha)."""
        if not defines:
            return source
        head, _, rest = source.partition("\n")
        return head + "\n" + "".join(f"#define {name}\n" for name in defines) + rest

    def set_defines(self, defines: Sequence[str]) -> None:
        """Troca para a variante do programa compilada com estes ``#define`` (compila na primeira vez). Os valores
        dos uniforms da variante atual passam para a nova: quem desenha não percebe a troca."""
        key = tuple(sorted(defines))
        if key == self.defines:
            return
        if key not in self._variants:
            self._variants[key] = (self._build(key), {})
        old = self.program_id
        self.program_id, self._uniform_cache = self._variants[key]
        self.defines = key
        _copy_uniforms(old, self.program_id)

    def _build(self, defines: Tuple[str, ...]) -> int:
        vertex_source = self._with_defines(self._read_source(self.vertex_path), defines)
        fragment_source = self._with_defines(self._read_source(self.fragment_path), defines)

        vert_shader = self._compile_shader(gl.GL_VERTEX_SHADER, vertex_source)
        frag_shader = self._compile_shader(gl.GL_FRAGMENT_SHADER, fragment_source)

        program_id = gl.glCreateProgram()
        gl.glAttachShader(program_id, vert_shader)
        gl.glAttachShader(program_id, frag_shader)
        gl.glLinkProgram(program_id)

        if not gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS):
            error_log = gl.glGetProgramInfoLog(program_id).decode("utf-8")
            gl.glDeleteProgram(program_id)
            gl.glDeleteShader(vert_shader)
            gl.glDeleteShader(frag_shader)
            raise RuntimeError(f"Erro ao linkar Shader Program:\n{error_log}")

        # Shaders individuais podem ser liberados após a linkagem bem-sucedida
        gl.glDeleteShader(vert_shader)
        gl.glDeleteShader(frag_shader)

        # Samplers que não são do atlas (unidade 0) precisam de unidade própria desde já: um sampler3D
        # que ficasse na 0, junto do sampler2D do atlas, faria o OpenGL recusar qualquer desenho.
        gl.glUseProgram(program_id)
        for sampler, unit in self.EXTRA_SAMPLER_UNITS.items():
            location = gl.glGetUniformLocation(program_id, sampler)
            if location >= 0:
                gl.glUniform1i(location, unit)
        gl.glUseProgram(0)
        return program_id

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

    def set_mat4_array(self, name: str, matrices: np.ndarray) -> None:
        """Envia um vetor de matrizes 4x4 float32 (N, 4, 4) para o shader."""
        loc = self.get_uniform_location(name)
        if loc != -1:
            data = np.ascontiguousarray(matrices, dtype=np.float32)
            gl.glUniformMatrix4fv(loc, len(data), gl.GL_TRUE, data)

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


_FLOAT_TYPES = {gl.GL_FLOAT: 1, gl.GL_FLOAT_VEC2: 2, gl.GL_FLOAT_VEC3: 3, gl.GL_FLOAT_VEC4: 4,
                gl.GL_FLOAT_MAT3: 9, gl.GL_FLOAT_MAT4: 16}
_INT_TYPES = {gl.GL_INT: 1, gl.GL_INT_VEC2: 2, gl.GL_INT_VEC3: 3, gl.GL_INT_VEC4: 4, gl.GL_BOOL: 1,
              gl.GL_SAMPLER_2D: 1, gl.GL_SAMPLER_3D: 1}


def _copy_uniforms(source: int, target: int) -> None:
    """Passa os valores dos uniforms ativos de um programa para outro (os que existem nos dois)."""
    import ctypes
    count = gl.glGetProgramiv(source, gl.GL_ACTIVE_UNIFORMS)
    previous = gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)
    gl.glUseProgram(target)
    for index in range(int(count)):
        name, size, kind = gl.glGetActiveUniform(source, index)
        name = name.decode() if isinstance(name, bytes) else str(name)
        base = name[:-3] if name.endswith("[0]") else name
        for element in range(int(size)):
            element_name = f"{base}[{element}]" if size > 1 else name
            src_loc = gl.glGetUniformLocation(source, element_name)
            dst_loc = gl.glGetUniformLocation(target, element_name)
            if src_loc < 0 or dst_loc < 0:
                continue
            if kind in _FLOAT_TYPES:
                n = _FLOAT_TYPES[kind]
                value = (ctypes.c_float * n)()
                gl.glGetUniformfv(source, src_loc, value)
                data = np.array(value, dtype=np.float32)
                if kind == gl.GL_FLOAT_MAT4:
                    gl.glUniformMatrix4fv(dst_loc, 1, gl.GL_FALSE, data)
                elif kind == gl.GL_FLOAT_MAT3:
                    gl.glUniformMatrix3fv(dst_loc, 1, gl.GL_FALSE, data)
                else:
                    (gl.glUniform1fv, gl.glUniform2fv, gl.glUniform3fv, gl.glUniform4fv)[n - 1](dst_loc, 1, data)
            elif kind in _INT_TYPES:
                n = _INT_TYPES[kind]
                value = (ctypes.c_int * n)()
                gl.glGetUniformiv(source, src_loc, value)
                data = np.array(value, dtype=np.int32)
                (gl.glUniform1iv, gl.glUniform2iv, gl.glUniform3iv, gl.glUniform4iv)[n - 1](dst_loc, 1, data)
    gl.glUseProgram(int(previous))
