"""NPCs (/criar npc): aliados na regra, NPCs no tabuleiro, comandos do chat e os corpos montados (sem OpenGL)."""
from types import SimpleNamespace

from src.combat.bestiary import BESTIARY, PlayerSheet, spawn
from src.combat.combatant import ENEMIES, PLAYERS, Combatant
from src.combat.dice import Dice, FixedDice
from src.combat.engine import DEFEAT, VICTORY, CombatSession
from src.combat.stats import WEAPONS, Abilities
from src.interactive.combat_controller import (DEFAULT_LINE, PLAYER_ID, TALK_REACH, CombatController,
                                               WorldTerrain)
from src.interactive.npc_models import NpcModels, look_key, npc_matrix

ORIGIN = [0.0, 0.0, 0.0]


def flat_floor(x, y, z):
    return y < 0


def controller(dice=None):
    c = CombatController(PlayerSheet(), dice=dice or Dice(5))
    c.terrain = WorldTerrain(flat_floor)
    return c


def hostile(**kw):
    return dict({"nome": "Rafa", "lado": "hostil", "fala": "Some daqui!"}, **kw)


def friendly(**kw):
    return dict({"nome": "Lia", "lado": "amigavel", "fala": "Bom dia!"}, **kw)


# ---------------------------------------------------------------- a regra: aliados da IA

def make(cid, team=ENEMIES, pos=(0.0, 0.0, 0.0), hp=20, **kw):
    return Combatant(cid, cid.capitalize(), team=team, abilities=Abilities({"for": 10, "des": 10}),
                     max_hp=hp, weapon=WEAPONS["espada"], position=list(pos), proficiency=0, **kw)


def test_ally_is_on_the_players_side_but_played_by_the_ai():
    ally = spawn(BESTIARY["guarda"], "lia", (1.0, 0.0, 0.0), name="Lia", ally=True)
    assert ally.team == PLAYERS and ally.ally and not ally.is_player and ally.name == "Lia"
    s = CombatSession([make("heroi", PLAYERS), ally, make("zumbi", pos=(2.0, 0.0, 0.0))],
                      dice=FixedDice([5, 20, 1, 15, 3, 3]))
    assert s.current.id == "lia" and not s.is_player_turn
    assert s.run_ai_turn()                                   # o aliado joga sozinho, contra o zumbi
    attacks = [e for e in s.take_events() if e.kind == "ataque"]
    assert attacks and attacks[0].actor == "lia" and attacks[0].target == "zumbi"


def test_losing_the_player_is_a_defeat_even_with_allies_standing():
    ally = spawn(BESTIARY["guarda"], "lia", (1.0, 0.0, 0.0), ally=True)
    player = make("heroi", PLAYERS, hp=1)
    s = CombatSession([player, ally, make("zumbi", pos=(1.0, 0.0, 1.0))], dice=FixedDice([1, 2, 20]))
    assert s.current.id == "zumbi"
    player.hp = 0.0
    s._check_end()
    assert s.outcome == DEFEAT


# ---------------------------------------------------------------- NPCs no tabuleiro

def test_add_npc_uses_the_side_template_and_name():
    c = controller()
    foe = c.add_npc(hostile(), [5.0, 3.0, 0.0])
    pal = c.add_npc(friendly(molde="ogro"), [-5.0, 0.0, 0.0])
    assert foe.combatant.name == "Rafa" and foe.creature.key == "bandido" and not foe.friendly
    assert pal.creature.key == "ogro" and pal.friendly and pal.combatant.ally
    assert foe.shown[1] == 0.0                                 # no chão
    assert foe.id != pal.id and c.find_npc("rafa") is foe and c.find_npc("LIA") is pal


