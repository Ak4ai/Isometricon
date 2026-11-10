"""Painel 2D do editor: ferramenta, material, grid, objeto e atalhos."""

from __future__ import annotations

from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

from src.rendering.hud_quad import HudQuad

PANEL_WIDTH = 470
PANEL_HEIGHT = 208

_FONT_CANDIDATES = (
    "consola.ttf", "consolas.ttf", "C:/Windows/Fonts/consola.ttf",
    "segoeui.ttf", "arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttf",
)


class EditorHud:
    """Desenha um painel PIL uma vez por mudança de estado."""

    def __init__(self) -> None:
        self.quad: HudQuad | None = HudQuad()
        self._key: tuple | None = None
        self._image: Image.Image | None = None
        self._dirty = False

    def _font(self, size: int) -> Any:
        for candidate in _FONT_CANDIDATES:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def set_state(self, title: str, lines: Iterable[tuple[str, tuple[int, int, int]]],
                  swatch: tuple[int, int, int] | None = None) -> None:
        rows = tuple(lines)
        key = (title, rows, swatch)
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 232), outline=(232, 186, 76, 255), width=2)
        title_font = self._font(18)
        body_font = self._font(14)
        small_font = self._font(12)
        draw.text((16, 12), title, font=title_font, fill=(240, 208, 120, 255))
        y = 42
        for text, colour in rows:
            draw.text((16, y), text, font=body_font, fill=(*colour, 255))
            y += 20
        if swatch is not None:
            draw.rounded_rectangle((PANEL_WIDTH - 54, 12, PANEL_WIDTH - 18, 34), radius=5,
                                   fill=(*swatch, 255), outline=(255, 255, 255, 200), width=1)
        draw.text((16, PANEL_HEIGHT - 38),
                  "F2 exportar  F3 objeto  F5 salvar  F9 carregar  Ctrl+Z desfazer",
                  font=small_font, fill=(150, 160, 175, 255))
        draw.text((16, PANEL_HEIGHT - 22),
                  "Botão esq: aplicar   R: girar   Tab: ferramenta   C: cor   X: textura",
                  font=small_font, fill=(150, 160, 175, 255))
        self._image = image
        self._dirty = True

    def render(self, window_width: int, window_height: int) -> None:
        if self._image is not None and self.quad is not None:
            if self._dirty:
                self.quad.set_image(self._image)
                self._dirty = False
            self.quad.draw(12.0, 12.0, window_width, window_height)

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None
