"""Ajustes de proporção do corpo: altura, cabeça, pescoço, tronco, braços, pernas, mãos, pés e a folga das roupas.

Cada ajuste é um número de -1 a 1 (0 = o corpo como foi modelado), guardado em
``AvatarCustomization.body_adjust``. Nenhum deles mexe só no corpo (o que desfaria o encaixe
pela cage): os de corpo agem do mesmo jeito sobre pele, roupa e cabelo.

- A maioria é uma **escala por osso**, aplicada com o esqueleto (``Skeleton.pose``): tudo o que
  o osso carrega muda junto, e os ossos filhos acompanham sem mudar. Com as pernas mais longas
  o corpo sobe (``ground_lift``), para os pés continuarem no chão.
- Peito, bunda e cintura não têm osso: são uma **deformação do espaço** na pose de vestir
  (``warp``), uma função da posição, igual para a pele e para o tecido que está por cima dela.
- A **folga** é a única que age só nas roupas: afasta o tecido ao longo da própria superfície
  (``clearance``), sem mudar onde ele foi encaixado.

Os ajustes do rosto (olhos, sobrancelhas) ficam no mesmo dicionário, mas agem na textura da
cabeça (``customization.LayeredHeadCompositor``).
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np

# The adjustments of the body by group, as the editor shows them: (name, label).
BODY_GROUPS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("Geral", [("altura", "Altura"), ("cabeca", "Cabeça"), ("pescoco", "Pescoço")]),
    ("Tronco", [("ombros", "Ombros"), ("peito", "Peito"), ("cintura", "Cintura"), ("pelve", "Pelve"),
                ("quadril", "Quadril"), ("bunda", "Bunda")]),
    ("Braços e mãos", [("bracos_comprimento", "Comprimento dos braços"), ("bracos", "Grossura dos braços"),
                       ("maos", "Mãos")]),
    ("Pernas e pés", [("pernas_comprimento", "Comprimento das pernas"), ("pernas", "Grossura das pernas"),
                      ("pes", "Pés")]),
    ("Roupas", [("folga", "Folga das roupas")]),
]
BODY = {name: label for _, group in BODY_GROUPS for name, label in group}
EYES = {"olhos_tamanho": "Tamanho dos olhos", "olhos_altura": "Altura dos olhos",
        "olhos_distancia": "Distância entre os olhos"}
# The eyebrows have their own: they do not follow the eyes.
BROWS = {"sobrancelha_tamanho": "Tamanho das sobrancelhas", "sobrancelha_altura": "Altura das sobrancelhas",
         "sobrancelha_distancia": "Distância entre as sobrancelhas"}
FACE = {**EYES, **BROWS}
NOSE = {"nariz_tamanho": "Tamanho do nariz", "nariz_altura": "Posição do nariz (altura)",
        "nariz_projecao": "Projeção do nariz", "nariz_largura": "Largura do nariz inteiro",
        "nariz_ponte_largura": "Largura da ponte", "nariz_ponte_altura": "Altura da ponte",
        "nariz_ponta_largura": "Largura da ponta", "nariz_ponta_projecao": "Projeção da ponta",
        "nariz_base_largura": "Largura da base",
        "nariz_base_altura": "Altura da base", "nariz_narinas_altura": "Posição das narinas (altura)",
        "nariz_ponta_cor": "Cor da ponta (rosada)",
        "nariz_sombra": "Sombra do nariz"}
# Drawn by the shader over the skin (CharacterModel.draw): 0 to 1 of the skin, and which pattern.
SKIN = {"vitiligo": "Vitiligo (quantidade)", "vitiligo_forma": "Vitiligo (desenho das manchas)"}
# The shading of the chin and the jaw: the facets under and beside the face are lit apart from it
# and take a darker tone of the head's texture. Down to none of it (a flat face), up to stronger.
SHADING = {"rosto_sombra": "Sombras do queixo e do maxilar"}
# The edges of the clothes, moved up or down the body: the cloth near the edge stretches or
# gathers, and the skin under it is hidden or shown to match (CharacterModel._apply_hsr_skin).
GARMENTS = {"blusa_barra": "Barra da blusa (altura)", "calca_cintura": "Cintura da calça (altura)",
            "calca_barra": "Barra da calça (altura)"}
# The part of the model each one moves, which of its edges (0 the lowest, 1 the highest) and
# whether that is its lower edge.
GARMENT_EDGES = {"blusa_barra": ("top", 0, True), "calca_cintura": ("bottom", 1, False), "calca_barra": ("bottom", 0, True)}
GARMENT_REACH = 0.08   # metres an edge moves at 1
EDGE_FALLOFF = 0.20    # metres of cloth from the edge that stretch with it
ADJUSTMENTS = {**BODY, **FACE, **NOSE, **SKIN, **SHADING, **GARMENTS}
# What an adjustment is on a body when it was never set: the female face has no shading under it.
DEFAULTS = {"female": {"rosto_sombra": -1.0}}


def resolved(adjust: Optional[Mapping[str, float]], body: str) -> Dict[str, float]:
    """Os ajustes como valem num corpo: os que foram dados e, para os outros, o padrão desse corpo."""
    return {**DEFAULTS.get(str(body).lower(), {}), **(adjust or {})}
# The adjustments drawn on the head's texture (the nose's shadow follows its size and place).
REDRAWS_FACE = set(FACE) | set(SHADING) | {"nariz_tamanho", "nariz_largura", "nariz_altura", "nariz_sombra"}
# With the shadow computed from the nose (customization.nose_shadow), every adjustment of the nose redraws it.
REDRAWS_SHADOW = set(NOSE)

# How much each adjustment changes at 1 (and the opposite at -1).
HEIGHT = 0.15          # of the whole character
HEAD = 0.25
NECK = 0.45            # length
SHOULDERS = 0.20       # width of the torso
HIPS = 0.20            # width of the pelvis
PELVIS = 0.15          # size of the pelvis, sideways and front to back
ARMS = 0.35            # thickness, across the bone
LEGS = 0.30
ARM_LENGTH = 0.15
LEG_LENGTH = 0.15
HANDS = 0.30
FEET = 0.30            # length and width (not height: the foot stays on the ground)
BULGE = 0.05           # metres the chest or the buttocks come out
WAIST = 0.22           # share the waist narrows or widens by
NOSE_SIZE, NOSE_WIDTH, NOSE_DEPTH = 0.5, 0.6, 0.8  # of the nose as a whole, sideways, and out of the face
NOSE_LIFT = 0.015      # metres up or down the face
CLEARANCE = (0.003, 0.02)  # metres the clothes can come closer to the body, and move off it
# Where the chest and the buttocks are: (how far up the torso, or metres above the hip joints;
# half the distance between the two sides; how wide the bulge is), in metres.
CHEST = (0.62, 0.075, 0.095)
BUTTOCKS = (0.03, 0.075, 0.11)
DEPTH_FADE = 0.05      # metres past the body's middle plane over which a bulge takes hold
# The waist: how far up the torso, how tall the band is, and the distances from the body's axis
# within which everything follows it and past which nothing does (the hands hang beside it).
WAIST_BAND = (0.18, 0.09)
WAIST_REACH = (0.24, 0.36)


def amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    """O ajuste ``name``, de -1 a 1 (0 se não foi mexido)."""
    try:
        return float(np.clip(float((adjust or {}).get(name, 0.0)), -1.0, 1.0))
    except (TypeError, ValueError):
        return 0.0


def height(adjust: Optional[Mapping[str, float]]) -> float:
    """Fator de escala do personagem inteiro."""
    return 1.0 + HEIGHT * amount(adjust, "altura")


def clearance(adjust: Optional[Mapping[str, float]]) -> float:
    """Metros que as roupas se afastam do corpo (negativo: aproximam, e bem menos: uma roupa justa
    fica a poucos milímetros da pele, e mais perto que isso a pele a atravessa)."""
    much = amount(adjust, "folga")
    return much * (CLEARANCE[1] if much > 0 else CLEARANCE[0])


def _across(axis: np.ndarray, factor: float) -> np.ndarray:
    """Scale by ``factor`` across an axis, leaving its length."""
    a = axis / np.linalg.norm(axis)
    return np.eye(3) + (factor - 1.0) * (np.eye(3) - np.outer(a, a))


def _along(axis: np.ndarray, factor: float) -> np.ndarray:
    """Scale by ``factor`` along an axis, leaving its thickness."""
    a = axis / np.linalg.norm(axis)
    return np.eye(3) + (factor - 1.0) * np.outer(a, a)


def bone_scales(skeleton, adjust: Optional[Mapping[str, float]]) -> Dict[int, np.ndarray]:
    """Escala 3x3 (nos eixos da malha) de cada osso que algum ajuste muda."""
    scales: Dict[int, np.ndarray] = {}

    def put(name: str, matrix: np.ndarray) -> None:
        if not np.allclose(matrix, np.eye(3)):
            scales[skeleton.index(name)] = matrix

    def axis(name: str) -> np.ndarray:
        index = skeleton.index(name)
        return skeleton.tails[index] - skeleton.heads[index]

    put("Head", np.eye(3) * (1.0 + HEAD * amount(adjust, "cabeca")))
    put("Neck", _along(axis("Neck"), 1.0 + NECK * amount(adjust, "pescoco")))
    put("Torso", np.diag([1.0 + SHOULDERS * amount(adjust, "ombros"), 1.0, 1.0]))
    pelvis = 1.0 + PELVIS * amount(adjust, "pelve")
    put("Pelvis", np.diag([pelvis * (1.0 + HIPS * amount(adjust, "quadril")), 1.0, pelvis]))
    feet = 1.0 + FEET * amount(adjust, "pes")
    for side in "LR":
        for bone, thick, most, long, longest in (("UpperArm", "bracos", ARMS, "bracos_comprimento", ARM_LENGTH),
                                                 ("LowerArm", "bracos", ARMS, "bracos_comprimento", ARM_LENGTH),
                                                 ("UpperLeg", "pernas", LEGS, "pernas_comprimento", LEG_LENGTH),
                                                 ("LowerLeg", "pernas", LEGS, "pernas_comprimento", LEG_LENGTH)):
            name = f"{bone}_{side}"
            put(name, _across(axis(name), 1.0 + most * amount(adjust, thick))
                @ _along(axis(name), 1.0 + longest * amount(adjust, long)))
        put(f"Hand_{side}", np.eye(3) * (1.0 + HANDS * amount(adjust, "maos")))
        put(f"Foot_{side}", np.diag([feet, 1.0, feet]))
    return scales


def ground_lift(skeleton, scales: Mapping[int, np.ndarray]) -> float:
    """Metros que o corpo sobe para os pés continuarem no chão quando as pernas mudam de comprimento."""
    lifts = []
    for side in "LR":
        upper, lower, foot = (skeleton.index(f"{bone}_{side}") for bone in ("UpperLeg", "LowerLeg", "Foot"))
        dropped = 0.0
        for bone, child in ((upper, lower), (lower, foot)):
            if bone in scales:
                offset = skeleton.heads[child] - skeleton.heads[bone]
                dropped += float((scales[bone] @ offset - offset)[1])
        lifts.append(-dropped)
    return float(np.mean(lifts))


def warps(adjust: Optional[Mapping[str, float]]) -> bool:
    """Se algum ajuste deforma a pose de vestir (peito, bunda, cintura)."""
    return bool(amount(adjust, "peito") or amount(adjust, "bunda") or amount(adjust, "cintura"))


def warp(points: np.ndarray, skeleton, adjust: Optional[Mapping[str, float]], surface: Optional[np.ndarray] = None) -> np.ndarray:
    """``points`` (N, 3) com o peito, a bunda e a cintura ajustados.

    Peito e bunda: cada lado é um volume suave; o que está diante do peito vai para a frente (o
    que está atrás do quadril, para trás), menos quanto mais longe do centro do volume, e nada
    do outro lado do corpo se mexe. Cintura: uma faixa em volta do eixo do corpo encolhe ou
    alarga, e o que está longe do tronco (as mãos ao lado) fica onde está. ``surface`` (pontos
    da cage) fica para ajustes que precisem da superfície.
    """
    points = np.asarray(points, dtype=np.float64)
    out = points.copy()
    torso, pelvis = skeleton.index("Torso"), skeleton.index("Pelvis")
    low, high = sorted((skeleton.heads[torso][1], skeleton.tails[torso][1]))
    middle = skeleton.heads[torso]

    waist = amount(adjust, "cintura")
    if waist:
        band = np.exp(-((points[:, 1] - (low + WAIST_BAND[0] * (high - low))) / WAIST_BAND[1]) ** 2)
        offset = points[:, [0, 2]] - middle[[0, 2]]
        t = np.clip((WAIST_REACH[1] - np.linalg.norm(offset, axis=1)) / (WAIST_REACH[1] - WAIST_REACH[0]), 0.0, 1.0)
        factor = 1.0 + WAIST * waist * band * t * t * (3 - 2 * t)
        out[:, [0, 2]] = middle[[0, 2]] + offset * factor[:, None]

    places = (("peito", low + CHEST[0] * (high - low), CHEST[1], CHEST[2], 1.0),
              ("bunda", skeleton.heads[pelvis][1] + BUTTOCKS[0], BUTTOCKS[1], BUTTOCKS[2], -1.0))
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


def nose_adjusted(adjust: Optional[Mapping[str, float]]) -> bool:
    return any(amount(adjust, name) for name in ("nariz_tamanho", "nariz_largura", "nariz_projecao", "nariz_altura"))


def nose_shape(points: np.ndarray, adjust: Optional[Mapping[str, float]]) -> np.ndarray:
    """Os vértices do nariz com tamanho, largura, projeção e altura ajustados, em torno do ponto
    onde ele se apoia no rosto (o nariz cresce para fora e não afunda na cabeça)."""
    points = np.asarray(points, dtype=np.float64)
    low, high = points.min(0), points.max(0)
    anchor = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    size = 1.0 + NOSE_SIZE * amount(adjust, "nariz_tamanho")
    scale = size * np.array([1.0 + NOSE_WIDTH * amount(adjust, "nariz_largura"), 1.0,
                             1.0 + NOSE_DEPTH * amount(adjust, "nariz_projecao")])
    return anchor + (points - anchor) * scale + np.array([0.0, NOSE_LIFT * amount(adjust, "nariz_altura"), 0.0])


def garment_shift(adjust: Optional[Mapping[str, float]], name: str) -> float:
    """Metres an edge of a garment is moved up (negative: down)."""
    return GARMENT_REACH * amount(adjust, name)


def move_edge(points: np.ndarray, edge: float, shift: float, lower: bool = True,
              keep: Optional[np.ndarray] = None) -> np.ndarray:
    """Os pontos de uma roupa com uma borda levada ``shift`` metros para cima: a borda (na altura
    ``edge``) vai inteira, e o tecido acompanha cada vez menos até EDGE_FALLOFF dela. ``lower``: é
    a borda de baixo (a barra); senão a de cima (a cintura). ``keep``: os pontos que se movem (as
    mangas de uma blusa ficam onde estão)."""
    points = np.array(points, dtype=np.float64, copy=True)
    y = points[:, 1]
    t = np.clip(((edge + EDGE_FALLOFF - y) if lower else (y - (edge - EDGE_FALLOFF))) / EDGE_FALLOFF, 0.0, 1.0)
    weight = t * t * (3.0 - 2.0 * t)
    if keep is not None:
        weight = np.where(keep, weight, 0.0)
    points[:, 1] = y + shift * weight
    return points


FACET_FRONT = 0.3      # a facet of the head whose normal points this much forwards is seen with the face
FACE_FLAT = 0.9        # and one pointing this much forwards is the flat front of the face itself
CHIN_HEIGHT = 0.066    # metres from the bottom of the head up to where that flat front starts
FACET_SHADE = 0.30     # how much darker the chin and the jaw are drawn at the strongest shading


def face_shading(rows: np.ndarray, adjust: Optional[Mapping[str, float]]) -> np.ndarray:
    """As linhas de vértice da cabeça com as sombras do queixo e do maxilar ajustadas. Elas vêm das
    facetas abaixo do rosto, viradas para baixo e para os lados: para menos, essas facetas recebem
    a luz como a frente do rosto (a normal delas vira a da frente); para mais, escurecem (cor do
    vértice). A frente do rosto fica como está."""
    much = amount(adjust, "rosto_sombra")
    if not much:
        return rows
    rows = np.array(rows, dtype=np.float32, copy=True)
    normals = rows[:, 3:6].astype(np.float64)
    low = rows[:, 1] < rows[:, 1].min() + CHIN_HEIGHT
    chin = low & (normals[:, 2] > FACET_FRONT)
    front = ~low & (normals[:, 2] > FACE_FLAT)
    if not chin.any() or not front.any():
        return rows
    if much < 0:
        lit = normals[front].mean(axis=0)
        turned = normals[chin] + (lit / max(np.linalg.norm(lit), 1e-9) - normals[chin]) * -much
        rows[chin, 3:6] = turned / np.maximum(np.linalg.norm(turned, axis=1, keepdims=True), 1e-9)
    else:
        rows[chin, 8:11] *= 1.0 - FACET_SHADE * much
    return rows


def smooth_normals(rows: np.ndarray) -> np.ndarray:
    """Normal de cada vértice, igual para os vértices na mesma posição (costuras de textura), para
    o tecido se afastar inteiro sem abrir nessas costuras."""
    positions = np.round(rows[:, :3].astype(np.float64), 5)
    _, inverse = np.unique(positions, axis=0, return_inverse=True)
    inverse = inverse.ravel()
    total = np.zeros((int(inverse.max()) + 1 if len(inverse) else 0, 3))
    np.add.at(total, inverse, rows[:, 3:6].astype(np.float64))
    normals = total[inverse]
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return normals / np.where(length > 1e-9, length, 1.0)
