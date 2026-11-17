"""Painel 2D do editor: ferramenta, material, grid, objeto, atalhos e botões."""

from __future__ import annotations

from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

from src.rendering.hud_quad import HudQuad

PANEL_WIDTH = 470
PANEL_HEIGHT = 390
TOOLS = (
    ("build", "Construir"), ("erase", "Apagar"), ("paint", "Pintar"),
    ("stamp", "Carimbar"), ("select", "Selecionar"),
)
ACTIONS = (
    ("save", "Salvar"), ("load", "Abrir"), ("export", "Export"),
    ("library", "Objeto"), ("undo", "Undo"), ("redo", "Redo"),
    ("grid", "Grade"), ("base", "Base"),
)

_FONT_CANDIDATES = (
    "consola.ttf", "consolas.ttf", "C:/Windows/Fonts/consola.ttf",
    "segoeui.ttf", "arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttf",
)


class EditorHud:
    """Desenha um painel PIL uma vez por mudança de estado e mapeia cliques."""

    def __init__(self) -> None:
        self.quad: HudQuad | None = HudQuad()
        self._key: tuple | None = None
        self._image: Image.Image | None = None
        self._dirty = False
        self._buttons: dict[str, tuple[int, int, int, int]] = {}
        self._colour_boxes: dict[int, tuple[int, int, int, int]] = {}

    def _font(self, size: int) -> Any:
        for candidate in _FONT_CANDIDATES:
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _button(self, draw, box, label: str, active: bool, font) -> None:
        x0, y0, x1, y1 = box
        draw.rounded_rectangle(box, radius=5,
                               fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                               outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
        text_colour = (20, 24, 30, 255) if active else (210, 218, 228, 255)
        try:
            width = draw.textbbox((0, 0), label, font=font)[2]
        except Exception:
            width = len(label) * 6
        draw.text(((x0 + x1 - width) / 2, y0 + 5), label, font=font, fill=text_colour)

    def set_state(self, title: str, lines: Iterable[tuple[str, tuple[int, int, int]]],
                  swatch: tuple[int, int, int] | None = None,
                  active_tool: str = "build",
                  palette: Iterable[tuple[str, tuple[int, int, int]]] = (),
                  colour_index: int = 0,
                  custom_colour: tuple[int, int, int] | None = None) -> None:
        rows = tuple(lines)
        palette = tuple(palette)
        key = (title, rows, swatch, active_tool, palette, colour_index, custom_colour)
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 238), outline=(232, 186, 76, 255), width=2)
        title_font = self._font(18)
        body_font = self._font(14)
        small_font = self._font(11)
        button_font = self._font(11)
        draw.text((16, 12), title, font=title_font, fill=(240, 208, 120, 255))
        y = 42
        for text, colour in rows:
            draw.text((16, y), text, font=body_font, fill=(*colour, 255))
            y += 19
        if swatch is not None:
            draw.rounded_rectangle((PANEL_WIDTH - 54, 12, PANEL_WIDTH - 18, 34), radius=5,
                                   fill=(*swatch, 255), outline=(255, 255, 255, 200), width=1)

        self._buttons = {}
        for index, (key_id, label) in enumerate(TOOLS):
            box = (14 + index * 88, 180, 14 + index * 88 + 82, 208)
            self._buttons[key_id] = box
            self._button(draw, box, label, key_id == active_tool, button_font)
        for index, (key_id, label) in enumerate(ACTIONS):
            box = (14 + index * 55, 216, 14 + index * 55 + 51, 242)
            self._buttons[key_id] = box
            self._button(draw, box, label, False, button_font)

        self._colour_boxes = {}
        if palette:
            draw.text((16, 252), "Paleta de cores  [C]  clique em um quadradinho", font=small_font,
                      fill=(180, 190, 205, 255))
            current = custom_colour if custom_colour is not None else palette[colour_index][1]
            draw.rounded_rectangle((PANEL_WIDTH - 62, 248, PANEL_WIDTH - 18, 270), radius=4,
                                   fill=(*current, 255), outline=(255, 255, 255, 220), width=1)
            for index, (name, colour) in enumerate(palette):
                column, row = index % 8, index // 8
                box = (16 + column * 52, 270 + row * 30, 16 + column * 52 + 48, 270 + row * 30 + 26)
                self._colour_boxes[index] = box
                active = custom_colour is None and index == colour_index
                draw.rounded_rectangle(box, radius=4, fill=(*colour, 255),
                                       outline=(255, 235, 160, 255) if active else (35, 42, 54, 255),
                                       width=3 if active else 1)

        draw.text((16, PANEL_HEIGHT - 50),
                  "F2 exportar  F3 objeto  F5 salvar  F9 carregar  Ctrl+Z desfazer",
                  font=small_font, fill=(150, 160, 175, 255))
        draw.text((16, PANEL_HEIGHT - 34),
                  "Botão esq: aplicar   R: girar   Tab: ferramenta   C: cor   X: textura",
                  font=small_font, fill=(150, 160, 175, 255))
        draw.text((16, PANEL_HEIGHT - 18),
                  "H: cor hexadecimal  -/=: pincel  [/]: grade  F8: base  Delete: excluir",
                  font=small_font, fill=(150, 160, 175, 255))
        self._image = image
        self._dirty = True

    def hit(self, x: float, y: float) -> str | None:
        """Retorna o id do botão na coordenada local do painel."""
        for key, (x0, y0, x1, y1) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def hit_colour(self, x: float, y: float) -> int | None:
        for index, (x0, y0, x1, y1) in self._colour_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index
        return None

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
