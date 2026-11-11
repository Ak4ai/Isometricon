"""Salto com Espaço, escadas de mão e os blocos com forma nova (plantas em cruz, tocha, fogo, trilhos...)."""

import glfw
import numpy as np
import pytest

from src.integration.voxel_grid import VoxelGridProvider
from src.interactive.token_system import CLIMB_SPEED, PlayerToken
from src.rendering.atlas import TextureAtlas
from src.world import BlockType, Chunk3D, ChunkMesher, Schematic, StructureMesher
from src.world.block import CUBE_LUT, is_ladder, is_shaped, is_solid, ladder_wall_direction
from src.world.block_shapes import Box, Quad, collides, quad_vertices, shape_for
from src.world.room_reveal import extract_window_cells
from src.world.structure_layer import PlacedStructure, StructureLayer
from src.world.terrain import TerrainGenerator

DT = 1.0 / 60.0
EAST = np.array([1.0, 0.0, 0.0], dtype=np.float32)
SOUTH = np.array([0.0, 0.0, 1.0], dtype=np.float32)


class DictWorld:
    """Mundo de teste: as células dadas (x, y, z) -> BlockType; o resto é ar."""

    def __init__(self, blocks):
        self.blocks = dict(blocks)

    def get_block_at(self, x, y, z):
        return self.blocks.get((x, y, z), BlockType.AIR)


def floor(size=4):
    return {(x, 0, z): BlockType.STONE for x in range(-size, size + 1) for z in range(-size, size + 1)}


def run(token, world, keys, frames, forward=EAST, right=SOUTH):
    peak = float(token.position[1])
    for _ in range(frames):
        token.update(DT, keys, forward, right, world)
        peak = max(peak, float(token.position[1]))
    return peak


def token_at(x, y, z):
    token = PlayerToken(start_x=x, start_z=z, create_mesh=False)
    token.position[1] = y
    return token


# ------------------------------------------------------------------------------------------- salto
def test_walking_into_a_block_stops_without_climbing_it():
    world = DictWorld({**floor(), (1, 1, 0): BlockType.STONE})
    token = token_at(0.5, 1.0, 0.5)
    run(token, world, {glfw.KEY_W: True}, 60)
    assert token.position[0] < 1.0          # encostou no degrau
    assert token.position[1] == pytest.approx(1.0)  # e não subiu sozinho


def test_space_jumps_onto_a_one_block_step():
    world = DictWorld({**floor(), (1, 1, 0): BlockType.STONE, (2, 1, 0): BlockType.STONE})
    token = token_at(0.5, 1.0, 0.5)
    run(token, world, {}, 5)
    assert token.grounded
    run(token, world, {glfw.KEY_W: True, glfw.KEY_SPACE: True}, 12)
    run(token, world, {glfw.KEY_W: True}, 30)
    assert token.position[0] > 1.3
    assert token.position[1] == pytest.approx(2.0)  # em cima do degrau
    assert token.grounded


def test_space_only_jumps_from_the_ground():
    world = DictWorld(floor())
    token = token_at(0.5, 1.0, 0.5)
    run(token, world, {}, 5)
    # segurando o Espaço o salto é um só por vez: no ar não ganha impulso de novo
    peak = run(token, world, {glfw.KEY_SPACE: True}, 30)
    assert 2.1 < peak < 2.5
    # no ar, sem chão, o Espaço não faz nada
    falling = token_at(0.5, 8.0, 0.5)
    falling.update(DT, {}, EAST, SOUTH, DictWorld(floor()))
    assert not falling.grounded
    falling.update(DT, {glfw.KEY_SPACE: True}, EAST, SOUTH, DictWorld(floor()))
    assert falling.vertical_velocity < 0.0


# ------------------------------------------------------------------------------------------- escada
def ladder_world():
    """Muro de 4 blocos de altura em z = 1 e escada de mão encostada nele em x = 0, de y = 1 a 4 (olhando para o
    norte)."""
    blocks = floor()
    for y in range(1, 5):
        for x in range(-4, 5):
            blocks[(x, y, 1)] = BlockType.STONE
        blocks[(0, y, 0)] = BlockType.LADDER_NORTH
    return DictWorld(blocks)


