"""Os objetos e o mapa do editor na revelação de cômodo do jogo (a câmera interna é uma só)."""

import numpy as np

from src.editor.map_world import MapWorld
from src.editor.room_structures import ObjectStructureCache, object_structure
from src.editor.voxel_object import VoxelObject
from src.editor.map_project import PlacedObject
from src.world import BlockType
from src.world.room_caps import _structure_caps
from src.world.room_reveal import compute_room, extract_window_cells, window_origin


def _terrain(x, y, z):
    return BlockType.STONE if y <= 0 else BlockType.AIR


def _height(x, z):
    return 0


def _house():
    return VoxelObject.load("assets/objects/casa_exemplo.json")


def _room_at(structures, position):
    origin = window_origin(position)
    cells = extract_window_cells(origin, {}, structures)
    return compute_room(cells.solid, cells.roof, origin, position, doors=cells.doors, details=cells.details)


def test_the_object_becomes_a_structure_with_the_same_occupied_cells():
    house = _house()
    placed = object_structure(house, (3, 1, 5), "casa")
    assert placed.origin == (3, 1, 5) and placed.name == "casa"
    occupied = np.argwhere(house.blocks != -1)
    assert placed._occupied.sum() == len(occupied) and placed._solid.sum() == len(occupied)
    x, y, z = (int(v) for v in occupied[0])
    assert placed.schematic.grid[y, z, x].startswith("minecraft:")          # o nome da textura do voxel
    material = house.material(int(house.blocks[x, y, z]))
    assert np.allclose(placed.schematic.tints[y, z, x], [c / 255.0 for c in material.color])


def test_inside_a_house_made_of_objects_the_room_reveal_turns_on_and_outside_it_does_not():
    structure = object_structure(_house(), (0, 0, 0), "casa")
    inside = _room_at([structure], (3.5, 1.0, 3.5))   # o miolo da casa de 7x7x7
    assert inside.active, "o jogador está dentro da casa: o cômodo deve se revelar"
    outside = _room_at([structure], (30.5, 1.0, 30.5))
    assert not outside.active
    assert not _room_at([], (3.5, 1.0, 3.5)).active                          # sem a casa, não há cômodo


def test_the_cache_keeps_the_same_structure_until_the_object_moves():
    cache = ObjectStructureCache()                                            # o mapa do editor (--map) usa
    placed = PlacedObject(_house(), (0, 0, 0), 0, "casa")
    first = cache.structures([placed])
    assert cache.structures([placed])[0] is first[0]                         # a mesma construção: o cômodo não recalcula
    placed.position = (4, 0, 4)
    moved = cache.structures([placed])
    assert moved[0] is not first[0] and moved[0].origin == (4, 0, 4)
    assert cache.structures([]) == []


def test_example_house_placed_in_the_world_can_be_entered_through_its_door():
    """A casa de exemplo colocada pelo painel (objeto do editor virando construção): a porta deixa passar."""
    from collections import deque
    from src.interactive.schematic_tool import SchematicTool

    tool = SchematicTool(mesh_factory=lambda schematic: None)
    assert tool.load("assets/objects/casa_exemplo.json", (0, 0, 0))[0]
    tool.confirm()
    look = tool.layer.wrap_lookup(_terrain)
    start, goal = (3, 1, -1), (3, 1, 3)
    queue, seen = deque([start]), {start}
    while queue:
        x, y, z = queue.popleft()
        if (x, y, z) == goal:
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y, z + dz)
            if nxt not in seen and look(*nxt) == BlockType.AIR and look(nxt[0], y + 1, nxt[2]) == BlockType.AIR:
                seen.add(nxt)
                queue.append(nxt)
    assert goal in seen


def test_the_caps_of_a_cut_wall_take_the_voxel_colour():
    structure = object_structure(_house(), (0, 0, 0), "casa")
    origin = window_origin((0.5, 1.0, 0.5))
    cells = extract_window_cells(origin, {}, [structure])
    visible = cells.owner >= 0
    culling = cells.culls
    seen = {}

    def uv(name, face):
        seen[name] = True
        return (0.0, 0.0, 1.0, 1.0)

    vertices, indices = _structure_caps(cells, visible, culling, origin, uv)
    assert len(vertices) > 0 and all(name.startswith("minecraft:") for name in seen)
    expected = np.array([[c / 255.0 for c in m.color] for m in _house().materials], dtype=np.float32)
    for colour in vertices[:, 8:11]:
        assert np.any(np.all(np.isclose(expected, colour, atol=1e-4), axis=1)), colour   # sempre a cor de um material


def test_a_playable_map_gives_its_base_and_objects_to_the_room_tracker(tmp_path):
    # o mapa de exemplo é um objeto, não um projeto: monta um projeto mínimo na mão
    from src.editor.map_project import MapProject
    base = VoxelObject((8, 4, 8))
    material = base.add_material((200, 200, 200), "white_concrete")
    base.blocks[:, 0, :] = material                       # um chão
    project = MapProject(base)
    project.add_object(_house(), (1, 1, 1))
    path = project.save(str(tmp_path / "mapa.json"))
    world = MapWorld(path, create_gl=False)
    structures = world.room_structures()
    assert [s.name for s in structures][0] == "mapa" and len(structures) == 2
    assert world.room_structures()[0] is structures[0]    # o volume base é calculado uma vez
