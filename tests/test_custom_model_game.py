"""O modelo personalizado (.glb) ligado ao jogo: pasta e escolha em disco, /skin modelo e o token."""

import os

import pytest

from src.clothing import custom_model_store as store
from src.clothing.glb import ModelError
from tests.test_procedural import skinned_glb
from src.interactive.skin_commands import SkinCommandHandler
from src.interactive.token_system import PlayerToken


@pytest.fixture
def glb(tmp_path):
    path = tmp_path / "Meu Monstro.glb"
    path.write_bytes(skinned_glb()[0])
    return str(path)


@pytest.fixture
def game(tmp_path):
    """Um handler ligado a um token de verdade, sem OpenGL, com pasta e escolha em arquivos temporários."""
    handler = SkinCommandHandler()
    handler.player_token = PlayerToken(create_mesh=False)
    handler.custom_model_dir = str(tmp_path / "modelos")
    handler.model_choice_path = str(tmp_path / "modelo.json")
    handler.model_gl = False
    return handler


def run(handler, line):
    return handler.execute(line, run_async=False)


# ---------------------------------------------------------------------------- pasta e escolha
def test_import_copies_and_lists(glb, tmp_path):
    folder = str(tmp_path / "pasta")
    name = store.import_model(glb, folder)
    assert name == "Meu_Monstro"
    assert store.list_models(folder) == ["Meu_Monstro"]
    assert store.path_of("Meu Monstro", folder) == os.path.join(folder, "Meu_Monstro.glb")


def test_bad_file_is_not_stored(tmp_path):
    bad = tmp_path / "lixo.glb"
    bad.write_bytes(b"isto nao e um glb")
    with pytest.raises(ModelError):
        store.import_model(str(bad), str(tmp_path / "pasta"))
    assert store.list_models(str(tmp_path / "pasta")) == []
    with pytest.raises(ModelError):
        store.import_model(str(tmp_path / "nao_existe.glb"), str(tmp_path / "pasta"))


def test_choice_round_trip_and_bad_files(tmp_path):
    path = str(tmp_path / "modelo.json")
    assert store.load_choice(path) is None
    store.save_choice({"arquivo": "x", "altura": 99, "giro": 5, "perfil": "quadrupede"}, path)
    assert store.load_choice(path) == {"arquivo": "x", "altura": store.MAX_HEIGHT, "giro": 1, "perfil": "quadrupede", "reparar": True}
    (tmp_path / "ruim.json").write_text("{nao é json", encoding="utf-8")
    assert store.load_choice(str(tmp_path / "ruim.json")) is None
    store.clear_choice(path)
    assert store.load_choice(path) is None


# ---------------------------------------------------------------------------- /skin modelo
def test_command_needs_the_terrain():
    handler = SkinCommandHandler()
    ok, text, _ = run(handler, "/skin modelo lista")
    assert not ok and "terreno" in text


def test_load_by_path_puts_the_model_on_the_token_and_remembers_it(game, glb):
    ok, text, _ = run(game, f"/skin modelo {glb}")
    assert ok, text
    token = game.player_token
    assert token.custom_model is not None and token.custom_model.name == "Meu_Monstro"
    assert token.custom_model.animator is not None       # o arquivo tem esqueleto: anda
    assert store.list_models(game.custom_model_dir) == ["Meu_Monstro"]
    assert store.load_choice(game.model_choice_path)["arquivo"] == "Meu_Monstro"
    assert "lista" in run(game, "/skin modelo lista")[1] or "Meu_Monstro" in run(game, "/skin modelo lista")[1]


def test_adjustments_rebuild_and_persist(game, glb):
    run(game, f"/skin modelo {glb}")
    assert run(game, "/skin modelo perfil quadrupede")[0]
    assert game.player_token.custom_model.animator.profile == "quadrupede"
    assert run(game, "/skin modelo altura 2.5")[0]
    assert game.player_token.custom_model.height == 2.5
    assert run(game, "/skin modelo giro 5")[0]
    saved = store.load_choice(game.model_choice_path)
    assert (saved["perfil"], saved["altura"], saved["giro"]) == ("quadrupede", 2.5, 1)
    assert not run(game, "/skin modelo perfil voador")[0]
    assert not run(game, "/skin modelo altura muito")[0]
    assert game.model_choice["altura"] == 2.5   # um comando errado não mexe no que está em uso


