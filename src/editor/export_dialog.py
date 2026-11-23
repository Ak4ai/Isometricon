"""Modal de nome e exportação de objeto do editor.

Um único lugar para nomear, ver o arquivo de destino, confirmar sobrescrita e
saber onde o objeto vai aparecer depois (``/schem``). É desenhado em Pillow e
apresentado por ``HudQuad`` em 2×; as hitboxes continuam em coordenadas
lógicas e acompanham a escala da janela.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PIL import Image, ImageDraw

from src.core.fonts import ui_font
from src.editor.object_names import EXPORT_OBJECTS, PROJECT_ROOT, slugify
from src.rendering.hud_quad import HudQuad
from src.rendering.scaled_draw import RENDER_SCALE, ScaledDraw

WIDTH = 600
HEIGHT = 330
MIN_SCALE = 0.45


class ExportDialog:
    """Modal de exportação; a lógica de salvar fica no ``MapEditor``."""

    def __init__(self, create_gl: bool = True) -> None:
        self.is_open = False
        self.done = False
        self.name = "objeto"
        self.path = ""
        self.error = ""
        self.dimensions = (16, 16, 16)
        self.voxels = 0
        self.materials = 0
        self._replace = True
        self._focused = True
        self._scale = 1.0
        self._origin = (0.0, 0.0)
        self._image: Optional[Image.Image] = None
        self._dirty = True
        self._key = None
        self.quad = HudQuad() if create_gl else None
        self.dim_quad = HudQuad() if create_gl else None
        if self.dim_quad is not None:
            self.dim_quad.set_image(Image.new("RGBA", (1, 1), (0, 0, 0, 255)))
        self.buttons: dict[str, Tuple[float, float, float, float]] = {}
        self.name_box = (24, 106, WIDTH - 24, 142)

    # ------------------------------------------------------------------ abrir/fechar
    def open(self, name: str, dimensions=(16, 16, 16), voxels: int = 0, materials: int = 0) -> None:
        self.is_open = True
        self.done = False
        self.name = str(name).strip() or "objeto"
        self.dimensions = tuple(int(v) for v in dimensions)
        self.voxels = int(voxels)
        self.materials = int(materials)
        self.error = ""
        self._replace = True
        self._focused = True
        self._refresh_path()
        self._dirty = True
        self._key = None

    def close(self) -> None:
        self.is_open = False
        self.done = False

    def mark_done(self, path: str) -> None:
        self.done = True
        self.path = os.path.abspath(path)
        self.error = ""
        self._dirty = True
        self._key = None

    def focus_name(self) -> None:
        self._focused = True
        self._dirty = True

    def set_error(self, message: str) -> None:
        self.error = str(message)
        self._dirty = True
        self._key = None

    @property
    def filename(self) -> str:
        return slugify(self.name) + ".json"

    def _refresh_path(self) -> None:
        self.path = os.path.abspath(os.path.join(EXPORT_OBJECTS, self.filename))

    def _relative_path(self) -> str:
        try:
            return os.path.relpath(self.path, PROJECT_ROOT)
        except ValueError:
            return self.path

    @property
    def overwrite(self) -> bool:
        return bool(self.path) and os.path.exists(self.path)

    # ------------------------------------------------------------------ entrada
    def handle_char(self, codepoint: int) -> bool:
        if not self.is_open or self.done:
            return False
        character = chr(codepoint)
        if not character.isprintable() or character in "/\\":
            return False
        if self._replace:
            self.name = character
            self._replace = False
        elif len(self.name) < 48:
            self.name += character
        else:
            return True
        self._focused = True
        self.error = ""
        self._refresh_path()
        self._dirty = True
        return True

    def handle_key(self, key: int, modifiers: int = 0) -> Optional[str]:
        """Devolve ``export``, ``cancel`` ou ``continue`` quando o editor deve agir."""
        import glfw

        if not self.is_open:
            return None
        if key == glfw.KEY_ESCAPE:
            return "continue" if self.done else "cancel"
        if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
            return "continue" if self.done else "export"
        if self.done:
            return "continue"
        if key == glfw.KEY_BACKSPACE:
            if self._replace:
                self.name = ""
                self._replace = False
            else:
                self.name = self.name[:-1]
            self.error = ""
            self._refresh_path()
            self._dirty = True
            return None
        if key == glfw.KEY_A and modifiers & glfw.MOD_CONTROL:
            self._replace = True
            return None
        return None

    # ------------------------------------------------------------------ mouse
    def _fit_scale(self, window_width: int, window_height: int) -> float:
        available_w = max(1.0, float(window_width) - 40.0)
        available_h = max(1.0, float(window_height) - 40.0)
        return max(MIN_SCALE, min(1.0, available_w / WIDTH, available_h / HEIGHT))

    def local_point(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        if not self.is_open:
            return None
        px = (float(x) - self._origin[0]) / self._scale
        py = (float(y) - self._origin[1]) / self._scale
        if 0 <= px <= WIDTH and 0 <= py <= HEIGHT:
            return px, py
        return None

    def hit(self, x: float, y: float) -> Optional[str]:
        for action, (x0, y0, x1, y1) in self.buttons.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return action
        if not self.done and self.name_box[0] <= x <= self.name_box[2] and self.name_box[1] <= y <= self.name_box[3]:
            return "name"
        return None

    # ------------------------------------------------------------------ desenho
    def _button(self, draw, box, label: str, primary: bool = False) -> None:
        active = primary
        draw.rounded_rectangle(box, radius=7,
                               fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                               outline=(255, 235, 160, 255) if active else (80, 95, 115, 255), width=1)
        font = ui_font(13 * RENDER_SCALE)
        width = draw.textbbox((0, 0), label, font=font)[2] / RENDER_SCALE
        draw.text((box[0] + (box[2] - box[0] - width) / 2, box[1] + 8), label, font=font,
                  fill=(20, 24, 30, 255) if active else (215, 222, 232, 255))

    def _draw(self) -> None:
        image = Image.new("RGBA", (WIDTH * RENDER_SCALE, HEIGHT * RENDER_SCALE), (0, 0, 0, 0))
        draw = ScaledDraw(ImageDraw.Draw(image), RENDER_SCALE)
        draw.rounded_rectangle((0, 0, WIDTH - 1, HEIGHT - 1), radius=12,
                               fill=(14, 20, 29, 250), outline=(232, 186, 76, 255), width=2)
        title_font = ui_font(20 * RENDER_SCALE, heading=True)
        body = ui_font(13 * RENDER_SCALE)
        small = ui_font(11 * RENDER_SCALE)
        draw.text((26, 18), "OBJETO EXPORTADO" if self.done else "SALVAR OBJETO",
                  font=title_font, fill=(240, 208, 120, 255))
        if self.done:
            draw.text((26, 54), "O arquivo já está na biblioteca de construções.", font=body,
                      fill=(205, 216, 226, 255))
            draw.text((26, 88), self._relative_path(), font=body, fill=(255, 229, 160, 255))
            draw.text((26, 124), "Para colocar no mundo:", font=small, fill=(150, 162, 178, 255))
            draw.text((26, 144), "Menu → Nova aventura → /schem → Exportados",
                      font=body, fill=(220, 228, 236, 255))
            if self.error:
                draw.text((26, 178), self.error, font=small, fill=(245, 120, 100, 255))
            draw.text((26, 244), "Enter/Esc: continuar", font=small, fill=(150, 162, 178, 255))
            self.buttons = {"continue": (420, 274, WIDTH - 24, 310)}
            self._button(draw, self.buttons["continue"], "Continuar", primary=True)
        else:
            draw.text((26, 50), "O arquivo fica em saves/objetos e aparece no /schem.",
                      font=body, fill=(185, 198, 212, 255))
            draw.text((24, 82), "Nome do objeto", font=small, fill=(160, 174, 190, 255))
            draw.rounded_rectangle(self.name_box, radius=5, fill=(25, 33, 44, 255),
                                   outline=(232, 186, 76, 255) if self._focused else (90, 105, 122, 255),
                                   width=2 if self._focused else 1)
            shown = self.name or "objeto"
            draw.text((self.name_box[0] + 10, self.name_box[1] + 8), shown,
                      font=body, fill=(240, 232, 210, 255) if self.name else (130, 142, 158, 255))
            if self._focused:
                caret_x = self.name_box[0] + 10 + draw.textbbox((0, 0), shown, font=body)[2] / RENDER_SCALE
                draw.line((caret_x, self.name_box[1] + 9, caret_x, self.name_box[3] - 9),
                          fill=(240, 208, 120, 255), width=2)
            draw.text((24, 154), "Arquivo", font=small, fill=(160, 174, 190, 255))
            draw.text((24, 172), self._relative_path(), font=body, fill=(205, 216, 226, 255))
            draw.text((24, 202),
                      f"{self.dimensions[0]}×{self.dimensions[1]}×{self.dimensions[2]}  ·  "
                      f"{self.voxels} voxels  ·  {self.materials} material(is)",
                      font=small, fill=(150, 162, 178, 255))
            if self.overwrite:
                draw.text((24, 226), "Já existe um arquivo com esse nome; exportar substitui.",
                          font=small, fill=(245, 190, 100, 255))
            elif self.error:
                draw.text((24, 226), self.error, font=small, fill=(245, 120, 100, 255))
            draw.text((24, 248), "Enter: exportar  ·  Esc: cancelar", font=small,
                      fill=(150, 162, 178, 255))
            self.buttons = {
                "export": (300, 274, 444, 310),
                "cancel": (456, 274, WIDTH - 24, 310),
            }
            self._button(draw, self.buttons["export"], "Substituir" if self.overwrite else "Exportar",
                         primary=True)
            self._button(draw, self.buttons["cancel"], "Cancelar")
        self._image = image
        self._dirty = True

    def render(self, window_width: int, window_height: int) -> None:
        if not self.is_open or self.quad is None:
            return
        self._scale = self._fit_scale(window_width, window_height)
        width, height = WIDTH * self._scale, HEIGHT * self._scale
        self._origin = ((window_width - width) / 2, (window_height - height) / 2)
        if self.dim_quad is not None:
            self.dim_quad.draw(0, 0, window_width, window_height,
                               size=(window_width, window_height), opacity=0.48)
        if self._image is None or self._dirty:
            self._draw()
            self.quad.set_image(self._image)
            self._dirty = False
        self.quad.draw(self._origin[0], self._origin[1], window_width, window_height,
                       size=(width, height))

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None
        if self.dim_quad is not None:
            self.dim_quad.delete()
            self.dim_quad = None
