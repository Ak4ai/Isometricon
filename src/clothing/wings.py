"""As asas 3D do personagem: membranas finas presas ao alto das costas.

Cada asa é feita de leques e de hastes, no plano da asa (para fora, para cima), que abre para os
lados e para trás (``sweep``). Um leque (``Fan``) são triângulos de um centro até um contorno: a
membrana de um morcego parte do pulso, de onde saem os dedos; as penas de um anjo, do ombro. Uma
haste (``Rib``) é uma tira estreita por cima da membrana: o braço e os dedos do morcego, as hastes
das penas, as nervuras de uma asa de fada. Todos os modelos têm os mesmos triângulos (os leques e
as hastes que sobram ficam vazios), então trocar de modelo ou mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

OUTLINE, FANS, RIBS = 16, 2, 8   # points of a fan's outline; fans and ribs of a wing (a model may leave some empty)
THICKNESS = 0.004                # metres between the front of the membrane and its back
RIB_OUT = 0.0025                 # metres a rib stands out of the membrane, on each face
ROOT_APART = 0.045               # metres from the spine to where each wing leaves the back
EMBED = 0.012                    # metres the root is inside the body
# What the adjustments do at 1: size as a share, and degrees the wings open (or fold back).
SIZE, OPEN = 0.5, 30.0
GORE_TONES = (1.0, 0.86)         # the gores of a membrane: one lighter, one darker
Point = Tuple[float, float]


@dataclass(frozen=True)
class Fan:
    """Um leque da membrana: o centro, o contorno (até OUTLINE pontos), a cor no centro e na borda
    (0 a 255, ou "skin" / "hair") e se os gomos alternam de tom."""
    centre: Point
    outline: Tuple[Point, ...]
    colour: Any
    edge: Any
    gores: bool = False


@dataclass(frozen=True)
class Rib:
    """Uma haste sobre a membrana: de onde a onde, a largura no começo (afina até 40% no fim) e a cor."""
    start: Point
    end: Point
    width: float
    colour: Any


@dataclass(frozen=True)
class Wing:
    """Um modelo de asa: os leques, as hastes, quanto o plano da asa vai para trás (graus; 0: aberta
    para os lados) e quanto ela é opaca (menos de 1: translúcida, como a de uma fada). As medidas
    são em centímetros, a partir de onde a asa sai das costas."""
    fans: Tuple[Fan, ...]
    ribs: Tuple[Rib, ...] = ()
    sweep: float = 28.0
    alpha: float = 1.0
    scale: float = 1.0


def _between(a: Point, b: Point, towards: Point, pull: float) -> Point:
    """The middle of a to b, pulled towards another point: the hollow of a scalloped edge."""
    middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    return middle[0] + (towards[0] - middle[0]) * pull, middle[1] + (towards[1] - middle[1]) * pull


def _bat(membrane: Any, edge: Any, bone: Any, scale: float = 1.0, sweep: float = 28.0) -> Wing:
    """A bat's wing: an arm up to the wrist, four fingers from it, and the membrane between them,
    scalloped along the trailing edge, down to the side of the body."""
    wrist, elbow = (24.0, 30.0), (10.0, 10.0)
    tips = ((62.0, 54.0), (68.0, 26.0), (58.0, 0.0), (42.0, -20.0))
    body = (3.0, -16.0)
    outline = [tips[0]]
    for a, b in zip(tips, tips[1:]):
        outline += [_between(a, b, wrist, 0.30), b]
    outline += [_between(tips[-1], body, wrist, 0.25), body, (0.0, 6.0), elbow]
    inner = Fan((8.0, 4.0), ((0.0, 6.0), elbow, wrist, body, (0.0, -10.0)), membrane, edge)   # between the arm and the body
    ribs = (Rib((0.0, 2.0), elbow, 3.2, bone), Rib(elbow, wrist, 2.8, bone), Rib(wrist, (26.0, 40.0), 1.6, bone),
            Rib(wrist, tips[0], 1.9, bone), Rib(wrist, tips[1], 1.7, bone), Rib(wrist, tips[2], 1.6, bone),
            Rib(wrist, tips[3], 1.5, bone))
    return Wing((Fan(wrist, tuple(outline), membrane, edge, gores=True), inner), ribs, sweep=sweep, scale=scale)


def _feathered() -> Wing:
    """An angel's wing: long flight feathers along the lower edge, a row of shorter ones over them."""
    shoulder = (12.0, 16.0)
    flight = ((0.0, 12.0), (14.0, 32.0), (34.0, 46.0), (56.0, 48.0), (72.0, 38.0), (64.0, 28.0), (66.0, 16.0), (55.0, 13.0),
              (56.0, 0.0), (45.0, 0.0), (44.0, -13.0), (32.0, -10.0), (28.0, -23.0), (15.0, -14.0), (4.0, -12.0))
    coverts = ((2.0, 14.0), (14.0, 31.0), (32.0, 43.0), (52.0, 45.0), (60.0, 36.0), (52.0, 30.0), (50.0, 22.0), (42.0, 20.0),
               (38.0, 12.0), (30.0, 12.0), (26.0, 4.0), (18.0, 6.0), (10.0, 2.0))
    shafts = tuple(Rib((14.0 + 6.0 * k, 26.0 + 3.0 * k), tip, 0.9, (196, 202, 216))
                   for k, tip in enumerate(((66.0, 16.0), (56.0, 0.0), (44.0, -13.0), (28.0, -23.0))))
    arm = (Rib((0.0, 8.0), (14.0, 30.0), 4.0, (255, 255, 255)), Rib((14.0, 30.0), (56.0, 47.0), 3.4, (255, 255, 255)))
    return Wing((Fan(shoulder, flight, (236, 238, 244), (206, 212, 226)), Fan((20.0, 26.0), coverts, (255, 255, 254), (232, 236, 244))),
                arm + shafts, sweep=24.0)


