"""Painel 2D do editor: ferramentas, cores, texturas, grid e atalhos.

Tudo é desenhado com Pillow e enviado como uma única textura ao ``HudQuad``.
As abas Cores/Texturas usam o mesmo espaço: roda HSV, paleta e recentes de um
lado; miniaturas reais do atlas do outro. Nenhum toolkit de UI é usado.
"""

from __future__ import annotations

from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

from src.editor.color_wheel import wheel_image
from src.rendering.hud_quad import HudQuad

PANEL_WIDTH = 470
PANEL_HEIGHT = 440
WHEEL_SIZE = 84
WHEEL_BOX = (16, 268, 16 + WHEEL_SIZE, 268 + WHEEL_SIZE)
VALUE_BOX = (16, 358, 16 + WHEEL_SIZE, 368)
TOOLS = (
    ("build", "Construir"), ("erase", "Apagar"), ("paint", "Pintar"),
    ("stamp", "Carimbar"), ("select", "Selecionar"),
)
ACTIONS = (
    ("save", "Salvar"), ("load", "Abrir"), ("export", "Export"),
    ("library", "Objeto"), ("undo", "Undo"), ("redo", "Redo"),
    ("grid", "Grade"), ("base", "Base"),
)
TABS = (("colors", "Cores"), ("textures", "Texturas"))

_FONT_CANDIDATES = (
    "consola.ttf", "consolas.ttf", "C:/Windows/Fonts/consola.ttf",
    "segoeui.ttf", "arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttf",
)


