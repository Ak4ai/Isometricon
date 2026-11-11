"""Nomes de objetos, nomes de arquivo e biblioteca compartilhada."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSET_OBJECTS = os.path.join(PROJECT_ROOT, "assets", "objects")
EXPORT_OBJECTS = os.path.join(PROJECT_ROOT, "saves", "objetos")
LEGACY_EXPORT = os.path.join(PROJECT_ROOT, "saves", "objeto.json")


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
