from src.editor.map_project import MapProject, PlacedObject
from src.editor.voxel_object import VoxelObject


def _house():
    return VoxelObject.load("assets/objects/casa_exemplo.json")


def test_object_occupies_and_rotates():
    house = _house()
    placed = PlacedObject(house, (2, 0, 3), 0, "casa")
    assert placed.occupies(2, 0, 3)
    assert not placed.occupies(100, 0, 100)
    assert placed.bounds() == ((2, 0, 3), (8, 6, 9))
    rotated = PlacedObject(house, (2, 0, 3), 1, "casa")
    assert rotated.bounds() == ((2, 0, 3), (8, 6, 9))
    # Um voxel da base continua ocupando a mesma célula após a rotação.
    assert rotated.occupies(2, 0, 3)


def test_map_project_save_load_keeps_base_and_objects(tmp_path):
    base = VoxelObject((8, 8, 8), "mapa", "map")
    base.set(1, 0, 1, base.add_material((10, 20, 30), "bricks"))
    project = MapProject(base, [PlacedObject(_house(), (0, 0, 0), 1, "casa")], "teste")
    path = tmp_path / "mapa.json"
    project.save(path)
    loaded = MapProject.load(path)
    assert loaded.size == (8, 8, 8)
    assert loaded.base.get(1, 0, 1) >= 0
    assert len(loaded.objects) == 1
    assert loaded.objects[0].rotation == 1
    assert loaded.objects[0].name == "casa"


def test_old_object_file_loads_as_map_base():
    project = MapProject.from_dict(_house().to_dict())
    assert project.size == (7, 7, 7)
    assert project.objects == []
    assert project.base.voxel_count == 204


def test_rotation_round_trip_for_a_non_symmetric_object():
    obj = VoxelObject((2, 2, 3), "x", "object")
    material = obj.material_index((1, 2, 3), "stone")
    for x in range(2):
        for z in range(3):
            obj.set(x, 1, z, material)
    for turns in range(4):
        rotated = obj.rotated_y(turns)
        placed = PlacedObject(obj, (5, 2, 7), turns, "x")
        for x, y, z in __import__("numpy").argwhere(rotated.blocks != -1):
            assert placed.occupies(5 + int(x), 2 + int(y), 7 + int(z))
