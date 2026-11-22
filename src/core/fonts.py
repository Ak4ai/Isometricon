"""Fontes empacotadas e carregadas em um único lugar.

As fontes ficam em ``assets/fonts`` e são incluídas pelo build do PyInstaller
(``--add-data assets;assets``). Inter é usada no texto de interface; JetBrains
Mono, em coordenadas, chat e rótulos técnicos.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

BODY_FONT = "Inter-Variable.ttf"
MONO_FONT = "JetBrainsMono-Variable.ttf"


def resource_root() -> Path:
    """Raiz dos recursos, tanto no código-fonte quanto no executável congelado."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


FONT_DIR = resource_root() / "assets" / "fonts"


def _fallback(size: int):
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


@lru_cache(maxsize=256)
def load_font(size: int, role: str = "body", bold: bool = False, heading: bool = False):
    """Carrega Inter/JetBrains Mono com peso variável e fallback seguro."""
    size = max(1, int(round(size)))
    filename = MONO_FONT if role == "mono" else BODY_FONT
    path = FONT_DIR / filename
    try:
        font = ImageFont.truetype(str(path), size)
        weight = 700 if bold else 600 if heading else 400
        try:
            axes = font.get_variation_axes()
        except (AttributeError, OSError):
            axes = []
        if axes:
            values = []
            for axis in axes:
                name = axis.get("name", b"")
                if name in (b"Weight", b"wght", "Weight", "wght"):
                    values.append(weight)
                else:
                    values.append(axis.get("default", 14))
            font.set_variation_by_axes(values)
        return font
    except (OSError, ValueError, TypeError):
        return _fallback(size)


def ui_font(size: int, *, heading: bool = False, bold: bool = False):
    return load_font(size, "body", bold=bold, heading=heading)


def mono_font(size: int, *, bold: bool = False):
    return load_font(size, "mono", bold=bold)


def font_path(filename: str) -> str:
    """Caminho absoluto de uma fonte empacotada (útil em diagnósticos)."""
    return os.fspath(FONT_DIR / filename)
