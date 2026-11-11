"""Uma construção de teste com uma amostra de cada forma de bloco (laje, degrau, cerca, alçapão...).

Serve para conferir as formas no visualizador: ``python scripts/demo_schematic.py --formas``.
"""

import numpy as np

from src.world.schematic import Schematic

FLOOR = "minecraft:stone_bricks"


def showcase_schematic() -> Schematic:
    width, length = 31, 22
    grid = np.full((6, length, width), "minecraft:air", dtype=object)
    grid[0, :, :] = FLOOR

    def put(x, z, name, y=1):
        grid[y, z, x] = name

    # fileira 1: lajes e degraus
    put(1, 2, "minecraft:oak_slab[type=bottom]")
    put(3, 2, "minecraft:oak_slab[type=top]")
    put(5, 2, "minecraft:oak_slab[type=double]")
    for i, facing in enumerate(("east", "south", "west", "north")):
        put(8 + 2 * i, 2, f"minecraft:oak_stairs[facing={facing},half=bottom,shape=straight]")
    put(17, 2, "minecraft:oak_stairs[facing=east,half=top,shape=straight]")
    for i, shape in enumerate(("outer_right", "outer_left", "inner_right", "inner_left")):
        put(19 + 2 * i, 2, f"minecraft:quartz_stairs[facing=east,half=bottom,shape={shape}]")

    # fileira 2: alçapões, cerca e portão
    put(1, 5, "minecraft:dark_oak_trapdoor[facing=north,half=bottom,open=false]")
    put(3, 5, "minecraft:dark_oak_trapdoor[facing=north,half=top,open=false]")
    for i, facing in enumerate(("north", "east", "south", "west")):
        put(5 + 2 * i, 5, f"minecraft:dark_oak_trapdoor[facing={facing},half=bottom,open=true]")
        put(5 + 2 * i, 4, "minecraft:stone_bricks")  # um apoio para ver o painel aberto
    put(15, 5, "minecraft:dark_oak_fence[east=false,north=false,south=false,west=false]")
    for x in (17, 18, 19):
        put(x, 5, "minecraft:dark_oak_fence[east=true,north=false,south=false,west=true]")
    put(18, 6, "minecraft:dark_oak_fence[east=false,north=true,south=false,west=false]")
    put(21, 5, "minecraft:oak_fence_gate[facing=north,open=false]")
    put(23, 5, "minecraft:oak_fence_gate[facing=north,open=true]")

    # fileira 3: muros, barras e placas
    put(1, 8, "minecraft:mud_brick_wall[east=low,north=none,south=none,up=true,west=none]")
    put(2, 8, "minecraft:mud_brick_wall[east=low,north=none,south=none,up=false,west=low]")
    put(3, 8, "minecraft:mud_brick_wall[east=none,north=none,south=none,up=true,west=low]")
    put(6, 8, "minecraft:polished_deepslate_wall[east=tall,north=none,south=none,up=true,west=none]")
    put(7, 8, "minecraft:polished_deepslate_wall[east=none,north=none,south=none,up=true,west=tall]")
    put(10, 8, "minecraft:iron_bars[east=true,north=false,south=false,west=true]")
    put(11, 8, "minecraft:iron_bars[east=true,north=false,south=false,west=true]")
    put(13, 8, "minecraft:black_stained_glass_pane[east=false,north=true,south=true,west=false]")
    for i, facing in enumerate(("north", "east", "south", "west")):
        put(17 + 2 * i, 8, f"minecraft:cherry_wall_sign[facing={facing}]")
    put(17, 9, "minecraft:stone_bricks")

    # fileira 4: portas, botões, placas de pressão, tochas, lanternas, correntes, velas
    put(1, 11, "minecraft:cherry_door[facing=east,half=lower,hinge=left,open=false]")
    put(1, 11, "minecraft:cherry_door[facing=east,half=upper,hinge=left,open=false]", y=2)
    put(3, 11, "minecraft:cherry_door[facing=east,half=lower,hinge=left,open=true]")
    put(3, 11, "minecraft:cherry_door[facing=east,half=upper,hinge=left,open=true]", y=2)
    put(5, 11, "minecraft:stone_button[face=floor,facing=north,powered=false]")
    put(7, 11, "minecraft:cherry_pressure_plate[powered=false]")
    put(9, 11, "minecraft:torch")
    put(11, 11, "minecraft:lantern[hanging=false]")
    put(13, 11, "minecraft:chain[axis=y]")
    put(13, 11, "minecraft:chain[axis=y]", y=2)
    put(15, 11, "minecraft:candle[candles=1,lit=false]")
    put(17, 11, "minecraft:pink_carpet")
    put(19, 11, "minecraft:potted_pink_tulip")
    put(23, 11, "minecraft:anvil[facing=north]")
    put(25, 11, "minecraft:cake[bites=0]")
    put(27, 11, "minecraft:decorated_pot[facing=north]")
    put(29, 11, "minecraft:heavy_weighted_pressure_plate[power=0]")
    put(28, 14, "minecraft:stone_bricks")
    put(28, 13, "minecraft:ladder[facing=south]")
    put(21, 12, "minecraft:stone_bricks")
    put(21, 11, "minecraft:wall_torch[facing=north]")

    # fileira 5: plantas em cruz (sobre grama), cogumelos e fogo
    plants = ("short_grass", "fern", "poppy", "dandelion", "blue_orchid", "allium", "azure_bluet", "red_tulip",
              "oxeye_daisy", "cornflower", "lily_of_the_valley", "torchflower", "oak_sapling", "cherry_sapling",
              "dead_bush", "red_mushroom", "brown_mushroom", "crimson_fungus", "warped_roots", "sugar_cane",
              "wheat[age=7]", "carrots[age=7]", "sweet_berry_bush[age=3]", "cobweb", "fire", "soul_fire")
    for i, name in enumerate(plants):
        x = 1 + i
        grid[0, 15, x] = "minecraft:grass_block[snowy=false]"
        put(x, 15, f"minecraft:{name}")
    for i, name in enumerate(("tall_grass", "large_fern", "lilac", "rose_bush", "peony", "sunflower")):
        put(1 + 2 * i, 17, f"minecraft:{name}[half=lower]")
        put(1 + 2 * i, 17, f"minecraft:{name}[half=upper]", y=2)

    # fileira 6: trilhos, cipó, fogueira, vitória-régia, neve, escada de mão em pé numa parede
    put(14, 17, "minecraft:rail[shape=north_south]")
    put(15, 17, "minecraft:rail[shape=east_west]")
    put(16, 17, "minecraft:rail[shape=north_east]")
    put(17, 17, "minecraft:powered_rail[powered=true,shape=north_south]")
    put(18, 17, "minecraft:detector_rail[powered=false,shape=east_west]")
    put(19, 17, "minecraft:rail[shape=ascending_east]")
    put(20, 17, "minecraft:stone_bricks")
    put(22, 17, "minecraft:campfire[facing=north,lit=true]")
    put(24, 17, "minecraft:lily_pad")
    put(26, 17, "minecraft:snow[layers=3]")
    put(28, 17, "minecraft:end_rod[facing=up]")
    for y in range(1, 5):
        put(1, 20, "minecraft:stone_bricks", y=y)
        put(1, 19, "minecraft:ladder[facing=north]", y=y)
        put(3, 20, "minecraft:stone_bricks", y=y)
        put(3, 19, "minecraft:vine[north=false,east=false,south=true,west=false,up=false]", y=y)
    put(5, 20, "minecraft:stone_bricks")
    put(5, 19, "minecraft:glow_lichen[south=true]")

    return Schematic(width, 6, length, grid, palette={}, name="formas")
