"""As orelhas 3D do personagem: placas finas recortadas num contorno, uma de cada lado da cabeça.

Cada modelo é um contorno de OUTLINE pontos no plano da orelha (afastando-se da raiz, ao longo
dela). As de gente ficam nos lados da cabeça, presas pela borda da frente e abertas para fora por
um ângulo (``flare``): deitadas na cabeça numa orelha humana, bem abertas numa de elfo. As de
bicho ficam no alto da cabeça (``mount="top"``), em pé ou caídas para o lado (``tilt``), na cor
do cabelo. Todos os modelos têm os mesmos triângulos, na mesma ordem, então trocar de modelo ou
mexer num ajuste só move os vértices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

OUTLINE = 10          # points of every outline: the same triangles for every model
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


@dataclass(frozen=True)
class EarShape:
    """Um modelo de orelha.

    ``outline``: o contorno (afastando-se da raiz, ao longo dela), em metros, a raiz em 0.
    ``flare``: numa orelha dos lados da cabeça, quanto ela abre para fora, em graus.
    ``mount``: "side" (nos lados, na altura dos olhos) ou "top" (no alto da cabeça).
    ``tilt``: numa do alto, quanto ela se inclina para fora (0 em pé, mais de 90 caída para o lado).
    ``turn``: e quanto a frente dela vira para fora, em graus.
    ``at``: onde fica no alto da cabeça, do meio (0) à borda (1).
    ``coat``: "skin" ou "hair", a cor dela; ``furry``: por dentro é rosada; ``scaly``: em escamas.
    ``other``: o modelo da orelha do outro lado, quando as duas diferem (uma em pé, uma caída).
    """
    outline: Tuple[Tuple[float, float], ...]
    flare: float = 30.0
    mount: str = "side"
    tilt: float = 0.0
    turn: float = 12.0
    at: float = 0.55
    coat: str = "skin"
    furry: bool = False
    scaly: bool = False
    other: Optional["EarShape"] = None


def _cm(*points: Tuple[float, float]) -> Tuple[Tuple[float, float], ...]:
    assert len(points) == OUTLINE
    return tuple((away / 100.0, along / 100.0) for away, along in points)


def _animal(outline, tilt: float, at: float = 0.55, turn: float = 12.0, other: Optional[EarShape] = None) -> EarShape:
    return EarShape(outline, mount="top", tilt=tilt, turn=turn, at=at, coat="hair", furry=True, other=other)


# Each outline runs from one end of the root, out along one edge to the tip and back along the
# other edge to the other end of the root, and ends at the middle of the root.
_RABBIT = _cm((0, -1.6), (2.5, -2.0), (6.0, -2.1), (10.0, -1.6), (13.0, 0.0), (10.0, 1.6), (6.0, 2.1), (2.5, 2.0), (0, 1.6), (0, 0))
_RABBIT_UP = _animal(_RABBIT, tilt=8.0, at=0.35, turn=6.0)
_RABBIT_DOWN = _animal(_RABBIT, tilt=160.0, at=0.9, turn=90.0)  # hanging flat against the side of the head
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
    # A dog's standing up: taller, with a rounded tip.
    "cachorro": _animal(_cm((0, -2.0), (1.6, -2.1), (3.4, -1.8), (5.0, -1.2), (6.3, 0.0), (5.0, 1.2), (3.4, 1.8), (1.6, 2.1),
                            (0, 2.0), (0, 0)), tilt=14.0),
    # A dog's large shaggy ear, lying down the side of the head.
    "cachorro_caido": _animal(_cm((0, -2.6), (2.5, -3.5), (6.0, -3.8), (9.0, -2.6), (10.5, 0.0), (9.0, 2.6), (6.0, 3.2),
                                  (2.5, 3.0), (0, 2.6), (0, 0)), tilt=162.0, at=0.92, turn=90.0),
    # A wolf's: large and pointed, with a tuft at the outer edge.
    "lobo": _animal(_cm((0, -2.8), (1.4, -3.0), (3.2, -2.2), (5.4, -1.0), (7.4, 0.3), (5.2, 1.3), (3.6, 1.4), (2.2, 2.6),
                        (0, 2.8), (0, 0)), tilt=22.0),
    # A fox's: larger still and wide, leaning out.
    "raposa": _animal(_cm((0, -3.0), (1.5, -3.0), (3.5, -2.2), (6.0, -1.0), (8.2, 0.4), (5.6, 1.6), (3.2, 2.4), (1.4, 3.0),
                          (0, 3.0), (0, 0)), tilt=28.0, at=0.6),
    # A rabbit's: two long ears up, one up and one down, or both down.
    "coelho": _RABBIT_UP,
    "coelho_uma_caida": EarShape(**{**_RABBIT_UP.__dict__, "other": _RABBIT_DOWN}),
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
ADJUSTMENTS = ("orelha_tamanho", "orelha_altura", "orelha_abertura")


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def build(shape: EarShape, side: float, adjust: Optional[Mapping[str, float]] = None,
          skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25)) -> np.ndarray:
    """Vértices (N, 11: posição, normal, UV, cor), três por triângulo, de uma orelha com o meio da
    raiz na origem: ``side`` +1 a do lado +x da cabeça, -1 a do outro (espelhada)."""
    grow = SCALE * (1.0 + SIZE * _amount(adjust, "orelha_tamanho"))
    opened = OPEN * _amount(adjust, "orelha_abertura")
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
    half = out * THICKNESS / 2.0
    coat = np.asarray(hair if shape.coat == "hair" else skin, dtype=np.float64)[:3]
    inner = coat + (np.array(PINK) - coat) * PINK_SHARE if shape.furry else coat * INNER_TONE
    triangles = []  # (three corners, colour of each)
    for k in range(OUTLINE):
        a, b = outline[k], outline[(k + 1) % OUTLINE]
        tone = SCALE_TONES[k % 2] if shape.scaly else 1.0
        triangles.append(((hollow + half, a + half, b + half), (inner if not shape.scaly else coat * tone * INNER_TONE,
                                                                coat * tone, coat * tone)))               # the front
        triangles.append(((hollow - half, b - half, a - half), (coat * BACK_TONE * tone,) * 3))             # the back
        triangles.append(((a + half, a - half, b - half), (coat * BACK_TONE,) * 3))                         # the rim
        triangles.append(((a + half, b - half, b + half), (coat * BACK_TONE,) * 3))
    rows = np.zeros((len(triangles) * 3, 11))
    middle = np.mean(outline, axis=0)
    for k, (corners, colours) in enumerate(triangles):
        p = np.array(corners)
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        length = np.linalg.norm(normal)
        normal = normal / length if length > 1e-12 else out
        if k % 4 >= 2 and normal @ (p.mean(0) - middle) < 0:  # the rim faces out of the plate
            normal = -normal
        elif k % 4 == 0:
            normal = out
        elif k % 4 == 1:
            normal = -out
        rows[3 * k:3 * k + 3, :3] = p
        rows[3 * k:3 * k + 3, 3:6] = normal
        rows[3 * k:3 * k + 3, 8:11] = np.array(colours)
    if side < 0:  # the other ear: mirrored across the head
        rows[:, 0] *= -1.0
        rows[:, 3] *= -1.0
    return rows


def styled_rows(head_rows: np.ndarray, style: str, adjust: Optional[Mapping[str, float]] = None,
                skin: Sequence[float] = (1.0, 1.0, 1.0), hair: Sequence[float] = (0.4, 0.3, 0.25)):
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
        ear = build(one, side, adjust, skin, hair)
        if one.mount == "top":
            ear[:, :3] += np.array([side * one.at * np.abs(head[:, 0]).max(), head[:, 1].max() - EMBED + lift, middle])
        else:
            ear[:, :3] += np.array([side * ((beside[:, 0] * side).max() - EMBED), height, middle + EAR_FORWARD])
        rows.append(ear)
    rows = np.concatenate(rows).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)
