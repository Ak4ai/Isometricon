"""Testes das formas de bloco que não são cubos inteiros (sem OpenGL)."""

import numpy as np
import pytest

from src.world import Schematic, StructureMesher
from src.world.block_shapes import (
    FACE_INDEX,
    FACES,
    Box,
    box_face_quad,
    collides,
    is_full_cube,
    parse_block,
    shape_for,
)
from src.world.room_caps import _structure_caps
from src.world.room_reveal import WindowCells
from src.world.shape_showcase import showcase_schematic
from src.world.structure_layer import PlacedStructure
from src.world.structure_mesher import FLOATS_PER_VERTEX


def boxes(name):
    shape = shape_for(name)
    assert shape is not None, name
    return shape


def extents(name):
    """Caixa que envolve a forma inteira: (lo, hi)."""
    shape = boxes(name)
    lo = tuple(min(b.lo[a] for b in shape) for a in range(3))
    hi = tuple(max(b.hi[a] for b in shape) for a in range(3))
    return lo, hi


def occupied_cells(name):
    """Grade 32x32x32 de voxels de 1/2 unidade, True onde a forma ocupa."""
    cells = np.zeros((32, 32, 32), dtype=bool)
    for b in boxes(name):
        lo = [int(round(v * 2)) for v in b.lo]
        hi = [int(round(v * 2)) for v in b.hi]
        cells[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] = True
    return cells


def test_parse_block_handles_namespace_and_properties():
    assert parse_block("minecraft:oak_stairs[facing=east,half=top]") == ("oak_stairs", {"facing": "east", "half": "top"})
    assert parse_block("minecraft:stone") == ("stone", {})
    assert parse_block("stone") == ("stone", {})


def test_cubes_have_no_shape():
    for name in ("minecraft:stone", "minecraft:oak_planks", "minecraft:oak_slab[type=double]", "minecraft:barrel[facing=up]",
                 "minecraft:brown_mushroom_block[down=true]", "minecraft:cherry_leaves[distance=1]"):
        assert shape_for(name) is None and is_full_cube(name)


def test_slabs():
    assert extents("minecraft:oak_slab[type=bottom]") == ((0, 0, 0), (16, 8, 16))
    assert extents("minecraft:oak_slab[type=top]") == ((0, 8, 0), (16, 16, 16))
    assert occupied_cells("minecraft:oak_slab[type=bottom]").sum() / (32 * 32 * 32) == 0.5
    assert occupied_cells("minecraft:oak_slab[type=top]").sum() / (32 * 32 * 32) == 0.5


@pytest.mark.parametrize("facing,region", [
    ("east", lambda c: c[16:32, 16:32, :].any() and not c[0:16, 16:32, :].any()),     # o degrau no lado leste (x grande)
    ("west", lambda c: c[0:16, 16:32, :].any() and not c[16:32, 16:32, :].any()),
    ("south", lambda c: c[:, 16:32, 16:32].any() and not c[:, 16:32, 0:16].any()),    # no sul (z grande)
    ("north", lambda c: c[:, 16:32, 0:16].any() and not c[:, 16:32, 16:32].any()),
])
def test_straight_stairs_climb_towards_their_facing(facing, region):
    cells = occupied_cells(f"minecraft:oak_stairs[facing={facing},half=bottom,shape=straight]")
    assert cells[0:32, 0:16, 0:32].all()      # a laje de baixo é inteira
    assert region(cells)


def test_stairs_volume_is_three_quarters_of_a_block():
    for shape, expected in (("straight", 0.75), ("outer_right", 0.625), ("outer_left", 0.625),
                            ("inner_right", 0.875), ("inner_left", 0.875)):
        cells = occupied_cells(f"minecraft:oak_stairs[facing=east,half=bottom,shape={shape}]")
        assert cells.sum() / (32 * 32 * 32) == pytest.approx(expected), shape


def test_stairs_top_half_is_the_mirror_in_y():
    bottom = occupied_cells("minecraft:oak_stairs[facing=south,half=bottom,shape=inner_left]")
    top = occupied_cells("minecraft:oak_stairs[facing=south,half=top,shape=inner_left]")
    assert np.array_equal(top, bottom[:, ::-1, :])


def test_stairs_corners_are_mirror_images():
    outer_r = occupied_cells("minecraft:oak_stairs[facing=east,half=bottom,shape=outer_right]")
    outer_l = occupied_cells("minecraft:oak_stairs[facing=east,half=bottom,shape=outer_left]")
    # o canto fica no lado sudeste (right) ou nordeste (left) quando se olha para leste
    assert outer_r[16:32, 16:32, 16:32].any() and not outer_r[16:32, 16:32, 0:16].any()
    assert outer_l[16:32, 16:32, 0:16].any() and not outer_l[16:32, 16:32, 16:32].any()
    assert np.array_equal(outer_l, outer_r[:, :, ::-1])


