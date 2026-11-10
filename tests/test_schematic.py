"""Testes do parser de Schematics (.schem), do StructureMesher e do SchematicAtlas (sem OpenGL)."""

import os

import numpy as np
import pytest

from src.rendering.schematic_atlas import FALLBACK, SchematicAtlas
from src.world import Schematic, StructureMesher
from src.world.schematic import is_air_name
from src.world.structure_mesher import FLOATS_PER_VERTEX

SCHEM_PATH = "assets/schematics/31422.schem"


def make_schematic(blocks, width, height, length):
    """Monta um Schematic pequeno a partir de {(x, y, z): nome}; o resto é ar."""
    grid = np.full((height, length, width), "minecraft:air", dtype=object)
    for (x, y, z), name in blocks.items():
        grid[y, z, x] = name
    return Schematic(width, height, length, grid, palette={})


def flat_uv(block, face):
    return (0.0, 0.0, 1.0, 1.0)


def test_schematic_loading():
    if not os.path.exists(SCHEM_PATH):
        pytest.skip(f"Arquivo {SCHEM_PATH} não encontrado")

    schem = Schematic.load_from_file(SCHEM_PATH)
    assert (schem.width, schem.height, schem.length) == (24, 12, 17)
    assert schem.grid.shape == (12, 17, 24)
    assert len(schem.palette) > 0
    assert "minecraft:quartz_block" in schem.palette or "minecraft:cherry_leaves" in str(schem.palette)

    block = schem.get_block(0, 0, 0)
    assert isinstance(block, str) and block
    # A máscara de sólidos concorda com is_air nos voxels consultados
    mask = schem.solid_mask
    assert mask.shape == schem.grid.shape
    assert mask.any()
    for x, y, z in [(0, 0, 0), (5, 3, 4), (23, 11, 16)]:
        assert mask[y, z, x] == (not schem.is_air(x, y, z))


def test_schematic_file_not_found():
    with pytest.raises(FileNotFoundError):
        Schematic.load_from_file("assets/schematics/inexistente.schem")


def test_is_air_name():
    assert is_air_name("minecraft:air")
    assert is_air_name("minecraft:cave_air")
    assert is_air_name("")
    assert not is_air_name("minecraft:stone")
    # nomes que apenas contêm "air" não são ar
    assert not is_air_name("minecraft:repeater[delay=1]")
    assert not is_air_name("minecraft:chair_block")


def test_out_of_bounds_is_air():
    schem = make_schematic({(0, 0, 0): "minecraft:stone"}, 1, 1, 1)
    assert schem.get_block(-1, 0, 0) == "minecraft:air"
    assert schem.is_air(0, 1, 0)
    assert not schem.is_air(0, 0, 0)


def test_single_block_has_six_faces():
    schem = make_schematic({(0, 0, 0): "minecraft:stone"}, 1, 1, 1)
    verts, inds = StructureMesher.build_arrays(schem, flat_uv)
    assert verts.dtype == np.float32 and inds.dtype == np.uint32
    assert len(verts) == 6 * 4 * FLOATS_PER_VERTEX
    assert len(inds) == 6 * 6


