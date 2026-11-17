from src.editor.map_editor import MapEditor
from src.editor.map_project import MapProject, PlacedObject
from src.editor.map_world import MapWorld
from src.editor.voxel_object import VoxelObject


def _project(tmp_path):
    base = VoxelObject((8, 8, 8), "mapa", "map")
    stone = base.material_index((100, 100, 100), "stone")
    for x in range(8):
        for z in range(8):
            base.set(x, 0, z, stone)
    house = VoxelObject.load("assets/objects/casa_exemplo.json")
    project = MapProject(base, [PlacedObject(house, (1, 0, 1), 0, "casa")], "teste")
    path = tmp_path / "mapa.json"
    project.save(path)
    return project, path


def test_map_world_collision_uses_base_and_objects(tmp_path):
    project, path = _project(tmp_path)
    world = MapWorld(path, create_gl=False)
    assert world.get_block_at(0, 0, 0).name == "STONE"      # base
    assert world.get_block_at(1, 0, 1).name == "STONE"      # objeto
    assert world.get_block_at(7, 7, 7).name == "AIR"
    top = world.get_top_solid_block(1, 1)
    assert top >= 4
    spawn = world.spawn_position()
    assert spawn[1] > top


def test_map_editor_brush_and_hex_and_shrink_confirmation(tmp_path):
    editor = MapEditor(create_gl=False, map_path=str(tmp_path / "mapa.json"))
    editor.brush_size = 2
    editor.cursor = (4, 0, 4)
    editor.tool = "build"
    assert editor.apply_current_tool()
    assert editor.map.voxel_count >= 1
    assert editor.handle_key(__import__("glfw").KEY_H, __import__("glfw").PRESS, 0)
    assert editor.handle_char(ord("f")) and editor.handle_char(ord("f")) and editor.handle_char(ord("8")) and editor.handle_char(ord("8")) and editor.handle_char(ord("0")) and editor.handle_char(ord("0"))
    assert editor._apply_hex()
    assert editor.custom_colour == (255, 136, 0)
    editor.map.clear(15, 15, 15) if editor.map.in_bounds(15, 15, 15) else None
    # shrink 16 -> 14 com um voxel fora exige confirmação
    editor.map.resize((16, 16, 16))
    editor.map.set(15, 15, 15, editor.map.add_material((1, 2, 3), "stone"))
    assert not editor.resize_grid(-2)
    assert editor.project.size == (16, 16, 16)
    assert editor.resize_grid(-2)
    assert editor.project.size == (14, 14, 14)
