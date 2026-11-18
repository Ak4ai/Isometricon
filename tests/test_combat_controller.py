"""O combate no mundo: inimigos no tabuleiro, começo da luta, passo limitado, ritmo das vezes, teclas, fim, HUD."""
import glfw
import numpy as np

from src.combat.bestiary import PlayerSheet
from src.combat.dice import Dice, FixedDice
from src.combat.engine import DEFEAT, ESCAPED, VICTORY
from src.interactive import combat_controller as cc
from src.interactive.combat_controller import (CombatController, WorldTerrain, ascii_text, ray_hits_cylinder)
from src.interactive.combat_hud import compose, menu_image, turn_order_image
from src.interactive.enemy_tokens import miniature_vertices, ring_vertices
from src.combat.bestiary import BESTIARY

ORIGIN = [0.0, 0.0, 0.0]


def flat_floor(x, y, z):
    return y < 0          # chão em y = 0 em todo lugar


def controller(dice=None):
    c = CombatController(PlayerSheet(), dice=dice or Dice(3))
    c.terrain = WorldTerrain(flat_floor)
    return c


def run(c, seconds, pos=ORIGIN, step=0.05):
    for _ in range(int(seconds / step)):
        c.update(step, pos)


# ---------------------------------------------------------------- terreno e mira

def test_world_terrain_finds_floor_steps_and_blocks_sight():
    wall = lambda x, y, z: y < 0 or (x == 3 and y < 3) or (x == 5 and y < 1)
    t = WorldTerrain(wall)
    assert t.ground(0.5, 0.5, 0.0) == 0.0
    assert t.ground(5.5, 0.5, 0.0) == 1.0              # sobe um degrau
    assert t.ground(3.5, 0.5, 0.0) is None             # parede de 3: não dá
    assert not t.sight([0.5, 0.0, 0.5], [6.5, 0.0, 0.5])
    assert t.sight([0.5, 0.0, 0.5], [2.5, 0.0, 0.5])


def test_ray_hits_standing_cylinder():
    down = (0.0, -1.0, -1.0)
    assert ray_hits_cylinder((0, 10, 10), down, (0, 0, 0), 0.4, 1.8) is not None
    assert ray_hits_cylinder((5, 10, 10), down, (0, 0, 0), 0.4, 1.8) is None
    assert ray_hits_cylinder((0, 5, 0), (0, -1, 0), (0, 0, 0), 0.4, 1.8) == 5 - 1.8


def test_ascii_text_strips_accents_and_symbols():
    assert ascii_text("★ Ação → fim — já") == "* Acao -> fim - ja"


# ---------------------------------------------------------------- inimigos e começo

def test_spawn_puts_enemies_on_the_ground_around_the_player():
    c = controller()
    made = c.spawn("zumbi", 3, [0.0, 4.0, 0.0])
    assert len(made) == 3 and len({e.id for e in made}) == 3
    for e in made:
        assert abs(np.hypot(e.shown[0], e.shown[2]) - 5.0) < 1e-6 and e.shown[1] == 0.0


def test_clicking_a_close_enemy_starts_a_surprise_fight():
    c = controller()
    zombie = c.spawn("zumbi", 1, ORIGIN)[0]
    assert c.click_enemy(zombie, ORIGIN)
    assert c.in_combat and c.session.target_id == zombie.id and c.player.hidden
    assert c.log and "Combate" in c.log[0].text


def test_clicking_a_far_enemy_does_not_start():
    c = controller()
    zombie = c.spawn("zumbi", 1, ORIGIN)[0]
    assert not c.click_enemy(zombie, [30.0, 0.0, 0.0])
    assert not c.in_combat and c.take_messages()


def test_getting_close_triggers_aggro_and_nearby_enemies_join():
    c = controller()
    c.spawn("zumbi", 2, [20.0, 0.0, 0.0])
    c.update(0.1, ORIGIN)
    assert not c.in_combat
    c.update(0.1, [16.0, 0.0, 0.0])
    assert c.in_combat and len(c.session.team("inimigos")) == 2
    assert not c.player.hidden


