"""Portas das construções: achar a que está perto, abrir, fechar e deixar passar."""

import numpy as np

from src.world.block_shapes import collides, shape_for
from src.world.doors import find_door, is_open_door, toggle_door, with_open
from src.world.room_reveal import RoomRevealTracker
from src.world.schematic import Schematic
from src.world.structure_layer import StructureLayer

LOWER = "minecraft:spruce_door[facing=east,half=lower,hinge=left,open=false,powered=false]"
UPPER = "minecraft:spruce_door[facing=east,half=upper,hinge=left,open=false,powered=false]"


def wall_with_door():
    """Uma parede de pedra de 5 de largura e 3 de altura, com uma porta no meio (x = 2), em x/y/z locais."""
    grid = np.full((3, 1, 5), "minecraft:stone", dtype=object)  # [y, z, x]
    grid[0, 0, 2] = LOWER
    grid[1, 0, 2] = UPPER
    layer = StructureLayer()
    placed = layer.add("parede", Schematic(5, 3, 1, grid, palette={}), (10, 3, 10))
    return layer, placed


def test_with_open_changes_only_the_open_property():
    assert with_open(LOWER, True) == LOWER.replace("open=false", "open=true")
    assert with_open("minecraft:oak_door", True) == "minecraft:oak_door[open=true]"


def test_the_nearest_door_is_found_by_its_lower_half():
    layer, placed = wall_with_door()
    door = find_door(layer.structures, (12.5, 3.0, 11.5))   # na frente da porta, do lado de fora
    assert door is not None and door.world == (12, 3, 10)
    assert door.cells() == [(12, 3, 10), (12, 4, 10)]
    assert find_door(layer.structures, (12.5, 3.0, 15.5)) is None  # longe
    assert find_door(layer.structures, (12.5, 8.0, 11.5)) is None  # no andar de cima


def test_opening_a_door_lets_the_player_through_and_closing_blocks_again():
    layer, placed = wall_with_door()
    door = find_door(layer.structures, (12.5, 3.0, 11.5))
    assert placed.is_solid_at(12, 3, 10) and placed.is_solid_at(12, 4, 10)
    assert toggle_door(door) is True
    assert is_open_door(placed.schematic.grid[0, 0, 2]) and is_open_door(placed.schematic.grid[1, 0, 2])
    assert not placed.is_solid_at(12, 3, 10) and not placed.is_solid_at(12, 4, 10)
    assert placed.is_solid_at(11, 3, 10)                     # a parede continua
    assert toggle_door(door) is False
    assert placed.is_solid_at(12, 3, 10)


def test_an_open_door_turns_ninety_degrees_and_does_not_collide():
    opened = with_open(LOWER, True)
    assert collides(LOWER) and not collides(opened)
    assert shape_for(LOWER) != shape_for(opened)


def test_toggling_a_door_makes_the_room_tracker_recompute():
    layer, placed = wall_with_door()
    tracker = RoomRevealTracker()
    tracker.update(0.0, (12.5, 3.0, 11.5), {}, 0, layer.structures)
    version = tracker.version
    tracker.update(1.0, (12.5, 3.0, 11.5), {}, 0, layer.structures)
    assert tracker.version == version                        # nada mudou
    toggle_door(find_door(layer.structures, (12.5, 3.0, 11.5)))
    tracker.update(1.0, (12.5, 3.0, 11.5), {}, 0, layer.structures)
    assert tracker.version == version + 1


def test_the_tool_does_not_close_a_door_on_the_player():
    from src.interactive.schematic_tool import SchematicTool

    layer, placed = wall_with_door()
    tool = SchematicTool(layer=layer, mesh_factory=lambda schematic: None)
    door = tool.door_near((12.5, 3.0, 11.5))
    assert tool.toggle_door(door, player_cells=[(12, 3, 11)])   # abre
    assert not tool.toggle_door(door, player_cells=[(12, 3, 10)])  # parado dentro da porta: não fecha
    assert door.is_open