def test_ladder_geometry_helpers():
    assert is_ladder(BlockType.LADDER_NORTH) and not is_ladder(BlockType.STONE)
    assert ladder_wall_direction(BlockType.LADDER_NORTH) == (0, 1)
    assert ladder_wall_direction(BlockType.LADDER_EAST) == (-1, 0)
    assert not is_solid(BlockType.LADDER_WEST) and is_shaped(BlockType.LADDER_WEST)


def test_w_climbs_and_standing_still_holds_on_the_ladder():
    world = ladder_world()
    token = token_at(0.5, 1.0, 0.5)
    run(token, world, {}, 3)
    # W sobe, mesmo com a câmera olhando ao longo da parede (W aponta para o leste)
    run(token, world, {glfw.KEY_W: True}, 30)
    assert token.on_ladder
    height = float(token.position[1])
    assert height == pytest.approx(1.0 + CLIMB_SPEED * 30 * DT, abs=0.05)
    assert abs(token.position[0] - 0.5) < 0.05  # o W não tirou o personagem da escada
    # parado na escada: não cai
    run(token, world, {}, 60)
    assert float(token.position[1]) == pytest.approx(height)


def test_s_descends_the_ladder_to_the_floor():
    world = ladder_world()
    token = token_at(0.5, 3.5, 0.5)
    run(token, world, {}, 3)
    assert float(token.position[1]) == pytest.approx(3.5)
    run(token, world, {glfw.KEY_S: True}, 90)
    assert float(token.position[1]) == pytest.approx(1.0)
    assert token.grounded


def test_walking_into_the_ladder_wall_climbs():
    world = ladder_world()
    token = token_at(0.5, 1.0, 0.5)
    run(token, world, {}, 3)
    run(token, world, {glfw.KEY_D: True}, 20)   # D aponta para o sul, contra a parede da escada
    assert token.position[1] > 1.5


@pytest.mark.parametrize("dt", [1 / 60, 1 / 30, 1 / 12])
def test_climbing_to_the_top_steps_onto_the_wall(dt):
    # W aponta para longe da parede (a câmera olha de lado): mesmo assim, no topo, o personagem passa para cima
    world = ladder_world()
    token = token_at(0.5, 1.0, 0.5)
    away = np.array([-0.7, 0.0, -0.7], dtype=np.float32)
    side = np.array([0.7, 0.0, -0.7], dtype=np.float32)
    for _ in range(3):
        token.update(dt, {}, away, side, world)
    for _ in range(int(4.0 / dt)):   # W até sair da escada por cima (aí o jogador solta o W)
        token.update(dt, {glfw.KEY_W: True}, away, side, world)
        if not token.on_ladder and token.position[2] > 1.0:
            break
    for _ in range(int(1.0 / dt)):
        token.update(dt, {}, away, side, world)
    assert token.position[2] > 1.0                      # passou para cima do muro
    assert float(token.position[1]) == pytest.approx(5.0)
    assert token.grounded and not token.on_ladder


def test_structure_ladders_are_climbable_through_the_layer_lookup():
    grid = np.full((3, 2, 1), "minecraft:air", dtype=object)
    for y in range(3):
        grid[y, 1, 0] = "minecraft:stone"
        grid[y, 0, 0] = "minecraft:ladder[facing=north]"
    layer = StructureLayer()
    layer.add("t", Schematic(1, 3, 2, grid, palette={}, name="t"), (0, 1, 0))
    lookup = layer.wrap_lookup(lambda x, y, z: BlockType.STONE if y <= 0 else BlockType.AIR)
    assert lookup(0, 1, 0) is BlockType.LADDER_NORTH
    assert lookup(0, 1, 1) is BlockType.STONE
    token = token_at(0.5, 1.0, 0.5)
    world = VoxelGridProvider(block_lookup=lookup)
    run(token, world, {}, 3)
    run(token, world, {glfw.KEY_W: True}, 20)
    assert token.on_ladder and token.position[1] > 1.5


