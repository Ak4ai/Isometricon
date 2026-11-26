"""Nomes de objetos, nomes de arquivo e biblioteca compartilhada."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from src.core.paths import RESOURCE_ROOT, saves_path

ASSET_OBJECTS = os.fspath(RESOURCE_ROOT / "assets" / "objects")
EXPORT_OBJECTS = os.fspath(saves_path("objetos"))
LEGACY_EXPORT = os.fspath(saves_path("objeto.json"))


def slugify(name: str, default: str = "objeto") -> str:
    """Converte um nome legível em um nome de arquivo seguro e estável."""
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_-").lower()
    slug = slug[:48].strip("_-")
    return slug or default


def object_library_paths() -> list[str]:
    """Objetos de exemplo + objetos exportados, sem mapas."""
    paths: list[str] = []
    for directory in (ASSET_OBJECTS, EXPORT_OBJECTS):
        if os.path.isdir(directory):
            paths.extend(str(path) for path in Path(directory).glob("*.json"))
    if os.path.exists(LEGACY_EXPORT):
        paths.append(LEGACY_EXPORT)
    return sorted(dict.fromkeys(paths))
