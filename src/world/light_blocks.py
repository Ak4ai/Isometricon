"""Intensidade e cor das famílias de blocos luminosos do Minecraft.

Usado pelo malhador (para marcar a face emissiva) e pelas luzes pontuais do
mundo/editor. A busca é por trecho do nome-base, então ``wall_torch`` e
``soul_torch`` entram como tocha.
"""

from __future__ import annotations

from typing import Optional, Tuple

LIGHT_BLOCKS = {
    "ochre_froglight": (15, (1.0, 0.82, 0.42)),
    "verdant_froglight": (15, (0.65, 1.0, 0.72)),
    "pearlescent_froglight": (15, (1.0, 0.75, 0.92)),
    "glowstone": (15, (1.0, 0.78, 0.35)),
    "sea_lantern": (15, (0.55, 0.92, 1.0)),
    "shroomlight": (15, (1.0, 0.55, 0.25)),
    "jack_o_lantern": (15, (1.0, 0.55, 0.15)),
    "soul_lantern": (12, (0.45, 0.8, 1.0)),
    "soul_torch": (12, (0.45, 0.8, 1.0)),
    "lantern": (12, (1.0, 0.78, 0.38)),
    "torch": (12, (1.0, 0.65, 0.22)),
    "campfire": (12, (1.0, 0.52, 0.18)),
    "end_rod": (14, (0.9, 0.78, 1.0)),
    "magma_block": (4, (1.0, 0.38, 0.12)),
    "candle": (8, (1.0, 0.82, 0.5)),
    "glow_lichen": (6, (0.5, 0.9, 0.65)),
    "redstone_lamp": (10, (1.0, 0.62, 0.18)),
    "beacon": (15, (0.7, 0.9, 1.0)),
    "conduit": (15, (0.4, 0.85, 1.0)),
}


def light_for_block(name: str) -> Optional[Tuple[int, Tuple[float, float, float]]]:
    base = str(name).split("[", 1)[0].split(":", 1)[-1]
    for key, value in LIGHT_BLOCKS.items():
        if key in base:
            return value
    return None