# ------------------------------------------------------------------------------------------- formas
def test_plants_are_crosses_that_do_not_collide():
    for name in ("minecraft:poppy", "minecraft:short_grass", "minecraft:oak_sapling", "minecraft:red_mushroom",
                 "minecraft:tall_grass[half=upper]", "minecraft:wheat[age=7]", "minecraft:fire",
                 "minecraft:crimson_roots", "minecraft:red_tulip"):
        parts = shape_for(name)
        assert parts is not None and len(parts) == 2, name
        assert all(isinstance(p, Quad) for p in parts), name
        assert not collides(name), name
    assert shape_for("minecraft:tall_grass[half=upper]")[0].texture == "tall_grass_top"
    assert shape_for("minecraft:wheat[age=7]")[0].texture == "wheat_stage7"
    assert shape_for("minecraft:carrots[age=7]")[0].texture == "carrots_stage3"
    assert shape_for("minecraft:fire")[0].texture == "fire_0"
    assert shape_for("minecraft:short_grass")[0].tint is not None   # a textura cinza ganha verde
    assert shape_for("minecraft:mangrove_roots") is None             # raiz de mangue é um bloco inteiro


def test_flat_and_wall_shapes():
    rail = shape_for("minecraft:rail[shape=east_west]")
    assert len(rail) == 1 and all(c[1] == 1.0 for c in rail[0].corners)
    assert shape_for("minecraft:rail[shape=north_east]")[0].texture == "rail_corner"
    assert shape_for("minecraft:powered_rail[shape=north_south,powered=true]")[0].texture == "powered_rail_on"
    ramp = shape_for("minecraft:rail[shape=ascending_east]")[0]
    high = [c for c in ramp.corners if c[1] > 16]
    assert len(high) == 2 and all(c[0] == 16.0 for c in high)   # sobe para o leste
    vine = shape_for("minecraft:vine[north=true,east=true]")
    assert len(vine) == 2 and not collides("minecraft:vine[north=true]")
    assert not collides("minecraft:rail") and not collides("minecraft:lily_pad")
    # a fogueira: toras com colisão e o fogo em cruz por cima
    campfire = shape_for("minecraft:campfire[lit=true]")
    assert sum(isinstance(p, Box) for p in campfire) == 4 and sum(isinstance(p, Quad) for p in campfire) == 2
    assert collides("minecraft:campfire")


def test_ladder_is_a_thin_plane_against_its_wall():
    for facing, axis, value in (("north", 2, 16 - 0.8), ("south", 2, 0.8), ("east", 0, 0.8), ("west", 0, 16 - 0.8)):
        (plane,) = shape_for(f"minecraft:ladder[facing={facing}]")
        assert isinstance(plane, Quad) and plane.texture == "ladder"
        assert all(c[axis] == pytest.approx(value) for c in plane.corners), facing


def test_quad_vertices_are_two_sided():
    quad = shape_for("minecraft:poppy")[0]
    verts = quad_vertices(quad, np.zeros(3, dtype=np.float32), (0.0, 0.0, 1.0, 1.0))
    assert verts.shape == (8, 11)
    np.testing.assert_allclose(verts[0, 3:6], -verts[4, 3:6])
    assert verts[:, :3].min() >= 0.0 and verts[:, :3].max() <= 1.0


def test_structure_mesher_draws_a_plant_as_four_quads():
    grid = np.full((1, 1, 2), "minecraft:air", dtype=object)
    grid[0, 0, 0] = "minecraft:poppy"
    grid[0, 0, 1] = "minecraft:stone"
    schem = Schematic(2, 1, 1, grid, palette={}, name="t")
    assert not schem.solid_mask[0, 0, 0] and schem.occupied_mask[0, 0, 0] and not schem.full_cube_mask[0, 0, 0]
    verts, inds = StructureMesher.build_arrays(schem, lambda name, face: (0.0, 0.0, 1.0, 1.0))
    # o cubo mostra as 6 faces (a planta não esconde nada) e a planta, 2 planos x 2 lados
    assert len(inds) // 6 == 6 + 4
    assert inds.max() < len(verts) // 11


