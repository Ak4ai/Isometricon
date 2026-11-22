"""Painel de construções: escolher, colocar com o mouse, girar, selecionar, remover e dar nome.

Fica escondido até o ``/schem``. Fechado, não desenha nem consome tecla, caractere ou clique. Comanda o
``SchematicTool`` (o motor: holograma, colisão, portas, baús, corte do terreno); o desenho do painel é o dos "objetos no
mundo" do editor do Rafael, que ele substitui no jogo.

Teclas com o painel aberto: P colocar, V selecionar, R girar, N nome, F3 próxima construção, F4 lista (↑/↓ e Enter),
Del/Backspace remover, Esc fecha. As setas, Shift+↑/↓ e Enter continuam com a ferramenta (ajuste fino do holograma).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import glfw
from PIL import Image, ImageDraw, ImageFont

from src.world import BlockType

PANEL_WIDTH = 440
PANEL_HEIGHT = 220
MARGIN = 16
LIST_ROWS = 7
_FONT_CANDIDATES = (
    "consola.ttf", "consolas.ttf", "C:/Windows/Fonts/consola.ttf",
    "segoeui.ttf", "arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttf",
)
ACTIONS = (
    ("place", "Colocar"),
    ("select", "Selecionar"),
    ("library", "Construção"),
    ("rotate", "Girar"),
    ("remove", "Remover"),
    ("close", "Sair"),
)
HELP = "P/V modo  F3/F4 construção  R girar  N nome  Del remover  Esc sair"


def _font(size: int):
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


class ConstructionPanel:
    PLACE = "place"
    SELECT = "select"

    def __init__(self, tool, library: Callable[[], List[Tuple[str, dict]]], create_gl: bool = True) -> None:
        self.tool = tool
        self._read_library = library
        self._items: Optional[List[Tuple[str, dict]]] = None   # lida ao abrir (ler os JSON a cada quadro pesa)
        self.is_open = False
        self.mode = self.PLACE
        self.selected = None
        self.cursor: Optional[Tuple[int, int, int]] = None
        self.valid = False
        self._aimed = None                      # (bloco, prévia) da última vez que o holograma seguiu o mouse
        self.entry: Optional[dict] = None       # a construção escolhida (para a próxima colocação)
        self.list_open = False
        self.list_index = 0
        self.name_mode = False
        self.name_buffer = ""
        self.status = ""
        self.buttons: Dict[str, Tuple[int, int, int, int]] = {
            action: (12 + i * 70, 176, 12 + i * 70 + 66, 206) for i, (action, _) in enumerate(ACTIONS)}
        self.quad = None
        if create_gl:
            from src.rendering.hud_quad import HudQuad
            self.quad = HudQuad()
        self._key = None
        self._image: Optional[Image.Image] = None
        self._dirty = False
        self._scale = 1.0

    def library(self) -> List[Tuple[str, dict]]:
        """(rótulo, entrada) de tudo que dá para colocar, lida da pasta ao abrir o painel."""
        if self._items is None:
            self._items = list(self._read_library())
        return self._items

    # ------------------------------------------------------------------ abrir e fechar
    def open(self, entry: Optional[dict] = None) -> None:
        """Abre em modo Colocar; com ``entry``, já com essa construção no holograma."""
        self._items = None   # relê: um .schem ou objeto novo aparece sem reiniciar o jogo
        self.is_open = True
        self.mode = self.PLACE
        self.selected = None
        if entry is not None:
            self._take(entry)
        elif self.tool.preview is not None:
            self.entry = self.tool.preview.entry
        else:
            items = self.library()
            if items:
                self._take(items[0][1])
            else:
                self.status = "Nenhuma construção na biblioteca."

    def close(self) -> None:
        """Fecha: o holograma some, o que já foi fixado fica."""
        self.tool.cancel(silent=True)
        self.is_open = False
        self.list_open = False
        self.name_mode = False
        self.selected = None
        self.cursor = None
        self.valid = False

    def _take(self, entry: dict, rotation: int = 0) -> bool:
        ok, message = self.tool.load_entry(entry)
        self.status = message.split(". ")[0] + "." if ok else message
        if ok:
            self.entry = entry
            self.mode = self.PLACE
            self.selected = None
            for _ in range(rotation % 4):
                self.tool.rotate_preview()
        return ok

    def _library_step(self, step: int) -> None:
        items = self.library()
        if not items:
            return
        labels = [e for _, e in items]
        current = labels.index(self.entry) if self.entry in labels else -1
        self._take(items[(current + step) % len(items)][1])

    # ------------------------------------------------------------------ cursor
    def update_cursor(self, hit, player_box) -> None:
        """``hit``: o bloco que o mouse aponta (``raycast_voxels``) ou ``None``; ``player_box``: células do jogador."""
        if not self.is_open:
            return
        self.cursor = None if hit is None else tuple(int(v) for v in hit.block)
        self.valid = False
        if self.mode != self.PLACE or hit is None or self.tool.preview is None:
            return
        if tuple(hit.normal) != (0, 1, 0) or hit.block_type == BlockType.WATER:
            return
        # só segue o mouse quando ele aponta outro bloco (ou a prévia é nova): as setas ajustam e o ajuste fica
        aimed = (self.cursor, self.tool.preview)   # o objeto, não o id: um id solto pode voltar numa prévia nova
        if self._aimed is None or aimed[0] != self._aimed[0] or aimed[1] is not self._aimed[1]:
            self._aimed = aimed
            self.tool.aim(self.cursor)
        self.valid = self.tool.fits(player_box)

    # ------------------------------------------------------------------ ações
    def _action(self, action: str) -> None:
        if action == "place":
            self.mode = self.PLACE
            self.selected = None
            if self.tool.preview is None and self.entry is not None:
                self._take(self.entry)
        elif action == "select":
            self.mode = self.SELECT
            self.tool.cancel(silent=True)
            self.status = "Clique numa construção para selecionar."
        elif action == "library":
            self.list_open = not self.list_open
            labels = [e for _, e in self.library()]
            self.list_index = labels.index(self.entry) if self.entry in labels else 0
        elif action == "rotate":
            if self.mode == self.PLACE:
                self.tool.rotate_preview()
            elif self.selected is not None:
                index = self.tool.layer.structures.index(self.selected)
                ok, self.status = self.tool.rotate_placed(self.selected)
                self.selected = self.tool.layer.structures[index] if ok else self.selected
        elif action == "remove":
            if self.selected is not None:
                _, self.status = self.tool.remove(self.selected)
                self.selected = None
        elif action == "close":
            self.close()

    def _place(self) -> None:
        if not self.valid or self.tool.preview is None:
            self.status = "Aqui não cabe: aponte para o topo de um bloco livre."
            return
        rotation = self.tool.preview.rotation
        _, self.status = self.tool.confirm()
        if self.entry is not None:
            message = self.status
            self._take(self.entry, rotation)   # já pronto para pôr outra igual
            self.status = message
        self.valid = False

    def _apply_name(self) -> None:
        name = self.name_buffer.strip() or "construção"
        self.name_mode = False
        self.name_buffer = ""
        if self.mode == self.SELECT and self.selected is not None:
            self.selected.name = name
            self.tool.on_change()
        elif self.tool.preview is not None:
            self.tool.preview.name = name
        self.status = f"Nome: {name}."

    # ------------------------------------------------------------------ entrada
    def handle_key(self, key: int, action: int, mods: int) -> bool:
        if not self.is_open or action not in (glfw.PRESS, glfw.REPEAT):
            return False
        if self.name_mode:
            if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
                self._apply_name()
            elif key == glfw.KEY_ESCAPE:
                self.name_mode = False
                self.name_buffer = ""
            elif key == glfw.KEY_BACKSPACE:
                self.name_buffer = self.name_buffer[:-1]
            return True
        if self.list_open:
            items = self.library()
            if key in (glfw.KEY_UP, glfw.KEY_DOWN) and items:
                self.list_index = (self.list_index + (1 if key == glfw.KEY_DOWN else -1)) % len(items)
            elif key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER) and items:
                self.list_open = False
                self._take(items[self.list_index][1])
            elif key in (glfw.KEY_ESCAPE, glfw.KEY_F4):
                self.list_open = False
            return True
        if key == glfw.KEY_ESCAPE:
            self.close()
            return True
        if key == glfw.KEY_P:
            self._action("place")
        elif key == glfw.KEY_V:
            self._action("select")
        elif key == glfw.KEY_R:
            self._action("rotate")
        elif key == glfw.KEY_F3:
            self._library_step(1)
        elif key == glfw.KEY_F4:
            self._action("library")
        elif key in (glfw.KEY_DELETE, glfw.KEY_BACKSPACE):
            self._action("remove")
        elif key == glfw.KEY_N:
            self.name_mode = True
            current = (self.selected.name if self.mode == self.SELECT and self.selected is not None
                       else (self.tool.preview.name if self.tool.preview is not None else ""))
            self.name_buffer = ""
            self.status = f"Novo nome para {current or 'a construção'}: digite e Enter."
        else:
            return False
        return True

    def handle_char(self, codepoint: int) -> bool:
        if not self.is_open or not self.name_mode:
            return False
        character = chr(codepoint)
        if character.isprintable() and character not in "/\\" and len(self.name_buffer) < 40:
            self.name_buffer += character
        return True

    @staticmethod
    def _panel_scale(window_width: int) -> float:
        """Escala o painel apenas quando a janela é estreita demais."""
        available = max(1.0, float(window_width) - 2.0 * MARGIN)
        return max(0.55, min(1.0, available / PANEL_WIDTH))

    def contains(self, x: float, y: float, window_width: int) -> bool:
        scale = self._panel_scale(window_width)
        x0 = window_width - PANEL_WIDTH * scale - MARGIN
        return x0 <= x <= x0 + PANEL_WIDTH * scale and MARGIN <= y <= MARGIN + PANEL_HEIGHT * scale

    def handle_mouse_button(self, button: int, action: int, shift: bool, mouse_window, window_width: int) -> bool:
        if not self.is_open or button != glfw.MOUSE_BUTTON_LEFT or action != glfw.PRESS or shift:
            return False
        if mouse_window is not None and self.contains(mouse_window[0], mouse_window[1], window_width):
            scale = self._panel_scale(window_width)
            x0 = window_width - PANEL_WIDTH * scale - MARGIN
            x = (mouse_window[0] - x0) / scale
            y = (mouse_window[1] - MARGIN) / scale
            for name, (x0, y0, x1, y1) in self.buttons.items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    self._action(name)
                    break
            return True   # o painel come o clique: nada é colocado atrás dele
        if self.mode == self.PLACE:
            self._place()
            return True
        if self.cursor is not None:
            self.selected = self.tool.layer.structure_at(*self.cursor)
            self.status = (f"{self.selected.name} selecionada." if self.selected is not None
                           else "Nenhuma construção aqui.")
        return True

    # ------------------------------------------------------------------ desenho
    def _lines(self) -> List[Tuple[str, Tuple[int, int, int]]]:
        if self.list_open:
            items = self.library()
            start = max(0, min(self.list_index - LIST_ROWS // 2, len(items) - LIST_ROWS))
            rows = []
            for i, (label, _) in enumerate(items[start:start + LIST_ROWS], start):
                mark = "›" if i == self.list_index else " "
                rows.append((f"{mark} {label}", (245, 210, 120) if i == self.list_index else (200, 210, 220)))
            return rows + [("↑/↓ escolhe · Enter pega · Esc volta", (150, 160, 175))]
        preview = self.tool.preview
        mode = "colocar" if self.mode == self.PLACE else "selecionar"
        cursor = "—" if self.cursor is None else f"({self.cursor[0]}, {self.cursor[1]}, {self.cursor[2]})"
        validity = "—" if self.mode != self.PLACE else ("cabe" if self.valid else "não cabe")
        selected = self.selected.name if self.selected is not None else "nenhuma"
        name = preview.name if preview is not None else selected
        lines = [
            (f"Modo: {mode}   Construção: {preview.name if preview is not None else '—'}", (220, 226, 235)),
            (f"No mundo: {len(self.tool.layer)}   Selecionada: {selected}", (200, 210, 220)),
            (f"Cursor: {cursor}   {validity}", (200, 210, 220)),
            (f"Nome: {name} [N]", (200, 210, 220)),
            (self.status, (245, 210, 120)),
            (HELP, (150, 160, 175)),
        ]
        if self.name_mode:
            lines[-1] = (f"Nome: {self.name_buffer}_  (Enter aplica, Esc cancela)", (245, 210, 120))
        return lines

    def _draw_image(self) -> None:
        lines = tuple(self._lines())
        key = (lines, self.mode)
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH, PANEL_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 238), outline=(232, 186, 76, 255), width=2)
        draw.text((14, 10), "CONSTRUÇÕES — ISOMETRICON", font=_font(16), fill=(240, 208, 120, 255))
        y = 36
        for text, colour in lines:
            draw.text((14, y), text, font=_font(13), fill=(*colour, 255))
            y += 18
        active_action = "library" if self.list_open else self.mode
        for action, label in ACTIONS:
            box = self.buttons[action]
            active = action == active_action
            draw.rounded_rectangle(box, radius=5,
                                   fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                                   outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
            colour = (20, 24, 30, 255) if active else (210, 218, 228, 255)
            try:
                width = draw.textbbox((0, 0), label, font=_font(10))[2]
            except Exception:
                width = len(label) * 6
            draw.text((box[0] + (box[2] - box[0] - width) / 2, box[1] + 6), label, font=_font(10), fill=colour)
        self._image = image
        self._dirty = True

    def render(self, window_width: int, window_height: int) -> None:
        if not self.is_open:
            return
        self._draw_image()
        if self.quad is None or self._image is None:
            return
        if self._dirty:
            self.quad.set_image(self._image)
            self._dirty = False
        self._scale = self._panel_scale(window_width)
        width = PANEL_WIDTH * self._scale
        height = PANEL_HEIGHT * self._scale
        self.quad.draw(
            float(window_width) - width - MARGIN, float(MARGIN), window_width, window_height,
            size=(width, height),
        )

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None
