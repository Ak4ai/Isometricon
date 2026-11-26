"""Endereços dos recursos instalados e dos dados do usuário."""

import os
from pathlib import Path
import sys


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def data_root() -> Path:
    """O código-fonte mantém os dados no checkout. O pacote Windows usa a pasta do usuário."""
    override = os.environ.get("ISOMETRICON_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        profile = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return profile / "Isometricon"
    return RESOURCE_ROOT


def saves_path(*parts: str) -> Path:
    return data_root().joinpath("saves", *parts)
