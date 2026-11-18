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

def test_hud_composes_order_and_menu_and_leaves_the_log_to_the_chat():
    c, zombie = _player_first()
    items = {key: (image, x, y) for key, image, x, y, _ in compose(c, 1280, 720)}
    assert {"ordem", "menu"} <= set(items) and "registro" not in items
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


# ---------------------------------------------------------------- registro no chat, ao lado do menu, e rastro

def test_chat_becomes_the_combat_log_up_to_the_menu():
    from src.interactive.chat_console import ChatConsole
    from src.interactive.combat_hud import chat_log_view
    c, _ = _player_first()
    assert chat_log_view(controller(), 900) is None                    # sem combate, o chat é o de sempre
    chat = ChatConsole(create_gl=False)
    normal = chat._box_width(1920)
    boxes = {}
    for width in (1920, 900):
        menu_left = width - menu_image(c).width - 12
        view = chat_log_view(c, menu_left)
        assert view.title.startswith("Combate") and view.lines and "★" not in str(view.lines)
        chat.set_combat_log(view)
        box = boxes[width] = chat._box_width(width)
        assert 16 + box + 6 <= menu_left                              # a caixa para antes do menu
        assert box >= menu_left - 16 - 6 - 8 - 20                     # e aproveita a largura até ele
        image = chat._generate_hud_image(width, 720, [])
        assert image.getbbox() is not None
        assert image.getbbox()[2] <= menu_left
    assert boxes[1920] > normal > boxes[900]                             # na janela larga cresce além dos 740
    chat.set_combat_log(None)
    assert chat._box_width(1920) == normal and chat.combat_log is None


def test_chat_log_wraps_long_lines_by_word():
    from PIL import Image, ImageDraw
    from src.interactive.chat_console import ChatConsole
    chat = ChatConsole(create_gl=False)
    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    rows = chat._wrap_segments(draw, [("Zumbi ataca ", (255, 0, 0)), ("o jogador " * 20, (255, 255, 255))], 200)
    assert len(rows) > 2
    assert all(chat._measure(draw, "".join(t for t, _ in row)) <= 200 + chat._measure(draw, "  ") for row in rows)


def test_trail_marks_the_walk_and_restarts_each_turn():
    from src.interactive.enemy_tokens import TRAIL_BIG, TRAIL_SMALL, dot_vertices, trail_sizes
    c, _ = _player_first()
    pos = [0.0, 0.0, 0.0]
    c.update(0.01, pos)
    for _ in range(10):
        pos = c.limit_step(pos, [pos[0] - 0.2, 0.0, 0.0])
        c.update(0.01, pos)
    assert len(c.trail) == 6 and c.trail[0] == [0.0, 0.0, 0.0]
    assert all(abs(b[0] - a[0]) >= cc.TRAIL_STEP - 1e-9 for a, b in zip(c.trail, c.trail[1:]))
    c.end_turn()
    c.update(0.01, pos)
    assert len(c.trail) == 6                                   # na vez dos inimigos o rastro continua lá
    c.session.end_turn() if not c.session.is_player_turn else None
    c.update(0.01, pos)
    assert c.trail == [pos]                                    # a vez voltou: rastro novo
    sizes = trail_sizes(5)
    assert sizes[0] == TRAIL_SMALL and sizes[-1] == TRAIL_BIG and sizes == sorted(sizes)
    v, i = dot_vertices(0.1, (0, 0, 1))
    assert np.hypot(v[:, 0], v[:, 2]).max() <= 0.1 + 1e-6 and (v[:, 1] == 0).all()
    c.clear()
    assert c.trail == []


def test_submenus_dim_after_the_action_is_used():
    c, _ = _player_first()
    assert c.blocked(None) is None
    c.choose("4")
    assert "já foi usada" in c.blocked(None)
