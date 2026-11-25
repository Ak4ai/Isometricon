"""O atalho do raio do sol (o mapa de alturas por quadrante) dá exatamente a mesma luz que o raio passo a passo."""

import math

import numpy as np

from src.rendering.sun_shadows import column_horizons, cone_rise, quadrant_channel

SOLID, WATER = 255, 128
WATER_TRANSMIT = 0.82


def trace(values, origin, direction, horizons=None, rise=0.0):
    """Cópia em Python de ``traceSun`` (assets/shaders/world_textured.frag). ``values`` é [x, y, z]."""
    size = np.array(values.shape)
    cell = np.floor(origin).astype(int)
    safe = np.array([d if abs(d) >= 1e-5 else 1e-5 for d in direction])
    step = np.sign(safe).astype(int)
    delta = np.abs(1.0 / safe)
    frac = origin - np.floor(origin)
    t_max = np.where(safe > 0, 1.0 - frac, frac) * delta
    channel = quadrant_channel(step[0], step[2])
    use_horizon = horizons is not None and step[1] > 0 and safe[1] >= rise * math.hypot(safe[0], safe[2])
    light = 1.0
    for _ in range(56):
        if np.any(cell < 0) or np.any(cell >= size):
            return light
        if use_horizon and cell[1] >= horizons[cell[0], cell[2], channel]:
            return light
        value = values[tuple(cell)]
        if value > 0.75 * 255:
            return 0.0
        if value > 0.25 * 255:
            light *= WATER_TRANSMIT
        if t_max[0] < t_max[1] and t_max[0] < t_max[2]:
            cell[0] += step[0]; t_max[0] += delta[0]
        elif t_max[1] < t_max[2]:
            cell[1] += step[1]; t_max[1] += delta[1]
        else:
            cell[2] += step[2]; t_max[2] += delta[2]
    return light


