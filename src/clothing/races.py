"""Raças: corpos prontos montados com o que a personalização já tem.

Uma raça não é outro modelo: é uma escolha de cor de pele, orelhas, olhos, nariz e proporções
(``body_shape``) aplicada ao corpo feminino ou masculino em uso. Depois de aplicada, cada coisa
continua ajustável como antes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from .body_shape import BODY, EARS
from .customization import IrisColor


@dataclass(frozen=True)
class Race:
    """Uma raça: o nome mostrado, a pele (0 a 255), o modelo de orelha (``ears``), a cor dos olhos,
    o formato do nariz (None: sem nariz) e os ajustes de proporção, de -100 a 100."""
    label: str
    skin: Tuple[int, int, int]
    ears: str
    eyes: IrisColor
    nose: Optional[str] = "padrao"
    adjust: Dict[str, int] = field(default_factory=dict)


RACES: Dict[str, Race] = {
    "humano": Race("Humano", (240, 212, 194), "humana", IrisColor.BROWN),
    # Tall and slender, with long ears swept back.
    "elfo": Race("Elfo", (247, 226, 208), "elfo_asa", IrisColor.GREEN, "fino",
                 {"altura": 35, "pescoco": 25, "ombros": -20, "cintura": -25, "bracos": -15, "pernas_comprimento": 25,
                  "orelha_tamanho": 10}),
    # Short, broad and heavy, with a large head and a potato nose.
    "anao": Race("Anão", (226, 180, 150), "redonda", IrisColor.BROWN, "batata",
                 {"altura": -90, "cabeca": 45, "pescoco": -60, "ombros": 70, "peito": 30, "cintura": 40, "bracos": 55,
                  "maos": 40, "pernas": 50, "pernas_comprimento": -60, "pes": 40}),
    # Large and green, all shoulders and arms.
    "orc": Race("Orc", (112, 140, 82), "elfo", IrisColor.GOLD, "achatado",
                {"altura": 45, "cabeca": 10, "pescoco": -30, "ombros": 90, "peito": 60, "bracos": 70, "maos": 50,
                 "pernas": 30, "orelha_tamanho": -35}),
    # Small, with a big head, big ears and a long nose.
    "goblin": Race("Goblin", (150, 170, 70), "elfo", IrisColor.GOLD, "longo",
                   {"altura": -85, "cabeca": 55, "ombros": -20, "bracos_comprimento": 30, "maos": 40, "pes": 35,
                    "orelha_tamanho": 60, "olhos_tamanho": 40}),
    # Red skin, golden eyes, ears like a bat's.
    "demonio": Race("Demônio", (190, 62, 58), "morcego", IrisColor.GOLD, "aquilino",
                    {"altura": 25, "ombros": 35, "cintura": -15, "orelha_tamanho": -20}),
    # Ashen, red-eyed, a little taller and thinner than a human.
    "vampiro": Race("Vampiro", (214, 214, 224), "elfo_asa", IrisColor.RED, "fino",
                    {"altura": 15, "pescoco": 15, "cintura": -20, "orelha_tamanho": -40}),
    # Sea folk (merman, triton): teal skin, fins for ears, large hands and feet to swim with.
    "tritao": Race("Tritão", (96, 186, 190), "barbatana", IrisColor.CYAN, "botao",
                   {"ombros": 15, "cintura": -20, "maos": 20, "pes": 35}),
    # The little green visitor: a huge head on a thin body, wide eyes far apart, no nose, no ears.
    "marciano": Race("Marciano", (126, 196, 110), "sem", IrisColor.PURPLE, None,
                     {"altura": -45, "cabeca": 85, "pescoco": 40, "ombros": -35, "bracos": -40, "bracos_comprimento": 30,
                      "pernas": -35, "olhos_tamanho": 100, "olhos_distancia": 45}),
    # Tiny and slight, with wing-like ears.
    "fada": Race("Fada", (250, 224, 226), "elfo_asa", IrisColor.PURPLE, "botao",
                 {"altura": -75, "cabeca": 15, "ombros": -35, "cintura": -30, "bracos": -30, "pernas": -25,
                  "orelha_tamanho": 20}),
}
RACE_NAMES = tuple(RACES)
# The adjustments a race decides: choosing another race takes these back and keeps the rest
# (makeup, the edges of the clothes, the details of the nose).
RACE_ADJUSTMENTS = (set(BODY) - {"folga"}) | set(EARS) | {"olhos_tamanho", "olhos_distancia", "olhos_altura"}


def apply(custom: Any, name: str) -> None:
    """Põe em ``custom`` (``AvatarCustomization``) a raça ``name``: pele, orelhas, olhos, nariz e
    proporções. O corpo (feminino ou masculino), o cabelo, o rosto e as roupas ficam como estão."""
    race = RACES[name]
    custom.race = name
    custom.skin_color_rgb = tuple(c / 255.0 for c in race.skin)
    custom.ear_style = race.ears
    custom.iris_color, custom.iris_color_other = race.eyes, None
    custom.has_3d_nose = race.nose is not None
    if race.nose is not None:
        custom.nose_style = race.nose
    kept = {k: v for k, v in (custom.body_adjust or {}).items() if k not in RACE_ADJUSTMENTS}
    custom.body_adjust = {**kept, **{k: v / 100.0 for k, v in race.adjust.items()}}
