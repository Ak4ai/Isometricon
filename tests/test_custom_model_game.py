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
    assert store.load_choice(path) == {"arquivo": "x", "altura": store.MAX_HEIGHT, "giro": 1, "perfil": "quadrupede"}
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


def test_editor_has_a_model_section(game, glb):
    from src.interactive.character_editor import CharacterEditor
    editor = CharacterEditor(game, {"active": False, "yaw": 0.0, "pitch": 0.0}, create_gl=False)
    section = next(s for s in editor.sections if s.title == "Modelo")
    groups = section.groups() if callable(section.groups) else section.groups
    assert [o.label for o in groups[0].options] == ["Personagem montado"]
    run(game, f"/skin modelo {glb}")
    groups = section.groups() if callable(section.groups) else section.groups
    labels = [o.label for o in groups[0].options]
    assert "Meu_Monstro" in labels and len(groups) == 4