def test_trapdoors():
    assert extents("minecraft:oak_trapdoor[facing=north,half=bottom,open=false]") == ((0, 0, 0), (16, 3, 16))
    assert extents("minecraft:oak_trapdoor[facing=north,half=top,open=false]") == ((0, 13, 0), (16, 16, 16))
    # aberto, o painel encosta no lado oposto ao do facing (north -> sul, east -> oeste...)
    assert extents("minecraft:oak_trapdoor[facing=north,half=bottom,open=true]") == ((0, 0, 13), (16, 16, 16))
    assert extents("minecraft:oak_trapdoor[facing=south,half=bottom,open=true]") == ((0, 0, 0), (16, 16, 3))
    assert extents("minecraft:oak_trapdoor[facing=east,half=bottom,open=true]") == ((0, 0, 0), (3, 16, 16))
    assert extents("minecraft:oak_trapdoor[facing=west,half=bottom,open=true]") == ((13, 0, 0), (16, 16, 16))


def test_fence_grows_arms_only_where_it_connects():
    post = boxes("minecraft:oak_fence[east=false,north=false,south=false,west=false]")
    assert len(post) == 1 and post[0].lo == (6, 0, 6) and post[0].hi == (10, 16, 10)
    line = boxes("minecraft:oak_fence[east=true,north=false,south=false,west=true]")
    assert len(line) == 1 + 2 + 2
    assert extents("minecraft:oak_fence[east=true,north=false,south=false,west=true]") == ((0, 0, 6), (16, 16, 10))
    assert extents("minecraft:oak_fence[east=false,north=true,south=false,west=false]")[0] == (6, 0, 0)


def test_walls_have_low_and_tall_arms_and_an_optional_post():
    lo, hi = extents("minecraft:mud_brick_wall[east=low,north=none,south=none,up=true,west=none]")
    assert lo == (4, 0, 4) and hi == (16, 16, 12)
    arms = [b for b in boxes("minecraft:mud_brick_wall[east=low,north=none,south=none,up=false,west=tall]")]
    assert sorted(b.hi[1] for b in arms) == [14.0, 16.0]       # um braço baixo (14) e um alto (16), sem poste
    assert all(b.lo != (4, 0, 4) for b in arms)


def test_wall_signs_stick_to_the_opposite_side():
    assert extents("minecraft:cherry_wall_sign[facing=north]") == ((0, 4.5, 14), (16, 12.5, 16))
    assert extents("minecraft:cherry_wall_sign[facing=south]")[1][2] == 2.0
    assert extents("minecraft:cherry_wall_sign[facing=east]")[0][0] == 0.0
    assert extents("minecraft:cherry_wall_sign[facing=west]")[0][0] == 14.0


def test_doors_close_on_the_opposite_side_and_swing_open():
    closed = boxes("minecraft:cherry_door[facing=east,half=lower,hinge=left,open=false]")[0]
    assert (closed.lo, closed.hi) == ((0, 0, 0), (3, 16, 16)) and closed.texture == "cherry_door_bottom"
    opened = boxes("minecraft:cherry_door[facing=east,half=upper,hinge=left,open=true]")[0]
    assert opened.hi[2] == 3.0 and opened.texture == "cherry_door_top"      # gira para o lado da dobradiça
    other = boxes("minecraft:cherry_door[facing=east,half=lower,hinge=right,open=true]")[0]
    assert other.lo[2] == 13.0


def test_small_blocks():
    assert extents("minecraft:torch") == ((7, 0, 7), (9, 10, 9))
    assert extents("minecraft:stone_button[face=floor,facing=north,powered=false]") == ((5, 0, 6), (11, 2, 10))
    assert extents("minecraft:stone_button[face=ceiling,facing=north,powered=false]")[0][1] == 14.0
    assert extents("minecraft:stone_pressure_plate[powered=false]") == ((1, 0, 1), (15, 1, 15))
    assert extents("minecraft:stone_pressure_plate[powered=true]")[1][1] == 0.5
    assert extents("minecraft:pink_carpet") == ((0, 0, 0), (16, 1, 16))
    assert boxes("minecraft:pink_carpet")[0].texture == "pink_wool"
    assert extents("minecraft:chain[axis=x]") == ((0, 6.5, 6.5), (16, 9.5, 9.5))
    assert extents("minecraft:lantern[hanging=true]")[0][1] == 1.0
    assert boxes("minecraft:heavy_weighted_pressure_plate[power=0]")[0].texture == "iron_block"
    assert boxes("minecraft:potted_bamboo")[0].texture == "flower_pot"


