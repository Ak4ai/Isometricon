"""Seleção de backend isolada do ambiente do runner e sem contexto gráfico."""

import os
import subprocess
import sys

import pytest

from src._platform import configure_opengl_platform


@pytest.mark.parametrize("system,environ,release,expected", [
    ("win32", {}, "10", None),
    ("win32", {"WSL_DISTRO_NAME": "Ubuntu"}, "Microsoft", None),
    ("darwin", {}, "Darwin", None),
    ("linux", {}, "6.8.0-generic", None),
    ("linux", {"WAYLAND_DISPLAY": "wayland-0"}, "6.8.0-generic", None),
    ("linux", {"WSL_DISTRO_NAME": "Ubuntu"}, "", "glx"),
    ("linux", {"WSL_INTEROP": "/run/WSL/123_interop"}, "", "glx"),
    ("linux", {}, "6.6.87.2-microsoft-standard-WSL2", "glx"),
    ("linux", {}, "4.4.0-Microsoft", "glx"),
])
def test_platform_fallback(system, environ, release, expected):
    before = environ.copy()
    configure_opengl_platform(environ, system, release)
    assert environ == (before if expected is None else {**before, "PYOPENGL_PLATFORM": expected})


@pytest.mark.parametrize("system", ["win32", "linux"])
@pytest.mark.parametrize("backend", ["egl", "glx", "osmesa", ""])
def test_explicit_choice_is_preserved(system, backend):
    environ = {"WSL_DISTRO_NAME": "Ubuntu", "PYOPENGL_PLATFORM": backend}
    before = environ.copy()
    configure_opengl_platform(environ, system, "Microsoft")
    assert environ == before


def test_default_arguments_use_runtime_environment(monkeypatch):
    monkeypatch.delenv("PYOPENGL_PLATFORM", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(sys, "platform", "linux")
    configure_opengl_platform()
    configure_opengl_platform()
    assert os.environ["PYOPENGL_PLATFORM"] == "glx"


@pytest.mark.parametrize("entrypoint", [
    "import src.rendering",
    "import src.core.window",
    "runpy.run_path('src/main.py', run_name='bootstrap_test')",
])
def test_bootstrap_precedes_first_opengl_import(entrypoint):
    # Processo novo: nenhum import/cache anterior pode mascarar a ordem.
    # Interrompe no primeiro import OpenGL, sem carregar driver ou criar janela.
    code = """
import importlib.abc
import os
import runpy
import sys

# GLFW não faz parte deste teste de ordem; evita carregar bibliotecas do host.
import types
sys.modules['glfw'] = types.ModuleType('glfw')
sys.platform = 'linux'
os.environ.pop('PYOPENGL_PLATFORM', None)
os.environ['WSL_DISTRO_NAME'] = 'Ubuntu'

class ReachedOpenGL(Exception):
    pass

class CheckOrder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'OpenGL':
            assert os.environ.get('PYOPENGL_PLATFORM') == 'glx'
            raise ReachedOpenGL

sys.meta_path.insert(0, CheckOrder())
try:
    exec(sys.argv[1])
except ReachedOpenGL:
    pass
else:
    raise AssertionError('O entrypoint não tentou importar OpenGL')
"""
    subprocess.run([sys.executable, "-c", code, entrypoint], check=True)