def test_npcs_round_trip_through_the_world_save():
    c = controller()
    c.add_npc(hostile(personagem={"versao": 1, "aparencia": {"body_type": "female"}}), [5.0, 0.0, 0.0], 1.5)
    c.add_npc(friendly(), [-3.0, 0.0, 2.0])
    c.spawn("zumbi", 1, ORIGIN)
    saved = c.npc_list()
    assert len(saved) == 2 and saved[0]["posicao"] == [5.0, 0.0, 0.0] and saved[0]["yaw"] == 1.5
    other = controller()
    other.load_npcs(saved)
    assert [e.combatant.name for e in other.npcs()] == ["Rafa", "Lia"]
    assert other.npcs()[0].npc["personagem"]["aparencia"]["body_type"] == "female"
    assert [e.id for e in other.npcs()] == [e["id"] for e in saved]


def test_friendly_npc_never_starts_a_fight_and_talks_on_click():
    c = controller()
    pal = c.add_npc(friendly(), [2.0, 0.0, 0.0])
    c.update(0.1, ORIGIN)
    assert not c.in_combat
    c.set_hover(pal)
    assert c.hover_hint()[0] == "clique: conversar"
    assert c.click_enemy(pal, ORIGIN) and not c.in_combat
    assert c.speech[:2] == (pal.id, "Bom dia!") and c.take_messages()[-1][0] == "[Lia] Bom dia!"
    far = [TALK_REACH + 5.0, 0.0, 0.0]
    c.player_position = far
    assert c.hover_hint()[0] == "longe demais para conversar"
    c.update(10.0, ORIGIN)
    assert c.speech is None


def test_hostile_npc_starts_the_fight_and_a_nearby_friend_joins_as_ally():
    c = controller()
    pal = c.add_npc(friendly(), [1.0, 0.0, 0.0])
    foe = c.add_npc(hostile(), [4.0, 0.0, 0.0])
    c.update(0.1, ORIGIN)
    assert c.in_combat
    ids = {x.id for x in c.session.order}
    assert {PLAYER_ID, pal.id, foe.id} <= ids
    assert c.session.get(pal.id).team == PLAYERS and not c.session.select_target(pal.id)
    c.set_hover(pal)
    assert c.hover_hint()[0] == "aliado nesta luta"


def test_fallen_ally_gets_up_after_the_fight_and_a_beaten_hostile_npc_is_gone():
    c = controller(FixedDice([20, 1, 1]))
    pal = c.add_npc(friendly(), [1.0, 0.0, 0.0])
    foe = c.add_npc(hostile(), [2.0, 0.0, 0.0])
    c.click_enemy(foe, ORIGIN)
    pal.combatant.hp = 0.0
    pal.fallen = 1e-3
    foe.combatant.hp = 0.0
    foe.fallen = 1e-3
    c.session._check_end()
    assert c.session.outcome == VICTORY
    for _ in range(40):
        c.update(0.05, ORIGIN)
    assert not c.in_combat
    assert pal in c.enemies and pal.fallen == 0.0 and pal.combatant.hp == pal.combatant.max_hp
    assert foe not in c.enemies and [e.combatant.name for e in c.npcs()] == ["Lia"]


def test_clearing_enemies_keeps_npcs_when_asked():
    c = controller()
    c.add_npc(friendly(), [-5.0, 0.0, 0.0])
    c.spawn("zumbi", 2, [30.0, 0.0, 0.0])
    assert c.clear(keep_npcs=True) == 2 and len(c.enemies) == 1
    assert c.clear() == 1 and c.enemies == []


def test_log_colors_allies_like_the_player():
    from src.combat.log import ALLY
    c = controller(FixedDice([20, 15, 1]))
    c.add_npc(friendly(), [1.0, 0.0, 0.0])
    foe = c.add_npc(hostile(), [4.0, 0.0, 0.0])
    c.click_enemy(foe, ORIGIN)
    start = c.log[0]
    assert any(text.startswith(", Lia") or text == "Lia" for text, color in start.segments if color == ALLY)


# ---------------------------------------------------------------- comandos

