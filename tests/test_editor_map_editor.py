import glfw

from src.editor.map_editor import MapEditor
from src.editor.voxel_object import VoxelObject


def _editor(tmp_path):
    editor = MapEditor(create_gl=False, map_path=str(tmp_path / "mapa.json"))
    editor.export_path = str(tmp_path / "objeto.json")
    return editor


def test_build_paint_erase_and_undo(tmp_path):
    editor = _editor(tmp_path)
    editor.tool = "build"
    editor.cursor = (2, 0, 3)
    assert editor.apply_current_tool()
    assert editor.map.get(2, 0, 3) >= 0
    editor.tool = "paint"
    editor.colour_index = 3
    assert editor.apply_current_tool()
    assert editor.map.material(editor.map.get(2, 0, 3)).color == editor.colour
    assert editor.undo()
    assert editor.map.get(2, 0, 3) >= 0
    assert editor.redo()
    editor.tool = "erase"
    assert editor.apply_current_tool()
    assert editor.map.get(2, 0, 3) == -1


def test_stamp_sample_house(tmp_path):
    editor = _editor(tmp_path)
    editor.stamp = VoxelObject.load("assets/objects/casa_exemplo.json")
    editor.stamp_name = "casa_exemplo.json"
    editor.tool = "stamp"
    editor.cursor = (0, 0, 0)
    before = editor.map.voxel_count
    assert editor.apply_current_tool()
    assert editor.map.voxel_count > before
    assert editor.map.voxel_count >= 100


def test_save_and_load_map(tmp_path):
    editor = _editor(tmp_path)
    editor.map.set(1, 1, 1, editor.map.add_material((10, 20, 30), "bricks"))
    path = editor.save_map()
    assert path is not None
    editor.map.clear(1, 1, 1)
    assert editor.load_map()
    assert editor.map.get(1, 1, 1) >= 0


def test_grid_resize_and_camera_free(tmp_path):
    editor = _editor(tmp_path)
    editor.map.set(15, 15, 15, editor.map.add_material((255, 255, 255), "stone"))
    assert editor.resize_grid(2)
    assert editor.map.size == (18, 18, 18)
    assert editor.map.get(15, 15, 15) >= 0
    assert editor.undo()
    assert editor.map.size == (16, 16, 16)
    assert editor.map.get(15, 15, 15) >= 0


def test_tool_shortcuts(tmp_path):
    editor = _editor(tmp_path)
    assert editor.handle_key(glfw.KEY_TAB, glfw.PRESS, 0)
    assert editor.tool == "erase"
    assert editor.handle_key(glfw.KEY_C, glfw.PRESS, 0)
    assert editor.handle_key(glfw.KEY_X, glfw.PRESS, 0)
    assert editor.handle_key(glfw.KEY_F6, glfw.PRESS, 0)
    assert editor.map.size[0] <= 16


def test_library_loading_and_object_export(tmp_path):
    editor = _editor(tmp_path)
    assert editor._load_next_library()
    assert editor.stamp is not None
    assert editor.tool == "stamp"
    path = editor.export_object()
    assert path is not None
    assert (tmp_path / "objeto.json").exists()
