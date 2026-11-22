"""Diagnóstico do contexto OpenGL e das unidades de textura.

Ativado por ``--gl-log`` (ou ``ISOMETRICON_GL_LOG=1``). Não altera o desenho;
serve para explicar por que uma pipeline caiu para software.
"""

from __future__ import annotations

import os
import sys

import OpenGL.GL as gl


def enabled() -> bool:
    return "--gl-log" in sys.argv or bool(os.environ.get("ISOMETRICON_GL_LOG"))


def _gl_string(name: int) -> str:
    value = gl.glGetString(name)
    if value is None:
        return "?"
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def log_context(prefix: str = "[GL]") -> None:
    if not enabled():
        return
    print(f"{prefix} Vendor: {_gl_string(gl.GL_VENDOR)}")
    print(f"{prefix} Renderer: {_gl_string(gl.GL_RENDERER)}")
    print(f"{prefix} Version: {_gl_string(gl.GL_VERSION)}")
    print(f"{prefix} GLSL: {_gl_string(gl.GL_SHADING_LANGUAGE_VERSION)}")
    for name in (
        "GL_MAX_TEXTURE_IMAGE_UNITS",
        "GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS",
        "GL_MAX_3D_TEXTURE_SIZE",
        "GL_MAX_ARRAY_TEXTURE_LAYERS",
    ):
        print(f"{prefix} {name}: {gl.glGetIntegerv(getattr(gl, name))}")


def check_error(label: str) -> int:
    """Consome e registra o próximo erro OpenGL; retorna o código (0 = nenhum)."""
    code = gl.glGetError()
    if code and enabled():
        print(f"[GL] erro 0x{code:04x} em {label}")
    return code


def sampler_type_name(value: int) -> str:
    return {
        gl.GL_SAMPLER_2D: "sampler2D",
        gl.GL_SAMPLER_3D: "sampler3D",
        gl.GL_SAMPLER_2D_ARRAY: "sampler2DArray",
        gl.GL_SAMPLER_CUBE: "samplerCube",
    }.get(value, f"type {value}")


def log_samplers(program_id: int, units: dict[str, int], label: str = "shader") -> None:
    if not enabled():
        return
    print(f"[GL] {label}: " + ", ".join(f"{name}={unit}" for name, unit in sorted(units.items())))


def log_texture_unit(unit: int, label: str, target: int = gl.GL_TEXTURE_2D_ARRAY) -> None:
    """Mostra qual textura está ligada numa unidade e se ela está completa."""
    if not enabled():
        return
    previous = gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)
    gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
    if target == gl.GL_TEXTURE_2D:
        binding_name = gl.GL_TEXTURE_BINDING_2D
    else:
        binding_name = gl.GL_TEXTURE_BINDING_2D_ARRAY
    texture = gl.glGetIntegerv(binding_name)
    if target != gl.GL_TEXTURE_2D:
        width = gl.glGetTexLevelParameteriv(target, 0, gl.GL_TEXTURE_WIDTH) if texture else 0
        height = gl.glGetTexLevelParameteriv(target, 0, gl.GL_TEXTURE_HEIGHT) if texture else 0
        depth = gl.glGetTexLevelParameteriv(target, 0, gl.GL_TEXTURE_DEPTH) if texture else 0
        print(f"[GL] {label} unit={unit} array={texture} size={width}x{height}x{depth}")
    else:
        width = gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_2D, 0, gl.GL_TEXTURE_WIDTH) if texture else 0
        height = gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_2D, 0, gl.GL_TEXTURE_HEIGHT) if texture else 0
        print(f"[GL] {label} unit={unit} 2D={texture} size={width}x{height}")
    gl.glActiveTexture(previous)


def log_shader_sampler_values(program_id: int, label: str = "shader") -> None:
    """Unidades efetivamente configuradas no programa, não só no build."""
    import ctypes
    if not enabled():
        return
    count = gl.glGetProgramiv(program_id, gl.GL_ACTIVE_UNIFORMS)
    rows = []
    for index in range(int(count)):
        name, _size, kind = gl.glGetActiveUniform(program_id, index)
        if kind not in (gl.GL_SAMPLER_2D, gl.GL_SAMPLER_3D, gl.GL_SAMPLER_2D_ARRAY):
            continue
        if isinstance(name, bytes):
            name = name.decode("utf-8", "replace")
        name = name.split("[", 1)[0]
        location = gl.glGetUniformLocation(program_id, name)
        if location < 0:
            continue
        value = (ctypes.c_int * 1)()
        gl.glGetUniformiv(program_id, location, value)
        rows.append(f"{name}={value[0]}({sampler_type_name(kind)})")
    print(f"[GL] {label} draw samplers: " + ", ".join(rows))


def log_units(units=(0, 2, 3, 4, 10, 11, 12), label: str = "units") -> None:
    if not enabled():
        return
    previous = gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)
    rows = []
    for unit in units:
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        u2 = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)
        u3 = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_3D)
        ua = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D_ARRAY)
        rows.append(f"u{unit}:2D={u2},3D={u3},arr={ua}")
    gl.glActiveTexture(previous)
    print(f"[GL] {label}: " + "; ".join(rows))
