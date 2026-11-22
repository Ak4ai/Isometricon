from src.editor.lighting import MAX_POINT_LIGHTS, collect_lights
from src.editor.map_project import MapProject, PlacedObject
from src.editor.voxel_object import VoxelMaterial, VoxelObject


def test_material_light_round_trip_and_reuse():
    obj = VoxelObject((2, 2, 2))
    dark = obj.add_material(VoxelMaterial((30, 30, 30), "stone", 0))
    glow = obj.add_material(VoxelMaterial((255, 220, 120), "yellow_concrete", 12))
    assert dark != glow
    obj.set(0, 0, 0, glow)
    loaded = VoxelObject.from_dict(obj.to_dict())
    assert loaded.materials[1].light == 12
    assert loaded.get(0, 0, 0) == 1


def test_default_lamp_objects_are_emissive():
    for name in ("lampiao", "lanterna", "tocha"):
        obj = VoxelObject.load(f"assets/objects/{name}.json")
        assert any(material.light > 0 for material in obj.materials), name


def test_collect_lights_from_base_and_placed_object():
    base = VoxelObject((4, 2, 4), "mapa", "map")
    glow = base.add_material(VoxelMaterial((255, 200, 90), "yellow_concrete", 15))
    base.set(0, 0, 0, glow)
    lamp = VoxelObject.load("assets/objects/lampiao.json")
    project = MapProject(base, [PlacedObject(lamp, (1, 0, 1))])
    lights = collect_lights(project)
    assert 1 <= len(lights) <= MAX_POINT_LIGHTS
    assert all(light.radius > 0 and light.intensity > 0 for light in lights)
    assert any(light.position[0] == 0.5 and light.position[2] == 0.5 for light in lights)


def test_object_schematic_keeps_lights_and_rotation():
    from src.editor.room_structures import object_schematic
    from src.world.block_rotation import rotate_schematic
    lamp = VoxelObject.load("assets/objects/lampiao.json")
    schematic = object_schematic(lamp, "lampiao")
    assert getattr(schematic, "lights", None) is not None
    assert int(schematic.lights.sum()) > 0
    rotated = rotate_schematic(schematic, 1)
    assert rotated.lights.shape == schematic.lights.shape
    assert int(rotated.lights.sum()) == int(schematic.lights.sum())


def test_structure_lights_find_exported_lamp():
    from src.editor.room_structures import object_schematic
    from src.editor.lighting import collect_structure_lights
    lamp = VoxelObject.load("assets/objects/lampiao.json")

    class Placed:
        schematic = object_schematic(lamp, "lampiao")
        origin = (3, 4, 5)

    lights = collect_structure_lights([Placed()])
    assert lights
    assert all(light.position[0] >= 3 and light.position[2] >= 5 for light in lights)
