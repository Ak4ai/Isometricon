"""Salvar e recarregar as construções colocadas (portas, giro, objetos do editor, formato antigo do Rafael)."""

import json

import numpy as np

from src.editor.map_project import PlacedObject
from src.editor.voxel_object import VoxelObject
from src.interactive.schematic_tool import SchematicTool
from src.world.doors import DoorRef, is_door, is_open_door
from src.world.structure_save import SeedStore, restore, seed_store_path, to_data


def make_tool():
    return SchematicTool(mesh_factory=lambda schematic: None)


def lower_doors(placed):
    grid = placed.schematic.grid
    return [(int(x), int(y), int(z)) for y, z, x in np.argwhere(np.vectorize(is_door, otypes=[bool])(grid))
            if "half=upper" not in grid[y, z, x]]


def place(tool, name, origin, turns=0):
    assert tool.load(name, origin)[0]
    for _ in range(turns):
        tool.rotate_preview()
    tool.preview.origin = list(origin)
    tool.confirm()
    return tool.layer.structures[-1]


def test_rotated_house_with_an_open_door_comes_back_the_same():
    tool = make_tool()
    house = place(tool, "sala-dupla", (10, 5, -3), turns=1)
    door = DoorRef(house, lower_doors(house)[0])
    if door.is_open:
        tool.toggle_door(door)
    tool.toggle_door(door)
    assert door.is_open
    data = json.loads(json.dumps(to_data(tool.layer)))     # passa por JSON, como no arquivo

    other = make_tool()
    assert restore(other, data) == []
    back = other.layer.structures[0]
    assert back.origin == house.origin and back.rotation == 1 and back.entry == house.entry
    assert (back.schematic.grid == house.schematic.grid).all()
    x, y, z = door.local
    assert is_open_door(back.schematic.grid[y, z, x])


def test_missing_schem_is_skipped_with_a_warning():
    tool = make_tool()
    place(tool, "sala-teste", (0, 5, 0))
    data = to_data(tool.layer) + [{"entry": {"kind": "schem", "name": "sumiu"}, "name": "sumiu",
                                    "origin": [50, 5, 50], "rotation": 0, "open_doors": []}]
    other = make_tool()
    warnings = restore(other, data)
    assert len(other.layer) == 1 and len(warnings) == 1 and "sumiu" in warnings[0]


def test_restore_replaces_what_was_there_and_tells_the_world():
    tool = make_tool()
    place(tool, "sala-teste", (0, 5, 0))
    data = to_data(tool.layer)
    other = make_tool()
    placed_boxes = []
    other.on_place = lambda p: placed_boxes.append(p.bounds())
    restore(other, data)
    restore(other, data)
    assert len(other.layer) == 1
    assert placed_boxes == [tool.layer.structures[0].bounds()] * 2


def test_restore_does_not_count_as_a_change():
    tool = make_tool()
    place(tool, "sala-teste", (0, 5, 0))
    other = make_tool()
    changes = []
    other.on_change = lambda: changes.append(1)
    restore(other, to_data(tool.layer))
    assert changes == []          # recarregar não regrava o arquivo que acabou de ser lido


def test_old_rafael_file_is_converted(tmp_path):
    obj = VoxelObject.load("assets/objects/casa_exemplo.json")
    old = {"format": "isometricon-world-objects", "version": 1, "seed": 7,
           "objects": [PlacedObject(obj, (3, 9, -4), 1, "Casinha", "x.json").to_dict()]}
    path = tmp_path / "mundo_7.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    items = SeedStore(str(path)).read()
    assert len(items) == 1
    item = items[0]
    assert item["entry"]["kind"] == "object" and item["name"] == "Casinha"
    assert item["origin"] == [3, 9, -4] and item["rotation"] == 1
    tool = make_tool()
    assert restore(tool, items) == []
    assert tool.layer.structures[0].schematic.width == obj.rotated_y(1).size[0]


def test_seed_store_round_trip_and_bad_file(tmp_path):
    path = tmp_path / "mundos" / "mundo_3.json"
    store = SeedStore(str(path))
    assert store.read() == []
    store.write([{"entry": {"kind": "formas"}, "name": "formas", "origin": [1, 2, 3], "rotation": 0, "open_doors": []}])
    assert SeedStore(str(path)).read()[0]["origin"] == [1, 2, 3]
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == "isometricon-structures"
    path.write_text("{", encoding="utf-8")
    assert SeedStore(str(path)).read() == []


def test_seed_store_path_is_the_old_rafael_place():
    assert seed_store_path(42).replace("\\", "/").endswith("saves/mundos/mundo_42.json")
