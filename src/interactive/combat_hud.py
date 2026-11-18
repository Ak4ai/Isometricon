"""A tela do combate: ordem dos turnos, menu de ações, vida sobre as cabeças e números que sobem.

``compose`` monta a lista do que desenhar (imagens PIL e onde), sem OpenGL, para os testes olharem; ``render`` a
desenha com um ``HudQuad`` por peça, refazendo a textura só quando a imagem daquela peça muda.

Tudo no visual das telas de entrada e de configurações (``combat_style``): pergaminho com cantos de metal, títulos
em Georgia, botões em relevo, o verde-escuro para quem está agindo.

- em cima, no meio: a rodada e a ordem da iniciativa (quem está agindo em verde, o alvo com borda vermelha);
- embaixo, à direita, na vez do personagem: movimento e ação, o alvo (vida, CA, distância e alcance) e o menu
  (1-6 em botões; o que não pode agora aparece apagado com o porquê); fora da vez dele: de quem é a vez;
- o registro da luta vai para a caixa do chat do jogo (``chat_log_view``), que no combate vira um pergaminho e se
  estica da margem esquerda até a borda do menu (``CombatHud.menu_left``), aproveitando a largura da janela;
- sobre cada inimigo na luta: o nome e a barra de vida; com o mouse em cima, uma dica do que o clique faria;
  os números de dano/cura sobem e somem.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.interactive import combat_style as st
from src.interactive.chat_console import CombatLogView
from src.interactive.combat_controller import PLAYER_ID, CombatController

Color = Tuple[int, int, int]
MARGIN = 12
LOG_GAP = 8          # espaço entre a caixa do registro (o chat) e o menu
CHIP_WIDTH = 118

DrawItem = Tuple[str, Image.Image, float, float, float]   # (chave, imagem, x, y, opacidade)


# ----------------------------------------------------------------------------------------------------------------------

def turn_order_image(controller: CombatController) -> Optional[Image.Image]:
    """A rodada e um cartão por combatente, na ordem da iniciativa."""
    session = controller.session
    if session is None:
        return None
    chip_h, gap = 54, 8
    count = len(session.order)
    inner_w = count * CHIP_WIDTH + (count - 1) * gap + 24
    inner_h = 30 + chip_h + 14
    image, pad = st.card(inner_w, inner_h, radius=12, corners=False)
    d = ImageDraw.Draw(image)
    title = f"Rodada {session.round}"
    tw = st.measure(title, 17, heading=True)
    cx = pad + inner_w // 2
    st.write(d, (cx - tw / 2, pad + 7), title, 17, st.INK, heading=True)
    d.line((pad + 14, pad + 17, cx - tw / 2 - 12, pad + 17), fill=(*st.LINE, 255))
    d.line((cx + tw / 2 + 12, pad + 17, pad + inner_w - 14, pad + 17), fill=(*st.LINE, 255))
    st.diamond(d, cx - tw / 2 - 7, pad + 17, 3)
    st.diamond(d, cx + tw / 2 + 7, pad + 17, 3)
    x = pad + 12
    y = pad + 32
    for c in session.order:
        acting = c is session.current
        targeted = c.id == session.target_id
        alive = c.alive
        box = (x, y, x + CHIP_WIDTH, y + chip_h)
        if acting:
            d.rounded_rectangle((x, y + 3, box[2], box[3] + 3), 7, fill=(28, 52, 42, 255))
            d.rounded_rectangle(box, 7, fill=(*st.FOREST, 255), outline=(*st.GOLD, 255), width=2)
        else:
            st.button(d, box, enabled=alive)
            if targeted:
                d.rounded_rectangle(box, 7, outline=(*st.FOE_INK, 255), width=2)
        name = controller.name_of(c.id)
        if acting:
            color = st.CREAM
        elif not alive:
            color = st.MUTED
        else:
            color = st.ALLY_INK if c.team == "jogadores" else st.FOE_INK
        st.write(d, (x + 9, y + 7), st.fit(name, 15, CHIP_WIDTH - 18, bold=True), 15, color, bold=True)
        st.bar(d, (x + 9, y + 28, x + CHIP_WIDTH - 9, y + 34), c.hp_ratio if alive else 0.0,
               temp_ratio=c.temp_hp / c.max_hp if c.max_hp else 0,
               track=(60, 96, 80) if acting else st.TRACK)
        sub = f"{int(c.hp)}/{c.max_hp}" if alive else "caído"
        st.write(d, (x + 9, y + 38), sub, 11, (216, 226, 204) if acting else st.MUTED)
        ini = f"ini {c.initiative}"
        st.write(d, (box[2] - 9 - st.measure(ini, 11), y + 38), ini, 11, (216, 226, 204) if acting else st.MUTED)
        if not alive:
            d.line((x + 9, y + 15, x + 9 + st.measure(name, 15, bold=True), y + 15), fill=(*st.MUTED, 255), width=1)
        x += CHIP_WIDTH + gap
    return image


def _waiting_image(name: str, mine: bool = False) -> Image.Image:
    text = "Sua vez" if mine else f"Vez de {name}"
    w = st.measure(text, 17, heading=True)
    image, pad = st.card(w + 60, 44, radius=10, corners=False)
    d = ImageDraw.Draw(image)
    st.diamond(d, pad + 18, pad + 22, 4, st.FOE_INK)
    st.write(d, (pad + 32, pad + 12), text, 17, st.INK, heading=True)
    for i in range(3):
        d.ellipse((pad + 38 + w + i * 6, pad + 27, pad + 41 + w + i * 6, pad + 30), fill=(*st.MUTED, 255))
    return image


STATUS_WIDTH = 214      # a coluna da esquerda (estado da vez e alvo)
TILE_W, TILE_H, TILE_GAP = 92, 70, 8
GRID_COLUMNS = 3


def _icon_kind(action: Optional[str], extra: Optional[str]) -> str:
    if action is None:
        return extra or ""
    if action == "usar_item":
        return extra or "items"
    return action


def _two_lines(text: str, size: int, width: int) -> List[str]:
    """O nome em uma linha, ou quebrado em duas (na fonte um pouco menor) quando não cabe."""
    if st.measure(text, size, bold=True) <= width:
        return [text]
    words = text.split(" ")
    for cut in range(len(words) - 1, 0, -1):
        first, second = " ".join(words[:cut]), " ".join(words[cut:])
        if st.measure(first, size - 1, bold=True) <= width:
            return [first, st.fit(second, size - 1, width, bold=True)]
    return [st.fit(text, size - 1, width, bold=True)]


def _short_reason(reason: str) -> str:
    """O motivo cabe no ladrilho: sem o detalhe entre parênteses (que vai na linha de baixo)."""
    return reason.split(" (")[0].split(":")[0]


def menu_image(controller: CombatController) -> Optional[Image.Image]:
    """O painel da vez do personagem, deitado: à esquerda o estado (movimento, ação, alvo), à direita as ações numa
    grade de ladrilhos com ícone, a tecla num selo pequeno no canto de cima e o motivo quando não pode agora."""
    session = controller.session
    if session is None or not session.active:
        return None
    if not controller.is_player_turn:
        return _waiting_image(controller.name_of(session.current.id), session.current.id == PLAYER_ID)
    entries = controller.menu_entries()
    target = session.target
    me = session.current
    rows = max(2, -(-len(entries) // GRID_COLUMNS))
    grid_w = GRID_COLUMNS * TILE_W + (GRID_COLUMNS - 1) * TILE_GAP
    grid_h = rows * TILE_H + (rows - 1) * TILE_GAP
    w = 22 + STATUS_WIDTH + 18 + grid_w + 30
    status_h = 18 + 28 + 40 + (78 if target is not None else 0)
    h = 24 + max(grid_h, status_h) + 14 + 22 + 10
    image, pad = st.card(w, h, radius=14)
    d = ImageDraw.Draw(image)

    # ---- coluna do estado
    x0 = pad + 22
    x1 = x0 + STATUS_WIDTH
    y = pad + 18
    kicker = {"skills": "HABILIDADES", "items": "ITENS"}.get(controller.menu, "SUA VEZ")
    st.write(d, (x0, y), f"{kicker} · RODADA {session.round}", 11, (126, 103, 58))
    y += 18
    st.write(d, (x0, y), "Escolha sua ação" if not session.action_used else "Ação usada", 19, st.INK, heading=True)
    y += 32
    left, speed = session.movement_left, me.speed
    st.write(d, (x0, y), "Movimento", 11, st.MUTED)
    mv = f"{left:.1f} / {speed:.0f}"
    st.write(d, (x0 + 118 - st.measure(mv, 11, bold=True), y), mv, 11, st.INK if left > 0 else st.MUTED, bold=True)
    st.bar(d, (x0, y + 16, x0 + 118, y + 22), left / speed if speed else 0, color=(70, 140, 160))
    free = not session.action_used
    pill = "Ação livre" if free else "Ação usada"
    pw = st.measure(pill, 12, bold=True) + 24
    d.rounded_rectangle((x1 - pw, y + 1, x1, y + 23), 11, fill=(*(st.FOREST if free else (182, 184, 165)), 255))
    d.ellipse((x1 - pw + 8, y + 9, x1 - pw + 14, y + 15), fill=(*(st.GOLD if free else st.CREAM), 255))
    st.write(d, (x1 - pw + 18, y + 6), pill, 12, st.CREAM if free else st.INK, bold=True)
    y += 38
    if target is not None:
        gap = me.distance_to(target)
        reach = me.reach
        th = 70
        d.rounded_rectangle((x0, y, x1, y + th), 8, fill=(*st.CARD, 255), outline=(*st.LINE, 255))
        d.rounded_rectangle((x0 + 2, y + 10, x0 + 5, y + th - 10), 2, fill=(*st.FOE_INK, 255))
        st.write(d, (x0 + 14, y + 8), "ALVO", 10, st.MUTED)
        st.write(d, (x0 + 14, y + 21), st.fit(target.name, 16, 110, heading=True), 16, st.FOE_INK, heading=True)
        info = f"CA {target.armor_class}"
        st.write(d, (x1 - 12 - st.measure(info, 12, bold=True), y + 9), info, 12, st.INK, bold=True)
        hp = f"{int(target.hp)}/{target.max_hp}"
        st.write(d, (x1 - 12 - st.measure(hp, 11), y + 25), hp, 11, st.MUTED)
        st.bar(d, (x0 + 14, y + 44, x1 - 12, y + 50), target.hp_ratio)
        dist = f"{gap:.1f} de {reach:.1f} blocos"
        st.write(d, (x0 + 14, y + 54), dist, 11, st.ALLY_INK if gap <= reach else st.FOE_INK, bold=True)

    # ---- divisória
    sx = x1 + 9
    d.line((sx, pad + 22, sx, pad + 20 + max(grid_h, status_h) - 4), fill=(*st.LINE, 255))
    st.diamond(d, sx, pad + 20 + max(grid_h, status_h) / 2, 3)

    # ---- grade das ações
    gx0 = x1 + 18
    gy0 = pad + 24
    detail = ""
    for i, (key, label, action, extra) in enumerate(entries):
        reason = controller.blocked(action, extra)
        enabled = reason is None
        col, row = i % GRID_COLUMNS, i // GRID_COLUMNS
        tx = gx0 + col * (TILE_W + TILE_GAP)
        ty = gy0 + row * (TILE_H + TILE_GAP)
        st.button(d, (tx, ty, tx + TILE_W, ty + TILE_H), enabled=enabled)
        st.badge(d, tx + 5, ty + 5, key, enabled, size=15)
        if enabled and action is None:     # abre um submenu: a setinha das telas no canto
            d.line((tx + TILE_W - 12, ty + 7, tx + TILE_W - 8, ty + 11, tx + TILE_W - 12, ty + 15),
                   fill=(*st.MUTED, 255), width=2)
        st.action_icon(d, _icon_kind(action, extra), tx + (TILE_W - 26) / 2, ty + 8, 26, enabled)
        color = st.INK if enabled else st.MUTED
        if action == "fugir" and enabled:
            color = st.DANGER
        name, count = label, ""
        if " x" in label and label.rsplit(" x", 1)[1].isdigit():      # "Poção de cura x2": a conta vai no canto
            name, count = label.rsplit(" x", 1)
            count = f"×{count}"
            st.write(d, (tx + TILE_W - 8 - st.measure(count, 11, bold=True), ty + 6), count, 11, st.GOLD_DARK,
                     bold=True)
        lines = _two_lines(name, 12, TILE_W - 8) if not reason else [st.fit(name, 12, TILE_W - 8, bold=True)]
        size = 12 if len(lines) == 1 else 11
        for n, text in enumerate(lines):
            st.write(d, (tx + (TILE_W - st.measure(text, size, bold=True)) / 2, ty + 38 + n * 14), text, size,
                     color, bold=True)
        if reason:
            short = st.fit(_short_reason(reason), 10, TILE_W - 8)
            st.write(d, (tx + (TILE_W - st.measure(short, 10)) / 2, ty + 55), short, 10, (150, 110, 90))
            if not detail and not session.action_used:
                detail = f"{label}: {reason}"

    # ---- rodapé: o motivo inteiro do primeiro bloqueio e os atalhos
    y = pad + 20 + max(grid_h, status_h) + 14
    d.line((x0, y - 6, pad + w - 22, y - 6), fill=(*st.LINE, 255))
    if detail:
        st.write(d, (x0, y), st.fit(detail, 11, STATUS_WIDTH + 30), 11, (150, 110, 90))
    hints = (("Enter", " encerra a vez"), ("Tab", " troca o alvo"), ("Clique", " mira e ataca"))
    total = sum(st.measure(k, 11, bold=True) + st.measure(r, 11) for k, r in hints) + 14 * (len(hints) - 1)
    hint_x = pad + w - 30 - total
    for word, rest in hints:
        hint_x += st.write(d, (hint_x, y), word, 11, st.GOLD_DARK, bold=True)
        hint_x += st.write(d, (hint_x, y), rest, 11, st.MUTED) + 14
    return image


def _chat_symbols(text: str) -> str:
    """Os símbolos do registro na fonte do pergaminho (Segoe UI tem a seta, não tem as espadas)."""
    for old, new in (("⚔ ", ""), ("⚔", ""), ("➜", "→"), ("★", "*"), ("✖", "×")):
        text = text.replace(old, new)
    return text


def chat_log_view(controller: CombatController, right: Optional[float]) -> Optional[CombatLogView]:
    """O registro da luta para a caixa do chat (até ``right``), enquanto há combate ou a faixa do fim está na tela."""
    if not controller.log or not (controller.in_combat or controller.banner is not None):
        return None
    session = controller.session
    if session is None:
        title = "Combate encerrado"
    elif controller.is_player_turn or session.current.id == PLAYER_ID:
        title = f"Combate · Rodada {session.round} · sua vez"
    else:
        title = f"Combate · Rodada {session.round} · vez de {controller.name_of(session.current.id)}"
    lines = [[(_chat_symbols(text), color) for text, color in line.segments] for line in controller.log]
    lines = [[(t, c) for t, c in line if t] for line in lines]
    detail = controller.log[-1].detail
    return CombatLogView(title, lines, detail, None if right is None else int(right) - LOG_GAP)


def overhead_image(name: str, hp: float, max_hp: float, targeted: bool, acting: bool,
                   ally: bool = False) -> Image.Image:
    """Nome e vida sobre a cabeça: uma etiqueta pequena de pergaminho (verde quando é a vez dele)."""
    w = max(64, st.measure(name, 12, bold=True) + 18)
    image = Image.new("RGBA", (w + 4, 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    fill = st.FOREST if acting else st.CARD
    edge = st.GOLD if acting else (st.FOE_INK if targeted else st.BORDER)
    d.rounded_rectangle((2, 3, w + 1, 33), 6, fill=(20, 30, 25, 90))
    d.rounded_rectangle((2, 1, w + 1, 31), 6, fill=(*fill, 235), outline=(*edge, 255), width=2 if targeted else 1)
    color = st.CREAM if acting else (st.FOE_INK if targeted else (st.ALLY_INK if ally else st.INK))
    nw = st.measure(name, 12, bold=True)
    st.write(d, ((w + 4 - nw) / 2, 6), name, 12, color, bold=True)
    ratio = hp / max_hp if max_hp else 0
    st.bar(d, (9, 22, w - 6, 26), ratio, track=(60, 96, 80) if acting else st.TRACK)
    return image


def hover_image(controller: CombatController) -> Optional[Image.Image]:
    """A dica do inimigo sob o mouse: nome, vida e CA, e o que o clique faria."""
    enemy = controller.hovered()
    hint = controller.hover_hint()
    if enemy is None or hint is None:
        return None
    c = enemy.combatant
    targeted = controller.session is not None and controller.session.target_id == c.id
    text, color = hint
    w = max(190, st.measure(text, 12, bold=True) + 32, st.measure(c.name, 17, heading=True) + 90)
    image, pad = st.card(w, 78, radius=10, corners=False)
    d = ImageDraw.Draw(image)
    x0, x1 = pad + 14, pad + w - 14
    st.write(d, (x0, pad + 10), c.name, 17, st.FOE_INK if targeted else st.INK, heading=True)
    ca = f"CA {c.armor_class}"
    st.write(d, (x1 - st.measure(ca, 12, bold=True), pad + 13), ca, 12, st.INK, bold=True)
    ratio = c.hp / c.max_hp if c.max_hp else 0
    st.bar(d, (x0, pad + 36, x1 - 70, pad + 42), ratio)
    hp = f"{int(c.hp)}/{int(c.max_hp)}"
    st.write(d, (x1 - st.measure(hp, 11), pad + 33), hp, 11, st.MUTED)
    d.line((x0, pad + 51, x1, pad + 51), fill=(*st.LINE, 255))
    st.diamond(d, x0 + 3, pad + 63, 3, st.GOLD if color != (170, 170, 170) else st.LINE)
    st.write(d, (x0 + 12, pad + 57), st.fit(text, 12, w - 40, bold=True), 12, st.ink(color), bold=True)
    return image


def speech_image(name: str, text: str) -> Image.Image:
    """O balão da fala de um NPC: um pergaminho com o nome e a fala (quebrada em até três linhas), com a ponta."""
    words, lines = text.split(), [""]
    for word in words:
        trial = (lines[-1] + " " + word).strip()
        if st.measure(trial, 13) > 240 and lines[-1]:
            lines.append(word)
        else:
            lines[-1] = trial
    lines = lines[:3]
    w = max(st.measure(name, 12, bold=True), *(st.measure(l, 13) for l in lines)) + 28
    h = 26 + 18 * len(lines) + 8
    card, pad = st.card(w, h, radius=10, corners=False)
    image = Image.new("RGBA", (card.width, card.height + 10), (0, 0, 0, 0))
    image.alpha_composite(card, (0, 0))
    d = ImageDraw.Draw(image)
    cx = pad + w // 2
    d.polygon([(cx - 8, pad + h - 2), (cx + 8, pad + h - 2), (cx, pad + h + 9)], fill=(*st.CARD, 255))
    d.line((cx - 8, pad + h - 1, cx, pad + h + 9, cx + 8, pad + h - 1), fill=(*st.BORDER, 255), width=2)
    st.write(d, (pad + 14, pad + 9), name, 12, st.ALLY_INK, bold=True)
    for i, line in enumerate(lines):
        st.write(d, (pad + 14, pad + 28 + 18 * i), line, 13, st.INK)
    return image


def banner_image(text: str, color: Color) -> Image.Image:
    """A faixa do fim da luta: um pergaminho com o título em Georgia."""
    tw = st.measure(text, 34, heading=True)
    w = tw + 120
    image, pad = st.card(w, 96, radius=14)
    d = ImageDraw.Draw(image)
    st.write(d, (pad + (w - tw) / 2, pad + 22), text, 34, st.ink(color), heading=True)
    cx = pad + w / 2
    d.line((cx - 90, pad + 74, cx - 8, pad + 74), fill=(184, 148, 79, 255))
    d.line((cx + 8, pad + 74, cx + 90, pad + 74), fill=(184, 148, 79, 255))
    st.diamond(d, cx, pad + 74, 4)
    return image


def floater_image(text: str, color: Color) -> Image.Image:
    """Os números que sobem: Segoe em negrito com contorno escuro (legíveis em qualquer chão)."""
    size = 22
    w = st.measure(text, size, bold=True) + 8
    image = Image.new("RGBA", (w, size + 10), (0, 0, 0, 0))
    st.write(ImageDraw.Draw(image), (4, 4), text, size, color, bold=True, stroke=3, stroke_color=(22, 34, 28))
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
    return ("vez", controller.menu, s.round, round(s.movement_left, 1), s.action_used, entries,
            None if target is None else (target.id, int(target.hp), target.armor_class,
                                         round(s.current.distance_to(target), 1)))


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
        items.append(("ordem", order, (width - order.width) / 2, MARGIN - 6, 1.0))
        if session.active:
            menu = _cached(cache, "menu", _menu_key(controller), lambda: menu_image(controller))
            if menu is not None:
                # a imagem traz a sombra em volta do cartão: a borda do cartão fica a MARGIN da janela
                items.append(("menu", menu, width - menu.width - MARGIN + 8, height - menu.height - MARGIN + 12,
                              1.0))
    if controller.banner is not None:
        text, color, left = controller.banner
        banner = _cached(cache, "faixa", (text, color), lambda: banner_image(text, color))
        items.append(("faixa", banner, (width - banner.width) / 2, height * 0.28, min(1.0, left)))
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
        key = (c.name, int(c.hp), c.max_hp, c.id == session.target_id, c is session.current, enemy.friendly)
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
            above = 34 if in_fight else 4
            x = min(max(MARGIN, spot[0] - tip.width / 2), width - tip.width - MARGIN)
            items.append(("dica", tip, x, max(MARGIN, spot[1] - above - tip.height), 1.0))
    if controller.speech is not None:
        who, text, left = controller.speech
        token = controller.token(who)
        if token is not None:
            spot = project((token.shown[0], token.shown[1] + token.creature.height + 0.3, token.shown[2]), mvp,
                           width, height)
            if spot is not None:
                bubble = _cached(cache, "fala", (token.combatant.name, text),
                                 lambda: speech_image(token.combatant.name, text))
                x = min(max(MARGIN, spot[0] - bubble.width / 2), width - bubble.width - MARGIN)
                items.append(("fala", bubble, x, max(MARGIN, spot[1] - bubble.height), min(1.0, left / 0.4)))
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
                        lambda: floater_image(floater.text, floater.color))
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
                and controller.hover is None and controller.speech is None):
            self._prune(set())
            return
        from src.rendering.hud_quad import HudQuad
        used = set()
        for slot, image, x, y, opacity in compose(controller, width, height, mvp, self._cache):
            if slot == "menu":
                self.menu_left = x + 8     # a borda do cartão, sem a sombra
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
