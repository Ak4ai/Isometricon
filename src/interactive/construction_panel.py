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
from PIL import Image, ImageDraw

from src.core.fonts import ui_font
from src.interactive.construction_thumb import thumbnail_for
from src.rendering.scaled_draw import RENDER_SCALE, ScaledDraw
from src.world import BlockType

PANEL_WIDTH = 620
PANEL_HEIGHT = 360
MARGIN = 16
LIST_ROWS = 8
FILTERS = (("todos", "Tudo"), ("exportados", "Exportados"), ("schem", "Schem"))
ACTIONS = (
    ("place", "Colocar"),
    ("select", "Selecionar"),
    ("library", "Construção"),
    ("rotate", "Girar"),
    ("remove", "Remover"),
    ("close", "Sair"),
)
HELP = "Clique no chão: colocar  ·  V: selecionar  ·  Del/botão direito: remover  ·  Esc: sair"


def _font(size: int):
    return ui_font(size)


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
            action: (12 + i * 100, 310, 12 + i * 100 + 94, 340) for i, (action, _) in enumerate(ACTIONS)}
        self.filters: Dict[str, Tuple[int, int, int, int]] = {}
        self.list_rows: Dict[int, Tuple[int, int, int, int]] = {}
        self.preview_box = (428, 36, 608, 196)
        self.filter_mode = "todos"
        self._filter_items: Optional[List[Tuple[str, dict]]] = None
        self._thumb_entry = None
        self._thumb_image: Optional[Image.Image] = None
        self._thumb_key = None
        self._last_entry = None
        self.quad = None
        if create_gl:
            from src.rendering.hud_quad import HudQuad
            self.quad = HudQuad()
        self._key = None
        self._image: Optional[Image.Image] = None
        self._dirty = False
        self._scale = 1.0

    def library(self) -> List[Tuple[str, dict]]:
        """(rótulo, entrada) da biblioteca, filtrada pela categoria ativa."""
        if self._items is None:
            self._items = list(self._read_library())
        if self._filter_items is None:
            if self.filter_mode == "exportados":
                self._filter_items = [(label, entry) for label, entry in self._items
                                      if entry.get("kind") == "object"]
            elif self.filter_mode == "schem":
                self._filter_items = [(label, entry) for label, entry in self._items
                                      if entry.get("kind") == "schem"]
            else:
                self._filter_items = list(self._items)
        return self._filter_items

    def select_filter(self, mode: str) -> None:
        if mode not in {key for key, _ in FILTERS}:
            return
        self.filter_mode = mode
        self._filter_items = None
        self.list_index = 0
        self.list_open = True
        self.status = "Filtro: " + dict(FILTERS)[mode] + "."
        self._dirty = True

    # ------------------------------------------------------------------ abrir e fechar
    def open(self, entry: Optional[dict] = None) -> None:
        """Abre em modo Colocar; com ``entry``, já com essa construção no holograma."""
        self._items = None   # relê: um .schem ou objeto novo aparece sem reiniciar o jogo
        self._filter_items = None
        self.is_open = True
        self.mode = self.PLACE
        self.selected = None
        if entry is not None:
            self._take(entry)
        elif self.tool.preview is not None:
            self.entry = self.tool.preview.entry
            self.list_open = False
        else:
            items = self.library()
            if items:
                # Abrir na lista evita começar com um .schem enorme e fora de
                # escala (29455) sem o jogador ter escolhido nada.
                self.entry = None
                self.list_open = True
                self.list_index = self._default_index(items)
                if self._last_entry in [entry for _, entry in items]:
                    self.list_index = [entry for _, entry in items].index(self._last_entry)
                self.status = "Escolha uma construção na lista; clique nela e depois no chão."
            else:
                self.list_open = False
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

    def _default_index(self, items: List[Tuple[str, dict]]) -> int:
        """Um padrão pequeno: objeto exportado, vitrine, ou o menor .schem."""
        for index, (_, entry) in enumerate(items):
            if entry.get("kind") == "object":
                return index
        for index, (_, entry) in enumerate(items):
            if entry.get("kind") == "formas":
                return index
        sizes = []
        import os
        for index, (_, entry) in enumerate(items):
            if entry.get("kind") == "schem":
                path = os.path.join(self.tool.schematics_dir, str(entry.get("name", "")) + ".schem")
                try:
                    sizes.append((os.path.getsize(path), index))
                except OSError:
                    pass
        return min(sizes)[1] if sizes else 0

    def _take(self, entry: dict, rotation: int = 0) -> bool:
        ok, message = self.tool.load_entry(entry)
        self.status = message.split(". ")[0] + "." if ok else message
        if ok:
            self.entry = entry
            self._last_entry = entry
            self.list_open = False
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
            self.status = "Clique numa construção para selecionar; Del ou botão direito remove."
        elif action == "library":
            self.list_open = not self.list_open
            labels = [e for _, e in self.library()]
            self.list_index = labels.index(self.entry) if self.entry in labels else 0
            if self.list_open:
                self.status = f"{len(self.library())} construção(ões) na biblioteca."
        elif action == "rotate":
            if self.mode == self.PLACE:
                self.tool.rotate_preview()
            elif self.selected is not None:
                index = self.tool.layer.structures.index(self.selected)
                ok, self.status = self.tool.rotate_placed(self.selected)
                self.selected = self.tool.layer.structures[index] if ok else self.selected
        elif action == "remove":
            self._remove_target()
        elif action == "close":
            self.close()

    def _remove_target(self) -> bool:
        """Remove a construção selecionada ou, no modo Selecionar, a apontada."""
        target = self.selected
        if target is None and self.mode == self.SELECT and self.cursor is not None:
            target = self.tool.layer.structure_at(*self.cursor)
        if target is None:
            if self.mode != self.SELECT:
                self.status = "Entre em Selecionar (V) e clique numa construção para remover."
            else:
                self.status = "Nenhuma construção neste ponto."
            return False
        ok, message = self.tool.remove(target)
        self.status = message
        if ok:
            self.selected = None
        return ok

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
            if key == glfw.KEY_F3 and items:
                self.list_index = (self.list_index + 1) % len(items)
                self._take(items[self.list_index][1])
                return True
            if key == glfw.KEY_E:
                self.select_filter("exportados")
                return True
            if key == glfw.KEY_T:
                self.select_filter("todos")
                return True
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
        if not self.is_open or action != glfw.PRESS or shift:
            return False
        if button == glfw.MOUSE_BUTTON_RIGHT:
            # Botão direito remove direto a construção apontada, sem caçar o botão.
            if self.mode == self.SELECT and self.cursor is not None:
                self._remove_target()
            elif self.mode == self.PLACE:
                self.status = "Botão direito remove no modo Selecionar (V)."
            return True
        if button != glfw.MOUSE_BUTTON_LEFT:
            return False
        if mouse_window is not None and self.contains(mouse_window[0], mouse_window[1], window_width):
            scale = self._panel_scale(window_width)
            x0 = window_width - PANEL_WIDTH * scale - MARGIN
            x = (mouse_window[0] - x0) / scale
            y = (mouse_window[1] - MARGIN) / scale
            for name, (x0, y0, x1, y1) in self.buttons.items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    self._action(name)
                    return True
            if self.list_open:
                for mode, (x0, y0, x1, y1) in self.filters.items():
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        self.select_filter(mode)
                        return True
                for index, (x0, y0, x1, y1) in self.list_rows.items():
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        items = self.library()
                        if 0 <= index < len(items):
                            self.list_open = False
                            self._take(items[index][1])
                        return True
            elif self.preview_box[0] <= x <= self.preview_box[2] and self.preview_box[1] <= y <= self.preview_box[3]:
                self._action("library")
                return True
            return True   # o painel come o clique: nada é colocado atrás dele
        if self.mode == self.PLACE:
            if self.list_open:
                self.status = "Escolha uma construção na lista primeiro."
                return True
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
            if not items:
                return [("Nenhuma construção neste filtro.", (245, 120, 100)),
                        ("Clique em Tudo/Exportados/Schem para trocar.", (150, 160, 175))]
            return [("Use ↑/↓ ou clique numa linha.", (150, 160, 175))]
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
        ]
        if self.name_mode:
            lines[-1] = (f"Nome: {self.name_buffer}_  (Enter aplica, Esc cancela)", (245, 210, 120))
        return lines

    def _thumbnail(self, entry: Optional[dict]) -> Optional[Image.Image]:
        if entry is None:
            return None
        key = (str(entry.get("kind", "")), str(entry.get("name", "")), id(entry))
        if key == self._thumb_key:
            return self._thumb_image
        self._thumb_key = key
        self._thumb_image = None
        try:
            from src.world.structure_sources import load_entry
            schematic = load_entry(entry, self.tool.schematics_dir)
            self._thumb_image = thumbnail_for(schematic, (164 * RENDER_SCALE, 124 * RENDER_SCALE))
        except Exception:
            self._thumb_image = None
        return self._thumb_image

    def _draw_image(self) -> None:
        lines = tuple(self._lines())
        items = self.library()
        start = max(0, min(self.list_index - LIST_ROWS // 2, len(items) - LIST_ROWS)) if items else 0
        preview_entry = None
        if self.list_open and items:
            preview_entry = items[min(self.list_index, len(items) - 1)][1]
        elif not self.list_open:
            preview_entry = self.entry
        preview = self._thumbnail(preview_entry)
        key = (lines, self.mode, self.list_open, self.list_index, self.filter_mode,
               len(items), tuple(label for label, _ in items), preview_entry is not None)
        if key == self._key:
            return
        self._key = key
        image = Image.new("RGBA", (PANEL_WIDTH * RENDER_SCALE, PANEL_HEIGHT * RENDER_SCALE), (0, 0, 0, 0))
        draw = ScaledDraw(ImageDraw.Draw(image), RENDER_SCALE)
        draw.rounded_rectangle((0, 0, PANEL_WIDTH - 1, PANEL_HEIGHT - 1), radius=10,
                               fill=(13, 18, 26, 238), outline=(232, 186, 76, 255), width=2)
        draw.text((14, 10), "CONSTRUÇÕES — ISOMETRICON", font=_font(16 * RENDER_SCALE),
                  fill=(240, 208, 120, 255))
        draw.line((14, 30, PANEL_WIDTH - 14, 30), fill=(80, 95, 115, 255), width=1)

        # Cartão da construção selecionada: miniatura + tipo/tamanho.
        draw.rounded_rectangle(self.preview_box, radius=7, fill=(20, 27, 36, 255),
                               outline=(90, 105, 125, 255), width=1)
        if preview is not None:
            image.paste(preview, (436 * RENDER_SCALE, 44 * RENDER_SCALE))
        else:
            draw.text((452, 92), "sem prévia", font=_font(12 * RENDER_SCALE), fill=(120, 132, 148, 255))
        if preview_entry is not None:
            kind = {"object": "exportado", "schem": "schem", "formas": "vitrine"}.get(
                preview_entry.get("kind"), "construção")
            draw.text((436, 174), f"{kind} · {preview_entry.get('name', '—')}"[:40],
                      font=_font(11 * RENDER_SCALE), fill=(225, 208, 160, 255))

        self.list_rows = {}
        self.filters = {}
        if self.list_open:
            y = 40
            if not items:
                draw.text((14, y), "Nenhuma construção neste filtro.", font=_font(13 * RENDER_SCALE),
                          fill=(245, 120, 100, 255))
            for i in range(start, min(len(items), start + LIST_ROWS)):
                label, entry = items[i]
                box = (14, y, 414, y + 20)
                self.list_rows[i] = box
                active = i == self.list_index
                draw.rounded_rectangle(box, radius=4,
                                       fill=(196, 150, 45, 255) if active else (27, 35, 46, 255),
                                       outline=(240, 205, 120, 255) if active else (50, 62, 78, 255), width=1)
                tag = "obj" if entry.get("kind") == "object" else "schem"
                draw.text((20, y + 3), f"[{tag}] {label}"[:48],
                          font=_font(11 * RENDER_SCALE),
                          fill=(20, 24, 30, 255) if active else (200, 210, 220, 255))
                y += 22
            draw.text((14, 232), "Filtro", font=_font(11 * RENDER_SCALE), fill=(150, 162, 178, 255))
            for index, (mode, label) in enumerate(FILTERS):
                box = (62 + index * 122, 228, 62 + index * 122 + 114, 250)
                self.filters[mode] = box
                active = mode == self.filter_mode
                draw.rounded_rectangle(box, radius=4,
                                       fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                                       outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
                draw.text((box[0] + 8, box[1] + 5), label, font=_font(10 * RENDER_SCALE),
                          fill=(20, 24, 30, 255) if active else (210, 218, 228, 255))
            draw.text((14, 262), f"{len(items)} construção(ões) · ↑/↓ ou clique · Enter pega",
                      font=_font(10 * RENDER_SCALE), fill=(150, 160, 175, 255))
        else:
            y = 40
            for text, colour in lines:
                draw.text((14, y), text, font=_font(12 * RENDER_SCALE), fill=(*colour, 255))
                y += 19
            draw.text((14, 246), f"Biblioteca: {len(items)} · clique na prévia para abrir",
                      font=_font(10 * RENDER_SCALE), fill=(150, 160, 175, 255))
            for index, (mode, label) in enumerate(FILTERS):
                box = (14 + index * 122, 266, 14 + index * 122 + 114, 288)
                self.filters[mode] = box
                active = mode == self.filter_mode
                draw.rounded_rectangle(box, radius=4,
                                       fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                                       outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
                draw.text((box[0] + 8, box[1] + 5), label, font=_font(10 * RENDER_SCALE),
                          fill=(20, 24, 30, 255) if active else (210, 218, 228, 255))
            draw.text((14, 292), HELP, font=_font(10 * RENDER_SCALE), fill=(150, 160, 175, 255))

        active_action = "library" if self.list_open else self.mode
        for action, label in ACTIONS:
            box = self.buttons[action]
            active = action == active_action
            draw.rounded_rectangle(box, radius=5,
                                   fill=(196, 150, 45, 255) if active else (32, 41, 54, 255),
                                   outline=(240, 205, 120, 255) if active else (80, 95, 115, 255), width=1)
            colour = (20, 24, 30, 255) if active else (210, 218, 228, 255)
            try:
                width = draw.textbbox((0, 0), label, font=_font(10 * RENDER_SCALE))[2] / RENDER_SCALE
            except Exception:
                width = len(label) * 6
            draw.text((box[0] + (box[2] - box[0] - width) / 2, box[1] + 6), label,
                      font=_font(10 * RENDER_SCALE), fill=colour)
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