def test_adjustments_need_a_model_first(game):
    ok, text, _ = run(game, "/skin modelo altura 2")
    assert not ok and "antes" in text


def test_off_goes_back_to_the_dressed_body(game, glb):
    run(game, f"/skin modelo {glb}")
    ok, _, _ = run(game, "/skin modelo off")
    assert ok and game.player_token.custom_model is None and game.model_choice is None
    assert store.load_choice(game.model_choice_path) is None


def test_unknown_and_broken_models_leave_things_alone(game, glb, tmp_path):
    run(game, f"/skin modelo {glb}")
    assert not run(game, "/skin modelo fantasma")[0]
    assert game.player_token.custom_model.name == "Meu_Monstro"
    bad = tmp_path / "ruim.glb"
    bad.write_bytes(b"nada")
    ok, text, _ = run(game, f"/skin modelo {bad}")
    assert not ok and "[Modelo]" in text
    assert game.player_token.custom_model.name == "Meu_Monstro"


def test_startup_restores_the_saved_choice(game, glb):
    run(game, f"/skin modelo {glb}")
    run(game, "/skin modelo perfil rastejante")
    fresh = SkinCommandHandler()
    fresh.player_token = PlayerToken(create_mesh=False)
    fresh.custom_model_dir, fresh.model_gl = game.custom_model_dir, False
    ok, _, _ = fresh.apply_custom_model(store.load_choice(game.model_choice_path))
    assert ok and fresh.player_token.custom_model.animator.profile == "rastejante"


def test_an_automated_run_does_not_touch_the_saved_choice(game, glb):
    game.save_model_choice = False
    run(game, f"/skin modelo {glb}")
    assert store.load_choice(game.model_choice_path) is None


# ---------------------------------------------------------------------------- o token
def test_token_animates_the_model_only_while_moving(game, glb):
    run(game, f"/skin modelo {glb}")
    token = game.player_token
    model = token.custom_model
    token.is_moving = False
    model.update(0.5, 0.0)
    still = model.animator.matrices.copy()
    token.is_moving = True
    model.update(0.25, token.speed)
    assert not (model.animator.matrices == still).all()


def test_set_custom_model_returns_the_previous_one(game, glb):
    run(game, f"/skin modelo {glb}")
    first = game.player_token.custom_model
    assert game.player_token.set_custom_model(None) is first
    assert game.player_token.custom_model is None


def test_the_first_tab_chooses_between_the_dressed_character_and_a_custom_model(game, glb):
    from src.interactive.character_editor import CharacterEditor
    editor = CharacterEditor(game, {"active": False, "yaw": 0.0, "pitch": 0.0}, create_gl=False)
    assert editor.sections[0].title == "Modelo"
    labels = lambda s: [o.label for g in s.groups() for o in g.options]
    tab = editor.sections[0]
    assert labels(tab) == ["Personagem", "Personalizado"]
    run(game, "/skin modelo modo")                         # personalizado, ainda sem modelo: pede para importar
    assert game.custom_mode and game.model_choice is None
    assert labels(tab) == ["Personagem", "Personalizado", "Importar modelo (.glb)..."]
    game.pick_file = lambda: glb
    assert run(game, "/skin modelo importar")[0]
    shown = labels(tab)
    assert "Meu_Monstro" in shown and "Bipede" in shown and "Mostrar os ossos" in shown and "1.8" in shown
    body = next(s for s in editor.sections if s.title == "Corpo")
    assert labels(body) == []                              # o corpo montado fica de lado enquanto o modelo está em uso
    assert "personalizado" in body.groups()[0].title
    run(game, "/skin modelo off")
    assert not game.custom_mode and labels(tab) == ["Personagem", "Personalizado"] and labels(body)


