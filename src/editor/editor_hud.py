"""Painel 2D do editor: ferramentas, cores, texturas, grid e atalhos.

Tudo é desenhado com Pillow e enviado como uma única textura ao ``HudQuad``.
As abas Cores/Texturas usam o mesmo espaço: roda HSV, paleta e recentes de um
lado; miniaturas reais do atlas do outro. Nenhum toolkit de UI é usado.
"""

from __future__ import annotations

from typing import Any, Iterable

from PIL import Image, ImageDraw

from src.core.fonts import ui_font
from src.editor.color_wheel import wheel_image
from src.rendering.scaled_draw import RENDER_SCALE, ScaledDraw
from src.rendering.hud_quad import HudQuad

PANEL_WIDTH = 500
PANEL_HEIGHT = 840
WHEEL_SIZE = 240
WHEEL_BOX = (18, 520, 18 + WHEEL_SIZE, 520 + WHEEL_SIZE)
VALUE_BOX = (18, 768, 18 + WHEEL_SIZE, 780)
TOOLS = (
    ("build", "Construir"), ("paint", "Pintar"), ("stamp", "Carimbar"),
    ("select", "Selecionar"),
)
ACTIONS = (
    ("save", "Salvar"), ("load", "Abrir"), ("export", "Exportar"),
    ("library", "Objeto"), ("undo", "Undo"), ("redo", "Redo"),
    ("grid", "Grade"), ("base", "Base"), ("menu", "Menu"),
)
TABS = (("colors", "Cores"), ("textures", "Texturas"))
MIN_UI_SCALE = 0.45

def fit_panel_scale(window_width: int, window_height: int,
                    panel_width: int = PANEL_WIDTH, panel_height: int = PANEL_HEIGHT) -> float:
    """Escala uniforme para caber no viewport e ocupar sua altura disponível."""
    available_w = max(1.0, float(window_width) - 24.0)
    available_h = max(1.0, float(window_height) - 24.0)
    return max(MIN_UI_SCALE, min(available_w / panel_width, available_h / panel_height))


RENDER_SCALE = 2  # mantido para os testes/leitores que importam daqui