def handler():
    from src.interactive.skin_commands import SkinCommandHandler
    h = SkinCommandHandler(character_model=None)
    h.combat = controller()
    h.player_token = SimpleNamespace(position=[0.0, 0.0, 0.0], yaw=0.0)
    return h


def test_criar_npc_asks_the_game_to_open_the_editor():
    h = handler()
    ok, text, _ = h.execute("/criar npc Rafa hostil feminino", run_async=False)
    assert ok and h.npc_request == {"nome": "Rafa", "lado": "hostil", "molde": "bandido", "fala": DEFAULT_LINE,
                                    "corpo": "feminino"}
    assert not h.execute("/criar npc Outro amigavel masculino", run_async=False)[0]   # um de cada vez
    h.npc_request = None
    assert h.execute("/criar npc ogro Velho_Joao masculino", run_async=False)[0]     # a ordem não importa
    assert h.npc_request["nome"] == "Velho Joao" and h.npc_request["molde"] == "ogro"
    h.npc_request = None
    assert not h.execute("/criar casa", run_async=False)[0]
    assert h.npc_request is None


def test_criar_npc_needs_nothing_and_the_name_never_repeats():
    h = handler()
    assert h.execute("/criar npc", run_async=False)[0]
    assert h.npc_request == {"nome": "Novo NPC", "lado": "amigavel", "molde": "guarda", "fala": DEFAULT_LINE,
                             "corpo": "masculino"}
    h.npc_request = None
    h.combat.add_npc(friendly(), [-3.0, 0.0, 0.0])
    assert h.execute("/criar npc Lia", run_async=False)[0] and h.npc_request["nome"] == "Lia 2"


def test_npc_definir_changes_the_npc_on_the_editor():
    h = handler()
    assert not h.execute("/npc definir nome Bia", run_async=False)[0]   # nenhum NPC na tela
    h.npc_editing = {"id": "npcx", "nome": "Novo NPC", "lado": "amigavel", "molde": "guarda", "fala": DEFAULT_LINE}
    assert h.execute("/npc definir nome Bia Ferreira", run_async=False)[0]
    assert h.npc_editing["nome"] == "Bia Ferreira"
    assert h.execute("/npc definir lado hostil", run_async=False)[0]
    assert h.npc_editing["lado"] == "hostil" and h.npc_editing["molde"] == "bandido"   # a ficha padrão acompanha
    assert h.execute("/npc definir molde ogro", run_async=False)[0] and h.npc_editing["molde"] == "ogro"
    assert h.execute("/npc definir lado amigavel", run_async=False)[0]
    assert h.npc_editing["molde"] == "ogro"                     # a escolhida à mão fica
    assert h.execute("/npc definir fala Bom dia, viajante.", run_async=False)[0]
    assert h.npc_editing["fala"] == "Bom dia, viajante."
    for bad in ("/npc definir lado neutro", "/npc definir molde dragao", "/npc definir idade 30",
                "/npc definir nome", "/npc definir"):
        assert not h.execute(bad, run_async=False)[0], bad
    h.combat.add_npc(friendly(), [-3.0, 0.0, 0.0])
    assert h.execute("/npc definir nome Lia", run_async=False)[0] and h.npc_editing["nome"] == "Lia 2"


def test_replace_npc_keeps_its_place_and_id():
    c = controller()
    token = c.add_npc(friendly(), [-3.0, 0.0, 2.0], yaw=1.5)
    other = c.add_npc(hostile(), [9.0, 0.0, 0.0])
    changed = c.replace_npc(token.id, dict(token.npc, nome="Lia Brava", lado="hostil", molde="bandido"))
    assert changed.id == token.id and c.enemies.index(changed) == 0 and c.enemies[1] is other
    assert changed.combatant.name == "Lia Brava" and not changed.friendly and changed.creature.key == "bandido"
    assert changed.shown[0] == -3.0 and changed.shown[2] == 2.0 and changed.yaw == 1.5
    assert c.unique_npc_name("Lia Brava") == "Lia Brava 2" and c.unique_npc_name("Lia Brava", keep=token.id) == "Lia Brava"
    assert c.replace_npc("ninguem", {}) is None