def test_import_cancelled_and_personalizado_remembers_the_last_model(game, glb):
    game.pick_file = lambda: None
    assert "Nenhum" in run(game, "/skin modelo importar")[1]
    run(game, f"/skin modelo {glb}")
    run(game, "/skin modelo off")
    ok, text, _ = run(game, "/skin modelo modo")           # volta ao modelo que já estava guardado
    assert ok and game.player_token.custom_model is not None and game.custom_mode


# ---------------------------------------------------------------------------- fase 3: clipes e papéis
def test_a_file_with_clips_plays_them_and_the_profile_can_override(game, tmp_path):
    from tests.test_clips import animated_glb
    path = tmp_path / "Animado.glb"
    path.write_bytes(animated_glb())
    ok, text, _ = run(game, f"/skin modelo {path}")
    assert ok and game.player_token.custom_model.animator.profile == "clipes", text
    assert run(game, "/skin modelo perfil bipede")[0]
    assert game.player_token.custom_model.animator.profile == "bipede"
    assert run(game, "/skin modelo perfil clipes")[0]
    assert game.player_token.custom_model.animator.profile == "clipes"


def test_clips_profile_is_refused_when_the_file_has_none(game, glb):
    run(game, f"/skin modelo {glb}")
    ok, text, _ = run(game, "/skin modelo perfil clipes")
    assert not ok and "clipes" in text
    assert game.player_token.custom_model is not None


def test_roles_file_is_saved_edited_and_used(game, glb):
    run(game, f"/skin modelo {glb}")
    target = store.roles_path("Meu_Monstro", game.custom_model_dir)
    assert not os.path.exists(target)
    assert run(game, "/skin modelo papeis salvar")[0] and os.path.isfile(target)
    ok, text, _ = run(game, f"/skin modelo papeis {target}")
    assert ok, text
    assert "papéis do arquivo" in text
    assert run(game, "/skin modelo papeis off")[0] and not os.path.exists(target)


def test_a_broken_roles_file_is_refused(game, glb, tmp_path):
    run(game, f"/skin modelo {glb}")
    bad = tmp_path / "ruim.json"
    bad.write_text('{"perfil": "voador"}', encoding="utf-8")
    ok, _, _ = run(game, f"/skin modelo papeis {bad}")
    assert not ok
    assert not os.path.exists(store.roles_path("Meu_Monstro", game.custom_model_dir))


# ---------------------------------------------------------------------------- papéis visuais (clicar no osso)
def test_a_bone_click_changes_its_role_saves_the_file_and_animates_with_it(game, glb):
    run(game, f"/skin modelo {glb}")
    labels = game.bone_labels()
    assert labels is not None and len(labels) == len(game.player_token.custom_model.rig)
    assert run(game, "/skin modelo osso cauda")[0] and game.bone_brush == "cauda"
    assert not run(game, "/skin modelo osso asa")[0]
    ok, text, _ = game.set_bone_role(2, "cauda")
    assert ok and "cauda" in text and game.bone_labels()[2] == "cauda"
    assert game.player_token.custom_model.roles is not None and 2 in game.player_token.custom_model.roles.tail
    assert os.path.isfile(store.roles_path("Meu_Monstro", game.custom_model_dir))
    assert not game.set_bone_role(99, "perna")[0] and not game.set_bone_role(1, "asa")[0]


def test_editing_roles_leaves_the_clips_for_the_procedural_animation(game, tmp_path):
    from tests.test_clips import animated_glb
    path = tmp_path / "Animado.glb"
    path.write_bytes(animated_glb())
    run(game, f"/skin modelo {path}")
    assert game.player_token.custom_model.animator.profile == "clipes"
    game.set_bone_role(1, "coluna")
    assert game.player_token.custom_model.animator.profile != "clipes"
    assert store.load_choice(game.model_choice_path)["perfil"] is None


