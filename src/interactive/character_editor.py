"""Tela de criação de personagem: seções à esquerda, opções em grade e o personagem girando ao lado.

Abre com ``/skin interface`` (no terreno ou no visualizador ``--char``). Cada opção da grade
executa o mesmo comando do chat (``/skin olhos azul``, ``/skin top <id>``...), então a tela e o
chat nunca divergem. As roupas vêm dos itens baixados em ``assets/models/clothing``, separadas
pelo tipo do asset do Roblox.

A disposição e os cliques não dependem de OpenGL (``create_gl=False`` nos testes); o painel é
uma imagem desenhada com PIL e enviada como textura só quando muda.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import glob
import os
import re
import subprocess
import sys
import time

import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.clothing.body_shape import BODY_GROUPS, BROWS, EYES, GARMENTS, NOSE, REDRAWS_FACE, SHADING, SKIN
from src.clothing.customization import MAKEUP_COLORS
from src.clothing.character_model import DEFAULT_HAIR_ID, MODELS_DIR, SKIN_PRESETS
from src.clothing.customization import HairStyle
from src.clothing.layer_clearance import fitted_asset_type
from src.interactive.skin_commands import (
    BODIES,
    CLOTHING_DIR,
    EYE_SHAPE_NAMES,
    EYEBROWS,
    EYE_COLORS,
    EYE_STYLES,
    HAIR_COLORS,
    HEADS,
    MOUTHS,
    NOSE_STYLE_NAMES,
    PRESETS,
    SKIN_TONES,
    SkinCommandHandler,
)

Rect = Tuple[int, int, int, int]  # x0, y0, x1, y1

PANEL_WIDTH = 408
TAB_WIDTH = 104
TAB_HEIGHT = 42
FOOTER_HEIGHT = 136
PAD = 12
CARD = (88, 112)   # a garment: picture and two lines of name
TEXT_TILE = 34     # height of a named option (two to a row)
SWATCH = 32        # a colour (seven to a row)
GAP = 8
SWATCHES_PER_ROW = 7
SLIDER_TILE = 46   # height of an adjustment: its name, its value and the track
SLIDER_SNAP = 5    # this close to the middle, a slider goes back to 0
FACE_REDRAW = 0.06 # seconds between two redraws of the face while one of its sliders is dragged
SCROLL_STEP = 60
DRAG_DEGREES = 0.45  # the character turns this much for each pixel dragged sideways
TILT_DEGREES = 0.30  # and the camera tilts this much for each pixel dragged up or down,
TILT_LIMITS = (-20.0, 80.0)  # from a little below the character to almost straight above
SPIN_DEGREES = 30.0  # and this much each second on its own
FACE_SECTIONS = ("Olhos", "Rosto", "Nariz", "Maquiagem")
FINE_SECTION = "Ajuste fino"  # where the skin brush works
BRUSHES = (("esconder", "Esconder pele"), ("mostrar", "Mostrar pele"), ("apagar", "Apagar pintura"))
BRUSH_SIZES = (("Pequeno", 10), ("Médio", 22), ("Grande", 40))  # radius, in pixels of the window  # sections worked on with the camera close to the face

BACKGROUND = (22, 24, 30, 240)
TAB_STRIP = (15, 16, 20, 245)
TILE = (44, 47, 57, 255)
TILE_HOVER = (62, 66, 80, 255)
ACCENT = (255, 200, 60, 255)
TEXT = (232, 234, 240, 255)
MUTED = (150, 155, 168, 255)

# Roblox asset types of the garments of each section.
PICTURED = ("top", "jacket", "bottom", "dress", "shoes", "hair")  # kinds the thumbnail script draws
KIND_OF_TYPE = {64: "top", 65: "top", 68: "top", 67: "jacket", 66: "bottom", 69: "bottom", 72: "dress",
                70: "shoe", 71: "shoe", 41: "hair", 19: "tool"}
HAIR_WORDS = ("hair", "cabelo", "wig", "ponytail", "pigtails", "braids")
LEFT_WORDS = ("left", "esquerdo")
RIGHT_WORDS = ("right", "direito")
SHOE_WORDS = ("shoe", "boots", "sneakers", "cal_ado", "calcado")

EYE_RGB = {"azul": (70, 130, 235), "verde": (70, 190, 110), "castanho": (120, 80, 50), "roxo": (150, 90, 220),
           "vermelho": (220, 60, 60), "dourado": (230, 185, 60), "ciano": (70, 215, 225)}
HAIR_RGB = {"castanho": (105, 70, 45), "loiro": (235, 205, 120), "preto": (30, 30, 34), "rosa": (245, 160, 195),
            "prata": (215, 218, 225), "ruivo": (170, 75, 40), "ciano": (80, 210, 225)}
PORTUGUESE_EYE_STYLES = ("anime", "piscando", "classico", "sem")
PORTUGUESE_MOUTHS = ("anime", "sorriso", "aberta", "piscando", "neutra", "classica", "gato", "beicinho", "sem")


@dataclass
class Option:
    """Uma opção da grade: o que mostra e o comando do chat que aplica."""
    label: str
    command: str
    color: Optional[Tuple[int, int, int]] = None  # a colour swatch
    image: Optional[str] = None                   # a picture file (a garment)
    selected: Callable[[Any], bool] = lambda model: False
    slider: Optional[str] = None                  # an adjustment of body_shape, set from -100 to 100

    @property
    def kind(self) -> str:
        if self.slider is not None:
            return "slider"
        return "card" if self.image is not None or self.command.startswith(CARD_COMMANDS) else \
            "swatch" if self.color is not None else "text"


CARD_COMMANDS = ("/skin top ", "/skin calca ", "/skin jaqueta ", "/skin sapato ", "/skin vestir ", "/skin extra ")


@dataclass
class Group:
    title: str
    options: List[Option]


@dataclass
class Section:
    title: str
    groups: Callable[[], List[Group]]


@dataclass
class CatalogItem:
    asset_id: str  # one id, or "left,right" for a pair of shoes
    name: str
    kind: str
    image: Optional[str] = None


def _same(a: Any, b: Any) -> bool:
    return a is not None and b is not None and str(a) == str(b)


def _value(thing: Any) -> str:
    return str(getattr(thing, "value", thing)).lower()


def catalog(clothing_dir: str = CLOTHING_DIR, models_dir: str = MODELS_DIR) -> Dict[str, List[CatalogItem]]:
    """Os itens baixados, por lugar onde se vestem (top, jacket, bottom, dress, shoes, hair, other).

    O tipo vem do item já encaixado em qualquer corpo (cabeçalho do OBJ); sem ele, do nome.
    Os dois pés de um calçado viram um item só.
    """
    found: Dict[str, List[CatalogItem]] = {k: [] for k in ("top", "jacket", "bottom", "dress", "shoes", "hair", "tool", "other")}
    halves: Dict[str, Dict[str, CatalogItem]] = {}
    for path in sorted(glob.glob(os.path.join(clothing_dir, "*.rbxm"))):
        base = os.path.basename(path)
        match = re.search(r"_(\d{6,})\.rbxm$", base)
        if not match:
            continue
        asset_id, stem = match.group(1), base[:match.start()]
        lower = stem.lower()
        asset_type = next((t for t in (fitted_asset_type(os.path.join(models_dir, f"character_native_{asset_id}_{body}.obj"))
                                       for body in ("female", "male")) if t is not None), None)
        kind = KIND_OF_TYPE.get(asset_type)
        if kind is None:
            is_side = any(w in lower for w in LEFT_WORDS + RIGHT_WORDS)
            kind = ("hair" if any(w in lower for w in HAIR_WORDS)
                    else "shoe" if is_side and any(w in lower for w in SHOE_WORDS) else "other")
        thumb = os.path.join(clothing_dir, "thumbs", f"{asset_id}.png")
        texture = path[:-len(".rbxm")] + ".png"
        image = thumb if os.path.exists(thumb) else texture if os.path.exists(texture) else None
        item = CatalogItem(asset_id, re.sub(r"[_\s]+", " ", stem).strip(" -"), kind, image)
        if kind != "shoe":
            found[kind].append(item)
            continue
        side = "left" if any(w in lower for w in LEFT_WORDS) else "right"
        pair = re.sub(r"[^a-z0-9]+", " ", re.sub("|".join(LEFT_WORDS + RIGHT_WORDS), "", lower)).strip()
        pair = re.sub(r"\b(shoe|accessory|acess rio de cal ado|cla|cl)\b", "", pair).strip()
        halves.setdefault(pair, {})[side] = item
    for pair in halves.values():
        if "left" in pair and "right" in pair:
            left, right = pair["left"], pair["right"]
            name = re.sub(r"(?i)\s*-?\s*(left|right)\s*(shoe)?\s*(accessory)?", "", left.name).strip(" -") or left.name
            found["shoes"].append(CatalogItem(f"{left.asset_id},{right.asset_id}", name, "shoes", left.image))
    return found


class CharacterEditor:
    """Estado, disposição e desenho da tela de criação de personagem."""

    def __init__(self, handler: SkinCommandHandler, turntable_state: Optional[Dict[str, Any]] = None,
                 create_gl: bool = True) -> None:
        self.handler = handler
        self.turntable = turntable_state if turntable_state is not None else {"active": True, "yaw": 0.0}
        self.create_gl = create_gl
        self.autosave = True  # closing the editor saves the character
        self.typing = False   # the field that adds a Roblox item has the keyboard
        self.entry = ""
        self.clipboard: Callable[[], str] = lambda: ""
        self.make_thumbnails = create_gl  # pictures of new items are rendered by a process of their own
        self._thumbnails: Any = None
        self._pictured: set = set()
        self.is_open = False
        self.active = 0
        self.scroll = 0
        self.hover: Optional[Tuple[str, Any]] = None
        self.message = ""
        self.dirty = True
        self._dragging = False
        self._drag_x = 0.0
        self._drag_y = 0.0
        self._slider: Optional[Tuple[Option, int, int]] = None  # the adjustment being dragged and its track
        self._slider_value = 0
        self._slider_sent = 0.0
        self._was_spinning = True
        self._hits: List[Tuple[Rect, str, Any]] = []
        self._content_height = 0
        self._size = (0, 0)
        self._busy = ""
        self._selected_key: Any = None
        self._images: Dict[Tuple[str, Tuple[int, int]], Any] = {}
        self._catalog: Dict[str, List[CatalogItem]] = {}
        self._groups: Optional[List[Group]] = None
        self._quad = None
        # The skin brush: what it does (None: off), its radius, whether it paints both sides, the
        # points taken by the stroke being made, and what the main loop gives it each frame: a
        # function from the cursor to the points under it, and the points to show on the character.
        self.brush: Optional[str] = None
        self.brush_size = BRUSH_SIZES[1][1]
        self.brush_mirror = False
        self.picker: Optional[Callable[..., Any]] = None
        self.overlay: Any = None
        self.cursor = (0.0, 0.0)
        self._stroke: Optional[set] = None
        self._overlay_quad = None
        self._overlay_key: Any = None
        self._ring_quad = None
        self._ring_size = 0
        self.sections = self._make_sections()

    # ------------------------------------------------------------------ o que há para escolher
    @property
    def model(self) -> Any:
        return self.handler.character_model

    def _custom(self) -> Any:
        return getattr(self.model, "customization", None)

    def _garments(self, kind: str, command: str, slot: str) -> List[Option]:
        options = [Option("Nenhum", f"/skin {command} none", selected=lambda m, s=slot: not getattr(m, s, None))]
        for item in self._catalog.get(kind, []):
            options.append(Option(item.name, f"/skin {command} {item.asset_id}", image=item.image or "",
                                  selected=lambda m, s=slot, i=item.asset_id: _same(getattr(m, s, None), i)))
        return options

    def _make_sections(self) -> List[Section]:
        custom = self._custom
        tone_rgb = lambda name: tuple(int(round(c * 255)) for c in SKIN_PRESETS[SKIN_TONES[name]])

        def body() -> List[Group]:
            return [
                Group("Corpo", [Option(n.capitalize(), f"/skin corpo {n}", selected=lambda m, v=BODIES[n]: _value(getattr(m, "body", "")) == _value(v))
                                for n in ("feminino", "masculino")]),
                Group("Tom de pele", [Option(n.capitalize(), f"/skin pele {n}", color=tone_rgb(n),
                                             selected=lambda m, n=n: custom() is not None and all(
                                                 abs(a - b) < 0.02 for a, b in zip(custom().skin_color_rgb, SKIN_PRESETS[SKIN_TONES[n]])))
                                      for n in SKIN_TONES]),
                Group("Cabeça", [Option(n.capitalize(), f"/skin cabeca {n}", selected=lambda m, v=HEADS[n]: custom() is not None and _value(custom().head_type) == _value(v))
                                 for n in ("arredondada", "quadrada")]),
                Group("Pele", [Option(label, "", slider=name) for name, label in SKIN.items()]),
            ]

        def eyes() -> List[Group]:
            return [
                Group("Olhos", [Option(n.capitalize(), f"/skin olhos {n}", selected=lambda m, v=EYE_STYLES[n]: custom() is not None and custom().resolved_eye_style == _value(v))
                                for n in PORTUGUESE_EYE_STYLES]),
                Group("Formato dos olhos", [
                    Option(n.replace("_", " ").capitalize(), f"/skin olhos {n}",
                           selected=lambda m, n=n: custom() is not None and getattr(custom(), "eye_shape", "padrao") == n
                           and custom().resolved_eye_style not in ("classic", "blank"))
                    for n in EYE_SHAPE_NAMES]),
                Group("Cor dos olhos", [Option(n.capitalize(), f"/skin olhos {n}", color=EYE_RGB[n],
                                               selected=lambda m, v=EYE_COLORS[n]: custom() is not None and _value(custom().iris_color) == _value(v))
                                        for n in EYE_COLORS]),
                Group("Olho direito", [Option(n.capitalize(), f"/skin olho direito {n}", color=EYE_RGB[n],
                                              selected=lambda m, v=EYE_COLORS[n]: custom() is not None and _value(custom().iris_color) == _value(v))
                                       for n in EYE_COLORS]),
                Group("Olho esquerdo", [Option(n.capitalize(), f"/skin olho esquerdo {n}", color=EYE_RGB[n],
                                               selected=lambda m, v=EYE_COLORS[n]: custom() is not None and _value(
                                                   custom().iris_color_other if custom().iris_color_other is not None else custom().iris_color) == _value(v))
                                        for n in EYE_COLORS]),
                Group("Ajustes dos olhos", [Option(label, "", slider=name) for name, label in EYES.items()]),
            ]

        def face() -> List[Group]:
            return [
                Group("Boca", [Option(n.capitalize(), f"/skin boca {n}", selected=lambda m, v=MOUTHS[n]: custom() is not None and _value(custom().mouth_style) == _value(v))
                               for n in PORTUGUESE_MOUTHS]),
                Group("Sobrancelhas", [Option(n.capitalize(), f"/skin sobrancelha {n}",
                                              selected=lambda m, v=EYEBROWS[n]: custom() is not None and custom().resolved_eyebrow_style == _value(v))
                                       for n in EYEBROWS]),
                Group("Ajustes das sobrancelhas", [Option(label, "", slider=name) for name, label in BROWS.items()]),
            ]

        def nose() -> List[Group]:
            return [
                Group("Nariz", [Option("Com nariz", "/skin nariz sim", selected=lambda m: custom() is not None and custom().should_render_3d_nose),
                                Option("Sem nariz", "/skin nariz nao", selected=lambda m: custom() is not None and not custom().should_render_3d_nose)]),
                Group("Formato do nariz", [
                    Option(n.replace("_", " ").capitalize(), f"/skin nariz {n}",
                           selected=lambda m, n=n: custom() is not None and custom().should_render_3d_nose and getattr(custom(), "nose_style", "padrao") == n)
                    for n in NOSE_STYLE_NAMES]),
                Group("Sombra do nariz", [
                    Option(label, f"/skin nariz sombra {kind}",
                           selected=lambda m, kind=kind: custom() is not None and getattr(custom(), "nose_shadow", "legado") == kind)
                    for kind, label in (("legado", "Legado"), ("calculada", "Calculada"))]),
                Group("Ajustes do nariz", [Option(label, "", slider=name) for name, label in NOSE.items()]),
            ]

        def shape() -> List[Group]:
            return [Group(title, [Option(label, "", slider=name) for name, label in group])
                    for title, group in BODY_GROUPS] + [Group("Recomeçar", [Option("Voltar ao padrão", "/skin ajuste reset")])]

        def hair() -> List[Group]:
            style = lambda: _value(custom().hair_style) if custom() is not None else ""
            hair_id = lambda m: getattr(m, "hair_id", None)
            styles = [
                Option("Padrão", "/skin cabelo padrao", selected=lambda m: style() == HairStyle.ANIME_LONG.value and (not hair_id(m) or _same(hair_id(m), DEFAULT_HAIR_ID))),
                Option("Raspado", "/skin cabelo raspado", selected=lambda m: style() == HairStyle.BUZZ_CUT.value),
                Option("Careca", "/skin cabelo careca", selected=lambda m: style() in (HairStyle.BALD.value, HairStyle.NONE.value)),
            ]
            worn = [Option(item.name, f"/skin cabelo {item.asset_id}", image=item.image or "",
                           selected=lambda m, i=item.asset_id: _same(hair_id(m), i) and style() == HairStyle.ANIME_LONG.value)
                    for item in self._catalog.get("hair", []) if not _same(item.asset_id, DEFAULT_HAIR_ID)]
            groups = [Group("Estilo", styles),
                      Group("Cor", [Option(n.capitalize(), f"/skin cabelo {n}", color=HAIR_RGB[n],
                                           selected=lambda m, v=HAIR_COLORS[n]: custom() is not None and _value(custom().hair_color) == _value(v))
                                    for n in HAIR_COLORS])]
            return groups + ([Group("Cabelos do Roblox", worn)] if worn else [])

        def makeup() -> List[Group]:
            worn = lambda what: (getattr(custom(), "makeup", None) or {}).get(what) if custom() is not None else None
            detail = lambda word: custom() is not None and word in custom().resolved_face_detail
            return [
                Group("Batom", [Option(n.capitalize(), f"/skin maquiagem batom {n}", color=MAKEUP_COLORS[n],
                                       selected=lambda m, n=n: worn("batom") == n) for n in MAKEUP_COLORS]),
                Group("Sombra dos olhos", [Option(n.capitalize(), f"/skin maquiagem sombra {n}", color=MAKEUP_COLORS[n],
                                                  selected=lambda m, n=n: worn("sombra") == n) for n in MAKEUP_COLORS]),
                Group("Contorno", [Option("Sem contorno", "/skin maquiagem contorno sem", selected=lambda m: not worn("contorno")),
                                   Option("Suave", "/skin maquiagem contorno suave", selected=lambda m: worn("contorno") == "suave"),
                                   Option("Marcado", "/skin maquiagem contorno marcado", selected=lambda m: worn("contorno") == "marcado")]),
                Group("Sombras do rosto", [Option(label, "", slider=name) for name, label in SHADING.items()]),
                Group("Rosto", [Option("Blush", "/skin maquiagem blush alternar", selected=lambda m: detail("blush")),
                                Option("Sardas", "/skin maquiagem sardas alternar", selected=lambda m: detail("freckles"))]),
                Group("Tirar", [Option("Sem batom", "/skin maquiagem batom sem"), Option("Sem sombra", "/skin maquiagem sombra sem"),
                                Option("Sem maquiagem", "/skin maquiagem sem")]),
            ]

        def fine() -> List[Group]:
            mirrored = lambda m: custom() is not None and bool(getattr(custom(), "hsr_mirror", False))
            painted = lambda: len(getattr(custom(), "hsr_hide", ()) or ()) + len(getattr(custom(), "hsr_show", ()) or ()) if custom() is not None else 0
            return [
                Group("Bordas das roupas", [Option(label, "", slider=name) for name, label in GARMENTS.items()]),
                Group("Pele sob a roupa: automático", [
                    Option("Espelhar os lados", "/skin hsr espelhar sim", selected=mirrored),
                    Option("Sem espelhar", "/skin hsr espelhar nao", selected=lambda m: not mirrored(m))]),
                Group("Pincel de pele (arraste no personagem)", [Option("Desligado", "@pincel", selected=lambda m: self.brush is None)] + [
                    Option(label, f"@pincel {name}", selected=lambda m, name=name: self.brush == name) for name, label in BRUSHES]),
                Group("Tamanho do pincel", [Option(label, f"@tamanho {size}", selected=lambda m, size=size: self.brush_size == size)
                                            for label, size in BRUSH_SIZES]),
                Group("Simetria do pincel", [Option("Um lado", "@simetria nao", selected=lambda m: not self.brush_mirror),
                                             Option("Os dois lados", "@simetria sim", selected=lambda m: self.brush_mirror)]),
                Group("Pintura", [Option("Apagar tudo", "/skin hsr limpar", selected=lambda m: False)]),
            ]

        def extras() -> List[Group]:
            worn = lambda m: [str(i) for i in getattr(m, "extra_ids", None) or []]
            groups = [Group("Tirar", [Option("Nenhuma peça extra", "/skin extra none", selected=lambda m: not worn(m))])]
            for title, kind in (("De baixo", "bottom"), ("Vestidos e saias", "dress"), ("De cima", "top"), ("Jaquetas", "jacket")):
                items = self._catalog.get(kind, [])
                if items:
                    groups.append(Group(f"{title} (clique veste ou tira)", [
                        Option(i.name, f"/skin extra {i.asset_id}", image=i.image or "",
                               selected=lambda m, a=i.asset_id: str(a) in worn(m)) for i in items]))
            return groups

        def looks() -> List[Group]:
            return [Group("Aparências prontas", [Option(n.replace("_", " ").capitalize(), f"/skin preset {n}") for n in PRESETS]),
                    Group("Recomeçar", [Option("Padrão", "/skin reset"), Option("Tirar roupas", "/skin tirar tudo")])]

        return [
            Section("Corpo", body),
            Section("Ajustes", shape),
            Section("Olhos", eyes),
            Section("Rosto", face),
            Section("Nariz", nose),
            Section("Maquiagem", makeup),
            Section("Cabelo", hair),
            Section("Superior", lambda: [Group("Roupa de cima", self._garments("top", "top", "top_id"))]),
            Section("Jaqueta", lambda: [Group("Por cima da roupa", self._garments("jacket", "jaqueta", "outer_top_id"))]),
            Section("Inferior", lambda: [Group("Roupa de baixo", self._garments("bottom", "calca", "bottom_id"))]),
            Section("Vestidos", lambda: [Group("Vestidos e saias", [
                Option(i.name, f"/skin vestir {i.asset_id}", image=i.image or "",
                       selected=lambda m, a=i.asset_id: _same(getattr(m, "top_id", None), a) or _same(getattr(m, "bottom_id", None), a))
                for i in self._catalog.get("dress", [])])]),
            Section("Extras", extras),
            Section("Sapatos", lambda: [Group("Calçados", self._garments("shoes", "sapato", "shoes_id"))]),
            Section(FINE_SECTION, fine),
            Section("Prontos", looks),
        ]

    @property
    def focus(self) -> str:
        """O que a câmera deve enquadrar na seção aberta: "face" (o rosto, de frente) ou "body"."""
        return "face" if self.sections[self.active].title in FACE_SECTIONS else "body"

    @property
    def brushing(self) -> bool:
        """O pincel de pele está ligado e na seção dele: o arraste no personagem pinta."""
        return self.is_open and self.brush is not None and self.sections[self.active].title == FINE_SECTION

    def _paint(self, x: float, y: float) -> None:
        if self._stroke is not None and self.picker is not None:
            self._stroke.update(self.picker(x, y, self.brush_size, self.brush_mirror))

    def groups(self) -> List[Group]:
        if self._groups is None:
            self._groups = self.sections[self.active].groups()
        return self._groups

    # ------------------------------------------------------------------ abrir, fechar, girar
    def open(self) -> None:
        self.refresh_catalog()
        self.is_open = True
        self.message = "Arraste para girar e inclinar a vista. Esc fecha."
        self._was_spinning = True
        self.turntable["active"] = True
        self.dirty = True

    def close(self) -> None:
        """Fecha a tela e grava o personagem (o que foi montado nela não se perde ao sair do jogo)."""
        if self.is_open and self.autosave and self.model is not None and hasattr(self.handler, "save"):
            self.handler.save()
        self.is_open = False
        self._dragging = False
        self.hover = None

    def refresh_catalog(self) -> None:
        """Relê os itens baixados e pede as miniaturas dos que ainda não têm."""
        self._catalog = catalog()
        self._groups = None
        self.dirty = True
        thumbs = os.path.join(CLOTHING_DIR, "thumbs")
        missing = {item.asset_id for kind, items in self._catalog.items() if kind in PICTURED for item in items
                   if item.image is None or os.path.dirname(item.image) != thumbs} - self._pictured
        if missing and self.make_thumbnails and self._thumbnails is None:
            self._pictured |= missing  # asked for once: an item that cannot be drawn is not asked for again
            script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                  "scripts", "render_catalog_thumbnails.py")
            try:
                self._thumbnails = subprocess.Popen([sys.executable, script], stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL)
            except OSError:
                self._thumbnails = None

    def select_section(self, index: int) -> None:
        if 0 <= index < len(self.sections) and index != self.active:
            self.active, self.scroll, self._groups, self.dirty = index, 0, None, True

    def update(self, dt: float) -> None:
        """Gira o personagem e nota o que mudou por fora (comando do chat, roupa que terminou de encaixar)."""
        if not self.is_open:
            return
        if self.turntable.get("active") and not self._dragging:
            self.turntable["yaw"] = (self.turntable.get("yaw", 0.0) + dt * SPIN_DEGREES) % 360.0
        busy = self.handler.busy_status or ""
        if self._busy and not busy:
            self.refresh_catalog()  # an item has just arrived
        if self._thumbnails is not None and self._thumbnails.poll() is not None:
            self._thumbnails = None
            self._images.clear()
            self.refresh_catalog()
        selected = tuple(self.slider_value(option) if option.slider else option.selected(self.model)
                         for group in self.groups() for option in group.options) if self.model is not None else ()
        if busy != self._busy or selected != self._selected_key:
            self._busy, self._selected_key, self.dirty = busy, selected, True

    # ------------------------------------------------------------------ disposição
    def scene_rect(self, width: int, height: int) -> Rect:
        """Onde o personagem é desenhado: a janela menos o painel."""
        return (min(PANEL_WIDTH, width), 0, width, height)

    def layout(self, width: int, height: int) -> List[Tuple[Rect, str, Any]]:
        """As áreas clicáveis, em pixels da janela: ('tab', índice), ('option', Option), ('button', nome)."""
        self._size = (width, height)
        hits: List[Tuple[Rect, str, Any]] = []
        for index in range(len(self.sections)):
            y = PAD + index * (TAB_HEIGHT + 4)
            hits.append(((6, y, TAB_WIDTH - 6, y + TAB_HEIGHT), "tab", index))
        left, right = TAB_WIDTH + PAD, PANEL_WIDTH - PAD
        top, bottom = PAD, height - FOOTER_HEIGHT
        for kind, (x0, y0, x1, y1), payload in self._tiles():
            y0, y1 = y0 + top - self.scroll, y1 + top - self.scroll
            if kind == "option" and y1 > top and y0 < bottom:
                hits.append(((x0, max(y0, top), x1, min(y1, bottom)), "option", payload))
        half = (right - left - GAP) // 2
        hits.append(((left, height - 86, right, height - 54), "field", "add"))
        hits.append(((left, height - 44, left + half, height - PAD), "button", "spin"))
        hits.append(((left + half + GAP, height - 44, right, height - PAD), "button", "done"))
        self._hits = hits
        return hits

    def _tiles(self) -> List[Tuple[str, Rect, Any]]:
        """A grade inteira, sem rolagem, com y a partir do seu topo: ('title', área, texto) e
        ('option', área, Option). Também mede a altura do conteúdo."""
        left, right = TAB_WIDTH + PAD, PANEL_WIDTH - PAD
        tiles: List[Tuple[str, Rect, Any]] = []
        y = 0
        for group in self.groups():
            tiles.append(("title", (left, y, right, y + 26), group.title))
            y += 26
            kind = group.options[0].kind if group.options else "text"
            if kind == "card":
                columns, (w, h) = 3, CARD
            elif kind == "swatch":
                columns, (w, h) = SWATCHES_PER_ROW, (SWATCH, SWATCH)
            elif kind == "slider":
                columns, (w, h) = 1, (right - left, SLIDER_TILE)
            else:
                columns, (w, h) = 2, ((right - left - GAP) // 2, TEXT_TILE)
            for k, option in enumerate(group.options):
                x, oy = left + (k % columns) * (w + GAP), y + (k // columns) * (h + GAP)
                tiles.append(("option", (x, oy, x + w, oy + h), option))
            y += -(-len(group.options) // columns) * (h + GAP) + 6
        self._content_height = y
        return tiles

    def _max_scroll(self) -> int:
        return max(0, self._content_height - (self._size[1] - FOOTER_HEIGHT - PAD))

    def hit(self, x: float, y: float) -> Optional[Tuple[Rect, str, Any]]:
        for rect, kind, payload in self._hits:
            if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                return rect, kind, payload
        return None

    # ------------------------------------------------------------------ entrada
    def over_panel(self, x: float) -> bool:
        return x < PANEL_WIDTH

    def handle_mouse_button(self, x: float, y: float, button: int, action: int, shift: bool = False) -> bool:
        """Clique esquerdo: escolhe no painel, ou começa a girar o personagem. True se o evento foi usado."""
        if not self.is_open:
            return False
        if button == 1 and self.brushing and not self.over_panel(x) and action != 0:
            # With the brush on, the left button paints: the right one turns the character.
            self._dragging, self._drag_x, self._drag_y = True, x, y
            self._was_spinning = bool(self.turntable.get("active"))
            return True
        if button == 1 and action == 0 and self._dragging:
            self._dragging = False
            self.turntable["active"] = self._was_spinning
            return True
        if button != 0:
            return False
        if action == 0:  # release
            if self._stroke is not None:
                points, self._stroke = sorted(self._stroke), None
                if points:
                    self.choose(Option("", f"/skin hsr {self.brush} {','.join(str(p) for p in points)}"))
                return True
            if self._slider is not None:
                option, self._slider = self._slider[0], None
                self.set_slider(option, self._slider_value)  # the face is drawn again only now
                return True
            if self._dragging:
                self._dragging = False
                self.turntable["active"] = self._was_spinning
                return True
            return self.over_panel(x)
        if not self.over_panel(x):
            if self.typing:
                self.typing, self.dirty = False, True
            if shift:
                return False  # Shift + arrastar continua sendo o pan da câmera
            if self.brushing:
                self._stroke = set()
                self._paint(x, y)
                return True
            self._dragging, self._drag_x, self._drag_y = True, x, y
            self._was_spinning = bool(self.turntable.get("active"))
            return True
        found = self.hit(x, y)
        typing = found is not None and found[1] == "field"
        if typing != self.typing:
            self.typing, self.dirty = typing, True
        if found is None:
            return True
        _, kind, payload = found
        if kind == "field":
            pass
        elif kind == "tab":
            self.select_section(payload)
        elif kind == "option" and payload.slider is not None:
            x0, x1 = TAB_WIDTH + PAD + 10, PANEL_WIDTH - PAD - 10
            self._slider = (payload, x0, x1)
            self._drag_slider(x)
        elif kind == "option":
            self.choose(payload)
        elif payload == "spin":
            self.turntable["active"] = self._was_spinning = not self.turntable.get("active")
            self.dirty = True
        elif payload == "done":
            self.close()
        return True

    def slider_value(self, option: Option) -> int:
        """O valor de um ajuste, de -100 a 100 (o que está sendo arrastado, enquanto é arrastado)."""
        if self._slider is not None and self._slider[0] is option:
            return self._slider_value
        custom = self._custom()
        adjust = getattr(custom, "resolved_body_adjust", None) or getattr(custom, "body_adjust", None) or {}
        return int(round(float(adjust.get(option.slider, 0.0)) * 100))

    def set_slider(self, option: Option, value: int) -> None:
        self.choose(Option(option.label, f"/skin ajuste {option.slider} {int(value)}"))

    def _drag_slider(self, x: float) -> None:
        option, x0, x1 = self._slider
        value = int(round((min(max(x, x0), x1) - x0) / (x1 - x0) * 200 - 100))
        value = 0 if abs(value) <= SLIDER_SNAP else value
        self._slider_value, self.dirty = value, True
        # The body follows the mouse. The face is a texture drawn again at each change: it
        # follows a few times a second, and takes the last value when the slider is let go.
        now = time.monotonic()
        if option.slider not in REDRAWS_FACE or now - self._slider_sent >= FACE_REDRAW:
            self._slider_sent = now
            self.set_slider(option, value)

    def choose(self, option: Option) -> None:
        if option.command.startswith("@"):  # the brush's own settings: nothing of the character changes
            name, _, value = option.command[1:].partition(" ")
            if name == "pincel":
                self.brush = value or None
                if self.brush is not None:
                    self.turntable["active"] = self._was_spinning = False  # a still character to paint on
                    self.message = ("Arraste sobre o personagem para pintar. Botão direito gira."
                                    if getattr(self.model, "hsr_cage", None) is not None
                                    else "Vista uma roupa: o pincel corrige a pele sob ela.")
            elif name == "tamanho":
                self.brush_size = int(value)
            elif name == "simetria":
                self.brush_mirror = value == "sim"
            self.dirty = True
            return
        _, feedback, _ = self.handler.execute(option.command)
        self.message = feedback.split("\n")[0] if feedback else ""
        self.dirty = True

    def handle_cursor(self, x: float, y: float) -> None:
        if not self.is_open:
            return
        self.cursor = (x, y)
        if self._stroke is not None:
            self._paint(x, y)
            return
        if self._slider is not None:
            self._drag_slider(x)
            return
        if self._dragging:
            self.turntable["yaw"] = (self.turntable.get("yaw", 0.0) + (x - self._drag_x) * DRAG_DEGREES) % 360.0
            if "pitch" in self.turntable:  # the camera's tilt, in degrees (the main loop applies it)
                tilt = self.turntable["pitch"] + (y - self._drag_y) * TILT_DEGREES
                self.turntable["pitch"] = min(max(tilt, TILT_LIMITS[0]), TILT_LIMITS[1])
            self._drag_x, self._drag_y = x, y
            return
        found = self.hit(x, y)
        hover = (found[1], id(found[2]) if found[1] == "option" else found[2]) if found else None
        if hover != self.hover:
            self.hover, self.dirty = hover, True

    def handle_scroll(self, x: float, y_offset: float) -> bool:
        """A roda do mouse sobre o painel rola a grade; fora dele continua sendo o zoom."""
        if not self.is_open or not self.over_panel(x):
            return False
        scroll = int(min(max(self.scroll - y_offset * SCROLL_STEP, 0), self._max_scroll()))
        if scroll != self.scroll:
            self.scroll, self.dirty = scroll, True
        return True

    def handle_char(self, codepoint: int) -> bool:
        """Um caractere digitado: vai para o campo de adicionar item, se ele tem o teclado."""
        if not (self.is_open and self.typing):
            return False
        if codepoint >= 32:
            self.entry, self.dirty = (self.entry + chr(codepoint))[:200], True
        return True

    def submit(self) -> None:
        """Baixa e veste o item do campo (id ou link do catálogo do Roblox)."""
        text = self.entry.strip()
        self.entry, self.typing, self.dirty = "", False, True
        if text:
            self.choose(Option(text, f"/skin vestir {text}"))

    def handle_key(self, key: int, action: int, mods: int = 0) -> bool:
        """Esc fecha; Espaço liga ou desliga o giro. Com o campo de adicionar item em uso, o
        teclado é dele: Enter envia, Esc desiste, Ctrl+V cola."""
        if not self.is_open:
            return False
        if self.typing:
            if action in (1, 2):  # press or repeat
                if key in (257, 335):   # Enter
                    self.submit()
                elif key == 256:        # Esc
                    self.entry, self.typing = "", False
                elif key == 259:        # Backspace
                    self.entry = self.entry[:-1]
                elif key == 86 and mods & 2:  # Ctrl+V
                    self.entry = (self.entry + (self.clipboard() or "").strip().replace("\n", " "))[:200]
                self.dirty = True
            return True
        if action != 1:
            return False
        if key == 256:  # GLFW_KEY_ESCAPE
            self.close()
            return True
        if key == 32:   # GLFW_KEY_SPACE
            self.turntable["active"] = self._was_spinning = not self.turntable.get("active")
            self.dirty = True
            return True
        return False

    # ------------------------------------------------------------------ desenho
    def _font(self, size: int) -> Any:
        from PIL import ImageFont
        for name in ("segoeui.ttf", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _picture(self, path: str, size: Tuple[int, int]) -> Any:
        """A imagem de um item, cortada ao centro e reduzida ao tamanho do quadro (com cache)."""
        from PIL import Image, ImageOps
        key = (path, size)
        if key not in self._images:
            try:
                self._images[key] = ImageOps.fit(Image.open(path).convert("RGBA"), size, Image.LANCZOS)
            except Exception:
                self._images[key] = None
        return self._images[key]

    def _fit_text(self, draw: Any, text: str, font: Any, width: int, lines: int) -> List[str]:
        words, out, line = text.split(), [], ""
        for word in words:
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=font) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = word
        out.append(line)
        out = out[:lines]
        while out and draw.textlength(out[-1], font=font) > width and len(out[-1]) > 1:
            out[-1] = out[-1][:-2] + "…"
        return out

    def image(self, width: int, height: int) -> Any:
        """O painel inteiro (PANEL_WIDTH x altura da janela) como imagem RGBA."""
        from PIL import Image, ImageDraw
        hits = self.layout(width, height)
        panel = Image.new("RGBA", (PANEL_WIDTH, height), BACKGROUND)
        draw = ImageDraw.Draw(panel)
        draw.rectangle((0, 0, TAB_WIDTH, height), fill=TAB_STRIP)
        title, text, small = self._font(15), self._font(14), self._font(11)
        left, top, bottom = TAB_WIDTH + PAD, PAD, height - FOOTER_HEIGHT

        # A grade é desenhada inteira e só a parte visível é copiada: um quadro cortado pela
        # borda aparece pela metade, não vazio.
        tiles = self._tiles()
        view = max(bottom - top, 1)
        grid = Image.new("RGBA", (PANEL_WIDTH, max(self._content_height, view)), (0, 0, 0, 0))
        pen = ImageDraw.Draw(grid)
        for kind, rect, payload in tiles:
            x0, y0, x1, y1 = rect
            if y1 < self.scroll or y0 > self.scroll + view:
                continue
            if kind == "title":
                pen.text((x0, y0 + 4), payload.upper(), font=small, fill=MUTED)
                continue
            draw_rect = (x0, y0, x1 - 1, y1 - 1)
            pen.rounded_rectangle(draw_rect, 6, fill=TILE_HOVER if self.hover == ("option", id(payload)) else TILE)
            if payload.kind == "slider":
                value = self.slider_value(payload) if self.model is not None else 0
                pen.text((x0 + 10, y0 + 13), payload.label, font=small, fill=TEXT, anchor="lm")
                pen.text((x1 - 10, y0 + 13), f"{value:+d}" if value else "0", font=small,
                         fill=ACCENT if value else MUTED, anchor="rm")
                t0, t1, ty = x0 + 10, x1 - 10, y0 + 31
                knob = t0 + (value + 100) / 200 * (t1 - t0)
                pen.line((t0, ty, t1, ty), fill=(14, 15, 19, 255), width=4)
                pen.line(((t0 + t1) / 2, ty, knob, ty), fill=ACCENT, width=4)
                pen.line(((t0 + t1) / 2, ty - 5, (t0 + t1) / 2, ty + 5), fill=MUTED, width=1)
                pen.ellipse((knob - 7, ty - 7, knob + 7, ty + 7), fill=TEXT)
                continue
            if payload.kind == "swatch":
                pen.rounded_rectangle((x0 + 4, y0 + 4, x1 - 5, y1 - 5), 5, fill=payload.color + (255,))
            elif payload.kind == "card":
                picture = self._picture(payload.image, (CARD[0] - 8, 72)) if payload.image else None
                if picture is not None:
                    grid.paste(picture, (x0 + 4, y0 + 4), picture)
                else:
                    pen.line((x0 + 30, y0 + 26, x1 - 30, y0 + 54), fill=MUTED, width=2)
                    pen.line((x1 - 30, y0 + 26, x0 + 30, y0 + 54), fill=MUTED, width=2)
                for k, line in enumerate(self._fit_text(pen, payload.label, small, CARD[0] - 8, 2)):
                    pen.text(((x0 + x1) // 2, y0 + 80 + k * 13), line, font=small, fill=TEXT, anchor="ma")
            else:
                pen.text(((x0 + x1) // 2, (y0 + y1) // 2), self._fit_text(pen, payload.label, text, x1 - x0 - 10, 1)[0],
                         font=text, fill=TEXT, anchor="mm")
            if self.model is not None and payload.selected(self.model):
                pen.rounded_rectangle(draw_rect, 6, outline=ACCENT, width=2)
        panel.alpha_composite(grid.crop((0, self.scroll, PANEL_WIDTH, self.scroll + view)), (0, top))

        for rect, kind, payload in hits:
            x0, y0, x1, y1 = rect
            hovered = self.hover == (kind, id(payload) if kind == "option" else payload)
            if kind == "option":
                continue
            if kind == "field":
                draw.rounded_rectangle(rect, 6, fill=(14, 15, 19, 255), outline=ACCENT if self.typing else TILE_HOVER)
                shown = self.entry + ("|" if self.typing else "")
                while shown and draw.textlength(shown, font=small) > x1 - x0 - 16:
                    shown = shown[1:]
                draw.text((x0 + 8, (y0 + y1) // 2), shown or "Adicionar do Roblox: cole o id ou o link",
                          font=small, fill=TEXT if shown else MUTED, anchor="lm")
                continue
            if kind == "tab":
                active = payload == self.active
                if active or hovered:
                    draw.rounded_rectangle(rect, 6, fill=TILE_HOVER if active else TILE)
                if active:
                    draw.rectangle((x0, y0 + 8, x0 + 3, y1 - 8), fill=ACCENT)
                draw.text((x0 + 14, (y0 + y1) // 2), self.sections[payload].title, font=title,
                          fill=TEXT if active else MUTED, anchor="lm")
            else:
                label = ("Girar: ligado" if self.turntable.get("active") else "Girar: parado") if payload == "spin" else "Concluir"
                fill = ACCENT if payload == "done" else (TILE_HOVER if hovered else TILE)
                draw.rounded_rectangle(rect, 6, fill=fill)
                draw.text(((x0 + x1) // 2, (y0 + y1) // 2), label, font=text,
                          fill=(20, 20, 24, 255) if payload == "done" else TEXT, anchor="mm")

        # rodapé: o que está acontecendo
        draw.rectangle((TAB_WIDTH, bottom, PANEL_WIDTH, bottom + 1), fill=TILE)
        status = self._busy or self.message
        for k, line in enumerate(self._fit_text(draw, status, small, PANEL_WIDTH - TAB_WIDTH - 2 * PAD, 2)):
            draw.text((left, bottom + 10 + k * 15), line, font=small, fill=ACCENT if self._busy else MUTED)
        if self._max_scroll() > 0:  # barra de rolagem
            track = bottom - top
            size = max(24, int(track * track / max(self._content_height, 1)))
            at = top + int((track - size) * self.scroll / self._max_scroll())
            draw.rounded_rectangle((PANEL_WIDTH - 6, at, PANEL_WIDTH - 3, at + size), 2, fill=TILE_HOVER)
        return panel

    def render(self, width: int, height: int) -> None:
        """Desenha o painel sobre a cena (a textura só é refeita quando algo mudou)."""
        if not self.is_open or not self.create_gl:
            return
        from src.rendering.hud_quad import HudQuad
        if self._quad is None:
            self._quad = HudQuad()
        if self.dirty or self._size != (width, height):
            self._quad.set_image(self.image(width, height))
            self.dirty = False
        self._quad.draw(0, 0, width, height)
        self._draw_brush(width, height)

    def _draw_brush(self, width: int, height: int) -> None:
        """Os pontos da cage sobre o personagem (o que cada um é) e o cursor do pincel."""
        if not self.brushing or self.overlay is None:
            return
        from src.interactive import skin_brush
        from src.rendering.hud_quad import HudQuad
        xy, facing, kinds = self.overlay
        x0, y0, x1, y1 = self.scene_rect(width, height)
        key = (x0, y0, x1, y1, np.round(xy).astype(np.int32).tobytes(), facing.tobytes(), kinds.tobytes(),
               tuple(sorted(self._stroke)) if self._stroke else ())
        if self._overlay_quad is None:
            self._overlay_quad, self._ring_quad = HudQuad(), HudQuad()
        if key != self._overlay_key:
            self._overlay_quad.set_image(skin_brush.overlay((x1 - x0, y1 - y0), (x0, y0), xy, facing, kinds, self._stroke or ()))
            self._overlay_key = key
        self._overlay_quad.draw(x0, y0, width, height)
        if self._ring_size != self.brush_size:
            self._ring_quad.set_image(skin_brush.ring(self.brush_size))
            self._ring_size = self.brush_size
        if not self.over_panel(self.cursor[0]):
            half = self._ring_quad.size[0] / 2
            self._ring_quad.draw(self.cursor[0] - half, self.cursor[1] - half, width, height)

    def delete(self) -> None:
        for name in ("_overlay_quad", "_ring_quad"):
            if getattr(self, name) is not None:
                getattr(self, name).delete()
                setattr(self, name, None)
        if self._quad is not None:
            self._quad.delete()
            self._quad = None