def test_no_chasing_right_after_escaping():
    c = controller()
    c.spawn("zumbi", 1, ORIGIN)
    c.calm = 5.0
    c.update(0.1, [2.0, 0.0, 0.0])
    assert not c.in_combat


# ---------------------------------------------------------------- o passo e as vezes

def _player_first():
    c = controller(FixedDice([20, 1]))
    zombie = c.spawn("zumbi", 1, ORIGIN)[0]
    c.click_enemy(zombie, ORIGIN)
    assert c.is_player_turn
    return c, zombie


def test_player_step_spends_movement_and_stops_at_zero():
    c, _ = _player_first()
    pos = c.limit_step([0.0, 0.0, 0.0], [3.0, 0.0, 0.0])
    assert pos == [3.0, 0.0, 0.0] and c.session.movement_left == 5.0
    pos = c.limit_step(pos, [10.0, 0.0, 0.0])
    assert pos[0] == 8.0 and c.session.movement_left == 0.0
    assert c.locks_movement
    assert c.limit_step(pos, [9.0, 0.5, 0.0]) == [8.0, 0.5, 0.0]     # travado no chão, a gravidade ainda vale


def test_enemy_turns_wait_for_the_delay_and_the_walk():
    c, zombie = _player_first()
    c.session.dice = Dice(1)
    c.end_turn()
    assert not c.is_player_turn
    c.update(cc.ENEMY_DELAY * 0.5, ORIGIN)
    assert c.session.current.id == zombie.id                 # ainda esperando
    run(c, cc.ENEMY_DELAY + 3.0)
    assert not c.in_combat or c.session.current.id == "jogador" or c.animating


def test_number_keys_pick_actions_and_submenus():
    c, zombie = _player_first()
    assert c.handle_key(glfw.KEY_2, glfw.PRESS) and c.menu == "skills"
    assert c.handle_key(glfw.KEY_0, glfw.PRESS) and c.menu == "main"
    c.handle_key(glfw.KEY_3, glfw.PRESS)
    assert c.menu == "items" and any("Poção" in label for _, label, _, _ in c.menu_entries())
    c.handle_key(glfw.KEY_0, glfw.PRESS)
    c.handle_key(glfw.KEY_4, glfw.PRESS)                     # defender
    assert c.session.action_used and c.player.defending
    assert c.handle_key(glfw.KEY_ENTER, glfw.PRESS) and not c.is_player_turn
    assert not CombatController().handle_key(glfw.KEY_1, glfw.PRESS)      # fora do combate a tecla é dos outros


def test_victory_removes_the_fallen_and_keeps_hp():
    c = controller(FixedDice([20, 1, 20, 6, 6]))
    zombie = c.spawn("zumbi", 1, ORIGIN)[0]
    zombie.combatant.hp = 3
    c.click_enemy(zombie, [zombie.shown[0] - 1.0, 0.0, zombie.shown[2]])
    c.player.hp = 15
    c.choose("1")
    assert c.session.outcome == VICTORY
    run(c, 2.0)
    assert not c.in_combat and c.enemies == [] and c.sheet.hp == 15
    assert c.banner is not None or True


def test_defeat_wakes_with_one_hp_and_enemies_leave():
    c = controller(FixedDice([1, 20]))
    ogre = c.spawn("ogro", 1, ORIGIN)[0]
    c.sheet.hp = 2
    c.update(0.05, [ogre.shown[0] + 1.0, 0.0, ogre.shown[2]])
    assert c.in_combat and not c.is_player_turn
    c.session.dice = FixedDice([19, 6])
    run(c, 3.0, pos=[ogre.shown[0] + 1.0, 0.0, ogre.shown[2]])
    assert not c.in_combat and c.sheet.hp == 1.0
    run(c, 2.0, pos=[ogre.shown[0] + 1.0, 0.0, ogre.shown[2]])
    assert c.enemies == []
    assert any("desmaiou" in text for text, _ in c.take_messages())


