"""As regras do combate por turnos: dados, CA, redução de dano, a resolução do golpe, efeitos e itens."""
import pytest

from src.combat import actions
from src.combat.combatant import PLAYERS, Combatant
from src.combat.dice import Dice, DiceExpr, FixedDice
from src.combat.effects import Effect, add_effect, damage_bonus, expire_one_round
from src.combat.stats import (ARMORS, WEAPONS, Abilities, Armor, ArmorCategory, armor_class, damage_after_armor,
                              modifier)


def fighter(cid="a", team=PLAYERS, weapon="espada", armor="nenhuma", **scores):
    base = {"for": 10, "des": 10, "con": 10, "sab": 10}
    base.update(scores)
    return Combatant(cid, cid.upper(), team=team, abilities=Abilities(base), weapon=WEAPONS[weapon],
                     armor=ARMORS[armor], proficiency=0)


# ---------------------------------------------------------------- dados

def test_dice_expression_parses_and_prints():
    assert DiceExpr.parse("2d6+1") == DiceExpr(2, 6, 1)
    assert DiceExpr.parse("d20") == DiceExpr(1, 20, 0)
    assert DiceExpr.parse(" 3 d 4 - 2 ") == DiceExpr(3, 4, -2)
    assert str(DiceExpr(2, 6, 1)) == "2d6+1" and str(DiceExpr(1, 8)) == "1d8" and str(DiceExpr(1, 4, -1)) == "1d4-1"
    assert DiceExpr(2, 4, 2).average == 7.0
    with pytest.raises(ValueError):
        DiceExpr.parse("2x6")


def test_seeded_dice_repeat_and_stay_in_range():
    a, b = Dice(7), Dice(7)
    first = [a.die(20) for _ in range(50)]
    assert first == [b.die(20) for _ in range(50)]
    assert all(1 <= v <= 20 for v in first)


def test_advantage_keeps_the_higher_and_disadvantage_the_lower():
    assert FixedDice([4, 17]).d20(1) == (17, [4, 17])
    assert FixedDice([4, 17]).d20(-1) == (4, [4, 17])


def test_fixed_dice_refuse_impossible_faces():
    with pytest.raises(ValueError):
        FixedDice([9]).die(6)


# ---------------------------------------------------------------- atributos e armadura

@pytest.mark.parametrize("score, mod", [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (18, 4), (20, 5)])
def test_modifier(score, mod):
    assert modifier(score) == mod


def test_armor_class_by_category_matches_the_rulebook():
    assert armor_class(3, ARMORS["nenhuma"]) == 13
    assert ARMORS["couro"].category is ArmorCategory.LEVE
    assert armor_class(3, ARMORS["couro"]) == 11 + 3 + 3                 # leve: DES inteira + armadura/2
    assert armor_class(9, ARMORS["couro"]) == 11 + 6 + 3                 # a DES tem teto de +6
    assert armor_class(3, ARMORS["ferro"]) == 11 + 1 + 7                 # média: no máximo +1 de DES
    assert armor_class(-2, ARMORS["ferro"]) == 11 - 2 + 7                # mas a DES negativa conta inteira
    assert armor_class(5, ARMORS["aco"]) == 16                           # pesada (20, dureza 8): ignora a DES
    assert armor_class(5, ARMORS["reforcada"]) == 17                     # dureza 12 dá +1
    assert armor_class(0, ARMORS["aco"], defending=True) == 21


def test_mixed_set_costs_one_ac_and_five_percent_reduction():
    full = ARMORS["ferro"]
    mixed = Armor("Ferro misturado", 15, 0, full_set=False)
    assert armor_class(0, mixed) == armor_class(0, full) - 1
    assert damage_after_armor(10, mixed) == pytest.approx(damage_after_armor(10, full) + 0.5)
    assert not Armor(full_set=False).mixed_penalty                       # sem armadura não há penalidade


def test_damage_reduction_grows_with_armor_and_caps_with_toughness():
    assert damage_after_armor(10, ARMORS["nenhuma"]) == 10
    light, medium, heavy = (damage_after_armor(10, ARMORS[k]) for k in ("couro", "ferro", "aco"))
    assert 10 > light > medium > heavy > 0
    assert damage_after_armor(10, ARMORS["aco"]) == pytest.approx(3.0)   # golpe grande fura mais: 70%
    assert damage_after_armor(4, ARMORS["aco"]) == pytest.approx(0.96)   # golpe pequeno: 76%
    assert damage_after_armor(10, ARMORS["reforcada"]) >= 10 * 0.18 - 1e-9
    assert damage_after_armor(0, ARMORS["aco"]) == 0.0


# ---------------------------------------------------------------- o golpe

