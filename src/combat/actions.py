"""Como se resolve um golpe, e o que fazem as habilidades e os itens (sem OpenGL).

No mod Lutar, Golpe Pesado e Ataque Furtivo eram três cópias do mesmo cálculo (e o Golpe Pesado esquecia o arco). Aqui
os três passam por ``resolve_attack`` e só mudam o modificador do acerto e os dados:

- acerto: ``d20 + atributo + proficiência`` contra a CA do alvo. 1 natural sempre erra; 20 natural sempre acerta e
  dobra os dados de dano (inclusive os do Ataque Furtivo), não o bônus;
- dano: os dados da arma + o atributo + Força/Fraqueza, no mínimo 1; depois a armadura do alvo reduz (no mínimo 1
  passa, num acerto), e a absorção do alvo é gasta antes da vida.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.combat.combatant import Combatant
from src.combat.dice import DiceExpr, Dice
from src.combat.effects import Effect, add_effect, damage_bonus
from src.combat.stats import damage_after_armor


@dataclass
class AttackResult:
    attacker: str
    target: str
    label: str
    d20: int
    d20_rolls: List[int]
    attack_bonus: int
    armor_class: int
    hit: bool
    critical: bool
    fumble: bool
    dice: str = ""                  # a fórmula rolada (ex.: 2d8+3)
    damage_rolls: List[int] = field(default_factory=list)
    raw_damage: int = 0             # antes da armadura
    damage: int = 0                 # depois da armadura
    absorbed: float = 0.0
    hp_damage: float = 0.0
    damage_type: str = ""
    applied_effect: Optional[str] = None

    @property
    def total(self) -> int:
        return self.d20 + self.attack_bonus

    @property
    def reduced_by_armor(self) -> int:
        return self.raw_damage - self.damage


def _round(value: float) -> int:
    return int(math.floor(value + 0.5))


def resolve_attack(attacker: Combatant, target: Combatant, dice: Dice, *, label: str = "Ataque",
                   to_hit: int = 0, dice_multiplier: int = 1, extra: Optional[DiceExpr] = None,
                   advantage: int = 0) -> AttackResult:
    """Rola o acerto e o dano de ``attacker`` em ``target`` e aplica o dano. Não confere alcance nem a vez."""
    d20, rolls = dice.d20(advantage)
    bonus = attacker.attack_bonus + to_hit
    ac = target.armor_class
    critical = d20 == 20
    fumble = d20 == 1
    hit = not fumble and (critical or d20 + bonus >= ac)
    result = AttackResult(attacker.id, target.id, label, d20, rolls, bonus, ac, hit, critical, fumble,
                          damage_type=attacker.weapon.damage_type)
    attacker.spend_ammo()
    if not hit:
        return result

    weapon_dice = attacker.weapon.damage.scaled(dice_multiplier * (2 if critical else 1))
    modifier = attacker.mod(attacker.attack_ability) + attacker.weapon.damage.bonus + damage_bonus(attacker.effects)
    damage_rolls = dice.rolls(weapon_dice.count, weapon_dice.sides)
    formula = f"{weapon_dice.count}d{weapon_dice.sides}"
    if extra is not None:
        extra_dice = extra.scaled(2 if critical else 1)
        damage_rolls += dice.rolls(extra_dice.count, extra_dice.sides)
        formula += f"+{extra_dice.count}d{extra_dice.sides}"
        modifier += extra.bonus
    if modifier:
        formula += f"{modifier:+d}"
    raw = max(1, sum(damage_rolls) + modifier)
    damage = max(1, _round(damage_after_armor(raw, target.armor)))
    absorbed, hurt = target.take_damage(damage)

    result.dice = formula
    result.damage_rolls = damage_rolls
    result.raw_damage = raw
    result.damage = damage
    result.absorbed = absorbed
    result.hp_damage = hurt
    if attacker.on_hit is not None and target.alive:
        add_effect(target.effects, attacker.on_hit)
        result.applied_effect = attacker.on_hit.kind
    return result


# ----------------------------------------------------------------------------------------------------------------------
# Habilidades
# ----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Skill:
    key: str
    name: str
    description: str
    attack: bool = False            # precisa de um alvo ao alcance
    per_combat: Optional[int] = None
    cooldown: int = 0               # rodadas de espera depois de usar


SKILLS: Dict[str, Skill] = {
    "golpe_pesado": Skill("golpe_pesado", "Golpe Pesado", "-2 no acerto; se acertar, rola os dados da arma duas vezes",
                          attack=True),
    "ataque_furtivo": Skill("ataque_furtivo", "Ataque Furtivo",
                            "só pegando o alvo de surpresa (ou atordoado): vantagem e +2d6 de dano", attack=True),
    "escudo_divino": Skill("escudo_divino", "Escudo Divino",
                           "5 + SAB de vida temporária (não soma) e postura defensiva (+5 CA)", cooldown=3),
    "foco_espiritual": Skill("foco_espiritual", "Foco Espiritual", "recupera 1d10 + nível de vida", per_combat=1),
}

HEAVY_STRIKE_TO_HIT = -2
SNEAK_EXTRA = DiceExpr(2, 6)
DIVINE_SHIELD_BASE = 5
SECOND_WIND = DiceExpr(1, 10)


def skill_block_reason(actor: Combatant, key: str) -> Optional[str]:
    """Por que ``actor`` não pode usar a habilidade agora (ou None)."""
    skill = SKILLS.get(key)
    if skill is None or key not in actor.skills:
        return "habilidade desconhecida"
    if skill.per_combat is not None and actor.uses.get(key, 0) >= skill.per_combat:
        return f"{skill.name} já foi usado neste combate"
    wait = actor.cooldowns.get(key, 0)
    if wait > 0:
        return f"{skill.name} recarrega em {wait} rodada{'s' if wait > 1 else ''}"
    return None


def mark_skill_used(actor: Combatant, key: str) -> None:
    skill = SKILLS[key]
    actor.uses[key] = actor.uses.get(key, 0) + 1
    if skill.cooldown:
        actor.cooldowns[key] = skill.cooldown


# ----------------------------------------------------------------------------------------------------------------------
# Itens de combate (até o inventário existir, o personagem leva um kit fixo)
# ----------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    key: str
    name: str
    description: str
    heal: Optional[DiceExpr] = None
    temp_hp: int = 0
    effects: tuple = ()


ITEMS: Dict[str, Item] = {
    "pocao_cura": Item("pocao_cura", "Poção de cura", "recupera 2d4+2 de vida", heal=DiceExpr(2, 4, 2)),
    "pocao_regeneracao": Item("pocao_regeneracao", "Poção de regeneração", "regenera 2 de vida por 4 rodadas",
                              effects=(Effect("regeneracao", 4, 1),)),
    "maca_dourada": Item("maca_dourada", "Maçã dourada", "4 de vida temporária e regeneração por 2 rodadas",
                         temp_hp=4, effects=(Effect("regeneracao", 2, 1),)),
}

STARTING_KIT = {"pocao_cura": 2, "pocao_regeneracao": 1}


def use_item(actor: Combatant, key: str, dice: Dice) -> Dict[str, object]:
    """Consome um ``key`` do inventário e aplica; devolve o que aconteceu (cura, absorção, efeitos)."""
    item = ITEMS[key]
    actor.items[key] = actor.items.get(key, 0) - 1
    if actor.items[key] <= 0:
        del actor.items[key]
    healed = 0.0
    rolls: List[int] = []
    if item.heal is not None:
        total, rolls = dice.roll(item.heal)
        healed = actor.heal(total)
    if item.temp_hp:
        actor.temp_hp = max(actor.temp_hp, float(item.temp_hp))
    for effect in item.effects:
        add_effect(actor.effects, effect)
    return {"item": key, "healed": healed, "rolls": rolls, "temp_hp": item.temp_hp,
            "effects": [effect.kind for effect in item.effects]}
