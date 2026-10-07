"""Ajustes de proporção do corpo: altura, cabeça, ombros, peito, quadril, bunda, braços, pernas, mãos e pés.

Cada ajuste é um número de -1 a 1 (0 = o corpo como foi modelado), guardado em
``AvatarCustomization.body_adjust``. Nenhum deles mexe só no corpo ou só na roupa (o que
desfaria o encaixe pela cage): todos agem do mesmo jeito sobre pele, roupa e cabelo.

- A maioria é uma **escala por osso**, aplicada com o esqueleto (``Skeleton.pose``): tudo o que
  o osso carrega cresce junto, e os ossos filhos acompanham sem crescer.
- Peito e bunda não têm osso: são uma **deformação do espaço** na pose de vestir (``warp``),
  uma função da posição, igual para a pele e para o tecido que está por cima dela.

Os ajustes do rosto (olhos, sobrancelhas) ficam no mesmo dicionário, mas agem na textura da
cabeça (``customization.LayeredHeadCompositor``).
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional

import numpy as np

# name -> label, in the order the editor shows them.
BODY = {"altura": "Altura", "cabeca": "Cabeça", "ombros": "Ombros", "peito": "Peito", "quadril": "Quadril",
        "bunda": "Bunda", "bracos": "Braços", "maos": "Mãos", "pernas": "Pernas", "pes": "Pés"}
FACE = {"olhos_tamanho": "Tamanho dos olhos", "olhos_altura": "Altura dos olhos",
        "olhos_distancia": "Distância entre os olhos", "sobrancelha_altura": "Altura das sobrancelhas"}
ADJUSTMENTS = {**BODY, **FACE}

# How much each adjustment changes at 1 (and the opposite at -1).
HEIGHT = 0.15          # of the whole character
HEAD = 0.25
SHOULDERS = 0.20       # width of the torso
HIPS = (0.20, 0.10)    # width and depth of the pelvis
ARMS = 0.35            # thickness, across the bone
LEGS = 0.30
HANDS = 0.30
FEET = 0.30            # length and width (not height: the foot stays on the ground)
BULGE = 0.05           # metres the chest or the buttocks come out
# Where the chest and the buttocks are: (how far up the torso, half the distance between the two
# sides, how wide the bulge is), in metres.
CHEST = (0.62, 0.075, 0.095)
BUTTOCKS = (0.03, 0.075, 0.11)
DEPTH_FADE = 0.05  # metres past the body's middle plane over which a bulge takes hold


def amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    """O ajuste ``name``, de -1 a 1 (0 se não foi mexido)."""
    try:
        return float(np.clip(float((adjust or {}).get(name, 0.0)), -1.0, 1.0))
    except (TypeError, ValueError):
        return 0.0


def height(adjust: Optional[Mapping[str, float]]) -> float:
    """Fator de escala do personagem inteiro."""
    return 1.0 + HEIGHT * amount(adjust, "altura")


def _across(axis: np.ndarray, factor: float) -> np.ndarray:
    """Scale by ``factor`` across an axis, leaving its length."""
    a = axis / np.linalg.norm(axis)
    return np.eye(3) + (factor - 1.0) * (np.eye(3) - np.outer(a, a))


def bone_scales(skeleton, adjust: Optional[Mapping[str, float]]) -> Dict[int, np.ndarray]:
    """Escala 3x3 (nos eixos da malha) de cada osso que algum ajuste muda."""
    scales: Dict[int, np.ndarray] = {}

    def put(name: str, matrix: np.ndarray) -> None:
        if not np.allclose(matrix, np.eye(3)):
            scales[skeleton.index(name)] = matrix

    put("Head", np.eye(3) * (1.0 + HEAD * amount(adjust, "cabeca")))
    put("Torso", np.diag([1.0 + SHOULDERS * amount(adjust, "ombros"), 1.0, 1.0]))
    hips = amount(adjust, "quadril")
    put("Pelvis", np.diag([1.0 + HIPS[0] * hips, 1.0, 1.0 + HIPS[1] * hips]))
    feet = 1.0 + FEET * amount(adjust, "pes")
    for side in "LR":
        for bone, name, most in (("UpperArm", "bracos", ARMS), ("LowerArm", "bracos", ARMS),
                                 ("UpperLeg", "pernas", LEGS), ("LowerLeg", "pernas", LEGS)):
            index = skeleton.index(f"{bone}_{side}")
            put(f"{bone}_{side}", _across(skeleton.tails[index] - skeleton.heads[index], 1.0 + most * amount(adjust, name)))
        put(f"Hand_{side}", np.eye(3) * (1.0 + HANDS * amount(adjust, "maos")))
        put(f"Foot_{side}", np.diag([feet, 1.0, feet]))
    return scales


def warps(adjust: Optional[Mapping[str, float]]) -> bool:
    """Se algum ajuste deforma a pose de vestir (peito, bunda)."""
    return bool(amount(adjust, "peito") or amount(adjust, "bunda"))


def warp(points: np.ndarray, skeleton, adjust: Optional[Mapping[str, float]], surface: np.ndarray) -> np.ndarray:
    """``points`` (N, 3) com o peito e a bunda ajustados.

    Cada lado é um volume suave: o que está diante do peito vai para a frente (o que está atrás
    do quadril, para trás), menos quanto mais longe do centro do volume, e nada do outro lado
    do corpo se mexe. ``surface`` (pontos da cage) fica para ajustes que precisem da superfície.
    """
    out = np.asarray(points, dtype=np.float64).copy()
    torso, pelvis = skeleton.index("Torso"), skeleton.index("Pelvis")
    low, high = sorted((skeleton.heads[torso][1], skeleton.tails[torso][1]))
    places = (("peito", low + CHEST[0] * (high - low), CHEST[1], CHEST[2], 1.0),
              ("bunda", skeleton.heads[pelvis][1] + BUTTOCKS[0], BUTTOCKS[1], BUTTOCKS[2], -1.0))
    middle = skeleton.heads[torso]
    for name, y, half, radius, towards in places:
        much = amount(adjust, name)
        if not much:
            continue
        for side in (-1.0, 1.0):
            x = middle[0] + side * half
            # The distance is measured across the bulge only, so the skin and the cloth lying
            # over the same spot move exactly alike and the cloth never ends up under the skin.
            # What is on the other side of the body (past its middle plane) stays.
            distance = np.hypot(points[:, 0] - x, points[:, 1] - y)
            this_side = np.clip(towards * (points[:, 2] - middle[2]) / DEPTH_FADE, 0.0, 1.0)
            out[:, 2] += towards * much * BULGE * np.exp(-(distance / radius) ** 2) * this_side * this_side * (3 - 2 * this_side)
    return out
