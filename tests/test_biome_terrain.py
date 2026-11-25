"""O chão, o relevo, a vegetação e as árvores de cada bioma (sem OpenGL)."""
import numpy as np

from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.terrain import TerrainGenerator
from src.world.terrain_options import make_generator, defaults


def region(gen, n=4, ys=(-1, 0, 1)):
    """Os blocos de n x n chunks (x, z de 0 a 16n) e das camadas ``ys``, num só array [x, y, z]."""
    keys = [(cx, cy, cz) for cx in range(n) for cz in range(n) for cy in ys]
    chunks = gen.generate_region(keys)
    out = np.zeros((16 * n, 16 * len(ys), 16 * n), dtype=np.uint8)
    for (cx, cy, cz) in keys:
        j = ys.index(cy)
        out[cx * 16:(cx + 1) * 16, j * 16:(j + 1) * 16, cz * 16:(cz + 1) * 16] = chunks[(cx, cy, cz)].blocks
    return out


def test_camadas_do_deserto():
    gen = TerrainGenerator(seed=5, biome="deserto", base_height=8)
    chunk = Chunk3D(0, 0, 0)
    gen.populate_chunk(chunk)
    checked = 0
    for x in range(16):
        for z in range(16):
            top = gen.get_height(x, z)
            if 8 <= top <= 15:
                col = chunk.blocks[x, :, z]
                assert col[top] == BlockType.SAND and col[top - 4] == BlockType.SAND
                assert col[top - 5] == BlockType.SANDSTONE and col[top - 7] == BlockType.SANDSTONE
                assert col[top - 8] == BlockType.STONE
                checked += 1
    assert checked > 10


def test_taiga_tem_grama_fria_e_podzol():
    blocks = region(TerrainGenerator(seed=11, biome="taiga", sea_level=-50))
    assert (blocks == BlockType.TAIGA_GRASS).any() and (blocks == BlockType.PODZOL).any()
    assert not (blocks == BlockType.GRASS).any()


def test_deserto_tem_dunas_maiores():
    plain = make_generator(3, dict(defaults(), bioma="planicie"))
    desert = make_generator(3, dict(defaults(), bioma="deserto"))
    assert desert.amplitude > plain.amplitude and desert.frequency < plain.frequency


def test_caverna_abre_a_areia():
    gen = TerrainGenerator(seed=1234, biome="deserto", enable_caves=True, cave_chance=1.0, sea_level=-50)
    blocks = region(gen, n=6)
    opened = 0
    for x in range(blocks.shape[0]):
        for z in range(blocks.shape[2]):
            top = gen.get_height(x, z) + 16           # a camada ys=-1 começa em y=-16
            if 0 <= top < blocks.shape[1] and blocks[x, top, z] == BlockType.AIR:
                opened += 1
    assert opened > 0
