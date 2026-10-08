"""As orelhas 3D do personagem: placas finas recortadas num contorno, uma de cada lado da cabeça.

Cada modelo é um contorno de OUTLINE pontos no plano da orelha (para trás, para cima), preso à
cabeça pela borda da frente e aberto para fora por um ângulo (``flare``): deitado na cabeça numa
orelha humana, bem aberto numa de elfo. Todos os modelos têm os mesmos triângulos, na mesma
ordem, então trocar de modelo ou mexer num ajuste só move os vértices.
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
INNER = (0.006, 0.0)  # the point of the plate (back, up) the front is fanned from: the hollow of the ear
SCALE = 1.45          # the outlines are drawn at a person's size; the character's head is large for its body
INNER_TONE, BACK_TONE = 0.80, 0.93  # the skin's colour at that hollow and on the back of the ear
# What the adjustments do at 1: size as a share, metres up the head, degrees more open.
SIZE, LIFT, OPEN = 0.5, 0.03, 30.0


@dataclass(frozen=True)
class EarShape:
    """Um modelo de orelha: o contorno (para trás, para cima; em metres, a raiz em back = 0) e o
    quanto ela abre para fora da cabeça, em graus."""
    outline: Tuple[Tuple[float, float], ...]
    flare: float


def _cm(*points: Tuple[float, float]) -> Tuple[Tuple[float, float], ...]:
    assert len(points) == OUTLINE
    return tuple((back / 100.0, up / 100.0) for back, up in points)


# Each outline runs from the foot of the root, out along the lower edge to the tip and back along
# the upper edge to the top of the root, and ends at the middle of the root.
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
          skin: Sequence[float] = (1.0, 1.0, 1.0)) -> np.ndarray:
    """Vértices (N, 11: posição, normal, UV, cor), três por triângulo, de uma orelha com o meio da
    raiz na origem: ``side`` +1 a do lado +x da cabeça, -1 a do outro (espelhada)."""
    grow = SCALE * (1.0 + SIZE * _amount(adjust, "orelha_tamanho"))
    flare = np.radians(min(max(shape.flare + OPEN * _amount(adjust, "orelha_abertura"), 5.0), 88.0))
    back = np.array([np.sin(flare), 0.0, -np.cos(flare)])   # along the plate, away from its root
    up = np.array([0.0, 1.0, 0.0])
    out = np.cross(back, up)                                 # the side of the plate that faces forwards
    plate = lambda b, u: grow * (b * back + u * up)
    outline = [plate(b, u) for b, u in shape.outline]
    hollow = plate(*INNER)
    half = out * THICKNESS / 2.0
    skin = np.asarray(skin, dtype=np.float64)[:3]
    triangles = []  # (three corners, colour of each)
    for k in range(OUTLINE):
        a, b = outline[k], outline[(k + 1) % OUTLINE]
        triangles.append(((hollow + half, a + half, b + half), (skin * INNER_TONE, skin, skin)))            # the front
        triangles.append(((hollow - half, b - half, a - half), (skin * BACK_TONE,) * 3))                    # the back
        triangles.append(((a + half, a - half, b - half), (skin * BACK_TONE,) * 3))                         # the rim
        triangles.append(((a + half, b - half, b + half), (skin * BACK_TONE,) * 3))
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
                skin: Sequence[float] = (1.0, 1.0, 1.0)):
    """(vertex rows, triangles) of the two ears of a style on a head, or None for no ears (an
    unknown style is none too). The ears sit on the sides of the head at the height of the eyes."""
    shape = EAR_STYLES.get(style)
    if shape is None:
        return None
    head = np.asarray(head_rows, dtype=np.float64).reshape(-1, 11)[:, :3]
    height = head[:, 1].min() + EAR_HEIGHT + LIFT * _amount(adjust, "orelha_altura")
    beside = head[np.abs(head[:, 1] - height) < 0.05]
    beside = beside if len(beside) else head
    depth = (head[:, 2].min() + head[:, 2].max()) / 2.0 + EAR_FORWARD
    rows = []
    for side in (1.0, -1.0):
        ear = build(shape, side, adjust, skin)
        reach = (beside[:, 0] * side).max() - EMBED
        ear[:, :3] += np.array([side * reach, height, depth])
        rows.append(ear)
    rows = np.concatenate(rows).astype(np.float32)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)
