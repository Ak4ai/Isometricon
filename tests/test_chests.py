"""Abrir baús com F: achar o baú ao alcance e a sessão aberta (escurece a tela, trava o personagem)."""

from types import SimpleNamespace

import numpy as np

from src.interactive.chest_session import DIM_MAX, FADE_SECONDS, ChestSession
from src.world.chests import ChestRef, distance_to, find_chest, is_chest


def structure(cells, size=(6, 4, 6), origin=(10, 20, 30)):
    """Uma construção falsa: ``cells`` mapeia (x, y, z) locais a nomes de bloco; o resto é ar."""
    width, height, length = size
    grid = np.full((height, length, width), "minecraft:air", dtype=object)
    for (x, y, z), name in cells.items():
        grid[y, z, x] = name
    schematic = SimpleNamespace(grid=grid, width=width, height=height, length=length)
    return SimpleNamespace(schematic=schematic, origin=origin)


def test_which_blocks_are_chests():
    assert is_chest("minecraft:chest[facing=north,type=single]")
    assert is_chest("minecraft:trapped_chest[facing=south]") and is_chest("minecraft:ender_chest")
    assert not is_chest("minecraft:oak_planks") and not is_chest("minecraft:barrel[facing=up]")


def test_the_nearest_chest_in_reach_is_found():
    placed = structure({(1, 1, 1): "minecraft:chest[facing=south]", (4, 1, 4): "minecraft:ender_chest[facing=south]"})
    near = find_chest([placed], (11.5, 21.0, 31.5))          # ao lado do baú de (1, 1, 1)
    assert near is not None and near.local == (1, 1, 1) and near.world == (11, 21, 31) and near.kind == "chest"
    both = find_chest([placed], (13.5, 21.0, 33.5), reach=4.0)   # os dois ao alcance: o mais perto
    assert both.local == (4, 1, 4) and both.kind == "ender_chest"


def test_too_far_or_on_another_floor_finds_nothing():
    placed = structure({(1, 1, 1): "minecraft:chest[facing=south]"})
    assert find_chest([placed], (15.5, 21.0, 35.5)) is None        # longe, na horizontal
    assert find_chest([placed], (11.5, 24.0, 31.5)) is None        # três andares acima
    assert find_chest([], (11.5, 21.0, 31.5)) is None


def test_distance_works_for_chests_and_doors_alike():
    placed = structure({(1, 1, 1): "minecraft:chest[facing=south]"})
    chest = ChestRef(placed, (1, 1, 1))
    assert abs(distance_to(chest, (11.5, 21.0, 32.5)) - 1.0) < 1e-9


def test_f_opens_then_closes_and_a_second_chest_does_not_open_on_top():
    placed = structure({(1, 1, 1): "minecraft:chest[facing=south]"})
    chest = ChestRef(placed, (1, 1, 1))
    session = ChestSession()
    assert not session.is_open and not session.locks_movement
    assert session.toggle(chest) and session.is_open and session.locks_movement
    assert not session.open(ChestRef(placed, (2, 1, 1)))           # já há um aberto
    assert session.toggle(None) and not session.is_open            # o F de novo fecha, mesmo sem baú ao alcance
    assert not session.toggle(None) and not session.close()        # sem baú ao alcance e fechado: nada acontece


def test_the_screen_fades_in_and_out_and_the_player_is_locked_while_open():
    session = ChestSession()
    session.open(SimpleNamespace())
    assert session.dim == 0.0
    session.update(FADE_SECONDS / 2)
    assert 0.0 < session.dim < DIM_MAX
    session.update(FADE_SECONDS)
    assert session.dim == DIM_MAX and session.locks_movement
    session.close()
    assert not session.locks_movement                              # fechou: o personagem anda de novo...
    assert session.dim > 0.0                                       # ...enquanto a tela ainda clareia
    session.update(FADE_SECONDS * 2)
    assert session.dim == 0.0
