"""A roupa de baixo do personagem: desenhada na pele, sem malha.

Sem roupas o corpo não fica nu: a cueca (no corpo masculino) ou a calcinha e o sutiã (no feminino)
são pintados pelo shader sobre a pele do tronco e das pernas, por onde cada ponto fica no corpo
sem pose (``v_BindPos``): uma faixa na pelve, com a borda de baixo subindo para os lados, e no
corpo feminino uma faixa no peito com duas alças. Não é uma peça: não tem encaixe, não esconde
pele e fica por baixo de qualquer roupa vestida.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

# Colours it can be given by name (besides any "#rrggbb").
COLORS = {"branco": (244, 244, 240), "preto": (34, 32, 36), "cinza": (150, 150, 156), "nude": (222, 190, 170),
          "rosa": (240, 160, 186), "vermelho": (190, 40, 52), "azul": (60, 100, 190), "roxo": (120, 80, 170)}
DEFAULT = "branco"
# The cut of each body's, as shares of the pelvis and of the torso (from the bottom of each):
# under the crotch the lower edge starts this far below the pelvis (metres), the waist is this far
# above its top, the strip between the legs is this wide (half of it), and the lower edge rises
# by this much for each metre out to the side. The top: from where to where up the torso, where
# the straps are across it and how wide (half of it).
CUTS: Dict[str, Dict[str, Any]] = {
    "female": {"below": 0.0, "above": -0.005, "strip": 0.035, "rise": 0.55, "top": (0.52, 0.72), "strap": (0.090, 0.011)},
    "male": {"below": 0.035, "above": 0.025, "strip": 0.050, "rise": 0.15, "top": None, "strap": None},
}
_regions: Dict[str, Optional[Dict[str, Tuple[float, ...]]]] = {}


def regions(body: str, clean_obj: Optional[str] = None) -> Optional[Dict[str, Tuple[float, ...]]]:
    """Where the underwear of a body is, in metres on the unposed body:
    ``bottom`` (the lowest of the edge between the legs, the waist, half the strip between the legs,
    the rise of the edge to the sides) and ``top`` (from, to, where the straps are, half their
    width, where they end), ``top`` None on a body without one. None when the body cannot be measured."""
    body = str(body).lower()
    if body not in _regions:
        from .character_model import BODY_MESHES, MODELS_DIR, parse_clean_obj_groups
        cut = CUTS.get(body)
        path = clean_obj or os.path.join(MODELS_DIR, BODY_MESHES.get(body, ""))
        pelvis = parse_clean_obj_groups(path, ["Export_pelve"]) if cut and os.path.exists(path) else None
        torso = parse_clean_obj_groups(path, ["Export_torso"]) if pelvis else None
        if not pelvis or not torso:
            _regions[body] = None
        else:
            hips, chest = pelvis[0].reshape(-1, 11)[:, 1], torso[0].reshape(-1, 11)[:, 1]
            low, tall = float(chest.min()), float(chest.max() - chest.min())
            found = {"bottom": (float(hips.min()) - cut["below"], float(hips.max()) + cut["above"], cut["strip"], cut["rise"]), "top": None}
            if cut["top"] is not None:
                found["top"] = (low + cut["top"][0] * tall, low + cut["top"][1] * tall, cut["strap"][0], cut["strap"][1], float(chest.max()))
            _regions[body] = found
    return _regions[body]


def colour_of(custom: Any) -> Optional[Tuple[float, float, float]]:
    """A cor da roupa de baixo do personagem (0 a 1), ou None quando ele não usa
    (``AvatarCustomization.underwear``: "" ou "sem" para nenhuma, um nome de COLORS ou "#rrggbb")."""
    value = str(getattr(custom, "underwear", DEFAULT) or "").strip().lower()
    rgb = COLORS.get(value)
    if rgb is None and value.startswith("#") and len(value) == 7:
        try:
            rgb = tuple(int(value[k:k + 2], 16) for k in (1, 3, 5))
        except ValueError:
            rgb = None
    return tuple(c / 255.0 for c in rgb) if rgb is not None else None


def covers(point: Tuple[float, float, float], found: Dict[str, Tuple[float, ...]]) -> bool:
    """Whether a point of the unposed body is under the underwear: the same test as the shader's."""
    x, y = abs(point[0]), point[1]
    low, waist, strip, rise = found["bottom"]
    if low + rise * max(x - strip, 0.0) <= y <= waist:
        return True
    top = found.get("top")
    if top is None:
        return False
    start, end, strap, half, shoulder = top
    return start <= y <= end or (end < y < shoulder and abs(x - strap) < half)
