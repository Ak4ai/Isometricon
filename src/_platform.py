"""Seleção de backend PyOpenGL antes de qualquer import de OpenGL."""

import os
import platform
import sys
from collections.abc import MutableMapping


def configure_opengl_platform(
    environ: MutableMapping[str, str] | None = None,
    sys_platform: str | None = None,
    kernel_release: str | None = None,
) -> None:
    """Usa GLX como fallback no WSL, preservando escolhas explícitas.

    Os parâmetros opcionais permitem testar a detecção sem depender do host.
    Linux nativo, Windows e outros sistemas mantêm a autodetecção do PyOpenGL.
    Não importa OpenGL nem cria contexto gráfico.
    """
    environ = os.environ if environ is None else environ
    sys_platform = sys.platform if sys_platform is None else sys_platform
    if sys_platform != "linux" or "PYOPENGL_PLATFORM" in environ:
        return

    is_wsl = bool(environ.get("WSL_DISTRO_NAME") or environ.get("WSL_INTEROP"))
    if not is_wsl:
        release = platform.release() if kernel_release is None else kernel_release
        is_wsl = "microsoft" in release.lower()
    if is_wsl:
        environ.setdefault("PYOPENGL_PLATFORM", "glx")
