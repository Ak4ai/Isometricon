import json

import numpy as np
import pytest

from src.editor.voxel_object import EMPTY, VoxelMaterial, VoxelObject


def test_materials_are_reused_by_colour_and_texture():
    obj = VoxelObject((4, 4, 4))
    a = obj.material_index((255, 0, 0), "bricks")
    b = obj.add_material(VoxelMaterial((255, 0, 0), "bricks"))
    c = obj.material_index((0, 255, 0), "bricks")
    assert a == b
    assert a != c
    assert len(obj.materials) == 2


def test_set_get_bounds_and_clear():
    obj = VoxelObject((3, 4, 5))
    material = obj.material_index((10, 20, 30), "stone")
    obj.set(1, 2, 3, material)
    assert obj.get(1, 2, 3) == material
    assert obj.voxel_count == 1
    assert obj.bounds() == ((1, 2, 3), (1, 2, 3))
    obj.clear(1, 2, 3)
    assert obj.get(1, 2, 3) == EMPTY
    assert obj.is_empty()
    with pytest.raises(IndexError):
        obj.set(3, 0, 0, material)


def test_resize_preserves_overlapping_region():
    obj = VoxelObject((3, 3, 3))
    material = obj.material_index((1, 2, 3), "stone")
    obj.set(2, 2, 2, material)
    obj.resize((5, 4, 6))
    assert obj.size == (5, 4, 6)
    assert obj.get(2, 2, 2) == material
    assert obj.voxel_count == 1
    obj.resize((2, 2, 2))
    assert obj.size == (2, 2, 2)
    assert obj.is_empty()


def test_rotation_changes_size_and_positions():
    obj = VoxelObject((2, 3, 4))
    material = obj.material_index((9, 8, 7), "oak_planks")
    obj.set(0, 1, 0, material)
    rotated = obj.rotated_y(1)
    assert rotated.size == (4, 3, 2)
    assert rotated.voxel_count == 1
    assert rotated.get(0, 1, 1) == material
    assert obj.rotated_y(4).size == obj.size


def test_blit_clips_and_merges_materials():
    base = VoxelObject((4, 4, 4))
    stamp = VoxelObject((2, 2, 2))
    material = stamp.material_index((200, 100, 50), "bricks")
    stamp.set(0, 0, 0, material)
    stamp.set(1, 1, 1, material)
    placed = base.blit(stamp, (3, 3, 3), 0)
    assert placed == 1  # only (3,3,3) fits; (4,4,4) is outside
    assert base.voxel_count == 1
    assert base.materials[base.get(3, 3, 3)].color == (200, 100, 50)


def test_json_round_trip(tmp_path):
    obj = VoxelObject((3, 2, 3), "teste", "object")
    material = obj.material_index((7, 8, 9), "stone_bricks")
    obj.set(0, 1, 2, material)
    path = tmp_path / "obj.json"
    obj.save(path)
    loaded = VoxelObject.load(path)
    assert loaded.size == obj.size
    assert loaded.name == "teste"
    assert loaded.get(0, 1, 2) == 0
    assert loaded.materials[0].texture == "stone_bricks"


def test_invalid_files_are_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": "outra-coisa"}), encoding="utf-8")
    with pytest.raises(ValueError):
        VoxelObject.load(path)
    path.write_text(json.dumps({"format": "isometricon-voxel-object", "version": 999,
                                "size": [2, 2, 2], "materials": [], "voxels": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        VoxelObject.load(path)


def test_sample_house_loads():
    house = VoxelObject.load("assets/objects/casa_exemplo.json")
    assert house.size == (7, 7, 7)
    assert house.voxel_count > 100
    assert len(house.materials) >= 4


def test_sample_house_is_hollow_and_has_an_open_door():
    house = VoxelObject.load("assets/objects/casa_exemplo.json")
    # Vãos abertos: 2 blocos de largura por 3 de altura, frente e fundos.
    for z in (0, 6):
        for x in (2, 3):
            for y in (1, 2, 3):
                assert house.get(x, y, z) == -1
    # Interior 5x5 com 4 blocos livres de altura.
    for x in range(1, 6):
        for y in range(1, 5):
            for z in range(1, 6):
                assert house.get(x, y, z) == -1
    # Piso e teto existem para o interior ser utilizável.
    assert house.get(3, 0, 3) >= 0
    assert house.get(3, 5, 3) >= 0
