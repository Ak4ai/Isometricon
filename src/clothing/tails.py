"""As caudas 3D do personagem: um tubo curvo que sai da base das costas.

A cauda é uma linha que sai para trás (``rise``: quanto acima da horizontal) e vai mudando de
direção ao longo do comprimento (``curl``), com anéis em volta cujo raio segue um perfil
(``profile``): fino e igual num felino, cheio no meio num lobo, com um tufo na ponta num leão. A cor
vem em faixas ao longo dela (``bands``): a ponta branca da raposa, as listras do tigre. Um dragão
tem espinhos em cima, que são tubos pequenos nascidos da cauda. Todos os modelos têm os mesmos
triângulos, então trocar de modelo ou mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

SEGMENTS, SIDES, SPIKES = 14, 8, 5   # rings along the tail, corners around it, and spikes a tail can have
SPIKE_SEGMENTS = 2
EMBED = 0.02           # metres the base starts inside the body
# What the adjustments do at 1: size as a share, and how much more (or less) the tail curves.
SIZE, CURVE = 0.6, 0.9
SKIN_COAT, HAIR_COAT = "pele", "cabelo"
SCALE_TONES = (1.0, 0.82)  # a scaly tail: its rings one lighter, one darker


@dataclass(frozen=True)
class Tail:
    """Um modelo de cauda.

    ``length``, ``radius``: o comprimento e o raio de referência, em metros.
    ``rise``: para onde sai, em graus acima da horizontal (para trás); ``curl``: quantos graus essa
    direção muda da base à ponta (positivo: enrola para cima).
    ``profile``: o raio ao longo dela, em pontos (parte do comprimento, parte do raio).
    ``flat``: achatada dos lados nesse tanto na ponta (a seta do diabo, vista de lado).
    ``coat``: "skin" ou "hair", ou uma cor (0 a 255); ``bands``: faixas de cor ao longo dela, cada
    uma (onde começa, o que multiplica a cor, ou uma cor 0 a 255); ``stripes``: quantas listras
    escuras em volta; ``scaly``: anéis alternando claro e escuro.
    ``spikes``: espinhos em cima, do começo até esta parte do comprimento (0: nenhum).
    """
    length: float = 0.45
    radius: float = 0.022
    rise: float = -20.0
    curl: float = 80.0
    profile: Tuple[Tuple[float, float], ...] = ((0.0, 1.0), (1.0, 0.6))
    flat: float = 0.0
    coat: Any = "hair"
    bands: Tuple[Tuple[float, Any], ...] = ()
    stripes: int = 0
    scaly: bool = False
    spikes: float = 0.0


WHITE, DARK = (245, 242, 235), 0.35
TAIL_STYLES: Dict[str, Tail] = {
    # A cat's: long, thin and even, curving up at the end.
    "felino": Tail(length=0.52, radius=0.018, rise=-35.0, curl=120.0, profile=((0.0, 1.0), (0.85, 0.9), (1.0, 0.5))),
    # A devil's: a thin whip of the skin's colour ending in a spade.
    "diabo": Tail(length=0.58, radius=0.011, rise=-30.0, curl=130.0, coat="skin", flat=0.75,
                  profile=((0.0, 1.0), (0.80, 0.7), (0.86, 3.6), (0.93, 2.0), (1.0, 0.1)), bands=((0.80, DARK + 0.3),)),
    # A tiger's or a jaguar's: long and thick, orange with dark rings.
    "tigre": Tail(length=0.56, radius=0.026, rise=-30.0, curl=95.0, coat=(226, 138, 52), stripes=6,
                  profile=((0.0, 1.0), (0.9, 0.85), (1.0, 0.5)), bands=((0.88, DARK),)),
    # A lion's: thin, of the skin's colour, with a tuft of hair at the end.
    "leao": Tail(length=0.55, radius=0.014, rise=-40.0, curl=110.0, coat="skin",
                 profile=((0.0, 1.0), (0.78, 0.85), (0.86, 2.6), (0.94, 2.4), (1.0, 0.3)), bands=((0.80, "hair"),)),
    # A wolf's: bushy, hanging low.
    "lobo": Tail(length=0.42, radius=0.034, rise=-55.0, curl=35.0,
                 profile=((0.0, 0.6), (0.3, 1.3), (0.7, 1.4), (1.0, 0.2))),
    # A fox's: very bushy, with a white tip.
    "raposa": Tail(length=0.50, radius=0.040, rise=-20.0, curl=70.0,
                   profile=((0.0, 0.45), (0.35, 1.3), (0.7, 1.5), (1.0, 0.15)), bands=((0.74, WHITE),)),
    # A dog's: shorter, curled up over the back.
    "cachorro": Tail(length=0.34, radius=0.024, rise=-5.0, curl=150.0, profile=((0.0, 0.9), (0.6, 1.0), (1.0, 0.35))),
    # A horse's: a long fall of hair.
    "cavalo": Tail(length=0.62, radius=0.034, rise=10.0, curl=-95.0,
                   profile=((0.0, 0.5), (0.2, 1.0), (0.75, 1.2), (1.0, 0.5))),
    # A rabbit's: a ball of fluff.
    "coelho": Tail(length=0.085, radius=0.040, rise=15.0, curl=20.0, coat=WHITE,
                   profile=((0.0, 0.55), (0.35, 1.0), (0.7, 1.0), (1.0, 0.35))),
    # A lizard's: thick at the base, tapering to a point, in scales.
    "reptil": Tail(length=0.60, radius=0.050, rise=-30.0, curl=28.0, coat="skin", scaly=True,
                   profile=((0.0, 1.0), (0.4, 0.62), (1.0, 0.04))),
    # A dragon's: the same, larger, with spines along the top.
    "dragao": Tail(length=0.72, radius=0.058, rise=-25.0, curl=40.0, coat="skin", scaly=True, spikes=0.8,
                   profile=((0.0, 1.0), (0.4, 0.66), (0.9, 0.16), (1.0, 0.05))),
}
NONE = "sem"
STYLE_NAMES = (NONE,) + tuple(TAIL_STYLES)
ADJUSTMENTS = ("cauda_tamanho", "cauda_curva")
MAIN = SEGMENTS * SIDES * 2 + SIDES                     # triangles of the tail itself: its wall and its end
SPIKE = SPIKE_SEGMENTS * 4 * 2 + 4                      # of one spike (four corners around)


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _rgb(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64) / 255.0


def _wall(rings: List[Tuple[List[np.ndarray], List[np.ndarray], np.ndarray]], end: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Rows (N, 11) of a tube: ``rings`` of (points, normals, colour), closed by a cap at ``end``."""
    corners = []
    for (low, low_n, low_c), (high, high_n, high_c) in zip(rings, rings[1:]):
        count = len(low)
        for j in range(count):
            k = (j + 1) % count
            a, b = (low[j], low_n[j], low_c), (low[k], low_n[k], low_c)
            c, d = (high[k], high_n[k], high_c), (high[j], high_n[j], high_c)
            corners += [a, b, c, a, c, d]
    last, _, colour = rings[-1]
    for j in range(len(last)):
        corners += [(end, direction, colour), (last[j], direction, colour), (last[(j + 1) % len(last)], direction, colour)]
    rows = np.zeros((len(corners), 11))
    for k, (point, normal, colour) in enumerate(corners):
        rows[k, :3], rows[k, 3:6], rows[k, 8:11] = point, normal, np.clip(colour, 0.0, 1.0)
    return rows


