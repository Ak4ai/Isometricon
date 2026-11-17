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


def test_the_lid_opens_and_closes_in_steps_and_reports_each_change_once():
    from src.interactive.chest_session import LID_SECONDS
    session = ChestSession()
    chest = SimpleNamespace(name="bau")
    assert session.take_lid_update() is None                       # nada se mexe: nada a refazer
    session.open(chest)
    amounts = []
    for _ in range(40):
        session.update(LID_SECONDS / 10)
        update = session.take_lid_update()
        if update is not None:
            assert update[0] is chest
            amounts.append(update[1])
    assert amounts == sorted(amounts) and amounts[-1] == 1.0       # só sobe, e chega toda aberta
    assert amounts.count(1.0) == 1                                 # parada de vez: não pede para refazer a malha de novo
    assert 0.0 < amounts[0] < 0.2                                  # começa devagar (suavizado)
    session.close()
    closing = []
    for _ in range(40):
        session.update(LID_SECONDS / 10)
        update = session.take_lid_update()
        if update is not None:
            closing.append(update[1])
    assert closing == sorted(closing, reverse=True) and closing[-1] == 0.0
    assert session.lid_chest is None and session.take_lid_update() is None     # soltou o baú depois de fechar


def test_the_lid_keeps_the_chest_until_it_is_shut_and_another_chest_waits():
    from src.interactive.chest_session import LID_SECONDS
    session = ChestSession()
    first, second = SimpleNamespace(name="um"), SimpleNamespace(name="dois")
    session.open(first)
    session.update(LID_SECONDS)                                    # aberta de vez
    session.close()
    session.update(LID_SECONDS / 4)                                # ainda fechando
    assert session.lid_chest is first and 0.0 < session.lid < 1.0
    assert not session.open(second)                                # o outro espera a tampa fechar
    session.update(LID_SECONDS)
    session.take_lid_update()
    assert session.open(second) and session.lid_chest is second
    # reabrir o mesmo baú no meio do fechamento continua de onde a tampa está, sem pulo
    session.close()
    session.update(LID_SECONDS / 5)
    middle = session.lid
    assert session.open(second) and session.lid == middle


def test_the_tool_hands_the_lid_amount_to_the_chest_mesh_of_that_structure():
    from src.interactive.schematic_tool import SchematicTool

    class FakeMeshes:
        def __init__(self):
            self.calls = []

        def rebuild_chests(self, lids=None):
            self.calls.append(lids)

    mesh = FakeMeshes()
    chest = SimpleNamespace(structure=SimpleNamespace(mesh=mesh), local=(2, 1, 3))
    tool = SchematicTool()
    tool.set_chest_lid(chest, 0.25)
    tool.set_chest_lid(chest, 0.0)
    assert mesh.calls == [{(2, 1, 3): 0.25}, None]                 # fechada de vez: sem entrada, o baú sai fechado
    tool.set_chest_lid(SimpleNamespace(structure=SimpleNamespace(mesh=None), local=(0, 0, 0)), 1.0)  # sem malha: nada
