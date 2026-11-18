"""Quem luta: a ficha de combate de um personagem ou inimigo (sem OpenGL).

No mod os números vinham dos atributos do Minecraft (FOR do dano de ataque, DES da velocidade, CA do valor de
armadura). Aqui a ficha guarda os atributos direto, e a arma e a armadura são dados; quando o inventário existir, ele só
troca ``weapon`` e ``armor``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from src.combat.effects import Effect, potency
from src.combat.stats import ARMORS, WEAPONS, Abilities, Armor, Weapon, armor_class

PLAYERS = "jogadores"
ENEMIES = "inimigos"
PLAYER_REACH = 3.0     # alcance corpo a corpo do personagem, em blocos
MOB_REACH = 2.0        # e de uma criatura do tamanho de uma pessoa (cresce com a largura)
MIN_REACH = 1.5
DEFAULT_SPEED = 8.0    # blocos por turno


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(p) - float(q)) ** 2 for p, q in zip(a, b)))


def flat_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Distância no chão (x, z), sem contar a altura."""
    return math.hypot(float(a[0]) - float(b[0]), float(a[2]) - float(b[2]))


@dataclass
class Combatant:
    id: str
    name: str
    team: str = ENEMIES
    abilities: Abilities = field(default_factory=Abilities)
    max_hp: int = 20
    hp: float = -1.0                       # -1: começa com a vida cheia
    temp_hp: float = 0.0                   # absorção: gasta antes da vida
    armor: Armor = field(default_factory=lambda: ARMORS["nenhuma"])
    weapon: Weapon = field(default_factory=lambda: WEAPONS["soco"])
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    speed: float = DEFAULT_SPEED
    base_reach: float = MOB_REACH
    proficiency: int = 2
    level: int = 1
    skills: Sequence[str] = ()
    items: Dict[str, int] = field(default_factory=dict)
    ammo: Optional[Dict[str, int]] = None  # None: munição sem fim
    on_hit: Optional[Effect] = None        # efeito que o golpe deixa no alvo (a picada da aranha)
    ai: str = "agressivo"
    kind: str = ""                          # a ficha do bestiário que gerou este combatente
    effects: List[Effect] = field(default_factory=list)
    defending: bool = False
    hidden: bool = False                    # pegou o alvo de surpresa: o Ataque Furtivo vale
    initiative: int = 0
    uses: Dict[str, int] = field(default_factory=dict)       # usos de cada habilidade neste combate
    cooldowns: Dict[str, int] = field(default_factory=dict)  # rodadas até poder usar de novo

    def __post_init__(self) -> None:
        if self.hp < 0:
            self.hp = float(self.max_hp)
        self.position = [float(v) for v in self.position]

    @property
    def is_player(self) -> bool:
        return self.team == PLAYERS

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def total_hp(self) -> float:
        return self.hp + self.temp_hp

    @property
    def hp_ratio(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    def mod(self, ability: str) -> int:
        return self.abilities.mod(ability)

    @property
    def armor_class(self) -> int:
        return armor_class(self.mod("des"), self.armor, defending=self.defending)

    @property
    def attack_ability(self) -> str:
        """DES para arco e adaga (quando a DES é maior); FOR para o resto."""
        if self.weapon.ranged:
            return "des"
        if self.weapon.finesse and self.mod("des") > self.mod("for"):
            return "des"
        return "for"

    @property
    def attack_bonus(self) -> int:
        return self.mod(self.attack_ability) + self.proficiency + potency(self.effects, "abencoado")

    @property
    def melee_reach(self) -> float:
        return max(MIN_REACH, self.base_reach + (0.0 if self.weapon.ranged else self.weapon.reach_bonus))

    @property
    def reach(self) -> float:
        """Até onde o ataque desta arma chega (o alcance do arco, ou o corpo a corpo)."""
        return self.weapon.range if self.weapon.ranged else self.melee_reach

    def has_ammo(self) -> bool:
        if self.weapon.ammo is None or self.ammo is None:
            return True
        return self.ammo.get(self.weapon.ammo, 0) > 0

    def spend_ammo(self) -> None:
        if self.weapon.ammo is not None and self.ammo is not None:
            self.ammo[self.weapon.ammo] = max(0, self.ammo.get(self.weapon.ammo, 0) - 1)

    def distance_to(self, other: "Combatant") -> float:
        return distance(self.position, other.position)

    def heal(self, amount: float) -> float:
        """Cura até a vida máxima; devolve quanto curou de fato."""
        before = self.hp
        self.hp = min(float(self.max_hp), self.hp + max(0.0, amount))
        return self.hp - before

    def take_damage(self, amount: float) -> tuple[float, float]:
        """Gasta a absorção e depois a vida; devolve (absorvido, tirado da vida)."""
        amount = max(0.0, float(amount))
        absorbed = min(self.temp_hp, amount)
        self.temp_hp -= absorbed
        hurt = min(self.hp, amount - absorbed)
        self.hp -= hurt
        return absorbed, hurt
