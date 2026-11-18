"""A fonte de bitmap do Minecraft para textos do HUD, lida do jogo do jogador (sem OpenGL).

``textures/font/ascii.png`` é uma folha 128x128 de 16x16 células de 8x8 pixels (a célula do caractere de código c fica na
linha c // 16, coluna c % 16). Cada letra ocupa da borda esquerda da célula até a última coluna com pixel, e o jogo
deixa 1 pixel entre as letras; o espaço vale 4. O texto sai com a sombra do jogo (a cor a um quarto, 1 pixel abaixo e
à direita).

A folha vem de ``assets/fonts/ascii.png`` (arte da Mojang, fora do git: ver ``.gitignore``) ou do ``client.jar`` do
jogador (o mesmo que os modelos de bloco usam). Sem nenhum dos dois, ``McFont.load()`` devolve ``None`` e quem usa
cai na fonte de reserva dele.
"""

from __future__ import annotations

import io
import os
import zipfile
from functools import lru_cache
from typing import Dict, Optional, Tuple

from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_SHEET = os.path.join(PROJECT_ROOT, "assets", "fonts", "ascii.png")
JAR_ENTRY = "assets/minecraft/textures/font/ascii.png"
CELL = 8
SPACE_WIDTH = 4       # o espaço do jogo
GAP = 1               # pixels entre as letras
ASCENT = 7            # a linha de base: o corpo da letra tem 7 pixels, o resto da célula é para as hastes de baixo
SHADOW = 0.25         # a sombra do jogo é a cor a um quarto do brilho


class McFont:
    """A folha de caracteres do jogo e o desenho de uma linha de texto."""

    def __init__(self, sheet: Image.Image) -> None:
        self.sheet = sheet.convert("RGBA")
        if self.sheet.size != (CELL * 16, CELL * 16):
            raise ValueError(f"A folha da fonte deve ter {CELL * 16}x{CELL * 16}, não {self.sheet.size}.")
        self._widths: Dict[str, int] = {}

    # ------------------------------------------------------------------ carregar
    @classmethod
    def load(cls) -> Optional["McFont"]:
        """A fonte do jogador (``assets/fonts/ascii.png`` ou o ``client.jar``), ou ``None`` se não há."""
        try:
            if os.path.isfile(LOCAL_SHEET):
                return cls(Image.open(LOCAL_SHEET))
            from src.rendering.mc_models import find_jar
            jar = find_jar()
            if jar:
                with zipfile.ZipFile(jar) as archive:
                    return cls(Image.open(io.BytesIO(archive.read(JAR_ENTRY))))
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            return None
        return None

    # ------------------------------------------------------------------ medidas
    def _cell(self, char: str) -> Tuple[int, int]:
        code = ord(char)
        return (code % 16) * CELL, (code // 16) * CELL

    def glyph_width(self, char: str) -> int:
        """A largura da letra em pixels da folha, sem o espaço entre as letras."""
        if char == " ":
            return SPACE_WIDTH - GAP
        if char not in self._widths:
            if ord(char) > 255:
                self._widths[char] = 0
            else:
                x0, y0 = self._cell(char)
                widest = 0
                for x in range(CELL):
                    if any(self.sheet.getpixel((x0 + x, y0 + y))[3] > 0 for y in range(CELL)):
                        widest = x + 1
                self._widths[char] = widest
        return self._widths[char]

    def text_width(self, text: str) -> int:
        """A largura do texto em pixels da folha (sem a escala e sem a sombra)."""
        if not text:
            return 0
        return sum(self.glyph_width(c) + GAP for c in text) - GAP

    # ------------------------------------------------------------------ desenho
    def render(self, text: str, color: Tuple[int, int, int] = (255, 255, 255), scale: int = 2,
               shadow: bool = True) -> Image.Image:
        """Uma imagem RGBA com ``text``: cada pixel da fonte vira ``scale`` x ``scale``; com a sombra do jogo."""
        scale = max(int(scale), 1)
        pad = 1 if shadow else 0
        width = max(self.text_width(text), 1) + pad
        base = Image.new("RGBA", (width, CELL + pad), (0, 0, 0, 0))
        x = 0
        for char in text:
            w = self.glyph_width(char)
            if w and char != " ":
                x0, y0 = self._cell(char)
                glyph = self.sheet.crop((x0, y0, x0 + w, y0 + CELL))
                mask = glyph.getchannel("A")
                if shadow:
                    dark = tuple(int(c * SHADOW) for c in color)
                    base.paste(Image.new("RGBA", glyph.size, (*dark, 255)), (x + pad, pad), mask)
                base.paste(Image.new("RGBA", glyph.size, (*color, 255)), (x, 0), mask)
            x += w + GAP
        return base.resize((base.width * scale, base.height * scale), Image.NEAREST)


@lru_cache(maxsize=1)
def default_font() -> Optional[McFont]:
    """A fonte carregada uma vez (``None`` se o jogador não tem a folha)."""
    return McFont.load()


__all__ = ["McFont", "default_font", "LOCAL_SHEET"]
