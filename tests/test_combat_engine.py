"""A sessão de combate: iniciativa, vez, movimento, ações, quem chega no meio, efeitos por rodada e o fim."""
import pytest

from src.combat.bestiary import BESTIARY, PlayerSheet, spawn
from src.combat.combatant import ENEMIES, PLAYERS, Combatant
from src.combat.dice import FixedDice
from src.combat.effects import Effect
from src.combat.engine import DEFEAT, ESCAPED, VICTORY, CombatSession
from src.combat.stats import ARMORS, WEAPONS, Abilities


def make(cid, team=ENEMIES, pos=(0.0, 0.0, 0.0), hp=20, des=10, weapon="espada", **kw):
    return Combatant(cid, cid.capitalize(), team=team, abilities=Abilities({"for": 10, "des": des}),
                     max_hp=hp, weapon=WEAPONS[weapon], position=list(pos), proficiency=0, **kw)


def hero(pos=(0.0, 0.0, 0.0), **kw):
    kw.setdefault("skills", ("golpe_pesado", "ataque_furtivo", "escudo_divino", "foco_espiritual"))
    kw.setdefault("base_reach", 3.0)
    return make("heroi", PLAYERS, pos, **kw)


def session_with(dice_values, *combatants, **kw):
    return CombatSession(combatants, dice=FixedDice(dice_values), **kw)


# ---------------------------------------------------------------- iniciativa e ordem

def test_initiative_orders_turns_and_player_wins_ties():
    s = session_with([5, 18, 5], hero(), make("zumbi", pos=(2, 0, 0)), make("rato", pos=(3, 0, 0)))
    assert [c.id for c in s.order] == ["zumbi", "heroi", "rato"]
    assert s.current.id == "zumbi" and not s.is_player_turn
    assert s.events[0].kind == "inicio"


def test_higher_dex_breaks_initiative_ties():
    s = session_with([10, 8], hero(des=10), make("gato", des=14, pos=(2, 0, 0)))   # 10+0 contra 8+2
    assert [c.id for c in s.order] == ["gato", "heroi"]


def test_session_needs_both_sides_and_unique_ids():
    with pytest.raises(ValueError):
        CombatSession([hero()])
    with pytest.raises(ValueError):
        CombatSession([hero(), make("heroi")])


# ---------------------------------------------------------------- movimento e vez

def test_movement_pool_is_enforced_and_turn_ends_after_action_and_movement():
    s = session_with([20, 1], hero(), make("zumbi", pos=(2, 0, 0)))
    assert s.is_player_turn and s.movement_left == 8.0
    assert s.spend_movement(5.0) == 5.0
    assert s.spend_movement(5.0) == 3.0                   # só sobravam 3
    assert s.is_player_turn                               # a ação ainda não foi usada
    s.act("defender")
    assert s.current.id == "zumbi"                        # ação e movimento gastos: a vez passou


def test_acting_first_keeps_the_movement_for_after():
    s = session_with([20, 1], hero(), make("zumbi", pos=(2, 0, 0)))
    s.act("defender")
    assert s.is_player_turn and s.action_used
    assert s.act("defender").ok is False                  # uma ação por vez
    s.spend_movement(8.0)
    assert not s.is_player_turn


def test_out_of_reach_attack_is_refused_without_spending_the_action():
    s = session_with([20, 1], hero(), make("zumbi", pos=(6, 0, 0)))
    outcome = s.act("atacar")
    assert not outcome.ok and "alcance" in outcome.reason and not s.action_used
    assert s.events[-1].kind == "recusado"


def test_dash_adds_a_second_movement():
    s = session_with([20, 1], hero(), make("zumbi", pos=(12, 0, 0)))
    s.act("disparada")
    assert s.movement_left == 16.0 and s.is_player_turn


# ---------------------------------------------------------------- ataque e fim

def test_killing_the_last_enemy_is_victory():
    s = session_with([20, 1, 15, 8], hero(**{}), make("rato", hp=3, pos=(1, 0, 0)))
    s.act("atacar")
    assert s.outcome == VICTORY and not s.active
    assert [e.kind for e in s.events][-2:] == ["derrotado", "fim"]


def test_target_moves_to_the_next_enemy_when_one_falls():
    s = session_with([20, 1, 1, 15, 8], hero(), make("rato", hp=3, pos=(1, 0, 0)), make("lobo", pos=(2, 0, 0)))
    s.select_target("rato")
    s.act("atacar")
    assert s.active and s.target_id == "lobo"


def test_player_falling_is_defeat():
    s = session_with([20, 1, 15, 8], make("ogro", pos=(1, 0, 0)), hero(hp=3))
    assert s.current.id == "ogro"
    s.run_ai_turn()
    assert s.outcome == DEFEAT


def test_new_enemy_joins_without_skipping_anyone():
    s = session_with([10, 5], hero(), make("zumbi", pos=(2, 0, 0)))
    assert s.current.id == "heroi"
    s.dice.push(19)
    s.add_combatant(make("lobo", pos=(5, 0, 0)))
    assert [c.id for c in s.order] == ["lobo", "heroi", "zumbi"]
    assert s.current.id == "heroi"                         # ainda é a vez do herói
    s.end_turn()
    assert s.current.id == "zumbi"                         # o lobo só age na próxima rodada
    assert s.events[-2].kind == "turno" or any(e.kind == "entrou" for e in s.events)


def test_round_counter_advances_when_the_order_wraps():
    s = session_with([20, 1], hero(), make("zumbi", pos=(12, 0, 0)))
    s.end_turn()
    s.end_turn()
    assert s.round == 2 and s.is_player_turn


# ---------------------------------------------------------------- defesa, habilidades, itens

