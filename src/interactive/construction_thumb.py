"""Miniatura isométrica de uma construção, desenhada com Pillow (sem OpenGL).

A biblioteca de construções mostra objetos exportados e ``.schem`` com o mesmo
cartão visual. A miniatura é uma aproximação por cores de bloco: serve para
reconhecer a construção, não para substituir a prévia 3D.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.world.schematic import Schematic, is_air_name


def _base(name: str) -> str:
    clean = str(name).split("[", 1)[0].strip()
    return clean.split(":", 1)[-1] if ":" in clean else clean


_PALETTE = {
    "dirt": (134, 96, 67), "grass_block": (90, 150, 65), "grass": (90, 150, 65),
    "stone": (130, 130, 130), "cobblestone": (115, 112, 108), "stone_bricks": (122, 118, 112),
    "sandstone": (210, 190, 140), "oak_planks": (170, 133, 82), "spruce_planks": (110, 84, 58),
    "oak_log": (116, 86, 52), "birch_planks": (210, 190, 140), "bricks": (150, 70, 55),
    "white_concrete": (210, 213, 218), "red_concrete": (145, 55, 45), "blue_concrete": (45, 70, 145),
    "yellow_concrete": (205, 170, 55), "green_concrete": (55, 105, 55), "black_concrete": (35, 38, 42),
    "water": (52, 92, 150), "glass": (170, 210, 220), "leaves": (65, 120, 55),
    "oak_leaves": (65, 120, 55), "short_grass": (100, 160, 70), "poppy": (190, 50, 45),
    "dandelion": (220, 190, 55), "torch": (240, 190, 70), "lantern": (230, 180, 80),
    "terracotta": (170, 100, 70), "deepslate": (75, 78, 82), "netherrack": (110, 50, 50),
}


def block_colour(name: str, tint: Optional[np.ndarray] = None) -> Tuple[int, int, int]:
    if tint is not None:
        r, g, b = (float(v) for v in tint[:3])
        if max(r, g, b) > 1.0:
            r, g, b = r / 255.0, g / 255.0, b / 255.0
        return max(0, min(255, int(r * 255))), max(0, min(255, int(g * 255))), max(0, min(255, int(b * 255)))
    base = _base(name)
    if base in _PALETTE:
        return _PALETTE[base]
    for key, colour in _PALETTE.items():
        if key in base:
            return colour
    digest = hashlib.md5(base.encode("utf-8")).digest()
    return 85 + digest[0] % 130, 85 + digest[1] % 130, 85 + digest[2] % 130


def _shade(colour: Tuple[int, int, int], factor: float) -> Tuple[int, int, int, int]:
    return tuple(max(0, min(255, int(v * factor))) for v in colour) + (255,)


@lru_cache(maxsize=128)
def thumbnail_for(schematic: Schematic, size: Tuple[int, int] = (150, 112)) -> Image.Image:
    """Cartão com a construção vista de cima, em projeção isométrica."""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    figure = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(figure)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=8, fill=(22, 29, 39, 255),
                           outline=(92, 104, 120, 255), width=1)
    occupied = schematic.occupied_mask
    if not occupied.any():
        draw.text((12, height // 2 - 6), "sem voxels", fill=(150, 160, 175, 255))
        return figure
    coords = np.argwhere(occupied)                       # (y, z, x)
    # Isométrico: x cresce para a direita/baixo, z para a esquerda/baixo, y para cima.
    ux = coords[:, 2] - coords[:, 1]
    uy = (coords[:, 2] + coords[:, 1]) * 0.5 - coords[:, 0] * 0.9
    min_x, max_x = float(ux.min()), float(ux.max())
    min_y, max_y = float(uy.min()), float(uy.max())
    unit = min((width - 26) / max(4.0, (max_x - min_x) + 2.0),
               (height - 24) / max(4.0, (max_y - min_y) + 2.0))
    unit = max(2.0, min(10.0, unit))
    cx = (width - (max_x - min_x) * unit) / 2 - min_x * unit
    cy = (height - (max_y - min_y) * unit) / 2 - min_y * unit
    tints = getattr(schematic, "tints", None)
    # De trás para a frente: z desc, x asc, y asc.
    order = np.lexsort((coords[:, 2], coords[:, 1], coords[:, 0]))
    for index in order:
        y, z, x = (int(v) for v in coords[index])
        name = schematic.grid[y, z, x]
        if is_air_name(name):
            continue
        tint = tints[y, z, x] if tints is not None else None
        colour = block_colour(name, tint)
        px = cx + (x - z) * unit
        py = cy + (x + z) * unit * 0.5 - y * unit * 0.9
        half = unit * 0.55
        top = [(px, py - half), (px + half, py), (px, py + half), (px - half, py)]
        left = [(px - half, py), (px, py + half), (px, py + half + unit * 0.7),
                (px - half, py + unit * 0.7)]
        right = [(px, py + half), (px + half, py), (px + half, py + unit * 0.7),
                 (px, py + half + unit * 0.7)]
        draw.polygon(left, fill=_shade(colour, 0.55))
        draw.polygon(right, fill=_shade(colour, 0.72))
        draw.polygon(top, fill=_shade(colour, 1.0))
    return figure


def thumbnail_key(label: str, entry: dict) -> Tuple[str, str, str]:
    return (label, str(entry.get("kind", "")), str(entry.get("name", "")))