def test_collision_only_for_blocks_that_stop_the_player():
    for name in ("minecraft:torch", "minecraft:wall_torch[facing=east]", "minecraft:pink_carpet", "minecraft:cherry_wall_sign[facing=north]",
                 "minecraft:stone_button[face=wall,facing=north]", "minecraft:cherry_pressure_plate", "minecraft:candle",
                 "minecraft:potted_bamboo", "minecraft:ladder[facing=north]", "minecraft:chain[axis=y]", "minecraft:lantern"):
        assert not collides(name), name
    for name in ("minecraft:stone", "minecraft:oak_slab[type=bottom]", "minecraft:oak_stairs[facing=east]", "minecraft:oak_fence",
                 "minecraft:mud_brick_wall", "minecraft:oak_trapdoor", "minecraft:anvil[facing=north]", "minecraft:cake"):
        assert collides(name), name


def test_covers_face_only_when_flush_and_whole():
    slab = Box((0, 0, 0), (16, 8, 16))
    assert slab.covers_face(FACE_INDEX["bottom"])            # a face de baixo é inteira e encosta
    assert not slab.covers_face(FACE_INDEX["top"])           # a de cima está no meio da célula
    assert not slab.covers_face(FACE_INDEX["east"])          # a lateral só tem a metade da altura
    post = Box((6, 0, 6), (10, 16, 10))
    assert not any(post.covers_face(f) for f in range(6))    # um poste nunca esconde nem é escondido


@pytest.mark.parametrize("name", [
    "minecraft:oak_stairs[facing=south,half=top,shape=inner_left]", "minecraft:oak_trapdoor[facing=east,half=bottom,open=true]",
    "minecraft:oak_fence[east=true,north=true,south=false,west=false]", "minecraft:mud_brick_wall[east=low,north=tall,south=none,up=true,west=none]",
    "minecraft:cherry_door[facing=west,half=lower,hinge=right,open=true]", "minecraft:anvil[facing=east]", "minecraft:wall_torch[facing=west]",
])
def test_every_quad_faces_outwards_and_has_area(name):
    """O triângulo (0, 1, 2) de cada face tem a normal geométrica igual à normal declarada."""
    for box in boxes(name):
        for face in range(6):
            quad = box_face_quad(box, face, np.zeros(3, dtype=np.float32), (0.0, 0.0, 1.0, 1.0))
            a, b, c = quad[0, :3], quad[1, :3], quad[2, :3]
            geometric = np.cross(b - a, c - a)
            assert np.linalg.norm(geometric) > 1e-9, (name, box, face)
            assert np.allclose(geometric / np.linalg.norm(geometric), quad[0, 3:6]), (name, box, FACES[face][2])


def test_uv_follows_the_box_cut_of_the_texture():
    """Uma laje mostra, nas laterais, só a metade de baixo da textura; o topo mostra o ladrilho inteiro."""
    slab = Box((0, 0, 0), (16, 8, 16))
    rect = (0.0, 0.0, 1.0, 1.0)
    side = box_face_quad(slab, FACE_INDEX["north"], np.zeros(3, dtype=np.float32), rect)
    assert side[:, 7].min() == pytest.approx(0.5) and side[:, 7].max() == pytest.approx(1.0)
    assert side[:, 6].min() == 0.0 and side[:, 6].max() == 1.0
    top = box_face_quad(Box((0, 0, 0), (16, 16, 16)), FACE_INDEX["top"], np.zeros(3, dtype=np.float32), rect)
    assert top[:, 6].min() == 0.0 and top[:, 6].max() == 1.0 and top[:, 7].min() == 0.0 and top[:, 7].max() == 1.0
    # fence post: 4 de 16 de largura, então pega 4/16 da textura
    post = box_face_quad(Box((6, 0, 6), (10, 16, 10)), FACE_INDEX["north"], np.zeros(3, dtype=np.float32), rect)
    assert post[:, 6].min() == pytest.approx(6 / 16) and post[:, 6].max() == pytest.approx(10 / 16)


def schematic_of(blocks, width, height, length):
    grid = np.full((height, length, width), "minecraft:air", dtype=object)
    for (x, y, z), name in blocks.items():
        grid[y, z, x] = name
    return Schematic(width, height, length, grid, palette={}, name="t")


def uv_stub(block, face):
    return (0.0, 0.0, 1.0, 1.0)