def test_defending_lasts_until_the_defenders_next_turn():
    s = session_with([20, 1], hero(), make("zumbi", pos=(12, 0, 0)))
    base = s.current.armor_class
    s.act("defender")
    s.end_turn()
    assert s.get("heroi").armor_class == base + 5          # na vez do zumbi continua defendendo
    s.end_turn()
    assert s.get("heroi").armor_class == base


def test_second_wind_once_per_combat():
    s = session_with([20, 1, 6], hero(), make("zumbi", pos=(12, 0, 0)))
    s.current.hp = 5
    assert s.act("foco_espiritual").ok
    assert s.current.hp == 5 + 6 + 1
    s.end_turn(); s.end_turn()
    outcome = s.act("foco_espiritual")
    assert not outcome.ok and "já foi usado" in outcome.reason


def test_divine_shield_does_not_stack_and_has_cooldown():
    s = session_with([20, 1], hero(), make("zumbi", pos=(12, 0, 0)))
    assert s.act("escudo_divino").ok
    me = s.get("heroi")
    assert me.temp_hp == 5 and me.defending
    s.end_turn(); s.end_turn()
    assert "recarrega" in s.act("escudo_divino").reason
    for _ in range(2):
        s.end_turn(); s.end_turn()
    assert s.act("escudo_divino").ok and me.temp_hp == 5


def test_sneak_attack_needs_surprise():
    s = session_with([20, 1, 15, 15, 3, 2, 2], hero(), make("zumbi", pos=(1, 0, 0), hp=40), surprise_by="heroi")
    assert s.get("heroi").hidden
    assert s.act("ataque_furtivo").ok
    attack = next(e for e in s.events if e.kind == "ataque").data["result"]
    assert attack.dice == "1d8+2d6" and attack.d20_rolls == [15, 15]
    assert not s.get("heroi").hidden
    s2 = session_with([20, 1], hero(), make("zumbi", pos=(1, 0, 0)))
    assert "surpresa" in s2.act("ataque_furtivo").reason


def test_using_an_item_spends_the_action_and_the_item():
    s = session_with([20, 1, 2, 2], hero(items={"pocao_cura": 1}), make("zumbi", pos=(12, 0, 0)))
    s.current.hp = 4
    assert s.act("usar_item", item="pocao_cura").ok
    assert s.current.hp == 10 and s.current.items == {}
    assert not s.act("usar_item", item="pocao_cura").ok


# ---------------------------------------------------------------- efeitos por rodada

def test_regeneration_heals_at_turn_start_and_expires():
    s = session_with([20, 1], hero(effects=[Effect("regeneracao", 1, 2)], hp=20), make("zumbi", pos=(12, 0, 0)))
    me = s.get("heroi")
    assert me.effects == []                               # agiu no começo da vez e acabou
    assert any(e.kind == "efeito_fim" for e in s.events)


def test_poison_hurts_but_never_knocks_out():
    poisoned = hero(effects=[Effect("veneno", 3, 2)])
    poisoned.hp = 2
    s = session_with([20, 1, 4, 4], poisoned, make("zumbi", pos=(12, 0, 0)))
    assert s.get("heroi").hp == 1 and s.active


def test_stunned_combatant_loses_the_turn():
    s = session_with([20, 1], hero(effects=[Effect("atordoado", 1)]), make("zumbi", pos=(12, 0, 0)))
    assert s.current.id == "zumbi"
    assert any(e.kind == "atordoado" for e in s.events)


# ---------------------------------------------------------------- fuga

def test_flee_without_anyone_in_reach_always_works():
    s = session_with([20, 1], hero(), make("zumbi", pos=(10, 0, 0)))
    assert s.flee_difficulty(s.current) is None
    s.act("fugir")
    assert s.outcome == ESCAPED


def test_flee_check_against_enemies_in_reach():
    s = session_with([20, 1, 1, 5], hero(des=14), make("zumbi", pos=(1, 0, 0)), make("rato", pos=(0, 0, 1)))
    assert s.flee_difficulty(s.current) == 16
    s.act("fugir")
    assert s.active and s.action_used                    # tirou 5 + 2 contra 16
    fail = next(e for e in s.events if e.kind == "fuga")
    assert fail.data["success"] is False and fail.data["dc"] == 16


def test_ending_the_turn_far_from_every_enemy_is_escaping():
    s = session_with([20, 1], hero(), make("zumbi", pos=(17, 0, 0)))
    s.end_turn()
    assert s.outcome == ESCAPED


# ---------------------------------------------------------------- fichas

def test_player_sheet_round_trips_and_ignores_bad_values():
    sheet = PlayerSheet()
    sheet.scores["for"] = 16
    data = sheet.to_dict()
    back = PlayerSheet.from_dict(data)
    assert back.scores["for"] == 16 and back.weapon == sheet.weapon
    bad = PlayerSheet.from_dict({"scores": {"for": 99, "des": "x"}, "weapon": "canhão", "level": 0})
    assert bad.scores == PlayerSheet().scores and bad.weapon == "espada_curta" and bad.level == 1
    assert PlayerSheet.from_dict(None).max_hp == 24        # 20 + 2 × CON +2


def test_bestiary_spawns_combatants_with_their_weapons():
    for key, creature in BESTIARY.items():
        c = spawn(creature, key + "1", (1, 2, 3))
        assert c.team == ENEMIES and c.hp == creature.max_hp and c.position == [1.0, 2.0, 3.0]
    assert spawn(BESTIARY["esqueleto"], "e", (0, 0, 0)).weapon.ranged
    assert spawn(BESTIARY["ogro"], "o", (0, 0, 0)).melee_reach > spawn(BESTIARY["zumbi"], "z", (0, 0, 0)).melee_reach