def test_terrain_mesher_draws_shaped_blocks():
    atlas = TextureAtlas()
    chunk = Chunk3D()
    chunk.set_block(1, 1, 1, BlockType.POPPY)
    chunk.set_block(2, 1, 1, BlockType.STONE)
    data = ChunkMesher(atlas).build(chunk)
    # a pedra mostra as 6 faces: a papoula não é opaca; a papoula vira 4 quads em X
    assert data.face_count == 6 + 4
    plant = data.vertices[-16:]
    assert plant[:, 0].min() >= 1.0 and plant[:, 0].max() <= 2.0
    u0, v0, u1, v1 = atlas.tile_rects["poppy"]
    assert plant[:, 6].min() == pytest.approx(u0) and plant[:, 6].max() == pytest.approx(u1)

    ladder = Chunk3D()
    ladder.set_block(3, 3, 3, BlockType.LADDER_EAST)
    quads = ChunkMesher(atlas).build(ladder).vertices
    assert len(quads) == 8 and np.allclose(quads[:, 0], 3.05)   # rente à parede do oeste

    torch = Chunk3D()
    torch.set_block(0, 0, 0, BlockType.TORCH)
    verts = ChunkMesher(atlas).build(torch).vertices
    assert verts[:, 1].max() == pytest.approx(10 / 16)           # a haste da tocha, não um cubo


def test_shaped_terrain_blocks_are_not_walls_in_the_room_mask():
    chunk = Chunk3D()
    chunk.set_block(1, 1, 1, BlockType.SHORT_GRASS)
    chunk.set_block(2, 1, 1, BlockType.LADDER_NORTH)
    chunk.set_block(3, 1, 1, BlockType.STONE)
    cells = extract_window_cells((0, 0, 0), {(0, 0, 0): chunk})
    assert not cells.solid[1, 1, 1] and not cells.solid[2, 1, 1] and cells.solid[3, 1, 1]
    assert cells.occupied[1, 1, 1] and cells.occupied[2, 1, 1]
    assert not cells.culls[1, 1, 1] and not cells.roof[2, 1, 1]
    assert not CUBE_LUT[int(BlockType.TORCH)] and CUBE_LUT[int(BlockType.STONE)]


def test_top_solid_block_skips_plants():
    chunk = Chunk3D()
    chunk.set_block(0, 4, 0, BlockType.GRASS)
    chunk.set_block(0, 5, 0, BlockType.SHORT_GRASS)
    provider = VoxelGridProvider({(0, 0, 0): chunk})
    assert provider.get_top_solid_block(0, 0) == 4
    dynamic = VoxelGridProvider(block_lookup=lambda x, y, z: chunk.get_block(x, y, z) if 0 <= y < 16 else 0)
    assert dynamic.get_top_solid_block(0, 0) == 4


def test_vegetation_grows_only_on_grass_and_is_reproducible():
    positions = [(x, 0, z) for x in range(-1, 1) for z in range(-1, 1)]
    a = TerrainGenerator(seed=350665, vegetation=True).generate_region(positions)
    b = TerrainGenerator(seed=350665, vegetation=True).generate_region(positions)
    plain = TerrainGenerator(seed=350665).generate_region(positions)
    plants = 0
    for key, chunk in a.items():
        np.testing.assert_array_equal(chunk.blocks, b[key].blocks)
        shaped = np.argwhere(np.isin(chunk.blocks, [int(t) for t in BlockType if is_shaped(t)]))
        for x, y, z in shaped:
            assert y > 0 and chunk.blocks[x, y - 1, z] == int(BlockType.GRASS)
        plants += len(shaped)
        # fora as plantas, o terreno é o mesmo de sempre
        mask = ~np.isin(chunk.blocks, [int(t) for t in BlockType if is_shaped(t)])
        np.testing.assert_array_equal(chunk.blocks[mask], plain[key].blocks[mask])
    assert plants > 0


def test_place_block_picks_the_ladder_facing_from_the_wall():
    from src.world.manager import WorldManager

    manager = WorldManager(TerrainGenerator(seed=1), render_distance=1, create_gl_meshes=False)
    chunk = Chunk3D(0, 0, 0)
    chunk.set_block(5, 14, 6, BlockType.STONE)
    manager.chunks[(0, 0, 0)] = chunk
    assert manager.place_block(5, 14, 5, BlockType.LADDER_NORTH) is BlockType.LADDER_NORTH  # parede ao sul
    assert manager.place_block(7, 14, 6, BlockType.LADDER_NORTH) is None   # sem parede ao lado: não há onde prender
    assert manager.place_block(6, 14, 6, BlockType.LADDER_NORTH) is BlockType.LADDER_EAST  # parede a oeste
    assert manager.place_block(5, 14, 6, BlockType.TORCH) is None          # ocupado
    assert chunk.get_block(5, 14, 5) is BlockType.LADDER_NORTH
