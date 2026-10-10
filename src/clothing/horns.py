"""Os chifres 3D do personagem: tubos que afinam, curvados, presos à cabeça.

Cada chifre é uma linha que sai da cabeça numa direção (``rise``, ``out``) e vai mudando de
direção ao longo do comprimento (``curl``, ``sweep``), com anéis em volta que afinam até a ponta.
Um modelo é um conjunto deles: um par espelhado, um no meio da testa, uma galhada (pontas que
nascem de outro chifre), um inteiro e um quebrado. Todos os modelos têm os mesmos triângulos
(TUBES tubos, os que sobram vazios), então trocar de modelo ou mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

SEGMENTS, SIDES, TUBES = 8, 6, 8   # rings along a horn, corners around it, horns of a model (both sides, tines too)
TRIANGLES = SEGMENTS * SIDES * 2 + SIDES  # of one horn: its wall and the cap at its end
EMBED = 0.008          # metres the base starts inside the head
BROKEN_EDGE = 0.25     # how uneven the end of a broken horn is, as a share of its radius there
# What the adjustments do at 1: size as a share, and how much more (or less) the horns curve.
SIZE, CURVE = 0.6, 0.8
# Colours a horn can be given by name (besides any "#rrggbb"); its tip is this much of the colour.
HORN_COLORS = {"marfim": (228, 218, 192), "osso": (200, 186, 160), "branco": (246, 244, 238), "cinza": (140, 140, 146),
               "marrom": (110, 80, 58), "preto": (38, 32, 34), "vermelho": (150, 40, 40), "dourado": (212, 170, 80)}
TIP_OF_GIVEN = 0.55


@dataclass(frozen=True)
class Horn:
    """Um chifre.

    ``pos``: onde nasce na cabeça: do meio (0) ao lado (1), abaixo do topo (em parte da altura da
    cabeça) e do meio (0) ao rosto (1; negativo, para trás).
    ``length``, ``radius``: o comprimento e o raio na base, em metros.
    ``rise``: para onde sai, em graus acima da horizontal; ``out``: e para que lado, 0 para o lado,
    90 para a frente, -90 para trás.
    ``curl``, ``sweep``: quantos graus essas duas direções mudam da base à ponta (a curva).
    ``taper``: o raio na ponta, em parte do da base; ``cut``: a parte do comprimento que existe
    (menos de 1: quebrado). ``ridged``: anéis em relevo; ``spiral``: sulcos em espiral.
    ``side``: "both" (um de cada lado), "centre", "right" (+x) ou "left".
    ``parent``, ``at``: uma ponta de galhada: nasce do chifre ``parent`` do mesmo lado, a ``at`` do comprimento dele.
    """
    pos: Tuple[float, float, float] = (0.5, 0.0, 0.3)
    length: float = 0.10
    radius: float = 0.020
    rise: float = 70.0
    out: float = 20.0
    curl: float = 0.0
    sweep: float = 0.0
    taper: float = 0.08
    cut: float = 1.0
    ridged: float = 0.0
    spiral: bool = False
    side: str = "both"
    parent: int = -1
    at: float = 0.5


@dataclass(frozen=True)
class HornSet:
    """Um modelo: os chifres, a cor na base e a cor na ponta (0 a 255)."""
    horns: Tuple[Horn, ...]
    colour: Tuple[int, int, int] = (228, 218, 192)
    tip: Tuple[int, int, int] = (120, 100, 80)


_PAIR = Horn(pos=(0.5, 0.0, 0.45), length=0.10, radius=0.020, rise=75.0, out=30.0, curl=10.0)
_MIDDLE = Horn(pos=(0.0, 0.10, 0.98), length=0.09, radius=0.020, rise=60.0, out=90.0, curl=15.0, side="centre")
HORN_STYLES: Dict[str, HornSet] = {
    # A demon's: short and thick, curving up and in, dark.
    "demonio": HornSet((Horn(pos=(0.55, 0.02, 0.45), length=0.12, radius=0.023, rise=50.0, out=25.0, curl=45.0, sweep=35.0),),
                       (70, 30, 30), (20, 10, 12)),
    # A goat's: long, swept back and curving down, ringed.
    "bode": HornSet((Horn(pos=(0.45, 0.0, 0.2), length=0.22, radius=0.022, rise=65.0, out=-60.0, curl=-85.0, sweep=-15.0, ridged=0.08),),
                    (156, 136, 106), (92, 76, 56)),
    # A ram's: a thick ringed horn curling round beside the head.
    "carneiro": HornSet((Horn(pos=(0.72, 0.03, 0.0), length=0.30, radius=0.030, rise=30.0, out=-75.0, curl=-250.0, sweep=35.0, ridged=0.08),),
                        (170, 150, 118), (110, 92, 70)),
    # A bull's: out to the sides, then up and forwards.
    "touro": HornSet((Horn(pos=(0.9, 0.08, 0.1), length=0.17, radius=0.026, rise=10.0, out=0.0, curl=70.0, sweep=25.0),),
                     (228, 218, 192), (60, 50, 46)),
    # An ox's: longer and wider, with a gentler curve.
    "boi": HornSet((Horn(pos=(0.9, 0.06, 0.0), length=0.26, radius=0.024, rise=5.0, out=5.0, curl=45.0, sweep=10.0),),
                   (222, 210, 182), (96, 80, 66)),
    # A deer's antlers: a beam with three tines.
    "cervo": HornSet((Horn(pos=(0.5, 0.0, 0.1), length=0.26, radius=0.016, rise=72.0, out=-20.0, curl=-22.0, taper=0.2),
                      Horn(length=0.09, radius=0.011, rise=50.0, out=80.0, curl=20.0, parent=0, at=0.30),
                      Horn(length=0.10, radius=0.010, rise=75.0, out=60.0, curl=10.0, parent=0, at=0.55),
                      Horn(length=0.08, radius=0.009, rise=60.0, out=-100.0, curl=15.0, parent=0, at=0.80)),
                     (140, 105, 70), (226, 212, 184)),
    # A unicorn's: one long straight horn on the forehead, with a spiral groove.
    "unicornio": HornSet((Horn(pos=(0.0, 0.12, 0.98), length=0.24, radius=0.017, rise=62.0, out=90.0, spiral=True, ridged=0.14,
                               taper=0.04, side="centre"),), (246, 240, 226), (255, 250, 240)),
    # Plain horns: one in the middle, two, three, and two with one of them broken.
    "um": HornSet((_MIDDLE,)),
    "dois": HornSet((_PAIR,)),
    "tres": HornSet((_PAIR, _MIDDLE)),
    "um_quebrado": HornSet((Horn(**{**_PAIR.__dict__, "side": "right"}), Horn(**{**_PAIR.__dict__, "side": "left", "cut": 0.42}))),
}
NONE = "sem"
STYLE_NAMES = (NONE,) + tuple(HORN_STYLES)
ADJUSTMENTS = ("chifre_tamanho", "chifre_curva")


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def colour_of(custom: Any) -> Optional[Tuple[int, int, int]]:
    """A cor que o personagem deu aos chifres (0 a 255), ou None para a de cada modelo: um nome de
    HORN_COLORS ou "#rrggbb" em ``AvatarCustomization.horn_color``."""
    value = str(getattr(custom, "horn_color", "") or "").strip().lower()
    rgb = HORN_COLORS.get(value)
    if rgb is None and value.startswith("#") and len(value) == 7:
        try:
            rgb = tuple(int(value[k:k + 2], 16) for k in (1, 3, 5))
        except ValueError:
            rgb = None
    return rgb


def _direction(rise: float, out: float) -> np.ndarray:
    rise, out = np.radians(rise), np.radians(out)
    return np.array([np.cos(rise) * np.cos(out), np.sin(rise), np.cos(rise) * np.sin(out)])


def _line(horn: Horn, start: np.ndarray, grow: float, curve: float):
    """The middle of a horn: for a share of its length, (position, direction), walked from ``start``."""
    steps = np.linspace(0.0, 1.0, 49)
    directions = np.array([_direction(horn.rise + horn.curl * curve * t, horn.out + horn.sweep * curve * t) for t in steps])
    middle = (directions[1:] + directions[:-1]) / 2.0
    places = np.concatenate([[start], start + np.cumsum(middle * (horn.length * grow / (len(steps) - 1)), axis=0)])

    def at(t: float):
        k = min(max(t, 0.0), 1.0) * (len(steps) - 1)
        low = int(min(np.floor(k), len(steps) - 2))
        share = k - low
        direction = directions[low] * (1 - share) + directions[low + 1] * share
        return places[low] * (1 - share) + places[low + 1] * share, direction / np.linalg.norm(direction)
    return at


def _tube(horn: Horn, line, grow: float, colour: np.ndarray, tip: np.ndarray) -> np.ndarray:
    """Rows (TRIANGLES * 3, 11) of one horn along its middle line."""
    rings = []
    for k in range(SEGMENTS + 1):
        t = horn.cut * k / SEGMENTS
        centre, direction = line(t)
        reference = np.array([0.0, 1.0, 0.0]) if abs(direction[1]) < 0.9 else np.array([0.0, 0.0, 1.0])
        across = np.cross(direction, reference)
        across /= np.linalg.norm(across)
        other = np.cross(direction, across)
        radius = horn.radius * grow * (1.0 - (1.0 - horn.taper) * t)
        tone = colour + (tip - colour) * t
        ring = []
        for j in range(SIDES):
            turn = 2 * np.pi * j / SIDES
            wide = radius
            if horn.spiral:
                wide *= 1.0 + horn.ridged * (1.0 if (j + k) % 2 else -1.0)   # grooves winding up the horn
            elif horn.ridged and 0 < k < SEGMENTS:
                wide *= 1.0 + horn.ridged * (1.0 if k % 2 else -1.0)         # rings
            away = np.cos(turn) * across + np.sin(turn) * other
            point = centre + wide * away
            if horn.cut < 1.0 and k == SEGMENTS:                             # a broken end: uneven
                point = point + direction * radius * BROKEN_EDGE * (1.0 if j % 2 else -1.0)
            ring.append((point, away, tone))
        rings.append((ring, centre, direction, tone))
    corners = []
    for k in range(SEGMENTS):
        low, high = rings[k][0], rings[k + 1][0]
        for j in range(SIDES):
            a, b, c, d = low[j], low[(j + 1) % SIDES], high[(j + 1) % SIDES], high[j]
            corners += [a, b, c, a, c, d]
    end, centre, direction, tone = rings[-1]
    for j in range(SIDES):                                                   # the cap at the end
        corners += [(centre, direction, tone * 0.8), (end[j][0], direction, tone * 0.8), (end[(j + 1) % SIDES][0], direction, tone * 0.8)]
    rows = np.zeros((len(corners), 11))
    for k, (point, normal, tone) in enumerate(corners):
        rows[k, :3], rows[k, 3:6], rows[k, 8:11] = point, normal, np.clip(tone, 0.0, 1.0)
    return rows


def styled_rows(head_rows: np.ndarray, style: str, adjust: Optional[Mapping[str, float]] = None,
                colour: Optional[Sequence[int]] = None):
    """(vertex rows, triangles) of the horns of a style on a head, or None for no horns (an unknown
    style is none too). ``colour``: theirs (0 to 255) when it is not the style's own."""
    made = HORN_STYLES.get(style)
    if made is None:
        return None
    head = np.asarray(head_rows, dtype=np.float64).reshape(-1, 11)[:, :3]
    top, tall = head[:, 1].max(), float(np.ptp(head[:, 1]))
    wide, middle, face = np.abs(head[:, 0]).max(), (head[:, 2].min() + head[:, 2].max()) / 2.0, head[:, 2].max()
    grow = 1.0 + SIZE * _amount(adjust, "chifre_tamanho")
    curve = 1.0 + CURVE * _amount(adjust, "chifre_curva")
    base = np.array(colour if colour is not None else made.colour, dtype=np.float64) / 255.0
    tip = base * TIP_OF_GIVEN if colour is not None else np.array(made.tip, dtype=np.float64) / 255.0
    tubes: List[np.ndarray] = []
    for side in (1.0, -1.0):
        lines = []  # of this side, by the horn's place in the style (None: not on this side)
        for horn in made.horns:
            here = horn.side == "both" or (horn.side == "centre" and side > 0) or (horn.side == "right" and side > 0) \
                or (horn.side == "left" and side < 0)
            if not here:
                lines.append(None)
                continue
            if horn.parent >= 0 and lines[horn.parent] is not None:
                start = lines[horn.parent](horn.at)[0]
            else:
                start = np.array([horn.pos[0] * wide, top - horn.pos[1] * tall, middle + horn.pos[2] * (face - middle)])
                start = start - _direction(horn.rise, horn.out) * EMBED
            line = _line(horn, start, grow, curve)
            lines.append(line)
            tube = _tube(horn, line, grow, base, tip)
            if side < 0:  # the other side: mirrored across the head
                tube[:, 0] *= -1.0
                tube[:, 3] *= -1.0
            tubes.append(tube)
    tubes = tubes[:TUBES] + [np.zeros((TRIANGLES * 3, 11))] * (TUBES - len(tubes))
    for tube in tubes:
        empty = np.abs(tube[:, 3:6]).sum(axis=1) < 1e-9
        tube[empty, 4] = 1.0                                                 # an empty horn: no area, any normal
        tube[empty, 8:11] = base
    rows = np.concatenate(tubes).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)


def rows_for(head_rows: np.ndarray, custom: Any, adjust: Optional[Mapping[str, float]] = None):
    """Os chifres de um personagem (``AvatarCustomization``) numa cabeça. None sem chifres."""
    if adjust is None:
        adjust = getattr(custom, "resolved_body_adjust", None)
    return styled_rows(head_rows, getattr(custom, "horn_style", NONE), adjust, colour_of(custom))
