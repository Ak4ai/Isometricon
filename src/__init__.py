"""Inicializa o pacote e configura o backend OpenGL antes dos submodulos."""

from src._platform import configure_opengl_platform

configure_opengl_platform()

__all__ = ["configure_opengl_platform"]