def _lobes(upper: Tuple[Point, ...], lower: Tuple[Point, ...], colour: Any, edge: Any, vein: Any, alpha: float, sweep: float) -> Wing:
    """An insect's wings: an upper and a lower one on each side, with veins from the root."""
    veins = tuple(Rib((1.0, 0.0), lobe[k], 0.8, vein) for lobe in (upper, lower) for k in (len(lobe) // 4, len(lobe) // 2, 3 * len(lobe) // 4))
    return Wing((Fan((1.0, 1.0), upper, colour, edge), Fan((1.0, -1.0), lower, colour, edge)), veins, sweep=sweep, alpha=alpha)


WING_STYLES: Dict[str, Wing] = {
    # A bat's (a demon's, a vampire's): a dark membrane between long fingers.
    "morcego": _bat((84, 50, 58), (40, 24, 30), (30, 18, 22)),
    # A dragon's: the same, larger, the membrane of the skin's colour.
    "dragao": _bat("skin", (70, 44, 44), (50, 30, 30), scale=1.4, sweep=22.0),
    # An angel's: white, feathered.
    "anjo": _feathered(),
    # A fairy's: two slim clear wings on each side.
    "fada": _lobes(((2, 4), (8, 22), (20, 40), (34, 50), (44, 50), (48, 40), (44, 26), (34, 14), (22, 6), (12, 2), (6, 0)),
                   ((2, -2), (10, -4), (22, -10), (32, -20), (36, -30), (32, -36), (24, -34), (16, -26), (10, -18), (6, -10), (3, -6)),
                   (214, 246, 250), (150, 214, 236), (120, 180, 210), alpha=0.6, sweep=32.0),
    # A butterfly's: two broad wings on each side, bright with dark edges and veins.
    "borboleta": _lobes(((2, 2), (10, 24), (24, 42), (42, 48), (56, 40), (60, 26), (54, 14), (42, 6), (28, 2), (16, 0), (8, 0)),
                        ((2, -2), (12, -2), (26, -6), (38, -14), (42, -26), (36, -38), (26, -40), (16, -34), (10, -24), (6, -14), (3, -8)),
                        (244, 150, 40), (34, 26, 30), (40, 28, 30), alpha=1.0, sweep=20.0),
}
NONE = "sem"
STYLE_NAMES = (NONE,) + tuple(WING_STYLES)
ADJUSTMENTS = ("asa_tamanho", "asa_abertura")
TRIANGLES = 2 * 2 * (FANS * (OUTLINE - 1) + RIBS * 2)  # both wings: each fan and each rib, front and back


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def alpha_of(custom: Any) -> float:
    """Quanto as asas do personagem são opacas (1: inteiras; sem asas, 1)."""
    wing = WING_STYLES.get(getattr(custom, "wing_style", NONE))
    return wing.alpha if wing is not None else 1.0


def styled_rows(root: Sequence[float], style: str, adjust: Optional[Mapping[str, float]] = None,
                skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25),
                coat: Optional[Sequence[float]] = None):
    """(vertex rows, triangles) of the two wings of a style leaving the back at ``root`` (the middle
    of the upper back, on its surface), or None for no wings (an unknown style is none too).
    ``coat``: their colour (0 to 1), when it is not the style's own."""
    wing = WING_STYLES.get(style)
    if wing is None:
        return None
    grow = wing.scale * (1.0 + SIZE * _amount(adjust, "asa_tamanho")) / 100.0   # the outlines are in centimetres
    sweep = np.radians(min(max(wing.sweep - OPEN * _amount(adjust, "asa_abertura"), -10.0), 80.0))
    named = {"skin": np.asarray(skin, dtype=np.float64)[:3], "hair": np.asarray(hair, dtype=np.float64)[:3]}
    given = np.asarray(coat, dtype=np.float64)[:3] if coat is not None else None

    def tone(value: Any, share: float = 1.0) -> np.ndarray:
        if given is not None:  # one colour given for the whole wing: its parts keep their light and dark
            return given * share
        return named[value] if isinstance(value, str) else np.asarray(value, dtype=np.float64) / 255.0

    out = np.array([np.cos(sweep), 0.0, -np.sin(sweep)])     # along the wing: to the side, and back
    up = np.array([0.0, 1.0, 0.0])
    front = np.cross(out, up)                                 # the face of the membrane turned forwards
    start = np.asarray(root, dtype=np.float64) + np.array([ROOT_APART, 0.0, EMBED])
    place = lambda p: start + grow * (p[0] * out + p[1] * up)
    corners = []  # (position, normal, colour), three to a triangle

    def both_faces(trio, colours, lift: float) -> None:
        corners.extend((p + front * lift, front, c) for p, c in zip(trio, colours))
        corners.extend((p - front * lift, -front, c) for p, c in zip(trio[::-1], colours[::-1]))

    nowhere = start
    for index in range(FANS):
        fan = wing.fans[index] if index < len(wing.fans) else None
        for j in range(OUTLINE - 1):
            if fan is None or j + 1 >= len(fan.outline):      # nothing here: a triangle of no area
                both_faces([nowhere] * 3, [np.zeros(3)] * 3, 0.0)
                continue
            shade = GORE_TONES[j % 2] if fan.gores else 1.0
            both_faces([place(fan.centre), place(fan.outline[j]), place(fan.outline[j + 1])],
                       [tone(fan.colour) * shade, tone(fan.edge, 0.6) * shade, tone(fan.edge, 0.6) * shade], THICKNESS / 2.0)
    for index in range(RIBS):
        rib = wing.ribs[index] if index < len(wing.ribs) else None
        if rib is None:
            both_faces([nowhere] * 3, [np.zeros(3)] * 3, 0.0)
            both_faces([nowhere] * 3, [np.zeros(3)] * 3, 0.0)
            continue
        a, b = np.array(rib.start, dtype=np.float64), np.array(rib.end, dtype=np.float64)
        along = (b - a) / max(np.linalg.norm(b - a), 1e-9)
        across = np.array([-along[1], along[0]])
        wide, narrow = across * rib.width / 2.0, across * rib.width * 0.2
        quad = [place(a - wide), place(a + wide), place(b + narrow), place(b - narrow)]
        colour = tone(rib.colour, 0.45)
        lift = THICKNESS / 2.0 + RIB_OUT
        both_faces([quad[0], quad[1], quad[2]], [colour] * 3, lift)
        both_faces([quad[0], quad[2], quad[3]], [colour] * 3, lift)
    one = np.zeros((len(corners), 11))
    for k, (point, normal, colour) in enumerate(corners):
        one[k, :3], one[k, 3:6], one[k, 8:11] = point, normal, np.clip(colour, 0.0, 1.0)
    other = one.copy()  # the other wing: mirrored across the body
    other[:, 0] *= -1.0
    other[:, 3] *= -1.0
    rows = np.concatenate([one, other]).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)


def rows_for(root: Sequence[float], custom: Any, adjust: Optional[Mapping[str, float]] = None):
    """As asas de um personagem (``AvatarCustomization``) saindo de ``root``. None sem asas."""
    from .ears import coat_of
    if adjust is None:
        adjust = getattr(custom, "resolved_body_adjust", None)
    return styled_rows(root, getattr(custom, "wing_style", NONE), adjust, getattr(custom, "skin_color_rgb", (1.0, 1.0, 1.0)),
                       tuple(c / 255.0 for c in getattr(custom, "hair_rgb_255", (102, 77, 64))), coat_of(custom, "wing_color"))
