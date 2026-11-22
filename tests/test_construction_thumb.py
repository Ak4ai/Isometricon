import numpy as np
from PIL import Image

from src.interactive.construction_thumb import block_colour, thumbnail_for
from src.world.schematic import Schematic


def test_thumbnail_is_a_nonempty_card():
    grid = np.full((4, 4, 4), "minecraft:air", dtype=object)
    grid[0, 0, 0] = "minecraft:grass_block"
    grid[1, 1, 1] = "minecraft:stone"
    grid[2, 2, 2] = "minecraft:oak_planks"
    schematic = Schematic(4, 4, 4, grid, {}, "teste")
    image = thumbnail_for(schematic, (150, 112))
    assert isinstance(image, Image.Image)
    assert image.size == (150, 112)
    assert image.getbbox() is not None


def test_block_colour_is_deterministic():
    assert block_colour("minecraft:stone") == block_colour("stone")
    assert block_colour("minecraft:unknown_block") == block_colour("unknown_block")
