"""As orelhas 3D do personagem: placas recortadas num contorno, uma de cada lado da cabeça.

Cada modelo é um contorno de OUTLINE pontos no plano da orelha (afastando-se da raiz, ao longo
dela). As de gente ficam nos lados da cabeça, presas pela borda da frente e abertas para fora por
um ângulo (``flare``): deitadas na cabeça numa orelha humana, bem abertas numa de elfo. As de
bicho ficam no alto da cabeça (``mount="top"``), em pé ou caídas: uma orelha caída é curvada de
verdade (``bend``), sobe da cabeça, dobra para fora e desce ao lado dela. Todos os modelos têm os
mesmos triângulos, na mesma ordem, então trocar de modelo ou mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

OUTLINE = 10          # points of every outline
STATIONS = 7          # cuts along a bent ear, from its root to its tip
FRONT = 4 * STATIONS  # triangles of the front of every model (and of its back); a flat ear leaves some empty
RIM = 2 * STATIONS + 2  # and quads around its edge
THICKNESS = 0.006     # metres from the front of the plate to its back
EMBED = 0.004         # metres the root goes into the head (no gap on a rounded head)
EAR_HEIGHT = 0.125    # metres from the bottom of the head up to the middle of the ear's root (the height of the eyes)
EAR_FORWARD = 0.012   # metres the root is in front of the middle of the head, front to back
INNER = (0.006, 0.0)  # the point of the plate (away, along) the front is fanned from: the hollow of the ear
SCALE = 1.45          # the outlines are drawn at a person's size; the character's head is large for its body
INNER_TONE, BACK_TONE = 0.80, 0.93  # the coat's colour at that hollow and on the back of the ear
PINK = (0.96, 0.72, 0.74)           # the inside of a furry ear, mixed into the coat there
PINK_SHARE = 0.65
SCALE_TONES = (1.0, 0.80)           # a scaly ear: its triangles one lighter, one darker
# What the adjustments do at 1: size as a share, metres up the head, degrees more open.
SIZE, LIFT, OPEN = 0.5, 0.03, 30.0
# Colours an ear can be given by name (besides the skin's, the hair's, and any "#rrggbb").
EAR_COLORS = {"branco": (245, 245, 240), "creme": (236, 214, 180), "caramelo": (196, 140, 84), "marrom": (120, 80, 56),
              "ruivo": (190, 90, 50), "cinza": (150, 150, 156), "preto": (40, 36, 40), "rosa": (240, 170, 190)}
SKIN_COAT, HAIR_COAT = "pele", "cabelo"


@dataclass(frozen=True)
class EarShape:
    """Um modelo de orelha.

    ``outline``: o contorno (afastando-se da raiz, ao longo dela), em metros, a raiz em 0.
    ``flare``: numa orelha dos lados da cabeça, quanto ela abre para fora, em graus.
    ``mount``: "side" (nos lados, na altura dos olhos) ou "top" (no alto da cabeça).
    ``tilt``: numa do alto, quanto ela se inclina para fora ao sair da cabeça (0: em pé).
    ``turn``: e quanto a frente dela vira para fora, em graus.
    ``at``: onde fica no alto da cabeça, do meio (0) à borda (1).
    ``bend``: numa caída, quantos graus ela se curva para fora e para baixo; ``span``: em que
    parte do comprimento, a partir da raiz, essa curva acontece (o resto desce reto).
    ``thick``: a espessura da placa, em metros.
    ``coat``: "skin" ou "hair", a cor dela; ``furry``: por dentro é rosada; ``scaly``: em escamas.
    ``other``: o modelo da orelha do outro lado, quando as duas diferem (uma em pé, uma caída).
    """
    outline: Tuple[Tuple[float, float], ...]
    flare: float = 30.0
    mount: str = "side"
    tilt: float = 0.0
    turn: float = 12.0
    at: float = 0.55
    bend: float = 0.0
    span: float = 0.42
    thick: float = THICKNESS
    coat: str = "skin"
    furry: bool = False
    scaly: bool = False
    other: Optional["EarShape"] = None


def _cm(*points: Tuple[float, float]) -> Tuple[Tuple[float, float], ...]:
    assert len(points) == OUTLINE
    return tuple((away / 100.0, along / 100.0) for away, along in points)


def _animal(outline, tilt: float, at: float = 0.55, turn: float = 12.0, **more) -> EarShape:
    return EarShape(outline, mount="top", tilt=tilt, turn=turn, at=at, coat="hair", furry=True, **more)


# Each outline runs from one end of the root, out along one edge to the tip and back along the
# other edge to the other end of the root, and ends at the middle of the root.
# A rabbit's: long and broad. A dog's is broader and thicker still, and not as long.
_RABBIT = _cm((0, -2.0), (2.5, -2.6), (6.0, -2.8), (10.0, -2.2), (13.0, 0.0), (10.0, 2.2), (6.0, 2.8), (2.5, 2.6), (0, 2.0), (0, 0))
_RABBIT_UP = _animal(_RABBIT, tilt=8.0, at=0.35, turn=6.0, thick=0.011)
_RABBIT_DOWN = _animal(_RABBIT, tilt=42.0, at=0.80, bend=134.0, span=0.32, thick=0.011)
_DOG = _cm((0, -2.8), (1.8, -3.0), (3.6, -2.6), (5.2, -1.7), (6.4, 0.0), (5.2, 1.7), (3.6, 2.6), (1.8, 3.0), (0, 2.8), (0, 0))
_DOG_LONG = _cm((0, -3.4), (2.2, -4.2), (5.0, -4.6), (7.6, -3.4), (9.2, 0.0), (7.6, 3.4), (5.0, 4.2), (2.2, 4.0), (0, 3.4), (0, 0))
_DOG_UP = _animal(_DOG, tilt=14.0, thick=0.015)
_DOG_DOWN = _animal(_DOG_LONG, tilt=55.0, at=0.84, bend=122.0, span=0.34, thick=0.016)
EAR_STYLES: Dict[str, EarShape] = {
    # A simple human ear, squarish, close to the head.
    "humana": EarShape(_cm((0, -1.7), (1.0, -1.9), (1.8, -1.4), (2.0, -0.5), (2.0, 0.5), (2.0, 1.4), (1.8, 1.9), (1.0, 2.0),
                           (0, 1.7), (0, 0)), 25.0),
    # Human still, rounder and a little larger.
    "redonda": EarShape(_cm((0, -1.6), (0.9, -2.1), (1.8, -1.8), (2.4, -0.9), (2.6, 0.1), (2.4, 1.1), (1.8, 1.9), (0.9, 2.2),
                            (0, 1.7), (0, 0)), 32.0),
    # An elf's, long and level, standing out to the side.
    "elfo": EarShape(_cm((0, -1.5), (1.1, -1.8), (2.6, -1.2), (4.6, -0.3), (7.2, 0.7), (4.8, 1.1), (2.8, 1.6), (1.3, 1.8),
                         (0, 1.6), (0, 0)), 58.0),
    # An elf's swept back and up, like a wing.
    "elfo_asa": EarShape(_cm((0, -1.5), (1.1, -1.7), (2.2, -0.9), (3.6, 0.9), (5.6, 5.0), (3.2, 3.3), (1.8, 2.4), (0.9, 2.0),
                             (0, 1.6), (0, 0)), 36.0),
    # A bat's: large, wide at the base, pointing up.
    "morcego": EarShape(_cm((0, -1.5), (1.4, -2.0), (3.0, -0.9), (3.9, 1.7), (3.4, 4.6), (1.8, 7.6), (1.3, 5.0), (0.7, 3.2),
                            (0, 1.7), (0, 0)), 42.0),
    # A fin, for sea folk and dragon kin: three spines joined by webbing.
    "barbatana": EarShape(_cm((0, -1.6), (1.5, -2.0), (4.4, -2.6), (2.8, -0.5), (5.8, 0.6), (3.2, 1.3), (4.8, 3.9), (1.7, 2.4),
                              (0, 1.7), (0, 0)), 50.0),
    # A cat's: a neat triangle on top of the head.
    "gato": _animal(_cm((0, -2.2), (1.2, -2.1), (2.6, -1.5), (3.9, -0.7), (5.0, 0.2), (3.8, 0.9), (2.5, 1.6), (1.2, 2.1),
                        (0, 2.2), (0, 0)), tilt=18.0),
    # A dog's: standing up, lying down the side of the head (large and shaggy), or one of each.
    "cachorro": _DOG_UP,
    "cachorro_caido": _DOG_DOWN,
    "cachorro_uma_caida": replace(_DOG_UP, other=_DOG_DOWN),
    # A wolf's: large and pointed, with a tuft at the outer edge.
    "lobo": _animal(_cm((0, -2.8), (1.4, -3.0), (3.2, -2.2), (5.4, -1.0), (7.4, 0.3), (5.2, 1.3), (3.6, 1.4), (2.2, 2.6),
                        (0, 2.8), (0, 0)), tilt=22.0),
    # A fox's: larger still and wide, leaning out.
    "raposa": _animal(_cm((0, -3.0), (1.5, -3.0), (3.5, -2.2), (6.0, -1.0), (8.2, 0.4), (5.6, 1.6), (3.2, 2.4), (1.4, 3.0),
                          (0, 3.0), (0, 0)), tilt=28.0, at=0.6),
    # A rabbit's: two long ears up, one up and one down, or both down.
    "coelho": _RABBIT_UP,
    "coelho_uma_caida": replace(_RABBIT_UP, other=_RABBIT_DOWN),
    "coelho_caidas": _RABBIT_DOWN,
    # A dragon's: a scaly frill of spines swept back and up.
    "dragao": EarShape(_cm((0, -1.6), (1.6, -2.2), (4.0, -2.4), (3.4, -0.4), (6.4, 0.6), (4.2, 1.8), (6.0, 4.6), (2.4, 3.0),
                           (0, 1.8), (0, 0)), 46.0, scaly=True),
    # A reptile's: a low scaly disc close to the head.
    "reptil": EarShape(_cm((0, -1.4), (0.8, -1.8), (1.8, -1.6), (2.6, -0.8), (2.9, 0.2), (2.6, 1.1), (1.8, 1.7), (0.8, 1.9),
                           (0, 1.5), (0, 0)), 12.0, scaly=True),
}
NONE = "sem"
STYLE_NAMES = (NONE,) + tuple(EAR_STYLES)
TONES = ("orelha_matiz", "orelha_saturacao", "orelha_brilho")  # the ear's colour moved from the one it has
ADJUSTMENTS = ("orelha_tamanho", "orelha_altura", "orelha_abertura") + TONES


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def coat_of(custom: Any) -> Optional[Tuple[float, float, float]]:
    """A cor que o personagem deu às orelhas (0 a 1), ou None para a de cada modelo: "pele",
    "cabelo", um nome de EAR_COLORS ou "#rrggbb" em ``AvatarCustomization.ear_color``."""
    value = str(getattr(custom, "ear_color", "") or "").strip().lower()
    if value == SKIN_COAT:
        return tuple(float(c) for c in custom.skin_color_rgb[:3])
    if value == HAIR_COAT:
        return tuple(c / 255.0 for c in custom.hair_rgb_255)
    rgb = EAR_COLORS.get(value)
    if rgb is None and value.startswith("#") and len(value) == 7:
        try:
            rgb = tuple(int(value[k:k + 2], 16) for k in (1, 3, 5))
        except ValueError:
            rgb = None
    return tuple(c / 255.0 for c in rgb) if rgb is not None else None


def _bent(shape: EarShape, length: float, start: float):
    """Where the middle line of a bent ear goes: for a distance from the root, (out of the head,
    up, the direction it runs in), found by walking the curve."""
    steps = np.linspace(0.0, length, 65)
    reach = np.clip(steps / max(shape.span * length, 1e-9), 0.0, 1.0)
    angle = start + np.radians(shape.bend) * reach * reach * (3.0 - 2.0 * reach)  # from the vertical, leaning out
    middle = (angle[1:] + angle[:-1]) / 2.0
    out = np.concatenate([[0.0], np.cumsum(np.sin(middle) * np.diff(steps))])
    up = np.concatenate([[0.0], np.cumsum(np.cos(middle) * np.diff(steps))])
    return lambda a: (np.interp(a, steps, out), np.interp(a, steps, up), np.interp(a, steps, angle))


def build(shape: EarShape, side: float, adjust: Optional[Mapping[str, float]] = None,
          skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25),
          coat: Optional[Sequence[float]] = None) -> np.ndarray:
    """Vértices (N, 11: posição, normal, UV, cor), três por triângulo, de uma orelha com o meio da
    raiz na origem: ``side`` +1 a do lado +x da cabeça, -1 a do outro (espelhada). ``coat``: a
    cor dela, quando não é a do modelo (a do cabelo num bicho, a da pele nos outros)."""
    grow = SCALE * (1.0 + SIZE * _amount(adjust, "orelha_tamanho"))
    opened = OPEN * _amount(adjust, "orelha_abertura")
    colour = np.asarray(coat if coat is not None else (hair if shape.coat == "hair" else skin), dtype=np.float64)[:3]
    if any(_amount(adjust, name) for name in TONES):
        from .customization import shift_colour
        colour = np.array(shift_colour(tuple(int(round(c * 255)) for c in np.clip(colour, 0.0, 1.0)),
                                       *(_amount(adjust, name) for name in TONES))) / 255.0
    inner = colour + (np.array(PINK) - colour) * PINK_SHARE if shape.furry else colour * INNER_TONE
    points = []  # the middle surface: (position, normal, colour) of each corner, three to a triangle
    edge = []    # its outline: (position, normal) of the two ends of each stretch

    if shape.bend:
        # A bent ear, cut across at STATIONS places from the root to the tip: it rises from the
        # head leaning out, bends over, and comes down beside it. Its width runs front to back.
        length = shape.outline[4][0]
        lower, upper = shape.outline[:5], (shape.outline[8], shape.outline[7], shape.outline[6], shape.outline[5], shape.outline[4])
        line = _bent(shape, length, np.radians(min(max(shape.tilt + opened, 0.0), 80.0)))
        width = np.array([0.0, 0.0, -1.0])

        def cut(a: float):
            out, up, angle = line(a)
            centre = grow * np.array([out, up, 0.0])
            normal = np.array([np.cos(angle), -np.sin(angle), 0.0])  # its inside: under it at the root, towards the head where it hangs
            low = float(np.interp(a, [p[0] for p in lower], [p[1] for p in lower]))
            high = float(np.interp(a, [p[0] for p in upper], [p[1] for p in upper]))
            return centre + grow * low * width, centre + grow * high * width, normal

        cuts = [cut(length * k / STATIONS) for k in range(STATIONS + 1)]
        for (a0, b0, n0), (a1, b1, n1) in zip(cuts, cuts[1:]):
            centre, normal = (a0 + b0 + a1 + b1) / 4.0, (n0 + n1) / 2.0
            for p, q, np_, nq in ((a0, a1, n0, n1), (a1, b1, n1, n1), (b1, b0, n1, n0), (b0, a0, n0, n0)):
                points += [(centre, normal, inner), (p, np_, colour), (q, nq, colour)]
            edge += [((a0, n0), (a1, n1)), ((b1, n1), (b0, n0))]
        edge += [((cuts[0][1], cuts[0][2]), (cuts[0][0], cuts[0][2]))]  # the root
    else:
        if shape.mount == "top":
            tilt, turn = np.radians(min(max(shape.tilt + opened, 0.0), 175.0)), np.radians(shape.turn)
            away = np.array([np.sin(tilt), np.cos(tilt), 0.0])           # from the root: up, leaning out of the head
            along = np.array([-np.cos(turn), 0.0, np.sin(turn)])         # along the root, across the head
        else:
            flare = np.radians(min(max(shape.flare + opened, 5.0), 88.0))
            away = np.array([np.sin(flare), 0.0, -np.cos(flare)])        # from the root: back, opening out of the head
            along = np.array([0.0, 1.0, 0.0])                            # along the root, up the head
        along = along - (along @ away) * away                             # square to it: the outline is not skewed
        along /= np.linalg.norm(along)
        out = np.cross(away, along)                                       # the face of the plate that is its front
        plate = lambda a, b: grow * (a * away + b * along)
        outline = [plate(a, b) for a, b in shape.outline]
        # The hollow: by the root in a person's ear; the middle of a furry one, where it is pink.
        hollow = 0.55 * np.mean(outline, axis=0) if shape.furry else plate(*INNER)
        for k in range(OUTLINE):
            a, b = outline[k], outline[(k + 1) % OUTLINE]
            tone = SCALE_TONES[k % 2] if shape.scaly else 1.0
            points += [(hollow, out, colour * tone * INNER_TONE if shape.scaly else inner), (a, out, colour * tone), (b, out, colour * tone)]
            edge.append(((a, out), (b, out)))
    nowhere = (np.zeros(3), np.array([0.0, 0.0, 1.0]), colour)
    points += [nowhere] * (3 * FRONT - len(points))            # every model has the same triangles
    edge += [(nowhere[:2], nowhere[:2])] * (RIM - len(edge))

    half = shape.thick / 2.0
    middle = np.mean([p for p, _, _ in points], axis=0)
    triangles = []  # (three positions, three colours, the way it faces)
    for k in range(0, len(points), 3):
        trio = points[k:k + 3]
        facing = np.mean([n for _, n, _ in trio], axis=0)
        triangles.append(([p + n * half for p, n, _ in trio], [c for _, _, c in trio], facing))                 # the front
        triangles.append(([p - n * half for p, n, _ in trio][::-1], [colour * BACK_TONE] * 3, -facing))         # the back
    for (p, n), (q, m) in edge:                                                                                  # the rim
        outward = (p + q) / 2.0 - middle
        for corners in ((p + n * half, p - n * half, q - m * half), (p + n * half, q - m * half, q + m * half)):
            triangles.append((list(corners), [colour * BACK_TONE] * 3, outward))
    rows = np.zeros((len(triangles) * 3, 11))
    for k, (corners, colours, facing) in enumerate(triangles):
        p = np.array(corners)
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        length = np.linalg.norm(normal)
        if length > 1e-12:
            normal = normal / length
            if normal @ facing < 0:
                normal = -normal
        else:  # an empty triangle, or one of no area
            normal = facing / max(np.linalg.norm(facing), 1e-12)
        rows[3 * k:3 * k + 3, :3] = p
        rows[3 * k:3 * k + 3, 3:6] = normal
        rows[3 * k:3 * k + 3, 8:11] = np.array(colours)
    if side < 0:  # the other ear: mirrored across the head
        rows[:, 0] *= -1.0
        rows[:, 3] *= -1.0
    return rows


def styled_rows(head_rows: np.ndarray, style: str, adjust: Optional[Mapping[str, float]] = None,
                skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25),
                coat: Optional[Sequence[float]] = None):
    """(vertex rows, triangles) of the two ears of a style on a head, or None for no ears (an
    unknown style is none too). A person's ears sit on the sides of the head at the height of the
    eyes; an animal's on top of it."""
    shape = EAR_STYLES.get(style)
    if shape is None:
        return None
    head = np.asarray(head_rows, dtype=np.float64).reshape(-1, 11)[:, :3]
    lift = LIFT * _amount(adjust, "orelha_altura")
    height = head[:, 1].min() + EAR_HEIGHT + lift
    beside = head[np.abs(head[:, 1] - height) < 0.05]
    beside = beside if len(beside) else head
    middle = (head[:, 2].min() + head[:, 2].max()) / 2.0
    rows = []
    for side in (1.0, -1.0):
        one = shape.other if side < 0 and shape.other is not None else shape
        ear = build(one, side, adjust, skin, hair, coat)
        if one.mount == "top":
            ear[:, :3] += np.array([side * one.at * np.abs(head[:, 0]).max(), head[:, 1].max() - EMBED + lift, middle])
        else:
            ear[:, :3] += np.array([side * ((beside[:, 0] * side).max() - EMBED), height, middle + EAR_FORWARD])
        rows.append(ear)
    rows = np.concatenate(rows).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)


def rows_for(head_rows: np.ndarray, custom: Any, adjust: Optional[Mapping[str, float]] = None):
    """As orelhas de um personagem (``AvatarCustomization``) numa cabeça: o modelo, os ajustes e
    as cores dele. None sem orelhas."""
    if adjust is None:
        adjust = getattr(custom, "resolved_body_adjust", None)
    return styled_rows(head_rows, getattr(custom, "ear_style", NONE), adjust, getattr(custom, "skin_color_rgb", (1.0, 1.0, 1.0)),
                       tuple(c / 255.0 for c in getattr(custom, "hair_rgb_255", (102, 77, 64))), coat_of(custom))
