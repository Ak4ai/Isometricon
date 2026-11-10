"""A tecla de interação ("E") que aparece ao lado do personagem quando há algo para usar perto (uma porta).

A imagem da tecla é feita uma vez com o PIL (uma tecla em pixel, com sombra embaixo e a legenda ao lado) e
desenhada sobre a cena com ``HudQuad``, presa ao ponto da tela acima da cabeça do jogador. Ela surge e some
com um fade curto e balança de leve para chamar a atenção.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

KEY_SIZE = 13          # lado da tecla, em pixels de arte (antes da escala)
SCALE = 3              # cada pixel de arte vira SCALE x SCALE na tela
FADE_HALF_LIFE = 0.06  # segundos para o fade andar metade do caminho
HEAD_HEIGHT = 2.25     # acima dos pés, onde a tecla fica presa


def _font(size: int):
    for name in ("consolab.ttf", "C:/Windows/Fonts/consolab.ttf", "arialbd.ttf", "consola.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def key_image(letter: str = "E", label: str = "") -> Image.Image:
    """A imagem pronta, no tamanho da tela: a tecla em pixel (ampliada ``SCALE`` vezes, sem borrar) e, ao lado,
    a legenda com contorno escuro, no tamanho final para ficar nítida."""
    s = KEY_SIZE
    key = Image.new("RGBA", (s + 2, s + 3), (0, 0, 0, 0))
    draw = ImageDraw.Draw(key)
    draw.rectangle((1, 2, s, s + 2), fill=(20, 22, 28, 150))                 # sombra no chão
    draw.rectangle((0, 0, s - 1, s), fill=(36, 38, 46, 255))                  # borda
    draw.rectangle((1, 1, s - 2, s - 1), fill=(150, 154, 166, 255))           # lado de baixo da tecla
    draw.rectangle((1, 1, s - 2, s - 3), fill=(236, 236, 240, 255))           # face
    draw.line((2, 2, s - 3, 2), fill=(255, 255, 255, 255))                    # brilho em cima
    key = key.resize((key.width * SCALE, key.height * SCALE), Image.NEAREST)

    font = _font(11 * SCALE)
    draw = ImageDraw.Draw(key)
    box = draw.textbbox((0, 0), letter, font=font)
    face = (s - 2) * SCALE
    tx = SCALE + (face - (box[2] - box[0])) // 2 - box[0]
    ty = SCALE + (face - (box[3] - box[1])) // 2 - box[1]
    draw.text((tx, ty), letter, font=font, fill=(30, 32, 40, 255))
    if not label:
        return key

    small = _font(16)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lbox = probe.textbbox((0, 0), label, font=small, stroke_width=2)
    image = Image.new("RGBA", (key.width + 6 + lbox[2] - lbox[0], key.height), (0, 0, 0, 0))
    image.paste(key, (0, 0))
    draw = ImageDraw.Draw(image)
    ly = (s * SCALE - (lbox[3] - lbox[1])) // 2 - lbox[1]
    draw.text((key.width + 6 - lbox[0], ly), label, font=small, fill=(255, 255, 255, 255),
              stroke_width=2, stroke_fill=(20, 22, 28, 230))
    return image


def project(point, mvp: np.ndarray, width: int, height: int) -> Optional[Tuple[float, float]]:
    """Ponto do mundo para pixels da janela (origem no canto de cima), ou ``None`` se está atrás da câmera."""
    clip = mvp @ np.array([float(point[0]), float(point[1]), float(point[2]), 1.0])
    if clip[3] <= 1e-6:
        return None
    ndc = clip[:3] / clip[3]
    return (ndc[0] * 0.5 + 0.5) * width, (1.0 - (ndc[1] * 0.5 + 0.5)) * height


class InteractPrompt:
    """Mostra a tecla perto do jogador enquanto ``target`` não é ``None``."""

    def __init__(self, create_gl: bool = True) -> None:
        self.level = 0.0
        self.time = 0.0
        self.label = ""
        self._quad = None
        self._image_key = None
        self._anchor = None
        if create_gl:
            import OpenGL.GL as gl
            from src.rendering.hud_quad import HudQuad
            self._quad = HudQuad()
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._quad.texture)   # desenhada 1:1: sem filtro
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

    def update(self, dt: float, visible: bool, label: str = "") -> None:
        target = 1.0 if visible else 0.0
        self.level += (target - self.level) * (1.0 - 0.5 ** (max(dt, 0.0) / FADE_HALF_LIFE))
        if abs(target - self.level) < 0.01:
            self.level = target
        self.time += dt
        if visible:
            self.label = label

    def render(self, feet, mvp: np.ndarray, width: int, height: int) -> None:
        if self._quad is None or self.level <= 0.0:
            return
        key = (self.label,)
        if key != self._image_key:
            self._quad.set_image(key_image("E", self.label))
            self._image_key = key
        spot = project((feet[0], feet[1] + HEAD_HEIGHT, feet[2]), mvp, width, height)
        if spot is None:
            return
        w, h = self._quad.size
        bob = math.sin(self.time * 5.0) * 1.5
        x = spot[0] + 10.0                                    # ao lado da cabeça, não em cima do rosto
        y = spot[1] - h * 0.5 + bob - (1.0 - self.level) * 6.0
        self._quad.draw(round(x), round(y), width, height, opacity=self.level)

    def delete(self) -> None:
        if self._quad is not None:
            self._quad.delete()
            self._quad = None