def styled_rows(root: Sequence[float], style: str, adjust: Optional[Mapping[str, float]] = None,
                skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25),
                coat: Optional[Sequence[float]] = None):
    """(vertex rows, triangles) of the tail of a style leaving the body at ``root`` (the middle of
    the base of the back), or None for no tail (an unknown style is none too). ``coat``: its colour
    (0 to 1), when it is not the style's own."""
    tail = TAIL_STYLES.get(style)
    if tail is None:
        return None
    grow = 1.0 + SIZE * _amount(adjust, "cauda_tamanho")
    curve = 1.0 + CURVE * _amount(adjust, "cauda_curva")
    skin, hair = np.asarray(skin, dtype=np.float64)[:3], np.asarray(hair, dtype=np.float64)[:3]
    named = {"skin": skin, "hair": hair}
    base = np.asarray(coat, dtype=np.float64)[:3] if coat is not None else \
        (named[tail.coat] if isinstance(tail.coat, str) else _rgb(tail.coat))

    def colour_at(t: float, ring: int) -> np.ndarray:
        colour = base
        for start, value in tail.bands:
            if t >= start:
                colour = named[value] if isinstance(value, str) else (_rgb(value) if isinstance(value, tuple) else base * value)
        if tail.stripes and int(t * tail.stripes * 2) % 2 == 1 and t < 0.88:
            colour = colour * DARK
        if tail.scaly:
            colour = colour * SCALE_TONES[ring % 2]
        return colour

    # The middle line, walked from the root: backwards, at ``rise`` above level, turning by ``curl``.
    steps = np.linspace(0.0, 1.0, 97)
    angles = np.radians(tail.rise + tail.curl * curve * steps)
    directions = np.column_stack((np.zeros(len(steps)), np.sin(angles), -np.cos(angles)))
    start = np.asarray(root, dtype=np.float64) - directions[0] * EMBED
    middle = (directions[1:] + directions[:-1]) / 2.0
    places = np.concatenate([[start], start + np.cumsum(middle * (tail.length * grow / (len(steps) - 1)), axis=0)])

    def at(t: float):
        k = min(max(t, 0.0), 1.0) * (len(steps) - 1)
        low = int(min(np.floor(k), len(steps) - 2))
        share = k - low
        direction = directions[low] * (1 - share) + directions[low + 1] * share
        return places[low] * (1 - share) + places[low + 1] * share, direction / np.linalg.norm(direction)

    radius_at = lambda t: tail.radius * grow * float(np.interp(t, [p[0] for p in tail.profile], [p[1] for p in tail.profile]))
    side = np.array([1.0, 0.0, 0.0])
    rings = []
    for k in range(SEGMENTS + 1):
        t = k / SEGMENTS
        centre, direction = at(t)
        above = np.cross(side, direction)                    # up, across the tail
        radius = radius_at(t)
        squash = 1.0 - tail.flat * np.clip((t - 0.7) / 0.15, 0.0, 1.0)  # flattened from the sides towards the end
        points, normals = [], []
        for j in range(SIDES):
            turn = 2 * np.pi * j / SIDES
            away = np.cos(turn) * side * squash + np.sin(turn) * above
            points.append(centre + radius * away)
            normals.append(away / max(np.linalg.norm(away), 1e-9))
        rings.append((points, normals, colour_at(t, k)))
    end, direction = at(1.0)
    parts = [_wall(rings, end, direction)]
    # The spines of a dragon: small four-sided points standing on top of the tail.
    for index in range(SPIKES):
        if not tail.spikes:
            parts.append(np.zeros((SPIKE * 3, 11)))
            continue
        t = tail.spikes * (index + 0.5) / SPIKES
        centre, direction = at(t)
        up = np.cross(side, direction)
        radius = radius_at(t)
        foot, tall, wide = centre + up * radius * 0.7, radius * 1.5, radius * 0.45
        colour = colour_at(t, 0) * 0.7
        cone = []
        for level in range(SPIKE_SEGMENTS + 1):
            share = level / SPIKE_SEGMENTS
            centre_here = foot + up * tall * share - direction * tall * 0.25 * share   # leaning back a little
            width = wide * (1.0 - 0.85 * share)
            corners = [centre_here + width * (c * side + s * direction) for c, s in ((1, 0), (0, 1), (-1, 0), (0, -1))]
            normals = [(c * side + s * direction) for c, s in ((1, 0), (0, 1), (-1, 0), (0, -1))]
            cone.append((corners, normals, colour))
        parts.append(_wall(cone, foot + up * tall - direction * tall * 0.25, up))
    for part in parts:
        empty = np.abs(part[:, 3:6]).sum(axis=1) < 1e-9
        part[empty, 4] = 1.0                                 # no spike here: no area, any normal
        part[empty, 8:11] = base
    rows = np.concatenate(parts).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)


def rows_for(root: Sequence[float], custom: Any, adjust: Optional[Mapping[str, float]] = None):
    """A cauda de um personagem (``AvatarCustomization``) saindo de ``root``. None sem cauda."""
    from .ears import coat_of
    if adjust is None:
        adjust = getattr(custom, "resolved_body_adjust", None)
    return styled_rows(root, getattr(custom, "tail_style", NONE), adjust, getattr(custom, "skin_color_rgb", (1.0, 1.0, 1.0)),
                       tuple(c / 255.0 for c in getattr(custom, "hair_rgb_255", (102, 77, 64))), coat_of(custom, "tail_color"))