def test_natural_one_always_misses_and_twenty_always_hits():
    a, b = fighter("a", **{"for": 30}), fighter("b", team="inimigos")
    miss = actions.resolve_attack(a, b, FixedDice([1]))
    assert miss.fumble and not miss.hit and b.hp == b.max_hp
    weak, tank = fighter("a", **{"for": 1}), fighter("b", team="inimigos", armor="reforcada")
    crit = actions.resolve_attack(weak, tank, FixedDice([20, 1, 1]))
    assert crit.critical and crit.hit and crit.dice.startswith("2d8")


def test_hit_needs_total_at_least_armor_class():
    a = fighter("a", **{"for": 14})                     # +2
    b = fighter("b", team="inimigos")                   # CA 10
    assert actions.resolve_attack(a, b, FixedDice([8, 1])).hit                 # 8 + 2 = 10
    assert not actions.resolve_attack(a, b, FixedDice([7])).hit                # 7 + 2 = 9


def test_damage_adds_ability_and_has_minimum_one():
    a = fighter("a", **{"for": 14})
    b = fighter("b", team="inimigos")
    result = actions.resolve_attack(a, b, FixedDice([15, 5]))
    assert result.raw_damage == 7 and result.damage == 7 and b.hp == b.max_hp - 7
    feeble = fighter("a", weapon="soco", **{"for": 1})                         # -5
    result = actions.resolve_attack(feeble, b, FixedDice([19, 1]))
    assert result.raw_damage == 1 and result.damage == 1


def test_temporary_hp_absorbs_before_life():
    a = fighter("a", **{"for": 10})
    b = fighter("b", team="inimigos")
    b.temp_hp = 3
    result = actions.resolve_attack(a, b, FixedDice([15, 5]))
    assert result.absorbed == 3 and result.hp_damage == 2 and b.temp_hp == 0 and b.hp == b.max_hp - 2


def test_heavy_strike_rolls_twice_the_dice_with_minus_two():
    a = fighter("a", **{"for": 10})
    b = fighter("b", team="inimigos")                   # CA 10
    miss = actions.resolve_attack(a, b, FixedDice([11]), to_hit=-2, dice_multiplier=2)
    assert not miss.hit                                 # 11 - 2 = 9
    hit = actions.resolve_attack(a, b, FixedDice([12, 3, 4]), to_hit=-2, dice_multiplier=2)
    assert hit.dice == "2d8" and hit.damage_rolls == [3, 4]
    crit = actions.resolve_attack(a, b, FixedDice([20, 1, 1, 1, 1]), to_hit=-2, dice_multiplier=2)
    assert crit.dice == "4d8"


def test_sneak_attack_extra_dice_double_on_critical():
    a = fighter("a")
    b = fighter("b", team="inimigos")
    b.max_hp = b.hp = 100
    result = actions.resolve_attack(a, b, FixedDice([20, 20, 1, 1, 1, 1, 1, 1]), extra=actions.SNEAK_EXTRA,
                                    advantage=1)
    assert result.dice == "2d8+4d6" and len(result.damage_rolls) == 6


def test_ranged_attack_uses_dex_and_spends_ammo():
    archer = fighter("a", weapon="arco", **{"for": 6, "des": 16})
    archer.ammo = {"flecha": 1}
    b = fighter("b", team="inimigos")
    assert archer.attack_ability == "des" and archer.reach == 20.0
    result = actions.resolve_attack(archer, b, FixedDice([8, 2]))
    assert result.hit and result.raw_damage == 2 + 3
    assert not archer.has_ammo()


def test_on_hit_effect_is_applied_to_the_target():
    spider = fighter("a", weapon="mordida")
    spider.on_hit = Effect("veneno", 2)
    b = fighter("b", team="inimigos")
    result = actions.resolve_attack(spider, b, FixedDice([15, 1]))
    assert result.applied_effect == "veneno" and b.effects[0].kind == "veneno"


# ---------------------------------------------------------------- efeitos e itens

def test_effects_do_not_stack_and_expire_by_round():
    effects = []
    add_effect(effects, Effect("forca", 2, 1))
    add_effect(effects, Effect("forca", 1, 2))
    assert len(effects) == 1 and effects[0].potency == 2 and effects[0].rounds == 2
    assert damage_bonus(effects) == 4
    assert expire_one_round(effects) == [] and effects[0].rounds == 1
    assert [e.kind for e in expire_one_round(effects)] == ["forca"] and effects == []
    with pytest.raises(ValueError):
        Effect("voo")


def test_healing_potion_rolls_and_is_consumed():
    a = fighter("a")
    a.hp = 5
    a.items = {"pocao_cura": 1}
    used = actions.use_item(a, "pocao_cura", FixedDice([3, 4]))
    assert used["healed"] == 3 + 4 + 2 and a.hp == 14 and "pocao_cura" not in a.items


def test_healing_never_passes_max_hp():
    a = fighter("a")
    a.hp = a.max_hp - 1
    assert a.heal(50) == 1 and a.hp == a.max_hp
