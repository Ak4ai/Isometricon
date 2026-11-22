"""Atributos, armaduras e armas do combate: modificadores, Classe de Armadura e redução de dano (sem OpenGL).

As regras vêm do livro do mod RPG (D&D 5e adaptado):

- modificador de um atributo: ``(valor - 10) // 2``;
- a CA depende da categoria da armadura: sem armadura ``10 + DES``; leve ``11 + DES + armadura/2``; média
  ``11 + min(1, DES) + armadura/2``; pesada ``10 + armadura/3 + dureza/10`` (ignora a DES). A DES que entra na CA tem teto
  de +6. Conjunto misto ou incompleto: -1 CA e 5% a menos de redução;
- a redução de dano segue a curva de armadura/dureza que o mod usava, com teto de 82% para a dureza alta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from src.combat.dice import DiceExpr

ABILITIES = ("for", "des", "con", "sab")
ABILITY_NAMES = {"for": "Força", "des": "Destreza", "con": "Constituição", "sab": "Sabedoria"}
DEX_AC_CAP = 6            # a DES que entra na CA tem esse teto
DEFEND_AC_BONUS = 5       # postura defensiva (Defender, Escudo Divino)
MIXED_SET_DR_PENALTY = 0.05
MAX_DR_WITH_TOUGHNESS = 0.82


def modifier(score: int) -> int:
    return (int(score) - 10) // 2


class ArmorCategory(str, Enum):
    NENHUMA = "nenhuma"
    LEVE = "leve"
    MEDIA = "média"
    PESADA = "pesada"


def armor_category(value: int) -> ArmorCategory:
    if value <= 0:
        return ArmorCategory.NENHUMA
    if value < 12:
        return ArmorCategory.LEVE
    if value < 20:
        return ArmorCategory.MEDIA
    return ArmorCategory.PESADA


@dataclass(frozen=True)
class Armor:
    """Uma armadura: ``value`` é o valor bruto (0 a 20), ``toughness`` a dureza; ``full_set`` False = peças misturadas."""

    name: str = "Sem armadura"
    value: int = 0
    toughness: int = 0
    full_set: bool = True

    @property
    def category(self) -> ArmorCategory:
        return armor_category(self.value)

    @property
    def mixed_penalty(self) -> bool:
        return self.value > 0 and not self.full_set


ARMORS: Dict[str, Armor] = {
    "nenhuma": Armor(),
    "couro": Armor("Armadura de couro", 7),
    "couro_batido": Armor("Couro batido", 11),
    "cota": Armor("Cota de malha", 12),
    "ferro": Armor("Placas de ferro", 15),
    "aco": Armor("Placas de aço", 20, 8),
    "reforcada": Armor("Placas reforçadas", 20, 12),
}


def armor_class(dex_mod: int, armor: Armor, *, defending: bool = False, bonus: int = 0) -> int:
    dex = min(DEX_AC_CAP, dex_mod)
    category = armor.category
    if category is ArmorCategory.NENHUMA:
        ac = 10 + dex
    elif category is ArmorCategory.LEVE:
        ac = 11 + dex + armor.value // 2
    elif category is ArmorCategory.MEDIA:
        ac = 11 + min(1, dex_mod) + armor.value // 2
    else:
        ac = 10 + armor.value // 3 + armor.toughness // 10
    if armor.mixed_penalty:
        ac -= 1
    if defending:
        ac += DEFEND_AC_BONUS
    return ac + bonus


def damage_after_armor(damage: float, armor: Armor) -> float:
    """O dano que passa pela armadura (a curva armadura/dureza; a dureza ≥ 10 reduz mais, até 82%)."""
    damage = float(damage)
    if damage <= 0.0:
        return 0.0
    if armor.value <= 0:
        return damage
    resist = 2.0 + armor.toughness / 4.0
    absorbed = min(20.0, max(armor.value * 0.2, armor.value - damage / resist))
    reduced = damage * (1.0 - absorbed / 25.0)
    milestone = armor.toughness // 10
    if milestone > 0:
        reduced = max((1.0 - MAX_DR_WITH_TOUGHNESS) * damage, reduced - 0.02 * milestone * damage)
    if armor.mixed_penalty:
        reduced = min(damage, reduced + MIXED_SET_DR_PENALTY * damage)
    return reduced


@dataclass(frozen=True)
class Weapon:
    """Uma arma: o dado de dano, o tipo, se é à distância e quanto ela soma ao alcance corpo a corpo."""

    name: str
    damage: DiceExpr
    damage_type: str = "impacto"
    ranged: bool = False
    range: float = 0.0           # alcance das armas à distância, em blocos
    reach_bonus: float = 0.0     # somado ao alcance corpo a corpo de quem empunha
    finesse: bool = False        # usa DES no lugar de FOR (adagas)
    ammo: Optional[str] = None   # o que gasta a cada disparo (None: nada)


WEAPONS: Dict[str, Weapon] = {
    "soco": Weapon("Soco", DiceExpr(1, 4)),
    "adaga": Weapon("Adaga", DiceExpr(1, 4), "perfuração", finesse=True),
    "espada_curta": Weapon("Espada curta", DiceExpr(1, 6), "corte", reach_bonus=0.5),
    "espada": Weapon("Espada", DiceExpr(1, 8), "corte", reach_bonus=0.5),
    "machado": Weapon("Machado", DiceExpr(1, 8), "corte", reach_bonus=0.5),
    "lanca": Weapon("Lança", DiceExpr(1, 6), "perfuração", reach_bonus=1.5),
    "arco": Weapon("Arco", DiceExpr(1, 6), "perfuração", ranged=True, range=20.0, ammo="flecha"),
    "besta": Weapon("Besta", DiceExpr(1, 8), "perfuração", ranged=True, range=20.0, ammo="flecha"),
    "garras": Weapon("Garras", DiceExpr(1, 6), "corte"),
    "mordida": Weapon("Mordida", DiceExpr(1, 6), "perfuração"),
    "pancada": Weapon("Pancada", DiceExpr(1, 6), "impacto"),
}


@dataclass
class Abilities:
    """FOR, DES, CON e SAB (10 = comum)."""

    scores: Dict[str, int] = field(default_factory=lambda: {key: 10 for key in ABILITIES})

    def __post_init__(self) -> None:
        for key in ABILITIES:
            self.scores.setdefault(key, 10)

    def score(self, key: str) -> int:
        return int(self.scores[key])

    def mod(self, key: str) -> int:
        return modifier(self.scores[key])
