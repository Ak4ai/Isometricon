"""Água com as regras do Minecraft: fonte, corrente, queda, direção da descida e fonte infinita."""

from src.world.block import BlockType
from src.world.water import FALLING, MAX_LEVEL, SOURCE, WaterSimulation, surface_height


class DictWorld:
    """Um mundo pequeno: chão de pedra em y = 0 numa área limitada; fora dela, desconhecido."""

    def __init__(self, size=20, floor=True):
        self.size = size
        self.cells = {}
        if floor:
            for x in range(-size, size + 1):
                for z in range(-size, size + 1):
                    self.cells[(x, 0, z)] = BlockType.STONE

    def block(self, x, y, z):
        if abs(x) > self.size or abs(z) > self.size or y < 0 or y > 30:
            return None
        return self.cells.get((x, y, z), BlockType.AIR)

    def set_block(self, x, y, z, block):
        if block is BlockType.AIR:
            self.cells.pop((x, y, z), None)
        else:
            self.cells[(x, y, z)] = block


def run(sim, ticks):
    for _ in range(ticks):
        sim.step()


def water_cells(world):
    return {c for c, b in world.cells.items() if b is BlockType.WATER}


def place_source(world, sim, cell):
    world.set_block(*cell, BlockType.WATER)
    sim.wake([cell])


def test_a_source_on_flat_ground_spreads_seven_blocks_and_stops():
    world = DictWorld()
    sim = WaterSimulation(world)
    place_source(world, sim, (0, 1, 0))
    run(sim, 30)
    assert sim.level((7, 1, 0)) == MAX_LEVEL
    assert sim.level((8, 1, 0)) is None                 # passa de 7, não há água
    assert sim.level((1, 1, 0)) == 1 and sim.level((4, 1, 3)) == 7  # um nível por passo, em distância de Manhattan
    assert not sim.busy                                 # assentou


def test_water_advances_one_block_per_update():
    world = DictWorld()
    sim = WaterSimulation(world)
    place_source(world, sim, (0, 1, 0))
    sim.step()
    assert sim.level((1, 1, 0)) == 1 and sim.level((2, 1, 0)) is None
    sim.step()
    assert sim.level((2, 1, 0)) == 2


def test_water_falls_in_a_column_and_spreads_where_it_lands():
    world = DictWorld()
    sim = WaterSimulation(world)
    world.set_block(0, 5, 0, BlockType.STONE)          # uma plataforma no alto
    place_source(world, sim, (0, 6, 0))
    run(sim, 40)
    assert sim.level((1, 6, 0)) == 1                    # sai da fonte para o lado
    assert sim.level((1, 5, 0)) == FALLING              # e cai da beira
    assert sim.level((1, 1, 0)) == FALLING              # até o chão, cheia
    assert sim.level((2, 1, 0)) == 1                    # e ao chegar ao chão se espalha de novo


def test_flowing_water_that_can_fall_does_not_spread_sideways():
    world = DictWorld()
    sim = WaterSimulation(world)
    world.set_block(0, 5, 0, BlockType.STONE)
    place_source(world, sim, (0, 6, 0))
    run(sim, 40)
    # a corrente em (1, 6, 0) tem ar embaixo: cai, e não continua para (2, 6, 0)
    assert sim.level((2, 6, 0)) is None


def test_flow_prefers_the_nearest_drop():
    world = DictWorld()
    sim = WaterSimulation(world)
    for x in range(-6, 7):
        for z in range(-6, 7):
            world.set_block(x, 1, z, BlockType.STONE)   # um piso elevado em y = 1
    world.set_block(3, 1, 0, BlockType.AIR)            # com um buraco a 3 blocos a leste
    place_source(world, sim, (0, 2, 0))
    run(sim, 3)
    # a fonte se espalha para todos os lados, mas a corrente segue só para o lado do buraco
    assert sim.level((2, 2, 0)) == 2
    assert sim.level((-2, 2, 0)) is None and sim.level((1, 2, 1)) is None


def test_two_sources_make_an_infinite_source_between_them():
    world = DictWorld()
    sim = WaterSimulation(world)
    for x in (-1, 0, 1):
        for z in (-1, 0, 1):
            world.set_block(x, 2, z, BlockType.STONE)  # uma vala de 3 blocos: paredes dos lados
    for x in (-1, 0, 1):
        world.set_block(x, 2, 0, BlockType.AIR)
    for z in (-2, 2):
        for x in range(-2, 3):
            world.set_block(x, 1, z, BlockType.STONE)
    place_source(world, sim, (-1, 1, 0))
    place_source(world, sim, (1, 1, 0))
    run(sim, 5)
    assert sim.level((0, 1, 0)) == SOURCE


def test_water_dries_up_when_its_source_is_removed():
    world = DictWorld()
    sim = WaterSimulation(world)
    place_source(world, sim, (0, 1, 0))
    run(sim, 30)
    assert len(water_cells(world)) > 50
    world.set_block(0, 1, 0, BlockType.AIR)
    sim.wake([(0, 1, 0)])
    run(sim, 30)
    assert water_cells(world) == set()


def test_water_never_enters_unknown_chunks():
    world = DictWorld(size=3)
    sim = WaterSimulation(world)
    place_source(world, sim, (0, 1, 0))
    run(sim, 30)
    assert all(abs(x) <= 3 and abs(z) <= 3 for x, _, z in water_cells(world))


def test_surface_heights_follow_the_level():
    assert surface_height(SOURCE) == 1.0 and surface_height(FALLING) == 1.0
    assert surface_height(1) == 7 / 8 and surface_height(MAX_LEVEL) == 1 / 8
    world = DictWorld()
    sim = WaterSimulation(world)
    place_source(world, sim, (0, 1, 0))
    run(sim, 3)
    assert sim.heights[(1, 1, 0)] == surface_height(1) and (0, 1, 0) not in sim.heights  # a fonte fica no padrão


def test_a_step_split_over_frames_gives_the_same_water():
    """A onda avaliada aos poucos (algumas células por quadro) chega à mesma água que de uma vez."""
    whole_world, split_world = DictWorld(), DictWorld()
    whole, split = WaterSimulation(whole_world), WaterSimulation(split_world)
    for world, sim in ((whole_world, whole), (split_world, split)):
        place_source(world, sim, (0, 1, 0))
        world.set_block(3, 1, 0, BlockType.STONE)
        place_source(world, sim, (-4, 6, 2))
    for _ in range(25):
        whole.step()
        split.begin_step()
        changed = None
        while changed is None:
            changed = split.advance(3)
            assert split.stepping == (changed is None)
    assert water_cells(whole_world) == water_cells(split_world)
    assert {c: whole.level(c) for c in water_cells(whole_world)} == {c: split.level(c) for c in water_cells(split_world)}
