"""Regressão do atalho R e da seleção de mundo pelo menu com o loop OpenGL real."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_regeneration_preserves_world_and_invalid_switch_cannot_replace_it(tmp_path):
    # A aplicação termina o GLFW. Isole o seu contexto e as funções que o PyOpenGL guarda entre testes.
    script = Path(__file__).resolve()
    root = script.parents[1]
    run = subprocess.run([sys.executable, str(script), str(tmp_path)], cwd=root,
                         env=dict(os.environ, PYTHONPATH=str(root)), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=90)
    if run.returncode == 77:
        pytest.skip(run.stdout.strip())
    assert run.returncode == 0, run.stdout + run.stderr


def exercise_world_session(tmp_path, monkeypatch):
    import glfw

    monkeypatch.setattr(sys, "argv", ["isometricon", "--menu", "--token-antigo", "--gl-debug"])
    from src import main
    from src.core.game_storage import Preferences, WorldLibrary
    from src.core.window import Window
    from src.interactive.game_menus import GameMenus
    from src.rendering.fog_of_war import ExploredMap

    settings = Preferences(tmp_path / "prefs.json")
    settings.data.update(vsync=False, render_distance=1)
    library = WorldLibrary(tmp_path / "worlds")
    original = library.create("Aventura", 42)
    bad = library.create("Save incompleto", 43)
    library.save(dict(bad, npcs=[{"posicao": [4, 6]}]))
    explored = ExploredMap()
    explored.reveal(20, 0)
    structures = [{"entry": {"kind": "schem", "name": "sala-teste"}, "name": "sala-teste",
                   "origin": [4, 11, 4], "rotation": 1, "open_doors": []}]
    original.update(structures=structures, nevoa_explorada=explored.to_data(),
                    npcs=[{"id": "npcA", "nome": "Aline", "posicao": [5., 9., 3.]}])
    library.save(original)

    open_window = Window.__init__
    open_menus = GameMenus.__init__
    tick = Window.update_delta_time
    session = {}

    def start_window(self, *args, **kwargs):
        try:
            open_window(self, *args, **kwargs)
        except RuntimeError as error:
            if "GLFW" not in str(error) and "janela" not in str(error):
                raise
            print(error)
            raise SystemExit(77) from error

    def select_original(self, version):
        open_menus(self, version, settings, library)
        self.go("worlds")
        self.activate("load:" + original["id"])
        session["menu"] = self

    save = library.save

    def exercise(self):
        dt = tick(self)
        frame = session["frame"] = session.get("frame", 0) + 1
        menu = session["menu"]
        if frame == 2:
            assert menu.world["id"] == original["id"]
            original_bytes = (library.directory / (original["id"] + ".json")).read_bytes()

            def fail_save(world):
                raise OSError("simulated write failure")

            with monkeypatch.context() as failure:
                failure.setattr(library, "save", fail_save)
                self._on_key(self._window, glfw.KEY_R, 0, glfw.PRESS, 0)
            assert menu.world["id"] == original["id"]
            assert (library.directory / (original["id"] + ".json")).read_bytes() == original_bytes

            def fail_new_world_save(world):
                if world["id"] != original["id"]:
                    raise OSError("simulated new world write failure")
                save(world)

            with monkeypatch.context() as failure:
                failure.setattr(library, "save", fail_new_world_save)
                self._on_key(self._window, glfw.KEY_R, 0, glfw.PRESS, 0)
            assert menu.world["id"] == original["id"]
            assert {world["id"] for world in library.list()} == {original["id"], bad["id"]}

            self._on_key(self._window, glfw.KEY_R, 0, glfw.PRESS, 0)
            assert menu.world["id"] != original["id"]
            assert menu.world["seed"] != original["seed"]
            session["new_id"] = menu.world["id"]
        elif frame == 4:
            menu.go("worlds")
            menu.activate("load:" + bad["id"])
        elif frame == 5:
            assert menu.world["id"] == session["new_id"]
            assert menu.message
            menu.go("game")
        elif frame == 7:
            glfw.set_window_should_close(self._window, True)
        return dt

    monkeypatch.setenv("ISOMETRICON_DATA_DIR", str(tmp_path / "app"))
    monkeypatch.setattr(main, "start_github_sync_check", lambda _: SimpleNamespace(join=lambda **_: None))
    monkeypatch.setattr(GameMenus, "__init__", select_original)
    monkeypatch.setattr(Window, "__init__", start_window)
    monkeypatch.setattr(Window, "update_delta_time", exercise)
    main.main()

    saved_original = library.load(original["id"])
    assert saved_original["seed"] == 42
    assert saved_original["structures"] == structures
    assert saved_original["npcs"][0]["id"] == "npcA"
    assert saved_original["nevoa_explorada"] == original["nevoa_explorada"]
    saved_new = library.load(session["new_id"])
    assert saved_new["position"] is not None
    assert saved_new["npcs"] == [] and saved_new["structures"] == [] and saved_new["nevoa_explorada"] == {}
    with pytest.raises(ValueError, match="NPC"):
        library.load(bad["id"])


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as patch:
        exercise_world_session(Path(sys.argv[1]), patch)