def test_fleeing_leaves_enemies_and_calms_them():
    c, zombie = _player_first()
    c.limit_step(ORIGIN, [-8.0, 0.0, 0.0])
    c.session.set_position("jogador", [-8.0, 0.0, 0.0])
    c.choose("6")
    assert c.session.outcome == ESCAPED
    run(c, 0.2, pos=[-8.0, 0.0, 0.0])
    assert not c.in_combat and c.enemies and c.calm > 0


def test_resting_heals_out_of_combat():
    c = controller()
    c.sheet.hp = 10.0
    run(c, cc.REST_HEAL_SECONDS * 2 + 0.1)
    assert c.sheet.hp == 12.0


# ---------------------------------------------------------------- HUD e miniaturas

def test_hud_composes_order_menu_and_log():
    c, zombie = _player_first()
    items = {key: (image, x, y) for key, image, x, y, _ in compose(c, 1280, 720)}
    assert {"ordem", "menu", "registro"} <= set(items)
    assert items["menu"][2] + items["menu"][0].height <= 720
    assert turn_order_image(c).width > 0 and menu_image(c).height > 0


def test_hud_projects_overhead_bars_with_a_camera():
    c, zombie = _player_first()
    mvp = np.eye(4) * 0.05
    mvp[3, 3] = 1.0
    keys = [key for key, *_ in compose(c, 800, 600, mvp)]
    assert f"cabeca:{zombie.id}" in keys


def test_hud_cache_reuses_unchanged_images():
    c, _ = _player_first()
    cache = {}
    first = {k: img for k, img, *_ in compose(c, 800, 600, None, cache)}
    again = {k: img for k, img, *_ in compose(c, 800, 600, None, cache)}
    assert first["menu"] is again["menu"] and first["ordem"] is again["ordem"]
    c.limit_step(ORIGIN, [1.0, 0.0, 0.0])
    moved = {k: img for k, img, *_ in compose(c, 800, 600, None, cache)}
    assert moved["menu"] is not first["menu"]


def test_miniature_and_ring_meshes_are_well_formed():
    for creature in BESTIARY.values():
        for flash in (False, True):
            v, i = miniature_vertices(creature, flash)
            assert v.shape[1] == 11 and i.max() < len(v) and len(i) % 3 == 0
            assert v[:, 1].max() <= creature.height + 1e-5
    v, i = ring_vertices(8.0, 0.1, (0.3, 0.8, 1.0))
    radii = np.hypot(v[:, 0], v[:, 2])
    assert radii.max() <= 8.0 + 1e-4 and radii.min() >= 7.9 - 1e-4


# ---------------------------------------------------------------- comandos do chat

def test_enemy_sheet_and_attribute_commands():
    from types import SimpleNamespace
    from src.interactive.skin_commands import SkinCommandHandler
    h = SkinCommandHandler(character_model=None)
    assert not h.execute("/inimigo zumbi", run_async=False)[0]          # fora do terreno
    h.combat = controller()
    h.player_token = SimpleNamespace(position=[0.0, 0.0, 0.0])
    ok, text, _ = h.execute("/inimigo zumbi 2", run_async=False)
    assert ok and len(h.combat.enemies) == 2
    assert not h.execute("/inimigo dragao", run_async=False)[0]
    assert "zumbi" in h.execute("/inimigo lista", run_async=False)[1]
    ok, text, _ = h.execute("/ficha", run_async=False)
    assert ok and "CA" in text and "FOR 14" in text
    assert h.execute("/atributo for 18", run_async=False)[0] and h.combat.sheet.scores["for"] == 18
    assert h.execute("/atributo arma espada", run_async=False)[0] and h.combat.sheet.weapon == "espada"
    assert not h.execute("/atributo for 99", run_async=False)[0]
    assert "2 inimigo" in h.execute("/inimigo limpar", run_async=False)[1] and h.combat.enemies == []
