"""Roda HSV pequena, desenhada com Pillow e testada por ângulo/raio.

O anel é gerado uma vez; o valor (brilho) é ajustado por uma barra separada.
Não usa toolkit: a imagem vira textura da HUD como qualquer outro painel.
"""

from __future__ import annotations

import colorsys
import math
from functools import lru_cache

from PIL import Image


@lru_cache(maxsize=8)
def wheel_image(size: int = 84) -> Image.Image:
    """Disco HSV opaco (matiz no ângulo, saturação no raio), valor 1."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()
    center = (size - 1) / 2.0
    radius = max(center, 1.0)
    for y in range(size):
        for x in range(size):
            dx = (x - center) / radius
            dy = (y - center) / radius
            distance = math.hypot(dx, dy)
            if distance > 1.0:
                continue
            hue = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
            red, green, blue = colorsys.hsv_to_rgb(hue, min(1.0, distance), 1.0)
            pixels[x, y] = (round(red * 255), round(green * 255), round(blue * 255), 255)
    return image


def hsv_at(x: float, y: float, size: int = 84) -> tuple[float, float] | None:
    """Converte uma coordenada local da roda em (hue, saturation), ou None."""
    center = (size - 1) / 2.0
    radius = max(center, 1.0)
    dx = (float(x) - center) / radius
    dy = (float(y) - center) / radius
    distance = math.hypot(dx, dy)
    if distance > 1.0:
        return None
    hue = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
    return hue, min(1.0, distance)


def hsv_to_hex(hue: float, saturation: float, value: float) -> str:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, max(0.0, min(1.0, saturation)),
                                           max(0.0, min(1.0, value)))
    return f"{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"
