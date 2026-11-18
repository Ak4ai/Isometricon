"""A vez dos inimigos: aproximar, disparar, atacar, recuar com arco, fugir ferido; e combates inteiros que terminam."""
import pytest

from src.combat import ai
from src.combat.bestiary import BESTIARY, PlayerSheet, spawn
from src.combat.dice import Dice, FixedDice
from src.combat.engine import CombatSession, ESCAPED, VICTORY, DEFEAT


class Steps:
    """Chão em degraus: depois de x = 4 o chão sobe 3 blocos (ninguém sobe andando)."""

    def ground(self, x, z, y_hint):
        return 3.0 if x >= 4.0 else 0.0

    def sight(self, a, b):
        return True


def setup(creature, enemy_pos, dice, player_pos=(0.0, 0.0, 0.0), **kw):
    player = PlayerSheet().combatant(player_pos)
    enemy = spawn(BESTIARY[creature], creature, enemy_pos)
    return CombatSession([enemy, player], dice=dice, **kw), player, enemy


def test_melee_enemy_walks_up_and_attacks():
    s, player, zombie = setup("zumbi", (5.0, 0.0, 0.0), FixedDice([20, 1, 19, 3]))
    assert s.current is zombie
    s.run_ai_turn()
    assert zombie.distance_to(player) <= zombie.melee_reach
    kinds = [e.kind for e in s.events]
    assert kinds.index("movimento") < kinds.index("ataque")
    assert s.is_player_turn


def test_far_enemy_dashes_instead_of_attacking():
    s, player, zombie = setup("zumbi", (14.0, 0.0, 0.0), FixedDice([20, 1]))
    s.run_ai_turn()
    kinds = [e.kind for e in s.events]
    assert "disparada" in kinds and "ataque" not in kinds
    assert zombie.position[0] < 14.0 - zombie.speed           # andou mais que um movimento normal


def test_walking_stops_at_a_wall_it_cannot_climb():
    s, player, zombie = setup("zumbi", (0.0, 0.0, 0.0), FixedDice([20, 1]), player_pos=(10.0, 3.0, 0.0),
                              terrain=Steps())
    s.run_ai_turn()
    assert zombie.position[0] < 4.0 and zombie.position[1] == 0.0


def test_archer_backs_off_when_too_close_then_shoots():
    s, player, archer = setup("esqueleto", (1.0, 0.0, 0.0), FixedDice([20, 1, 15, 3]))
    s.run_ai_turn()
    assert archer.distance_to(player) > ai.TOO_CLOSE
    assert any(e.kind == "ataque" for e in s.events)


def test_archer_in_range_just_shoots():
    s, player, archer = setup("esqueleto", (10.0, 0.0, 0.0), FixedDice([20, 1, 15, 3]))
    s.run_ai_turn()
    assert not any(e.kind == "movimento" for e in s.events)
    assert any(e.kind == "ataque" for e in s.events)


def test_wounded_coward_runs_away_and_leaves_the_fight():
    s, player, spider = setup("aranha", (1.0, 0.0, 0.0), FixedDice([20, 1]))
    spider.hp = 2
    player.position = [-7.0, 0.0, 0.0]
    s.run_ai_turn()
    assert spider not in s.order and spider in s.left
    assert any(e.kind == "fugiu" and e.actor == "aranha" for e in s.events)
    assert s.outcome == VICTORY                                # o único inimigo foi embora


def test_target_choice_prefers_close_and_weak():
    s, player, zombie = setup("zumbi", (5.0, 0.0, 0.0), FixedDice([20, 1]))
    assert ai.choose_target(s, zombie) is player
    assert ai.hit_chance(zombie, player) == pytest.approx(
        (21 - (player.armor_class - zombie.attack_bonus)) / 20)


def test_heavy_strike_is_chosen_when_the_hit_is_easy():
    s, player, ogre = setup("ogro", (1.0, 0.0, 0.0), FixedDice([20, 1, 15, 3, 3]))
    player.armor = player.armor.__class__()                    # sem armadura: CA baixa
    s.run_ai_turn()
    attack = next(e for e in s.events if e.kind == "ataque").data["result"]
    assert attack.label == "Golpe Pesado"


def _auto_play(seed, creatures):
    dice = Dice(seed)
    player = PlayerSheet().combatant((0.0, 0.0, 0.0))
    enemies = [spawn(BESTIARY[k], f"{k}{i}", (4.0 + 2 * i, 0.0, 1.5 * i)) for i, k in enumerate(creatures)]
    s = CombatSession([player] + enemies, dice=dice)
    for _ in range(400):
        if not s.active:
            break
        if s.is_player_turn:
            target = s.target
            if target is not None and not s.in_reach(player, target):
                gap = player.distance_to(target) - player.reach + 0.5
                step = s.spend_movement(gap)
                dx, dz = target.position[0] - player.position[0], target.position[2] - player.position[2]
                norm = max(1e-9, (dx * dx + dz * dz) ** 0.5)
                player.position[0] += dx / norm * step
                player.position[2] += dz / norm * step
            if s.is_player_turn:
                if player.hp_ratio < 0.4 and player.items.get("pocao_cura"):
                    s.act("usar_item", item="pocao_cura")
                elif s.block_reason("atacar") is None:
                    s.act("atacar")
                if s.is_player_turn:
                    s.end_turn()
        else:
            s.run_ai_turn()
    return s


@pytest.mark.parametrize("seed", range(40))
def test_seeded_fights_always_end(seed):
    s = _auto_play(seed, ["zumbi", "esqueleto", "aranha"][: 1 + seed % 3])
    assert s.outcome in (VICTORY, DEFEAT, ESCAPED)
    assert s.events[-1].kind == "fim"


def test_same_seed_same_fight():
    a = _auto_play(123, ["zumbi", "aranha"])
    b = _auto_play(123, ["zumbi", "aranha"])
    assert [(e.kind, e.actor, e.target) for e in a.events] == [(e.kind, e.actor, e.target) for e in b.events]