def face_count(blocks, w=2, h=1, l=1):
    verts, inds = StructureMesher.build_arrays(schematic_of(blocks, w, h, l), uv_stub)
    return len(inds) // 6


def test_a_cube_beside_a_slab_keeps_its_face_but_two_cubes_hide_theirs():
    assert face_count({(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:stone"}) == 10
    # com uma laje ao lado, o cubo mostra todas as 6 faces: a laje não é um cubo inteiro
    assert face_count({(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:oak_slab[type=bottom]"}) == 6 + 6


def test_two_bottom_slabs_hide_their_touching_halves():
    # a face da laje que encosta no vizinho cobre só metade da altura: não é escondida (sem corte em faces parciais)
    assert face_count({(0, 0, 0): "minecraft:oak_slab[type=bottom]", (1, 0, 0): "minecraft:oak_slab[type=bottom]"}) == 12


def test_a_slab_on_a_cube_loses_only_the_face_that_sits_on_the_cube():
    # o fundo da laje cobre a célula inteira e some contra o cubo de baixo; o cubo não perde nada (a laje não é cubo)
    assert face_count({(0, 0, 0): "minecraft:stone", (0, 1, 0): "minecraft:oak_slab[type=bottom]"}, w=1, h=2) == 6 + 5


def test_masks_keep_decorations_drawn_but_not_solid():
    s = schematic_of({(0, 0, 0): "minecraft:torch", (1, 0, 0): "minecraft:stone"}, 2, 1, 1)
    assert s.occupied_mask[0, 0, 0] and not s.solid_mask[0, 0, 0]
    assert s.occupied_mask[0, 0, 1] and s.solid_mask[0, 0, 1]
    assert not s.full_cube_mask[0, 0, 0] and s.full_cube_mask[0, 0, 1]
    verts, inds = StructureMesher.build_arrays(s, uv_stub)
    assert len(inds) > 0


def test_showcase_meshes_every_shape_without_errors():
    show = showcase_schematic()
    verts, inds = StructureMesher.build_arrays(show, uv_stub)
    assert len(inds) > 0 and len(verts) == (len(inds) // 6) * 4 * FLOATS_PER_VERTEX
    assert inds.max() < len(verts) // FLOATS_PER_VERTEX
    shaped = [b for b in set(show.grid.ravel().tolist()) if b != "minecraft:air" and shape_for(b) is not None]
    assert len(shaped) >= 30                               # a vitrine cobre mais de 30 blocos com forma


# ------------------------------------------------------------------------------------- tampas com formas
def window_for(blocks, width, height, length, hidden_cells):
    """Janela mínima para testar as tampas: as construções e quais células estão escondidas."""
    schem = schematic_of(blocks, width, height, length)
    placed = PlacedStructure("t", schem, (0, 0, 0))
    shape = (width, height, length)
    occupied = placed._occupied.transpose(2, 0, 1)
    culls = placed._culls.transpose(2, 0, 1)
    owner = np.where(occupied, 0, -1).astype(np.int8)
    window = WindowCells(placed._solid.transpose(2, 0, 1), placed._solid.transpose(2, 0, 1),
                         np.zeros(shape, dtype=np.uint8), owner, [placed], occupied, culls)
    hidden = np.zeros(shape, dtype=bool)
    for cell in hidden_cells:
        hidden[cell] = True
    return window, hidden


def caps_count(blocks, hidden_cells, w=2, h=1, l=1):
    window, hidden = window_for(blocks, w, h, l, hidden_cells)
    visible = window.occupied & ~hidden
    culling = hidden & window.culls
    verts, inds = _structure_caps(window, visible, culling, np.zeros(3, dtype=np.float32), uv_stub)
    return len(inds) // 6


def test_cap_for_a_cube_beside_a_hidden_cube():
    assert caps_count({(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:stone"}, [(1, 0, 0)]) == 1


def test_no_cap_beside_a_hidden_slab_because_a_slab_never_hid_the_face():
    assert caps_count({(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:oak_slab[type=bottom]"}, [(1, 0, 0)]) == 0


def test_cap_for_a_carpet_on_a_hidden_cube():
    # o tapete encosta, inteiro, no cubo de baixo: a face de baixo dele foi descartada e volta
    assert caps_count({(0, 0, 0): "minecraft:stone", (0, 1, 0): "minecraft:pink_carpet"}, [(0, 0, 0)], w=1, h=2) == 1


def test_no_cap_for_a_fence_post_beside_a_hidden_cube():
    assert caps_count({(0, 0, 0): "minecraft:oak_fence", (1, 0, 0): "minecraft:stone"}, [(1, 0, 0)]) == 0
