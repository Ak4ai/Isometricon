import glfw

from src.editor.map_editor import MapEditor
from src.editor.voxel_object import VoxelObject


def _editor(tmp_path):
    editor = MapEditor(create_gl=False, map_path=str(tmp_path / "mapa.json"))
    editor.export_dir = str(tmp_path)
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


def test_stamp_sample_house_as_independent_object(tmp_path):
    editor = _editor(tmp_path)
    editor.stamp = VoxelObject.load("assets/objects/casa_exemplo.json")
    editor.stamp_name = "casa_exemplo.json"
    editor.tool = "stamp"
    editor.cursor = (0, 0, 0)
    assert editor.apply_current_tool()
    assert len(editor.objects) == 1
    assert editor.objects[0].name == "casa_exemplo"
    assert editor.project.voxel_count >= 100
    assert editor.map.voxel_count == 0  # o objeto não é achatado na base


def test_select_move_rotate_duplicate_delete_object(tmp_path):
    editor = _editor(tmp_path)
    editor.stamp = VoxelObject.load("assets/objects/casa_exemplo.json")
    editor.tool = "stamp"
    editor.cursor = (0, 0, 0)
    assert editor.apply_current_tool()
    house = editor.objects[0]
    editor.tool = "select"
    editor.cursor = (0, 0, 0)
    assert editor.apply_current_tool()
    assert editor.selected_index == 0
    assert editor._move_selected(1, 0, 1)
    assert house.position == (1, 0, 1)
    assert editor._rotate_selected()
    assert house.rotation == 1
    assert editor._duplicate_selected()
    assert len(editor.objects) == 2
    assert editor._delete_selected()
    assert len(editor.objects) == 1


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


def test_drag_paints_cells_while_held(tmp_path):
    editor = _editor(tmp_path)
    editor.tool = "build"
    editor.last_mouse = (0.0, 0.0)
    assert editor.handle_mouse_button(glfw.MOUSE_BUTTON_LEFT, glfw.PRESS)
    editor.cursor = (1, 0, 1)
    assert editor.process_click()
    # Sem mover o mouse, o cursor pode pular para o topo do novo voxel; não deve
    # colocar outro cubo automaticamente.
    editor.cursor = (2, 0, 1)
    editor.update_drag()
    assert editor.map.get(2, 0, 1) == -1
    # Com movimento real e após o atraso de armação, o arrasto funciona.
    editor._press_time -= 1.0
    editor.last_mouse = (20.0, 0.0)
    editor.update_drag()
    assert editor.map.get(2, 0, 1) >= 0
    editor.handle_mouse_button(glfw.MOUSE_BUTTON_LEFT, glfw.RELEASE)
    assert not editor.dragging


def test_fill_base_creates_floor_and_undoes(tmp_path):
    editor = _editor(tmp_path)
    assert editor.fill_base()
    assert editor.map.get(0, 0, 0) >= 0
    assert editor.map.get(15, 0, 15) >= 0
    assert editor.undo()
    assert editor.map.get(0, 0, 0) == -1


def test_library_panel_choose_duplicate_delete(tmp_path):
    import shutil
    library = tmp_path / "objects"
    library.mkdir()
    shutil.copyfile("assets/objects/casa_exemplo.json", library / "casa.json")
    from src.editor.map_editor import MapEditor
    editor = MapEditor(create_gl=False, library_dir=str(library))
    assert editor.open_library()
    assert editor.library_open
    assert editor._library_duplicate()
    assert len(list(library.glob("*.json"))) == 2
    editor.library_cursor = 1
    assert not editor._library_delete()
    assert editor._library_delete()
    assert len(list(library.glob("*.json"))) == 1
    assert editor.handle_key(glfw.KEY_ENTER, glfw.PRESS, 0)
    assert editor.stamp is not None
    assert not editor.library_open


def test_name_object_and_export_with_slug(tmp_path):
    editor = _editor(tmp_path)
    assert editor.handle_key(glfw.KEY_N, glfw.PRESS, 0)
    for character in "Casa do João":
        assert editor.handle_char(ord(character))
    assert editor.handle_key(glfw.KEY_ENTER, glfw.PRESS, 0)
    assert editor.object_name == "Casa do João"
    path = editor.export_object()
    assert path is not None
    assert path.endswith("casa_do_joao.json")
    loaded = VoxelObject.load(path)
    assert loaded.name == "Casa do João"


def test_palette_selection_sets_colour(tmp_path):
    editor = _editor(tmp_path)
    editor.custom_colour = (1, 2, 3)
    assert editor.select_colour(3)
    assert editor.colour_index == 3
    assert editor.custom_colour is None
    assert editor.colour == (205, 55, 55)


def test_texture_tab_and_recent_colours(tmp_path):
    editor = _editor(tmp_path)
    assert editor.select_texture(6)
    assert editor.active_tab == "textures"
    assert editor.texture == "bricks"
    assert editor.select_colour(3)
    assert editor.active_tab == "colors"
    assert editor.recent_colours[0] == (205, 55, 55)
    editor.hsv = (0.0, 1.0, 1.0)
    editor._wheel_click("wheel", 0.0, 1.0)
    assert editor.custom_colour == (255, 0, 0)
    assert editor.recent_colours[0] == (255, 0, 0)
    assert editor.select_recent(1)
    assert editor.custom_colour == (205, 55, 55)


def test_texture_filter_and_eyedropper(tmp_path):
    editor = _editor(tmp_path)
    editor.select_texture_filter("Pedra")
    assert editor.active_tab == "textures"
    names = [name for _, name, _ in editor.texture_entries()]
    assert names and all(name in ("stone", "cobblestone", "stone_bricks", "sandstone") for name in names)
    material = editor.map.add_material((12, 34, 56), "bricks")
    editor.map.set(2, 0, 3, material)
    editor.hit_block = (2, 0, 3)
    assert editor._pick_material((2, 0, 3))
    assert editor.custom_colour == (12, 34, 56)
    assert editor.texture == "bricks"
    assert editor.active_tab == "colors"


def test_alt_click_picks_material_from_canvas(tmp_path):
    editor = _editor(tmp_path)
    material = editor.map.add_material((9, 8, 7), "stone")
    editor.map.set(0, 0, 0, material)
    editor.hit_block = (0, 0, 0)
    assert editor.handle_mouse_button(glfw.MOUSE_BUTTON_LEFT, glfw.PRESS, alt=True)
    assert editor.custom_colour == (9, 8, 7)
    assert editor.texture == "stone"
    assert not editor.click_pending


def test_texture_search_and_favourites(tmp_path):
    editor = _editor(tmp_path)
    editor.open_texture_search()
    assert editor.search_mode
    for char in "brick":
        assert editor.handle_char(ord(char))
    assert editor.texture_search == "brick"
    names = [name for _, name, _ in editor.texture_entries()]
    assert "bricks" in names and all("brick" in name for name in names)
    assert editor.handle_key(glfw.KEY_ENTER, glfw.PRESS, 0)
    assert not editor.search_mode
    editor.select_texture(6)
    editor.toggle_favourite_texture()
    assert "bricks" in editor.favourite_textures
    editor.select_texture_filter("Favoritas")
    names = [name for _, name, _ in editor.texture_entries()]
    assert "bricks" in names and all("brick" in name for name in names)
