"""Core module: gerenciamento de janela, versionamento e ciclo de vida."""

from .version import VersionInfo, get_local_version_info, start_github_sync_check
from .window import Window

__all__ = [
    "Window",
    "VersionInfo",
    "get_local_version_info",
    "start_github_sync_check",
]
