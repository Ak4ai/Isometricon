"""A tela do combate: ordem dos turnos, menu de ações, vida sobre as cabeças e números que sobem.

``compose`` monta a lista do que desenhar (imagens PIL e onde), sem OpenGL, para os testes olharem; ``render`` a
desenha com um ``HudQuad`` por peça, refazendo a textura só quando a imagem daquela peça muda.

- em cima, no meio: a ordem da iniciativa (quem está agindo com borda dourada, o alvo com borda vermelha) e a rodada;
- embaixo, à direita, na vez do personagem: movimento que sobra, o alvo (vida, CA, distância e alcance) e o menu
  (1-6; o que não pode agora aparece apagado com o porquê); fora da vez dele: de quem é a vez;
- o registro da luta vai para a caixa do chat do jogo (``chat_log_view``), que no combate muda de estilo e se estica
  da margem esquerda até a borda do menu (``CombatHud.menu_left``), aproveitando a largura da janela;
- sobre cada inimigo na luta: o nome e a barra de vida; os números de dano/cura sobem e somem.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.interactive.chat_console import CombatLogView
from src.interactive.combat_controller import PLAYER_ID, CombatController, ascii_text, plain_symbols
from src.rendering.mc_font import default_font

Color = Tuple[int, int, int]
PANEL = (16, 18, 24, 200)
GOLD = (255, 200, 60)
RED = (230, 70, 70)
GREEN = (90, 210, 90)
DIM = (130, 130, 130)
WHITE = (235, 235, 235)
SCALE = 2
LINE = 9 * SCALE + 4
MARGIN = 12
LOG_GAP = 8          # espaço entre a caixa do registro (o chat) e o menu

DrawItem = Tuple[str, Image.Image, float, float, float]   # (chave, imagem, x, y, opacidade)


def text_image(text: str, color: Color = WHITE, scale: int = SCALE) -> Image.Image:
    text = ascii_text(text)
    font = default_font()
    if font is not None:
        return font.render(text or " ", color=color, scale=scale)
    pil = ImageFont.load_default()
    box = pil.getbbox(text or " ")
    image = Image.new("RGBA", (max(1, box[2] + 2), 8 * scale + 2), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.text((1, 1), text, font=pil, fill=(30, 30, 30, 255))
    pen.text((0, 0), text, font=pil, fill=(*color, 255))
    return image


def row_image(segments: Sequence[Tuple[str, Color]], scale: int = SCALE) -> Image.Image:
    parts = [text_image(t, c, scale) for t, c in segments if t]
    if not parts:
        return Image.new("RGBA", (1, 8 * scale), (0, 0, 0, 0))
    width = sum(p.width for p in parts)
    image = Image.new("RGBA", (width, max(p.height for p in parts)), (0, 0, 0, 0))
    x = 0
    for p in parts:
        image.alpha_composite(p, (x, 0))
        x += p.width
    return image


def panel_image(rows: Sequence[Image.Image], pad: int = 8, gap: int = 4, min_width: int = 0,
                border: Optional[Color] = None, center: bool = False) -> Image.Image:
    width = max([min_width] + [r.width for r in rows]) + 2 * pad
    height = sum(r.height for r in rows) + gap * max(0, len(rows) - 1) + 2 * pad
    image = Image.new("RGBA", (width, height), PANEL)
    pen = ImageDraw.Draw(image)
    if border is not None:
        pen.rectangle((0, 0, width - 1, height - 1), outline=(*border, 255), width=2)
    y = pad
    for r in rows:
        x = (width - r.width) // 2 if center else pad
        image.alpha_composite(r, (x, y))
        y += r.height + gap
    return image


def bar_image(width: int, height: int, ratio: float, color: Color, temp_ratio: float = 0.0) -> Image.Image:
    image = Image.new("RGBA", (width, height), (40, 40, 40, 230))
    pen = ImageDraw.Draw(image)
    filled = int(round((width - 2) * max(0.0, min(1.0, ratio))))
    if filled > 0:
        pen.rectangle((1, 1, filled, height - 2), fill=(*color, 255))
    temp = int(round((width - 2) * max(0.0, min(1.0, temp_ratio))))
    if temp > 0:
        pen.rectangle((1, 1, temp, 3), fill=(*GOLD, 255))
    return image


def hp_color(ratio: float) -> Color:
    return GREEN if ratio > 0.5 else ((230, 190, 60) if ratio > 0.25 else RED)


# ----------------------------------------------------------------------------------------------------------------------

def turn_order_image(controller: CombatController) -> Optional[Image.Image]:
    session = controller.session
    if session is None:
        return None
    chips: List[Image.Image] = []
    for c in session.order:
        name = controller.name_of(c.id)
        color = (120, 255, 140) if c.is_player else (255, 140, 140)
        rows = [row_image([(name, color if c.alive else DIM)]),
                bar_image(96, 8, c.hp_ratio, hp_color(c.hp_ratio), c.temp_hp / c.max_hp if c.max_hp else 0),
                row_image([(f"{int(c.hp)}/{c.max_hp}", WHITE if c.alive else DIM), (f"  ini {c.initiative}", DIM)],
                          scale=1)]
        border = GOLD if c is session.current else (RED if c.id == session.target_id else None)
        chips.append(panel_image(rows, pad=5, gap=3, min_width=96, border=border))
    title = row_image([(f"Rodada {session.round}", GOLD)])
    width = max(title.width, sum(ch.width for ch in chips) + 6 * (len(chips) - 1))
    height = title.height + 4 + max(ch.height for ch in chips)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    image.alpha_composite(title, ((width - title.width) // 2, 0))
    x = (width - (sum(ch.width for ch in chips) + 6 * (len(chips) - 1))) // 2
    for ch in chips:
        image.alpha_composite(ch, (x, title.height + 4))
        x += ch.width + 6
    return image


def menu_image(controller: CombatController) -> Optional[Image.Image]:
    session = controller.session
    if session is None or not session.active:
        return None
    if not controller.is_player_turn:
        who = controller.name_of(session.current.id)
        return panel_image([row_image([("Vez de ", DIM), (who, (255, 140, 140)), ("...", DIM)])], center=True)
    rows: List[Image.Image] = []
    left, speed = session.movement_left, session.current.speed
    status = [("Sua vez", GOLD), (f"  Mov {left:.1f}/{speed:.0f}", WHITE if left > 0 else DIM),
              ("  Acao " + ("usada" if session.action_used else "livre"), DIM if session.action_used else GREEN)]
    rows.append(row_image(status))
    target = session.target
    me = session.current
    if target is not None:
        gap = me.distance_to(target)
        reach = me.reach
        rows.append(row_image([("Alvo: ", DIM), (target.name, (255, 140, 140))]))
        rows.append(row_image([(f"{int(target.hp)}/{target.max_hp} vida   CA {target.armor_class}   ", WHITE),
                               (f"{gap:.1f} de {reach:.1f} blocos", GREEN if gap <= reach else RED)], scale=1))
    for key, label, action, extra in controller.menu_entries():
        reason = controller.blocked(action, extra)
        if reason is None:
            rows.append(row_image([(f"[{key}] ", GOLD), (label, WHITE)]))
        else:
            entry = row_image([(f"[{key}] ", DIM), (label, DIM)])
            why = text_image(f"  {reason}", (170, 120, 120), scale=1)
            line = Image.new("RGBA", (entry.width + why.width, entry.height), (0, 0, 0, 0))
            line.alpha_composite(entry, (0, 0))
            line.alpha_composite(why, (entry.width, (entry.height - why.height) // 2))
            rows.append(line)
    rows.append(row_image([("Enter", GOLD), (" encerra a vez   ", DIM), ("Tab", GOLD), (" troca o alvo   ", DIM),
                           ("clique", GOLD), (" mira / ataca", DIM)], scale=1))
    return panel_image(rows, min_width=300)


def chat_log_view(controller: CombatController, right: Optional[float]) -> Optional[CombatLogView]:
    """O registro da luta para a caixa do chat (até ``right``), enquanto há combate ou a faixa do fim está na tela."""
    if not controller.log or not (controller.in_combat or controller.banner is not None):
        return None
    session = controller.session
    if session is None:
        title = "Combate encerrado"
    elif controller.is_player_turn:
        title = f"Combate  -  Rodada {session.round}  -  sua vez"
    else:
        title = f"Combate  -  Rodada {session.round}  -  vez de {controller.name_of(session.current.id)}"
    lines = [[(plain_symbols(text), color) for text, color in line.segments] for line in controller.log]
    detail = controller.log[-1].detail
    return CombatLogView(title, lines, detail, None if right is None else int(right) - LOG_GAP)


def overhead_image(name: str, hp: float, max_hp: float, targeted: bool, acting: bool) -> Image.Image:
    color = GOLD if acting else ((255, 120, 120) if targeted else WHITE)
    label = row_image([(("> " if targeted else "") + name, color)], scale=1)
    bar = bar_image(48, 6, hp / max_hp if max_hp else 0, hp_color(hp / max_hp if max_hp else 0))
    image = Image.new("RGBA", (max(label.width, bar.width), label.height + 2 + bar.height), (0, 0, 0, 0))
    image.alpha_composite(label, ((image.width - label.width) // 2, 0))
    image.alpha_composite(bar, ((image.width - bar.width) // 2, label.height + 2))
    return image


def _cached(cache: Optional[dict], slot: str, key, build):
    if cache is None:
        return build()
    hit = cache.get(slot)
    if hit is not None and hit[0] == key:
        return hit[1]
    image = build()
    cache[slot] = (key, image)
    return image


def _order_key(controller: CombatController):
    s = controller.session
    return (tuple((c.id, int(c.hp), round(c.temp_hp), c.initiative) for c in s.order), s.current.id, s.target_id,
            s.round)


def _menu_key(controller: CombatController):
    s = controller.session
    if not controller.is_player_turn:
        return ("espera", s.current.id)
    target = s.target
    entries = tuple((k, label, controller.blocked(a, e)) for k, label, a, e in controller.menu_entries())
    return ("vez", round(s.movement_left, 1), s.action_used, entries,
            None if target is None else (target.id, int(target.hp), target.armor_class,
                                         round(s.current.distance_to(target), 1)))


def hover_image(controller: CombatController) -> Optional[Image.Image]:
    """A dica do inimigo sob o mouse: nome, vida e CA, e o que o clique faria."""
    enemy = controller.hovered()
    hint = controller.hover_hint()
    if enemy is None or hint is None:
        return None
    c = enemy.combatant
    targeted = controller.session is not None and controller.session.target_id == c.id
    ratio = c.hp / c.max_hp if c.max_hp else 0
    rows = [row_image([(c.name, RED if targeted else WHITE)], scale=SCALE),
            row_image([(f"{int(c.hp)}/{int(c.max_hp)} vida", hp_color(ratio)), (f"   CA {c.armor_class}", WHITE)],
                      scale=1),
            row_image([hint], scale=1)]
    return panel_image(rows, pad=6, gap=3, border=GOLD)


def _hover_key(controller: CombatController):
    enemy = controller.hovered()
    if enemy is None:
        return None
    c = enemy.combatant
    return (c.id, int(c.hp), c.armor_class, controller.hover_hint(),
            controller.session is not None and controller.session.target_id == c.id)


def compose(controller: CombatController, width: int, height: int, mvp: Optional[np.ndarray] = None,
            cache: Optional[dict] = None) -> List[DrawItem]:
    """O que desenhar neste quadro: (chave, imagem, x, y, opacidade). ``cache`` guarda as imagens entre quadros."""
    from src.interactive.interact_prompt import project
    items: List[DrawItem] = []
    session = controller.session
    if session is not None:
        order = _cached(cache, "ordem", _order_key(controller), lambda: turn_order_image(controller))
        items.append(("ordem", order, (width - order.width) / 2, MARGIN, 1.0))
        if session.active:
            menu = _cached(cache, "menu", _menu_key(controller), lambda: menu_image(controller))
            if menu is not None:
                items.append(("menu", menu, width - menu.width - MARGIN, height - menu.height - MARGIN, 1.0))
    if controller.banner is not None:
        text, color, left = controller.banner
        banner = _cached(cache, "faixa", (text, color),
                         lambda: panel_image([row_image([(text, color)], scale=3)], pad=12))
        items.append(("faixa", banner, (width - banner.width) / 2, height * 0.3, min(1.0, left)))
    if mvp is None:
        return items
    for enemy in controller.enemies:
        if enemy.fallen or session is None or session.get(enemy.id) is None:
            continue
        c = enemy.combatant
        top = (enemy.shown[0], enemy.shown[1] + enemy.creature.height + 0.35, enemy.shown[2])
        spot = project(top, mvp, width, height)
        if spot is None:
            continue
        key = (c.name, int(c.hp), c.max_hp, c.id == session.target_id, c is session.current)
        image = _cached(cache, f"cabeca:{enemy.id}", key, lambda: overhead_image(*key))
        items.append((f"cabeca:{enemy.id}", image, spot[0] - image.width / 2, spot[1] - image.height, 1.0))
    hovered = controller.hovered()
    hover_key = _hover_key(controller)
    if hovered is not None and hover_key[3] is not None:
        # a dica fica em cima da cabeça (acima da barra de vida, quando há luta)
        in_fight = session is not None and session.get(hovered.id) is not None
        lift = hovered.creature.height + (0.35 if in_fight else 0.2)
        spot = project((hovered.shown[0], hovered.shown[1] + lift, hovered.shown[2]), mvp, width, height)
        if spot is not None:
            tip = _cached(cache, "dica", hover_key, lambda: hover_image(controller))
            above = 30 if in_fight else 4
            x = min(max(MARGIN, spot[0] - tip.width / 2), width - tip.width - MARGIN)
            items.append(("dica", tip, x, max(MARGIN, spot[1] - above - tip.height), 1.0))
    for i, floater in enumerate(controller.floaters):
        if floater.target == PLAYER_ID:
            base, lift = controller.player_position, 2.1
        else:
            token = controller.token(floater.target)
            if token is None:
                continue
            base, lift = token.shown, token.creature.height + 0.8
        if base is None:
            continue
        spot = project((base[0], base[1] + lift + floater.age * 0.9, base[2]), mvp, width, height)
        if spot is None:
            continue
        image = _cached(cache, f"numero:{i}", (floater.text, floater.color),
                        lambda: text_image(floater.text, floater.color, scale=2))
        items.append((f"numero:{i}", image, spot[0] - image.width / 2, spot[1], max(0.0, 1.0 - floater.age / 1.4)))
    return items


class CombatHud:
    def __init__(self) -> None:
        self._quads: Dict[str, Tuple[object, object]] = {}   # peça -> (HudQuad, imagem enviada)
        self._cache: dict = {}
        self.menu_left: Optional[float] = None   # a borda esquerda do menu no último quadro (None: sem menu)

    def render(self, controller: CombatController, width: int, height: int, mvp: Optional[np.ndarray]) -> None:
        self.menu_left = None
        if (not controller.in_combat and controller.banner is None and not controller.floaters
                and controller.hover is None):
            self._prune(set())
            return
        from src.rendering.hud_quad import HudQuad
        used = set()
        for slot, image, x, y, opacity in compose(controller, width, height, mvp, self._cache):
            if slot == "menu":
                self.menu_left = x
            used.add(slot)
            quad, sent = self._quads.get(slot, (None, None))
            if quad is None:
                quad = HudQuad()
            if sent is not image:
                quad.set_image(image)
            self._quads[slot] = (quad, image)
            quad.draw(round(x), round(y), width, height, opacity=opacity)
        self._prune(used)

    def _prune(self, keep) -> None:
        for slot in [s for s in self._quads if s not in keep]:
            self._quads.pop(slot)[0].delete()
            self._cache.pop(slot, None)

    def delete(self) -> None:
        self._prune(set())
