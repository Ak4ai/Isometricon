"""Uma biblioteca só para as construções: os .schem, a vitrine de formas e os objetos do editor."""

import shutil

import numpy as np
import pytest

from src.editor.voxel_object import EMPTY, VoxelObject
from src.world.structure_sources import entry_for_text, library, load_entry

HOUSE = "assets/objects/casa_exemplo.json"


@pytest.fixture
def schem_dir(tmp_path):
    folder = tmp_path / "schematics"
    folder.mkdir()
    shutil.copy("assets/schematics/sala-teste.schem", folder / "sala-teste.schem")
    shutil.copy("assets/schematics/sala-dupla.schem", folder / "b-casa.schem")
    return str(folder)


def test_library_lists_schem_then_showcase_then_objects(schem_dir, tmp_path):
    broken = tmp_path / "quebrado.json"
    broken.write_text("{")
    items = library(schem_dir, [HOUSE, str(broken)])
    assert [label for label, _ in items] == ["b-casa", "sala-teste", "formas", "casa_exemplo"]
    assert items[0][1] == {"kind": "schem", "name": "b-casa"}
    assert items[2][1] == {"kind": "formas"}
    assert items[3][1]["kind"] == "object" and items[3][1]["name"] == "casa_exemplo"


def test_object_entry_loads_as_schematic_with_the_material_colours():
    obj = VoxelObject.load(HOUSE)
    entry = entry_for_text(HOUSE, "assets/schematics")
    schematic = load_entry(entry, "assets/schematics")
    assert (schematic.width, schematic.height, schematic.length) == obj.size
    occupied = {(int(x), int(y), int(z)) for y, z, x in np.argwhere(schematic.grid != "minecraft:air")}
    assert occupied == {(int(x), int(y), int(z)) for x, y, z in np.argwhere(obj.blocks != EMPTY)}
    x, y, z = next(iter(sorted(occupied)))
    material = obj.materials[obj.blocks[x, y, z]]
    assert np.allclose(schematic.tints[y, z, x], [c / 255.0 for c in material.color])


def test_object_entry_keeps_the_object_even_if_the_file_changes(tmp_path):
    path = tmp_path / "obj.json"
    shutil.copy(HOUSE, path)
    entry = entry_for_text(str(path), "assets/schematics")
    path.unlink()
    assert load_entry(entry, "assets/schematics").width == VoxelObject.load(HOUSE).size[0]


def test_text_finds_showcase_and_schem_names(schem_dir):
    assert entry_for_text("formas", schem_dir) == {"kind": "formas"}
    assert entry_for_text("Vitrine", schem_dir) == {"kind": "formas"}
    assert entry_for_text("sala-teste", schem_dir) == {"kind": "schem", "name": "sala-teste"}
    assert entry_for_text('"sala-teste.schem"', schem_dir) == {"kind": "schem", "name": "sala-teste"}
    assert entry_for_text("nada", schem_dir) is None
    assert load_entry({"kind": "formas"}, schem_dir).width > 0


def test_schem_given_by_a_path_outside_the_folder_loads(schem_dir):
    entry = entry_for_text("assets/schematics/sala-andar.schem", schem_dir)
    assert entry["kind"] == "schem"
    assert load_entry(entry, schem_dir).height > 0


def test_missing_schem_raises(schem_dir):
    with pytest.raises(FileNotFoundError):
        load_entry({"kind": "schem", "name": "sumiu"}, schem_dir)