def random_world(rng, size=(14, 12, 13)):
    """Um terreno de colunas com morros, algumas árvores soltas no ar e poças de água."""
    sx, sy, sz = size
    values = np.zeros(size, dtype=np.uint8)
    ground = rng.integers(0, sy // 2, size=(sx, sz))
    for x in range(sx):
        for z in range(sz):
            values[x, :ground[x, z], z] = SOLID
            if rng.random() < 0.15:
                values[x, ground[x, z]:ground[x, z] + rng.integers(1, 4), z] = WATER
    for _ in range(rng.integers(0, 6)):  # blocos soltos (copas, beirais)
        values[rng.integers(sx), rng.integers(sy), rng.integers(sz)] = rng.choice([SOLID, WATER])
    return values


def test_without_rise_the_horizon_is_one_above_the_highest_filled_cell_in_the_quadrant_ahead():
    values = np.zeros((3, 5, 2), dtype=np.uint8)
    values[0, 3, 0] = SOLID
    values[2, 1, 1] = WATER
    horizons = column_horizons(values)
    assert horizons.shape == (3, 2, 4)
    plus_plus = horizons[..., quadrant_channel(1, 1)]
    minus_minus = horizons[..., quadrant_channel(-1, -1)]
    assert plus_plus[0, 0] == 4 and plus_plus[1, 0] == 2 and plus_plus[1, 1] == 2 and plus_plus[0, 1] == 2
    assert minus_minus[2, 1] == 4 and minus_minus[0, 0] == 4 and minus_minus[1, 0] == 4 and minus_minus[2, 0] == 4
    assert horizons[1, 1, quadrant_channel(-1, 1)] == 0  # x <= 1 e z >= 1: nada


def test_a_rising_ray_discounts_far_columns():
    values = np.zeros((20, 12, 1), dtype=np.uint8)
    values[19, :10, 0] = SOLID                                    # um muro de 10 no fim
    flat = column_horizons(values)[..., quadrant_channel(1, 1)][:, 0]
    rising = column_horizons(values, rise=0.5)[..., quadrant_channel(1, 1)][:, 0]
    assert (flat == 10).all()
    assert rising[19] == 10 and rising[18] == 10 and rising[17] == 10 and rising[0] <= 4  # de longe passa por cima


def test_cone_rise_is_the_lowest_ray_of_the_cone():
    sun = np.array([0.55, 0.26, 0.7])
    rise = cone_rise(sun)
    assert 0.0 < rise < 0.26 / math.hypot(0.55, 0.7)
    assert cone_rise((0.3, -0.01, 0.2)) == 0.0                    # o cone chega ao horizonte: sem desconto


def test_the_shortcut_gives_the_same_light_as_the_full_ray():
    rng = np.random.default_rng(7)
    checked = shortcuts = 0
    for _ in range(150):
        values = random_world(rng)
        rise = rng.choice([0.0, 0.1, 0.3, 1.0])
        horizons = column_horizons(values, rise)
        size = np.array(values.shape)
        for _ in range(60):
            origin = rng.random(3) * size
            # do sol baixo do jogo (16 graus) ao quase a pino, em qualquer rumo; às vezes num eixo exato
            elevation = rng.uniform(0.02, 1.5)
            heading = rng.uniform(0, 2 * math.pi) if rng.random() > 0.2 else rng.integers(4) * math.pi / 2
            direction = np.array([math.cos(heading) * math.cos(elevation), math.sin(elevation),
                                  math.sin(heading) * math.cos(elevation)])
            assert trace(values, origin, direction, horizons, rise) == trace(values, origin, direction)
            shortcuts += math.tan(elevation) >= rise
            checked += 1
    assert checked == 9000 and shortcuts > 4000


# ------------------------------------------------------------------------------------- blocos parciais
def test_shadow_boxes_follow_the_shape_of_the_block():
    from src.world.block_shapes import shadow_boxes
    assert shadow_boxes("minecraft:stone") == ()
    assert shadow_boxes("minecraft:oak_slab[type=bottom]") == (((0.0, 0.0, 0.0), (1.0, 0.5, 1.0)),)
    post = shadow_boxes("minecraft:oak_fence[east=false,north=false,south=false,west=false]")
    assert post == (((0.375, 0.0, 0.375), (0.625, 1.0, 0.625)),)           # a cerca é só o poste fino
    assert len(shadow_boxes("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]")) == 2


def test_the_same_shape_gets_the_same_number():
    from src.world.shadow_shapes import TABLE
    a = TABLE.id_for("minecraft:oak_slab[type=bottom]")
    assert a > 0 and TABLE.id_for("minecraft:stone_slab[type=bottom]") == a
    assert TABLE.id_for("minecraft:stone") == 0
    np.testing.assert_allclose(TABLE.boxes(a), [[[0, 0, 0], [1, 0.5, 1]]])


def test_partial_and_decoration_blocks_go_to_the_mask_with_their_shape():
    from src.rendering.sun_shadows import PARTIAL_VALUE, SOLID_VALUE, mask_values, shape_texels
    from src.world.room_reveal import extract_window_cells
    from src.world.schematic import Schematic
    from src.world.shadow_shapes import TABLE
    from src.world.structure_layer import PlacedStructure

    grid = np.full((1, 1, 3), "minecraft:stone", dtype=object)
    grid[0, 0, 1] = "minecraft:oak_slab[type=bottom]"
    grid[0, 0, 2] = "minecraft:stone_pressure_plate"            # não barra o personagem, mas faz sombra
    placed = PlacedStructure("t", Schematic(3, 1, 1, grid, {}, "t"), (0, 0, 0))
    window = extract_window_cells((0, 0, 0), {}, [placed])
    values, ids = mask_values(window), shape_texels(window)
    assert values[0, 0, 0] == SOLID_VALUE and tuple(ids[0, 0, 0]) == (0, 0)
    slab = TABLE.id_for("minecraft:oak_slab[type=bottom]")
    assert values[1, 0, 0] == PARTIAL_VALUE and tuple(ids[1, 0, 0]) == (slab & 0xFF, slab >> 8)
    assert values[2, 0, 0] == PARTIAL_VALUE


def test_plants_get_their_own_value_in_the_mask():
    from src.rendering.sun_shadows import PLANT_VALUE, mask_values
    from src.world.room_reveal import extract_window_cells
    from src.world.schematic import Schematic
    from src.world.structure_layer import PlacedStructure

    grid = np.full((1, 1, 1), "minecraft:oak_sapling[stage=0]", dtype=object)
    placed = PlacedStructure("t", Schematic(1, 1, 1, grid, {}, "t"), (0, 0, 0))
    assert mask_values(extract_window_cells((0, 0, 0), {}, [placed]))[0, 0, 0] == PLANT_VALUE


def test_plants_cast_the_drawing_of_their_texture():
    from src.world.block_shapes import shadow_plant
    from src.world.shadow_shapes import TABLE
    assert shadow_plant("minecraft:oak_sapling[stage=0]") == ("oak_sapling", 0.0, 1.0)
    assert shadow_plant("minecraft:fire") is None                   # o fogo é luz
    assert shadow_plant("minecraft:rail[shape=north_south]") is None
    shape = TABLE.id_for("minecraft:oak_sapling[stage=0]")
    mask_row = TABLE.texels()[shape][0]
    assert mask_row[3] == 2.0                                       # a marca de planta
    drawing = TABLE.plant_masks()[int(mask_row[0]) * 16:int(mask_row[0]) * 16 + 16]
    assert 0 < (drawing > 0).sum() < 256                            # tem folha e tem fresta


def test_shadow_detail_levels_go_from_cubes_to_grass():
    from src.rendering.sun_shadows import (DETAIL_CUBES, DETAIL_FULL, DETAIL_PLANTS, DETAIL_SHAPES, PARTIAL_VALUE,
                                           PLANT_VALUE, SOLID_VALUE, mask_values)
    from src.world.room_reveal import extract_window_cells
    from src.world.schematic import Schematic
    from src.world.structure_layer import PlacedStructure

    grid = np.array([[["minecraft:oak_slab[type=bottom]", "minecraft:stone_pressure_plate",
                       "minecraft:oak_sapling[stage=0]", "minecraft:short_grass"]]], dtype=object)
    placed = PlacedStructure("t", Schematic(4, 1, 1, grid, {}, "t"), (0, 0, 0))
    window = extract_window_cells((0, 0, 0), {}, [placed])
    row = lambda detail: [int(v) for v in mask_values(window, detail)[:4, 0, 0]]
    assert row(DETAIL_CUBES) == [SOLID_VALUE, 0, 0, 0]               # como antes: a laje é cubo, o resto não tapa
    assert row(DETAIL_SHAPES) == [PARTIAL_VALUE, PARTIAL_VALUE, 0, 0]
    assert row(DETAIL_PLANTS) == [PARTIAL_VALUE, PARTIAL_VALUE, PLANT_VALUE, 0]   # sem o capim
    assert row(DETAIL_FULL) == [PARTIAL_VALUE, PARTIAL_VALUE, PLANT_VALUE, PLANT_VALUE]


def test_shadow_distance_grows_the_window_one_chunk_each_side():
    from src.rendering.sun_shadows import far_window_origin, far_window_size
    from src.world.room_reveal import WINDOW
    assert far_window_size(1) == WINDOW
    assert far_window_size(2)[0] == WINDOW[0] + 32
    assert far_window_size(6)[0] == far_window_size(6)[2] == WINDOW[0] + 160
    size = far_window_size(4)
    ox, oy, oz = far_window_origin((10.5, 40.2, -3.0), size)
    assert (ox + size[0] // 2, oz + size[2] // 2) == (10, -3) and oy < 40 < oy + size[1]


def test_the_far_window_reads_every_loaded_chunk_inside_it():
    from src.rendering.sun_shadows import far_window_origin, far_window_size
    from src.world.chunk import Chunk3D
    from src.world.room_reveal import extract_window_cells
    far = Chunk3D.__new__(Chunk3D)
    far.blocks = np.zeros((16, 16, 16), dtype=np.uint8)
    far.blocks[3, 5, 3] = 1                       # um bloco a 3 chunks do jogador
    size = far_window_size(4)
    origin = far_window_origin((0, 2, 0), size)
    window = extract_window_cells(origin, {(3, 0, 3): far}, (), size)
    assert window.solid.shape == size
    assert window.solid[48 + 3 - origin[0], 5 - origin[1], 48 + 3 - origin[2]]
