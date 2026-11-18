"""A fonte de bitmap do Minecraft no HUD: larguras das letras, sombra e o texto das coordenadas."""

import numpy as np
import pytest
from PIL import Image

from src.interactive.coordinate_overlay import coordinate_text
from src.rendering.mc_font import CELL, GAP, SPACE_WIDTH, McFont


def sheet_with(glyphs):
    """Uma folha 128x128 transparente; ``glyphs`` mapeia um caractere às colunas (0 a 7) que têm pixel acesos."""
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for char, columns in glyphs.items():
        x0, y0 = (ord(char) % 16) * CELL, (ord(char) // 16) * CELL
        for column in columns:
            for row in range(1, 8):
                sheet.putpixel((x0 + column, y0 + row), (255, 255, 255, 255))
    return sheet


def test_a_letter_is_as_wide_as_its_last_lit_column():
    font = McFont(sheet_with({"I": [0, 1], "M": range(0, 7), ":": [0]}))
    assert (font.glyph_width("I"), font.glyph_width("M"), font.glyph_width(":")) == (2, 7, 1)
    assert font.glyph_width(" ") == SPACE_WIDTH - GAP and font.glyph_width("é") == 0   # fora da folha / sem desenho
    assert font.text_width("IM") == 2 + GAP + 7 and font.text_width("") == 0
    assert font.text_width("I I") == 2 + GAP + 3 + GAP + 2          # o espaço soma 4 com o espaço entre as letras


def test_the_text_image_has_the_scaled_size_the_shadow_and_the_color():
    font = McFont(sheet_with({"I": [0, 1]}))
    plain = font.render("I", color=(250, 200, 50), scale=3, shadow=False)
    assert plain.size == (2 * 3, CELL * 3)
    assert plain.getpixel((0, 3 * 1))[:3] == (250, 200, 50) and plain.getpixel((0, 0))[3] == 0   # linha 1 acesa; 0 apagada
    shadowed = font.render("I", color=(200, 100, 40), scale=2)
    assert shadowed.size == ((2 + 1) * 2, (CELL + 1) * 2)           # a sombra pede 1 pixel a mais, à direita e embaixo
    lit = shadowed.getpixel((0, 2))                                  # (0, linha 1) em escala 2
    behind = shadowed.getpixel((2 * 2 + 1, 2 * 2))                   # a ponta direita e baixo: só a sombra
    assert lit[:3] == (200, 100, 40) and behind[:3] == (50, 25, 10) and behind[3] == 255


def test_a_sheet_of_the_wrong_size_is_refused():
    with pytest.raises(ValueError):
        McFont(Image.new("RGBA", (64, 64)))


def test_coordinates_read_like_the_game_hud():
    assert coordinate_text(np.array([0.5, 13.0, -2.25], dtype=np.float32)) == "X: 0.5  Y: 13.0  Z: -2.2"
    assert coordinate_text((10.04, 3.0, 99.96)) == "X: 10.0  Y: 3.0  Z: 100.0"