def test_the_editor_draws_and_picks_bones_on_the_model_tab(game, glb):
    import numpy as np
    from src.interactive.character_editor import CharacterEditor
    run(game, f"/skin modelo {glb}")
    editor = CharacterEditor(game, {"active": False, "yaw": 0.0, "pitch": 0.0}, create_gl=False)
    editor.open()
    editor.layout(1280, 720)
    editor.active = 0
    rig = game.player_token.custom_model.rig
    editor.bones_view = {"xy": np.array([[700.0, 200.0 + 100 * i] for i in range(len(rig))]),
                         "depth": np.zeros(len(rig)), "parents": rig.parents, "names": rig.names}
    labels = [o.label for g in editor.groups() for o in g.options]
    assert "Mostrar os ossos" in labels and "Cauda" in labels and "Voltar ao automático" in labels
    assert editor.bone_under(702, 302) == 1 and editor.bone_under(900, 300) is None
    editor.handle_cursor(700, 200)
    assert editor.bone_hover == 0
    run(game, "/skin modelo osso coluna")
    assert editor.handle_mouse_button(700, 400, 0, 1) is True
    assert game.bone_labels()[2] == "coluna"
    run(game, "/skin modelo ossos off")
    assert editor.bone_under(700, 400) is None
    editor.active = 1                                     # outra aba: os ossos não pegam o clique
    run(game, "/skin modelo ossos on")
    assert editor.bone_under(700, 400) is None


def test_repair_option_is_remembered_and_toggles(game, glb):
    run(game, f"/skin modelo {glb}")
    assert game.model_choice["reparar"] is True
    ok, _, _ = run(game, "/skin modelo reparar off")
    assert ok and game.model_choice["reparar"] is False
    assert store.load_choice(game.model_choice_path)["reparar"] is False
    run(game, "/skin modelo reparar")
    assert game.model_choice["reparar"] is True
    assert not run(SkinCommandHandler(), "/skin modelo reparar")[0]


def test_the_model_tab_shows_the_new_options_right_after_a_click_with_no_tab_change(game, glb):
    from src.interactive.character_editor import CharacterEditor
    editor = CharacterEditor(game, {"active": False, "yaw": 0.0, "pitch": 0.0}, create_gl=False)
    editor.open()
    editor.layout(1280, 720)
    labels = lambda: [o.label for g in editor.groups() for o in g.options]
    editor.choose(next(o for g in editor.groups() for o in g.options if o.label == "Personalizado"))
    assert "Importar modelo (.glb)..." in labels()                  # sem trocar de aba
    game.pick_file = lambda: glb
    editor.choose(next(o for g in editor.groups() for o in g.options if o.label.startswith("Importar")))
    assert "Meu_Monstro" in labels() and "Altura (m)" not in labels() and "Bipede" in labels()
    editor.choose(next(o for g in editor.groups() for o in g.options if o.label == "Personagem"))
    assert labels() == ["Personagem", "Personalizado"]


def test_same_basename_keeps_both_models_and_their_saved_ids(tmp_path):
    from pathlib import Path

    from src.clothing.glb_writer import sample_humanoid

    first = tmp_path / "original" / "Mesmo nome.glb"
    second = tmp_path / "novo" / first.name
    for path, data in ((first, skinned_glb()[0]), (second, sample_humanoid())):
        path.parent.mkdir()
        path.write_bytes(data)
    folder = tmp_path / "biblioteca"
    old_id = store.import_model(first, folder)
    choice_path = tmp_path / "escolha.json"
    store.save_choice({"arquivo": old_id}, choice_path)
    new_id = store.import_model(second, folder)
    assert old_id == "Mesmo_nome" and new_id != old_id
    assert store.import_model(second, folder) == new_id
    assert sorted(store.list_models(folder)) == sorted([old_id, new_id])
    assert Path(store.path_of(store.load_choice(choice_path)["arquivo"], folder)).read_bytes() == first.read_bytes()
    assert Path(store.path_of(new_id, folder)).read_bytes() == second.read_bytes()