class EditorHud:
    """Desenha um painel PIL e mapeia botões, cores, texturas e roda."""

    def __init__(self) -> None:
        self.quad: HudQuad | None = HudQuad()
        self.backdrop: HudQuad | None = HudQuad()
        if self.backdrop is not None:
            self.backdrop.set_image(Image.new("RGBA", (1, 1), (13, 18, 26, 255)))
        self._key: tuple | None = None
        self._image: Image.Image | None = None
        self._dirty = False
        self._buttons: dict[str, tuple[int, int, int, int]] = {}
        self._colour_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._texture_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._filter_boxes: dict[str, tuple[int, int, int, int]] = {}
        self._recent_boxes: dict[int, tuple[int, int, int, int]] = {}
        self._search_box: tuple[int, int, int, int] | None = None
        self._texture_names: dict[int, str] = {}
        self._wheel_box: tuple[int, int, int, int] | None = None
        self._value_box: tuple[int, int, int, int] | None = None
        self._scale = 1.0
        self._panel_origin = (12.0, 12.0)
        self._panel_size = (float(PANEL_WIDTH), float(PANEL_HEIGHT))

    def _font(self, size: int) -> Any:
        return ui_font(size)

    def _button(self, draw, box, label: str, active: bool, font, large: bool = False) -> None:
        x0, y0, x1, y1 = box
        draw.rounded_rectangle(box, radius=5,
                               fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                               outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
        text_colour = (20, 24, 30, 255) if active else (210, 218, 228, 255)
        try:
            width = draw.textbbox((0, 0), label, font=font)[2] / RENDER_SCALE
        except Exception:
            width = len(label) * 6
        text_y = y0 + max(5, (y1 - y0 - 16) / 2) if large else y0 + 5
        draw.text(((x0 + x1 - width) / 2, text_y), label, font=font, fill=text_colour)

    def _tab(self, draw, box, label: str, active: bool, font) -> None:
        self._button(draw, box, label, active, font)

    def set_state(self, title: str, lines: Iterable[tuple[str, tuple[int, int, int]]],
                  swatch: tuple[int, int, int] | None = None,
                  active_tool: str = "build",
                  palette: Iterable[tuple[str, tuple[int, int, int]]] = (),
                  colour_index: int = 0,
                  custom_colour: tuple[int, int, int] | None = None,
                  textures: Iterable[tuple[int, str, Image.Image]] = (),
                  texture_index: int = 0,
                  active_tab: str = "colors",
                  recent_colours: Iterable[tuple[int, int, int]] = (),
                  hsv: tuple[float, float, float] = (0.0, 0.0, 1.0),
                  filters: Iterable[str] = (),
                  active_filter: str = "Todas",
                  texture_search: str = "",
                  search_mode: bool = False,
                  favourites: Iterable[str] = (),
                  hover_texture: str = "",
                  texture_name: str = "",
                  grid_size: tuple[int, int, int] = (16, 16, 16),
                  grid_spacing: int = 1,
                  light_enabled: bool = False) -> None:
        rows = tuple(lines)
        palette = tuple(palette)
        textures = tuple(textures)
        filters = tuple(filters)
        recent = tuple(recent_colours)
        texture_names = tuple((texture_id, name) for texture_id, name, _ in textures)
        favourites = tuple(sorted(favourites))
        key = (title, rows, swatch, active_tool, palette, colour_index, custom_colour,
               texture_names, texture_index, active_tab, recent, filters, active_filter,
               texture_search, search_mode, favourites, hover_texture, texture_name,
               grid_size, grid_spacing, light_enabled,
               (round(hsv[0] * 360), round(hsv[1] * 100), round(hsv[2] * 100)))
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH * RENDER_SCALE, PANEL_HEIGHT * RENDER_SCALE), (0, 0, 0, 0))
        draw = ScaledDraw(ImageDraw.Draw(image), RENDER_SCALE)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 255), outline=(232, 186, 76, 255), width=2)
        title_font = self._font(18 * RENDER_SCALE)
        body_font = self._font(14 * RENDER_SCALE)
        small_font = self._font(11 * RENDER_SCALE)
        button_font = self._font(11 * RENDER_SCALE)
        tool_font = self._font(16 * RENDER_SCALE)
        draw.text((16, 12), title, font=title_font, fill=(240, 208, 120, 255))
        y = 42
        for text, colour in rows:
            draw.text((16, y), text, font=body_font, fill=(*colour, 255))
            y += 19
        if swatch is not None:
            draw.rounded_rectangle((PANEL_WIDTH - 54, 12, PANEL_WIDTH - 18, 34), radius=5,
                                   fill=(*swatch, 255), outline=(255, 255, 255, 200), width=1)

        grid_box = (14, 140, 246, 170)
        light_box = (254, 140, PANEL_WIDTH - 14, 170)
        draw.rounded_rectangle(grid_box, radius=6, fill=(31, 57, 78, 255),
                               outline=(90, 167, 220, 255), width=2)
        draw.text((grid_box[0] + 12, grid_box[1] + 8),
                  f"GRADE {grid_size[0]}x{grid_size[1]}x{grid_size[2]}  PASSO {grid_spacing}",
                  font=small_font, fill=(220, 240, 255, 255))
        light_fill = (37, 74, 57, 255) if light_enabled else (55, 43, 48, 255)
        light_outline = (105, 220, 145, 255) if light_enabled else (174, 105, 112, 255)
        light_text = "BLOCO COM LUZ: ATIVO" if light_enabled else "BLOCO COM LUZ: INATIVO"
        draw.rounded_rectangle(light_box, radius=6, fill=light_fill, outline=light_outline, width=2)
        draw.text((light_box[0] + 12, light_box[1] + 8), light_text, font=body_font,
                  fill=(225, 245, 230, 255) if light_enabled else (235, 210, 214, 255))

        self._buttons = {}
        for index, (key_id, label) in enumerate(TOOLS):
            top = 180 + index * 52
            box = (14, top, PANEL_WIDTH - 14, top + 46)
            self._buttons[key_id] = box
            self._button(draw, box, label, key_id == active_tool, tool_font, large=True)
        for index, (key_id, label) in enumerate(ACTIONS):
            column, row = index % 5, index // 5
            box = (14 + column * 94, 392 + row * 34,
                   14 + column * 94 + 88, 420 + row * 34)
            self._buttons[key_id] = box
            self._button(draw, box, label, False, button_font)

        # Abas de conteúdo: só uma ocupa o espaço, evitando um painel gigante.
        for index, (tab_id, label) in enumerate(TABS):
            box = (14 + index * 112, 458, 14 + index * 112 + 106, 488)
            self._buttons["tab:" + tab_id] = box
            self._tab(draw, box, label, tab_id == active_tab, button_font)

        self._colour_boxes = {}
        self._texture_boxes = {}
        self._filter_boxes = {}
        self._recent_boxes = {}
        self._search_box = None
        self._texture_names = {texture_id: name for texture_id, name, _ in textures}
        self._wheel_box = None
        self._value_box = None
        if active_tab == "textures":
            for position, (texture_id, name, thumb) in enumerate(textures):
                column, row = position % 8, position // 8
                box = (16 + column * 58, 560 + row * 56,
                       16 + column * 58 + 52, 560 + row * 56 + 52)
                self._texture_boxes[texture_id] = box
                if thumb.size != (52 * RENDER_SCALE, 52 * RENDER_SCALE):
                    thumb = thumb.resize((52 * RENDER_SCALE, 52 * RENDER_SCALE), Image.Resampling.NEAREST)
                image.paste(thumb.convert("RGBA"), (box[0] * RENDER_SCALE, box[1] * RENDER_SCALE))
                active = texture_id == texture_index
                draw.rounded_rectangle(box, radius=3,
                                       outline=(255, 235, 160, 255) if active else (45, 55, 68, 255),
                                       width=3 if active else 1)
                if name in favourites:
                    draw.ellipse((box[2] - 9, box[1] + 3, box[2] - 3, box[1] + 9),
                                 fill=(240, 200, 90, 255), outline=(40, 34, 20, 255))
            # Busca textual: campo próprio, sem depender de janela nativa.
            self._search_box = (16, 500, PANEL_WIDTH - 16, 524)
            draw.rounded_rectangle(self._search_box, radius=4, fill=(25, 33, 44, 255),
                                   outline=(100, 118, 140, 255), width=1)
            query = (f"Buscar: {texture_search}_" if search_mode else
                     (f"Buscar: {texture_search}" if texture_search else "Buscar textura… [S]"))
            draw.text((23, 505), query, font=small_font,
                      fill=(240, 228, 195, 255) if search_mode else (165, 178, 195, 255))
            for index, label in enumerate(filters):
                box = (14 + index * 78, 530, 14 + index * 78 + 74, 552)
                self._filter_boxes[label] = box
                self._button(draw, box, label, label == active_filter, small_font)
            if not textures:
                draw.text((16, 792), "Nenhuma textura neste filtro.", font=small_font,
                          fill=(245, 120, 100, 255))
            elif hover_texture:
                draw.text((16, 792), f"Sobre: {hover_texture}", font=small_font,
                          fill=(240, 205, 140, 255))
            else:
                draw.text((16, 792), f"Textura: {texture_name}", font=small_font,
                          fill=(190, 202, 218, 255))
        else:
            if swatch is not None:
                wheel = wheel_image(WHEEL_SIZE * RENDER_SCALE)
                image.alpha_composite(wheel, (WHEEL_BOX[0] * RENDER_SCALE, WHEEL_BOX[1] * RENDER_SCALE))
                self._wheel_box = WHEEL_BOX
                # Barra de valor: preta -> cor de matiz/saturação atual.
                vx0, vy0, vx1, vy1 = VALUE_BOX
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hsv[0] % 1.0, max(0.0, min(1.0, hsv[1])), 1.0)
                for x in range(vx0, vx1):
                    t = (x - vx0) / max(1, vx1 - vx0 - 1)
                    draw.line((x, vy0, x, vy1), width=RENDER_SCALE,
                              fill=(round(r * 255 * t), round(g * 255 * t),
                                    round(b * 255 * t), 255))
                self._value_box = VALUE_BOX
                knob = vx0 + round((vx1 - vx0 - 1) * max(0.0, min(1.0, hsv[2])))
                draw.rectangle((knob - 1, vy0 - 2, knob + 1, vy1 + 2), fill=(255, 255, 255, 255))

            draw.text((18, 502), "RODA DE COR", font=small_font,
                      fill=(180, 190, 205, 255))
            draw.text((280, 502), "PALETA", font=small_font, fill=(180, 190, 205, 255))
            current = custom_colour if custom_colour is not None else (
                palette[colour_index][1] if palette else (255, 255, 255))
            for index, (name, colour) in enumerate(palette):
                column, row = index % 8, index // 8
                box = (280 + column * 23, 522 + row * 30,
                       280 + column * 23 + 20, 522 + row * 30 + 20)
                self._colour_boxes[index] = box
                active = custom_colour is None and index == colour_index
                draw.rounded_rectangle(box, radius=3, fill=(*colour, 255),
                                       outline=(255, 235, 160, 255) if active else (40, 50, 62, 255),
                                       width=2 if active else 1)
            draw.text((280, 610), "Recentes", font=small_font, fill=(160, 172, 188, 255))
            for index, colour in enumerate(recent[:8]):
                box = (280 + index * 21, 640, 280 + index * 21 + 17, 657)
                self._recent_boxes[index] = box
                draw.rounded_rectangle(box, radius=3, fill=(*colour, 255),
                                       outline=(80, 92, 108, 255), width=1)
            draw.rounded_rectangle((PANEL_WIDTH - 64, 606, PANEL_WIDTH - 18, 632), radius=3,
                                   fill=(*current, 255), outline=(255, 255, 255, 200), width=1)

        draw.text((16, 808),
                  "F2 exportar  F3 objeto  F5 salvar  F9 carregar  Ctrl+Z desfazer",
                  font=small_font, fill=(150, 160, 175, 255))
        draw.text((16, 824),
                  "Esq: ferramenta / Construir apaga  Dir: construir  F10: menu",
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

    def hit_filter(self, x: float, y: float) -> str | None:
        for label, (x0, y0, x1, y1) in self._filter_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return label
        return None

    def hit_search(self, x: float, y: float) -> bool:
        if self._search_box is None:
            return False
        x0, y0, x1, y1 = self._search_box
        return x0 <= x <= x1 and y0 <= y <= y1

    def texture_at(self, x: float, y: float) -> str | None:
        for texture_id, (x0, y0, x1, y1) in self._texture_boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return self._texture_names.get(texture_id)
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

    def _fit_scale(self, window_width: int, window_height: int) -> float:
        """Escala o painel para acompanhar a altura do canvas sem cobri-lo."""
        available_w = max(1.0, float(window_width) * 0.5 - 24.0)
        available_h = max(1.0, float(window_height) - 24.0)
        return max(MIN_UI_SCALE, min(available_w / PANEL_WIDTH, available_h / PANEL_HEIGHT))

    def canvas_rect(self, window_width: int, window_height: int) -> tuple[int, int, int, int]:
        """Área do mundo (x, y, largura, altura) à esquerda da barra lateral."""
        scale = self._fit_scale(window_width, window_height)
        panel_width = PANEL_WIDTH * scale
        right = max(1, int(round(window_width - panel_width - 24)))
        return 12, 12, max(1, right - 12), max(1, window_height - 24)

    def local_point(self, x: float, y: float) -> tuple[float, float] | None:
        """Converte coordenadas de janela para o espaço lógico do painel."""
        if self._scale <= 0.0:
            return None
        x0, y0 = self._panel_origin
        px = (float(x) - x0) / self._scale
        py = (float(y) - y0) / self._scale
        if 0.0 <= px <= PANEL_WIDTH and 0.0 <= py <= PANEL_HEIGHT:
            return px, py
        return None

    def contains_window(self, x: float, y: float) -> bool:
        return self.local_point(x, y) is not None

    def render(self, window_width: int, window_height: int) -> None:
        if self._image is not None and self.quad is not None:
            if self._dirty:
                self.quad.set_image(self._image)
                self._dirty = False
            self._scale = self._fit_scale(window_width, window_height)
            self._panel_size = (PANEL_WIDTH * self._scale, PANEL_HEIGHT * self._scale)
            x = float(window_width) - self._panel_size[0] - 12.0
            y = 12.0
            self._panel_origin = (x, y)
            if self.backdrop is not None:
                self.backdrop.draw(x, 0.0, window_width, window_height,
                                   size=(self._panel_size[0] + 12.0, float(window_height)))
            self.quad.draw(x, y, window_width, window_height, size=self._panel_size)

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None
        if self.backdrop is not None:
            self.backdrop.delete()
            self.backdrop = None
