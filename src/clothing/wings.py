"""As asas 3D do personagem: membranas finas presas ao alto das costas.

Cada asa é um ou dois painéis (a asa de cima e a de baixo de uma borboleta), e cada painel é um
leque de triângulos da raiz até um contorno de OUTLINE pontos no plano da asa (para fora, para
cima). O plano abre para os lados e para trás (``sweep``). A cor vai da raiz à borda, e num
morcego os gomos da membrana alternam de tom. Todos os modelos têm os mesmos triângulos, então
trocar de modelo ou mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

OUTLINE, PANELS = 12, 2      # points of a panel's outline; panels of a wing (a model may leave the second empty)
THICKNESS = 0.004            # metres between the front of the membrane and its back
ROOT_APART = 0.045           # metres from the spine to where each wing leaves the back
EMBED = 0.015                # metres the root is inside the body
# What the adjustments do at 1: size as a share, and degrees the wings open (or fold back).
SIZE, OPEN = 0.5, 30.0
PANEL_TONES = (1.0, 0.86)    # the gores of a membrane: one lighter, one darker


@dataclass(frozen=True)
class Wing:
    """Um modelo de asa.

    ``panels``: os contornos (para fora, para cima), em metros, a partir da raiz em (0, 0).
    ``sweep``: quanto o plano da asa vai para trás, em graus (0: aberta para os lados).
    ``colour``, ``edge``: a cor na raiz e na borda (0 a 255), ou "skin" / "hair".
    ``gores``: os gomos alternam de tom (a membrana entre os dedos de um morcego).
    ``alpha``: quanto ela é opaca (menos de 1: translúcida, como a de uma fada).
    """
    panels: Tuple[Tuple[Tuple[float, float], ...], ...]
    sweep: float = 28.0
    colour: Any = (60, 40, 46)
    edge: Any = (30, 20, 24)
    gores: bool = False
    alpha: float = 1.0


def _cm(*points: Tuple[float, float], scale: float = 1.0) -> Tuple[Tuple[float, float], ...]:
    assert len(points) == OUTLINE
    return tuple((out * scale / 100.0, up * scale / 100.0) for out, up in points)


# Each outline runs from the top of the root, out along the leading edge to the tip, and back along
# the trailing edge to the bottom of the root.
_BAT = ((4, 10), (16, 30), (34, 44), (56, 48), (46, 30), (58, 20), (44, 10), (52, -6), (34, -8), (36, -24), (18, -14), (6, -12))
_FEATHERS = ((4, 12), (18, 34), (38, 46), (60, 44), (72, 30), (62, 22), (66, 10), (52, 6), (54, -8), (38, -8), (36, -22), (14, -16))
WING_STYLES: Dict[str, Wing] = {
    # A bat's (a demon's, a vampire's): a dark membrane between long fingers, scalloped behind.
    "morcego": Wing((_cm(*_BAT),), colour=(70, 44, 50), edge=(34, 22, 26), gores=True),
    # A dragon's: the same, larger, of the skin's colour.
    "dragao": Wing((_cm(*_BAT, scale=1.4),), sweep=22.0, colour="skin", edge=(60, 40, 40), gores=True),
    # An angel's: white, feathered along the lower edge.
    "anjo": Wing((_cm(*_FEATHERS),), sweep=24.0, colour=(250, 250, 248), edge=(214, 220, 232)),
    # A fairy's: two slim clear wings on each side.
    "fada": Wing((_cm((2, 4), (8, 22), (20, 40), (34, 50), (44, 50), (48, 40), (44, 26), (34, 14), (22, 6), (12, 2), (6, 0), (2, 0)),
                  _cm((2, -2), (10, -4), (22, -10), (32, -20), (36, -30), (32, -36), (24, -34), (16, -26), (10, -18), (6, -10),
                      (3, -6), (1, -3))), sweep=32.0, colour=(214, 246, 250), edge=(150, 214, 236), alpha=0.6),
    # A butterfly's: two broad wings on each side, bright with dark edges.
    "borboleta": Wing((_cm((2, 2), (10, 24), (24, 42), (42, 48), (56, 40), (60, 26), (54, 14), (42, 6), (28, 2), (16, 0), (8, 0), (3, 0)),
                       _cm((2, -2), (12, -2), (26, -6), (38, -14), (42, -26), (36, -38), (26, -40), (16, -34), (10, -24),
                           (6, -14), (3, -8), (1, -4))), sweep=20.0, colour=(244, 150, 40), edge=(34, 26, 30)),
}
NONE = "sem"
STYLE_NAMES = (NONE,) + tuple(WING_STYLES)
ADJUSTMENTS = ("asa_tamanho", "asa_abertura")
TRIANGLES = 2 * 2 * PANELS * (OUTLINE - 1)  # both wings: each panel's front and its back


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
    of the upper back), or None for no wings (an unknown style is none too). ``coat``: their colour
    (0 to 1), when it is not the style's own."""
    wing = WING_STYLES.get(style)
    if wing is None:
        return None
    grow = 1.0 + SIZE * _amount(adjust, "asa_tamanho")
    sweep = np.radians(min(max(wing.sweep - OPEN * _amount(adjust, "asa_abertura"), -10.0), 80.0))
    named = {"skin": np.asarray(skin, dtype=np.float64)[:3], "hair": np.asarray(hair, dtype=np.float64)[:3]}
    tone = lambda value: named[value] if isinstance(value, str) else np.asarray(value, dtype=np.float64) / 255.0
    base, edge = (np.asarray(coat, dtype=np.float64)[:3], np.asarray(coat, dtype=np.float64)[:3] * 0.6) if coat is not None \
        else (tone(wing.colour), tone(wing.edge))
    out = np.array([np.cos(sweep), 0.0, -np.sin(sweep)])     # along the wing: to the side, and back
    up = np.array([0.0, 1.0, 0.0])
    front = np.cross(out, up)                                 # the face of the membrane turned forwards
    half = front * THICKNESS / 2.0
    start = np.asarray(root, dtype=np.float64) + np.array([ROOT_APART, 0.0, EMBED])
    rows = []
    for side in (1.0, -1.0):
        wing_rows = np.zeros((2 * PANELS * (OUTLINE - 1) * 3, 11))
        wing_rows[:, 3:6], wing_rows[:, 8:11] = front, base
        k = 0
        for index in range(PANELS):
            panel = wing.panels[index] if index < len(wing.panels) else None
            for j in range(OUTLINE - 1):
                if panel is None:                             # a model of one panel: this one is empty
                    wing_rows[k:k + 6, :3] = start
                    k += 6
                    continue
                a, b = (start + grow * (p[0] * out + p[1] * up) for p in (panel[j], panel[j + 1]))
                shade = PANEL_TONES[j % 2] if wing.gores else 1.0
                for corners, normal, lift in (((start, a, b), front, half), ((start, b, a), -front, -half)):
                    wing_rows[k:k + 3, :3] = np.array(corners) + lift
                    wing_rows[k:k + 3, 3:6] = normal
                    wing_rows[k:k + 3, 8:11] = np.array([base * shade, edge * shade, edge * shade])
                    k += 3
        if side < 0:  # the other wing: mirrored across the body
            wing_rows[:, 0] *= -1.0
            wing_rows[:, 3] *= -1.0
        rows.append(wing_rows)
    rows = np.concatenate(rows).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)


def rows_for(root: Sequence[float], custom: Any, adjust: Optional[Mapping[str, float]] = None):
    """As asas de um personagem (``AvatarCustomization``) saindo de ``root``. None sem asas."""
    from .ears import coat_of
    if adjust is None:
        adjust = getattr(custom, "resolved_body_adjust", None)
    return styled_rows(root, getattr(custom, "wing_style", NONE), adjust, getattr(custom, "skin_color_rgb", (1.0, 1.0, 1.0)),
                       tuple(c / 255.0 for c in getattr(custom, "hair_rgb_255", (102, 77, 64))), coat_of(custom, "wing_color"))