def npc_editor():
    from src.interactive.character_editor import CharacterEditor
    sent = []
    h = SimpleNamespace(character_model=SimpleNamespace(body="male", customization=None), busy_status="",
                        npc_editing={"nome": "Bia", "lado": "amigavel", "molde": "guarda", "fala": "Oi"},
                        execute=lambda command: (sent.append(command), (True, "feito", (0, 0, 0)))[1])
    editor = CharacterEditor(h, {"active": False, "yaw": 0.0}, create_gl=False)
    editor.open()
    return editor, h, sent


def press(editor, rect):
    x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    editor.handle_mouse_button(x, y, 0, 1)
    editor.handle_mouse_button(x, y, 0, 0)


def button(editor, name):
    return next(r for r, k, p in editor.layout(1280, 720) if k == "button" and p == name)


def test_npc_creation_is_a_wizard_that_ends_with_the_identity():
    from src.interactive.character_editor import NPC_SECTION
    editor, h, _ = npc_editor()
    assert editor.wizard and [name for name, _ in editor.steps] == \
        ["Modelo", "Roupa", "Ajustes", "Rosto", "Cabelo", "Identidade"]
    assert editor.step == 0 and editor.sections[editor.active].title == "Modelo"
    hits = editor.layout(1280, 720)
    assert not any(k == "field" for _, k, _ in hits)               # o campo do Roblox fica na etapa da roupa
    pills = [editor.sections[p].title for _, k, p in hits if k == "tab"]
    assert pills == ["Modelo", "Corpo", "Prontos"]                 # as abas da etapa, nada das outras
    press(editor, button(editor, "back"))
    assert editor.step == 0                                        # antes da primeira não há nada
    press(editor, button(editor, "next"))
    assert editor.step == 1 and any(k == "field" for _, k, _ in editor.layout(1280, 720))
    step = next(r for r, k, p in editor.layout(1280, 720) if k == "step" and p == 5)
    press(editor, step)                                            # um clique na régua pula para a etapa
    assert editor.sections[editor.active].title == NPC_SECTION
    image = editor.image(1280, 720)                                # o pergaminho desenha sem erro
    assert image.size[1] == 720 and image.getpixel((200, 400))[:3] != (22, 24, 30)
    press(editor, button(editor, "next"))                          # na última, o botão cria o NPC
    assert not editor.is_open
    h.npc_editing = None
    editor.open()
    assert not editor.wizard and NPC_SECTION not in [x.title for x in editor.sections]


def test_editor_has_an_npc_tab_while_an_npc_is_on_it():
    editor, h, sent = npc_editor()
    editor.go_step(len(editor.steps) - 1)
    hits = editor.layout(1280, 720)
    option = lambda label: next((r, p) for r, k, p in hits if k == "option" and p.label == label)
    click = lambda rect: press(editor, rect)

    rect, name = option("Nome")
    click(rect)
    assert editor.typing and editor.entry == "Bia"          # o campo começa com o nome que ele tem
    editor.handle_key(259, 1)                                # Backspace
    for ch in "a Lima":
        editor.handle_char(ord(ch))
    editor.handle_key(257, 1)                                # Enter
    assert sent[-1] == "/npc definir nome Bia Lima" and not editor.typing
    click(option("Hostil")[0])
    assert sent[-1] == "/npc definir lado hostil"
    assert option("Amigável")[1].selected(h.character_model)
    assert any(p.label.startswith("Ogro") for _, k, p in hits if k == "option")
    rect, _ = option("Fala")
    click(rect)
    editor.handle_key(256, 1)                                # Esc desiste sem mandar nada
    assert sent[-1] == "/npc definir lado hostil" and not editor.typing and editor.is_open