def test_adjacent_blocks_hide_shared_faces():
    schem = make_schematic(
        {(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:stone"}, 2, 1, 1
    )
    verts, inds = StructureMesher.build_arrays(schem, flat_uv)
    # 2 cubos = 12 faces, menos as 2 que se encostam
    assert len(inds) // 6 == 10


def test_empty_schematic_makes_empty_mesh():
    schem = make_schematic({}, 2, 2, 2)
    verts, inds = StructureMesher.build_arrays(schem, flat_uv)
    assert len(verts) == 0 and len(inds) == 0


def test_center_moves_structure_to_origin():
    schem = make_schematic({(0, 0, 0): "minecraft:stone", (1, 0, 0): "minecraft:stone"}, 2, 1, 1)
    verts, _ = StructureMesher.build_arrays(schem, flat_uv, center=True)
    pos = verts.reshape(-1, FLOATS_PER_VERTEX)[:, :3]
    assert pos[:, 0].min() == pytest.approx(-1.0) and pos[:, 0].max() == pytest.approx(1.0)
    verts, _ = StructureMesher.build_arrays(schem, flat_uv, center=False)
    pos = verts.reshape(-1, FLOATS_PER_VERTEX)[:, :3]
    assert pos[:, 0].min() == pytest.approx(-0.5) and pos[:, 0].max() == pytest.approx(1.5)


def test_faces_are_counter_clockwise_seen_from_outside():
    """O triângulo (0, 1, 2) de cada face tem a normal geométrica igual à normal declarada."""
    schem = make_schematic({(0, 0, 0): "minecraft:stone"}, 1, 1, 1)
    verts, inds = StructureMesher.build_arrays(schem, flat_uv)
    vertices = verts.reshape(-1, FLOATS_PER_VERTEX)
    for first in range(0, len(inds), 6):
        a, b, c = (vertices[inds[first + k]] for k in range(3))
        geometric = np.cross(b[:3] - a[:3], c[:3] - a[:3])
        assert np.allclose(geometric / np.linalg.norm(geometric), a[3:6]), a[3:6]


def test_mesher_asks_for_top_and_bottom_textures():
    seen = []

    def spy(block, face):
        seen.append(face)
        return (0.0, 0.0, 1.0, 1.0)

    schem = make_schematic({(0, 0, 0): "minecraft:stone"}, 1, 1, 1)
    StructureMesher.build_arrays(schem, spy)
    assert {"top", "bottom"} <= set(seen)


@pytest.fixture(scope="module")
def atlas(tmp_path_factory):
    from PIL import Image

    folder = tmp_path_factory.mktemp("blocks")
    for name, color in {
        "stone": (120, 120, 120, 255),
        "oak_log": (100, 70, 30, 255),
        "oak_log_top": (160, 130, 80, 255),
        "oak_planks": (170, 130, 80, 255),
    }.items():
        Image.new("RGBA", (16, 16), color).save(folder / f"{name}.png")
    # tira vertical de 4 quadros: só o primeiro entra no atlas
    strip = Image.new("RGBA", (16, 64), (0, 0, 255, 255))
    strip.paste(Image.new("RGBA", (16, 16), (255, 0, 0, 255)), (0, 0))
    strip.save(folder / "water_still.png")
    return SchematicAtlas(str(folder), tile_size=16, atlas_size=64)


def test_atlas_resolves_names_with_namespace_and_properties(atlas):
    assert atlas.get_uv("minecraft:stone") == atlas.uv_map["stone"]
    assert atlas.get_uv("minecraft:stone[waterlogged=false]", "top") == atlas.uv_map["stone"]


def test_atlas_log_top_and_side(atlas):
    assert atlas.get_uv("minecraft:oak_log[axis=y]", "top") == atlas.uv_map["oak_log_top"]
    assert atlas.get_uv("minecraft:oak_log[axis=y]", "north") == atlas.uv_map["oak_log"]


def test_atlas_stairs_use_base_material(atlas):
    assert atlas.get_uv("minecraft:oak_stairs[facing=east]", "top") == atlas.uv_map["oak_planks"]


def test_atlas_derived_blocks_use_material_texture():
    atlas = SchematicAtlas()
    uv = atlas.uv_map
    assert atlas.get_uv("minecraft:dark_oak_fence[east=true]", "north") == uv["dark_oak_planks"]
    assert atlas.get_uv("minecraft:cherry_wall_sign[facing=east]", "north") == uv["cherry_planks"]
    assert atlas.get_uv("minecraft:quartz_slab[type=top]", "top") == uv["quartz_block_top"]
    assert atlas.get_uv("minecraft:quartz_slab[type=top]", "north") == uv["quartz_block_side"]
    assert atlas.get_uv("minecraft:smooth_quartz_stairs[facing=north]", "north") == uv["quartz_block_bottom"]


def test_atlas_unknown_block_uses_fallback(atlas):
    assert atlas.get_uv("minecraft:zzzz_nao_existe") == atlas.uv_map[FALLBACK]


def test_atlas_animated_strip_keeps_first_frame(atlas):
    u0, v0, u1, v1 = atlas.uv_map["water_still"]
    px, py = int(u0 * 64), int(v0 * 64)
    assert atlas.atlas_image.getpixel((px + 8, py + 8)) == (255, 0, 0, 255)


def test_atlas_missing_folder():
    with pytest.raises(FileNotFoundError):
        SchematicAtlas("pasta/que/nao/existe")


def test_atlas_loads_project_textures():
    atlas = SchematicAtlas()
    assert len(atlas.uv_map) > 500
    assert atlas.get_uv("minecraft:stone") != atlas.uv_map[FALLBACK]


def test_real_schematic_meshes_with_project_atlas():
    if not os.path.exists(SCHEM_PATH):
        pytest.skip(f"Arquivo {SCHEM_PATH} não encontrado")
    schem = Schematic.load_from_file(SCHEM_PATH)
    atlas = SchematicAtlas()
    verts, inds = StructureMesher.build_arrays(schem, atlas.get_uv)
    assert len(inds) > 0 and len(inds) % 6 == 0
    assert len(verts) == (len(inds) // 6) * 4 * FLOATS_PER_VERTEX
    assert inds.max() < len(verts) // FLOATS_PER_VERTEX
    uvs = verts.reshape(-1, FLOATS_PER_VERTEX)[:, 6:8]
    assert uvs.min() >= 0.0 and uvs.max() <= 1.0
