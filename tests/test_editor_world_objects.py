import json

from src.editor.voxel_object import VoxelObject
from src.editor.world_objects import (
    WorldObjectEditor,
    WorldObjectProvider,
    WorldObjectStore,
    WorldTokenProvider,
)
from src.world import BlockType


def _terrain(x, y, z):
    return BlockType.STONE if y <= 0 else BlockType.AIR


def _height(x, z):
    return 0


def _house():
    return VoxelObject.load("assets/objects/casa_exemplo.json")


def test_store_round_trip_and_collision(tmp_path):
    store = WorldObjectStore(42, path=str(tmp_path / "mundo_42.json"))
    store.add(_house(), (3, 1, 5), 1, "casa", "assets/objects/casa_exemplo.json")
    path = store.save()
    loaded = WorldObjectStore.load(path)
    assert loaded.seed == 42
    assert len(loaded.objects) == 1
    assert loaded.objects[0].position == (3, 1, 5)
    assert loaded.objects[0].rotation == 1
    assert loaded.occupied(3, 1, 5)
    assert not loaded.occupied(100, 1, 100)
    provider = WorldObjectProvider(loaded, _terrain, _height)
    assert provider.get_block_at(3, 1, 5) == BlockType.STONE
    assert provider.get_block_at(3, 0, 5) == BlockType.STONE
    assert provider.get_block_at(20, 0, 20) == BlockType.STONE
    assert provider.get_block_at(20, 10, 20) == BlockType.AIR


def test_editor_place_remove_save_and_reload(tmp_path):
    path = tmp_path / "mundo_7.json"
    editor = WorldObjectEditor(7, _terrain, _height, create_gl=False, store_path=None)
    editor.store.path = str(path)
    editor.stamp = _house()
    editor.stamp_name = "casa_exemplo.json"
    editor.mode = editor.PLACE
    editor.cursor = (0, 1, 0)
    editor.valid = True
    assert editor.place_current()
    assert len(editor.store.objects) == 1
    assert path.exists()
    loaded = WorldObjectStore.load(path)
    assert len(loaded.objects) == 1
    assert loaded.objects[0].name == "casa_exemplo"
    # seleção/remoção
    editor.selected_index = 0
    assert editor.remove_selected()
    assert not editor.store.objects
    assert not WorldObjectStore.load(path).objects


def test_corrupt_file_does_not_crash_editor(tmp_path):
    path = tmp_path / "mundo_9.json"
    path.write_text("{ nao e json", encoding="utf-8")
    editor = WorldObjectEditor(9, _terrain, _height, create_gl=False, store_path=str(path))
    assert editor.store.objects == []
    assert "não carregados" in editor.status


def test_token_overlap_rejects_position():
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False)
    cells = editor._object_grid_cells(_house(), (0, 1, 0), 0)
    assert editor._overlaps_token(cells, (0.5, 1.0, 0.5))
    assert not editor._overlaps_token(cells, (50.0, 1.0, 50.0))


def test_source_is_persisted(tmp_path):
    store = WorldObjectStore(1, path=str(tmp_path / "mundo_1.json"))
    store.add(_house(), (0, 1, 0), 0, "casa", "assets/objects/casa_exemplo.json")
    path = store.save()
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["objects"][0]["source"] == "assets/objects/casa_exemplo.json"
    assert data["format"] == "isometricon-world-objects"


def test_p_enters_placement_mode_with_library(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    assert editor.handle_key(__import__("glfw").KEY_P, __import__("glfw").PRESS, 0)
    assert editor.mode == editor.PLACE
    assert editor.stamp is not None
    assert editor.handle_key(__import__("glfw").KEY_R, __import__("glfw").PRESS, 0)
    assert editor.rotation == 1


def test_invalid_placement_is_rejected(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    editor.stamp = _house()
    editor.stamp_name = "casa.json"
    editor.mode = editor.PLACE
    editor.cursor = (0, 1, 0)
    editor.valid = False
    assert not editor.place_current()
    assert not editor.store.objects


def test_token_provider_keeps_height_and_adds_objects():
    store = WorldObjectStore(1)
    store.add(_house(), (4, 1, 4), 0, "casa")
    provider = WorldTokenProvider(store, _height)
    assert provider.get_block_at(0, 0, 0) == BlockType.STONE
    assert provider.get_block_at(0, 5, 0) == BlockType.AIR
    assert provider.get_block_at(4, 1, 4) == BlockType.STONE
    assert provider.get_top_solid_block(4, 4) >= 1


def test_select_and_rotate_placed_object(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    editor.store.add(_house(), (0, 1, 0), 0, "casa")
    editor.mode = editor.SELECT
    editor.cursor = (0, 1, 0)
    assert editor.select_at_cursor()
    assert editor.selected is not None
    assert editor.rotate_selected()
    assert editor.selected.rotation == 1


def test_hud_actions_toggle_modes(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    editor._hud_action("place")
    assert editor.mode == editor.PLACE
    assert editor.stamp is not None
    editor._hud_action("select")
    assert editor.mode == editor.SELECT
    editor._hud_action("cancel")
    assert editor.mode == editor.OFF


def test_example_house_door_is_walkable_from_outside_to_interior():
    from collections import deque
    store = WorldObjectStore(1)
    store.add(_house(), (0, 0, 0), 0, "casa")
    provider = WorldTokenProvider(store, _height)
    start = (3, 1, -1)
    goal = (3, 1, 3)
    queue = deque([start])
    seen = {start}
    while queue:
        x, y, z = queue.popleft()
        if (x, y, z) == goal:
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y, z + dz)
            if nxt not in seen and provider.get_block_at(*nxt) == BlockType.AIR:
                seen.add(nxt)
                queue.append(nxt)
    assert goal in seen


def test_token_inside_object_requests_cutaway(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    editor.store.add(_house(), (0, 0, 0), 0, "casa")
    editor.token_position = (0.5, 1.5, 0.5)
    assert editor._token_inside_object()
    editor.token_position = (0.5, 7.5, 0.5)  # em cima do telhado
    assert not editor._token_inside_object()


def test_world_placement_name(tmp_path):
    editor = WorldObjectEditor(1, _terrain, _height, create_gl=False,
                               store_path=str(tmp_path / "mundo_1.json"))
    editor.stamp = _house()
    editor.stamp_name = "casa_exemplo.json"
    editor.mode = editor.PLACE
    assert editor.handle_key(__import__("glfw").KEY_N, __import__("glfw").PRESS, 0)
    for character in "Casa da Praia":
        assert editor.handle_char(ord(character))
    assert editor.handle_key(__import__("glfw").KEY_ENTER, __import__("glfw").PRESS, 0)
    editor.cursor = (0, 1, 0)
    editor.valid = True
    assert editor.place_current()
    assert editor.store.objects[0].name == "Casa da Praia"