def test_npc_commands_list_talk_edit_and_remove():
    h = handler()
    assert "Nenhum NPC" in h.execute("/npc lista", run_async=False)[1]
    h.combat.add_npc(friendly(), [-3.0, 0.0, 0.0])
    assert "Lia (amigável, guarda)" in h.execute("/npc lista", run_async=False)[1]
    assert h.execute("/npc fala lia Cuidado com os zumbis!", run_async=False)[0]
    assert h.combat.find_npc("Lia").npc["fala"] == "Cuidado com os zumbis!"
    assert h.execute("/npc editar Lia", run_async=False)[0]
    assert h.npc_request == {"editar": h.combat.find_npc("Lia").id}
    assert not h.execute("/criar npc Lia amigavel feminino", run_async=False)[0]     # um NPC já está na tela
    assert h.execute("/npc remover Lia", run_async=False)[0] and h.combat.npcs() == []
    assert not h.execute("/npc remover Lia", run_async=False)[0]


# ---------------------------------------------------------------- os corpos montados

class FakeModel:
    def __init__(self, npc_id, look):
        self.npc_id, self.look = npc_id, look
        self.is_loading = True
        self.deleted = False
        self.polls = 0
        self.drawn = []

    def poll(self):
        self.polls += 1
        if self.polls >= 2:
            self.is_loading = False

    def delete(self):
        self.deleted = True

    def draw(self, shader, matrix):
        self.drawn.append(matrix)


class FakeAnimator:
    def __init__(self, model):
        self.walking = False
        self.updates = 0

    def update(self, dt):
        self.updates += 1


def test_npc_bodies_follow_the_tokens():
    import numpy as np
    c = controller()
    foe = c.add_npc(hostile(personagem={"a": 1}), [8.0, 0.0, 0.0])
    models = NpcModels(FakeModel, FakeAnimator)
    models.sync(c, 0.1)
    body = models.bodies[foe.id]
    assert body.model.look == {"a": 1} and not models.ready(foe.id)
    models.sync(c, 0.1)
    assert models.ready(foe.id) and models.ready_ids() == {foe.id} and body.animator.updates == 1
    models.draw(None, np.eye(4), c)
    assert len(body.model.drawn) == 1 and np.allclose(body.model.drawn[0][:3, 3], [8.0, 0.0, 0.0])
    foe.npc["personagem"] = {"a": 2}                          # /npc editar mudou a aparência: monta de novo
    models.sync(c, 0.1)
    assert body.model.deleted and models.bodies[foe.id].model.look == {"a": 2}
    c.remove_npc("Rafa")
    models.sync(c, 0.1)
    assert models.bodies == {}


def test_adopted_body_is_kept_and_skip_leaves_the_edited_one_alone():
    c = controller()
    pal = c.add_npc(friendly(personagem={"b": 1}), [-3.0, 0.0, 0.0])
    models = NpcModels(FakeModel, FakeAnimator)
    built = FakeModel(pal.id, {"b": 1})
    models.adopt(pal.id, built, FakeAnimator(built), {"b": 1})
    models.sync(c, 0.1)
    assert models.bodies[pal.id].model is built                # o da tela de criação, sem montar de novo
    released = models.release(pal.id)
    models.sync(c, 0.1, skip=pal.id)
    assert released.model is built and pal.id not in models.bodies and not built.deleted
    assert look_key({"x": 1, "y": 2}) == look_key({"y": 2, "x": 1})


def test_fallen_npc_lies_down():
    import numpy as np
    standing = npc_matrix([0, 0, 0], 0.0)
    lying = npc_matrix([0, 0, 0], 0.0, fallen=1.0)
    up = np.array([0.0, 1.0, 0.0, 0.0])
    assert np.allclose(standing @ up, up) and abs((lying @ up)[1]) < 0.2