class EditorHud:
    """Desenha um painel PIL e mapeia botões, cores, texturas e roda."""

    def __init__(self) -> None:
        self.quad: HudQuad | None = HudQuad()
        self._key: tuple | None = None
        self._image: Image.Image | None = None
        self._dirty = False
        self._buttons: dict[str, tuple[int, int, int, int]] = {}
        self._colour_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._texture_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._recent_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._wheel_box: tuple[int, int, int, int] | None = None
        self._value_box: tuple[int, int, int, int] | None = None

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

    def _tab(self, draw, box, label: str, active: bool, font) -> None:
        self._button(draw, box, label, active, font)

    def set_state(self, title: str, lines: Iterable[tuple[str, tuple[int, int, int]]],
                  swatch: tuple[int, int, int] | None = None,
                  active_tool: str = "build",
                  palette: Iterable[tuple[str, tuple[int, int, int]]] = (),
                  colour_index: int = 0,
                  custom_colour: tuple[int, int, int] | None = None,
                  textures: Iterable[tuple[str, Image.Image]] = (),
                  texture_index: int = 0,
                  active_tab: str = "colors",
                  recent_colours: Iterable[tuple[int, int, int]] = (),
                  hsv: tuple[float, float, float] = (0.0, 0.0, 1.0)) -> None:
        rows = tuple(lines)
        palette = tuple(palette)
        textures = tuple(textures)
        recent = tuple(recent_colours)
        texture_names = tuple(name for name, _ in textures)
        key = (title, rows, swatch, active_tool, palette, colour_index, custom_colour,
               texture_names, texture_index, active_tab, recent,
               (round(hsv[0] * 360), round(hsv[1] * 100), round(hsv[2] * 100)))
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
            box = (14 + index * 88, 164, 14 + index * 88 + 82, 192)
            self._buttons[key_id] = box
            self._button(draw, box, label, key_id == active_tool, button_font)
        for index, (key_id, label) in enumerate(ACTIONS):
            box = (14 + index * 55, 198, 14 + index * 55 + 51, 224)
            self._buttons[key_id] = box
            self._button(draw, box, label, False, button_font)

        # Abas de conteúdo: só uma ocupa o espaço, evitando um painel gigante.
        for index, (tab_id, label) in enumerate(TABS):
            box = (14 + index * 112, 230, 14 + index * 112 + 106, 256)
            self._buttons["tab:" + tab_id] = box
            self._tab(draw, box, label, tab_id == active_tab, button_font)

        self._colour_boxes = {}
        self._texture_boxes = {}
        self._recent_boxes = {}
        self._wheel_box = None
        self._value_box = None
        if active_tab == "textures":
            for index, (name, thumb) in enumerate(textures):
                column, row = index % 8, index // 8
                box = (16 + column * 52, 268 + row * 54, 16 + column * 52 + 48, 268 + row * 54 + 48)
                self._texture_boxes[index] = box
                if thumb.size != (48, 48):
                    thumb = thumb.resize((48, 48), Image.Resampling.NEAREST)
                image.paste(thumb.convert("RGBA"), (box[0], box[1]))
                active = index == texture_index
                draw.rounded_rectangle(box, radius=3,
                                       outline=(255, 235, 160, 255) if active else (45, 55, 68, 255),
                                       width=3 if active else 1)
            current = textures[texture_index][0] if textures else "—"
            draw.text((16, 378), f"Textura selecionada: {current}   [X]", font=small_font,
                      fill=(190, 202, 218, 255))
        else:
            if swatch is not None:
                wheel = wheel_image(WHEEL_SIZE)
                image.alpha_composite(wheel, (WHEEL_BOX[0], WHEEL_BOX[1]))
                self._wheel_box = WHEEL_BOX
                # Barra de valor: preta -> cor de matiz/saturação atual.
                vx0, vy0, vx1, vy1 = VALUE_BOX
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hsv[0] % 1.0, max(0.0, min(1.0, hsv[1])), 1.0)
                for x in range(vx0, vx1):
                    t = (x - vx0) / max(1, vx1 - vx0 - 1)
                    draw.line((x, vy0, x, vy1), fill=(round(r * 255 * t), round(g * 255 * t),
                                                      round(b * 255 * t), 255))
                self._value_box = VALUE_BOX
                knob = vx0 + round((vx1 - vx0 - 1) * max(0.0, min(1.0, hsv[2])))
                draw.rectangle((knob - 1, vy0 - 2, knob + 1, vy1 + 2), fill=(255, 255, 255, 255))

            draw.text((112, 258), "Cores  [C]  clique na roda ou na paleta", font=small_font,
                      fill=(180, 190, 205, 255))
            current = custom_colour if custom_colour is not None else (
                palette[colour_index][1] if palette else (255, 255, 255))
            for index, (name, colour) in enumerate(palette):
                column, row = index % 8, index // 8
                box = (112 + column * 28, 280 + row * 28, 112 + column * 28 + 24, 280 + row * 28 + 24)
                self._colour_boxes[index] = box
                active = custom_colour is None and index == colour_index
                draw.rounded_rectangle(box, radius=3, fill=(*colour, 255),
                                       outline=(255, 235, 160, 255) if active else (40, 50, 62, 255),
                                       width=2 if active else 1)
            draw.text((112, 340), "Recentes", font=small_font, fill=(160, 172, 188, 255))
            for index, colour in enumerate(recent[:8]):
                box = (166 + index * 22, 348, 166 + index * 22 + 16, 364)
                self._recent_boxes[index] = box
                draw.rounded_rectangle(box, radius=3, fill=(*colour, 255),
                                       outline=(80, 92, 108, 255), width=1)
            draw.rounded_rectangle((PANEL_WIDTH - 62, 356, PANEL_WIDTH - 18, 372), radius=3,
                                   fill=(*current, 255), outline=(255, 255, 255, 200), width=1)

        draw.text((16, 396),
                  "F2 exportar  F3 objeto  F5 salvar  F9 carregar  Ctrl+Z desfazer",
                  font=small_font, fill=(150, 160, 175, 255))
        draw.text((16, 414),
                  "Botão esq: aplicar  R: girar  Tab: ferramenta  C/X: cor/textura  H: hex",
                  font=small_font, fill=(150, 160, 175, 255))
        self._image = image
        self._dirty = True

    def hit(self, x: float, y: float) -> str | None:
        for key, (x0, y0, x1, y1) in self._buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def hit_colour(self, x: float, y: float) -> int | None:
        for index, (x0, y0, x1, y1) in self._colour_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index
        return None

    def hit_texture(self, x: float, y: float) -> int | None:
        for index, (x0, y0, x1, y1) in self._texture_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index
        return None

    def hit_recent(self, x: float, y: float) -> int | None:
        for index, (x0, y0, x1, y1) in self._recent_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return index
        return None

    def hit_wheel(self, x: float, y: float) -> tuple[str, float, float] | None:
        """Retorna (tipo, primeiro, segundo): roda=(h,s), barra=(v, 0)."""
        if self._wheel_box is not None:
            x0, y0, x1, y1 = self._wheel_box
            if x0 <= x <= x1 and y0 <= y <= y1:
                from src.editor.color_wheel import hsv_at
                found = hsv_at(x - x0, y - y0, WHEEL_SIZE)
                if found is not None:
                    return "wheel", found[0], found[1]
        if self._value_box is not None:
            x0, y0, x1, y1 = self._value_box
            if x0 <= x <= x1 and y0 - 4 <= y <= y1 + 4:
                return "value", max(0.0, min(1.0, (x - x0) / max(1, x1 - x0))), 0.0
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
