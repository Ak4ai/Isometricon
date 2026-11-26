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


def test_cactos_nao_se_encostam_e_tem_ate_3_blocos():
    blocks = region(TerrainGenerator(seed=21, biome="deserto", vegetation=True, sea_level=-50), n=6)
    cacti = set(map(tuple, np.argwhere(blocks == BlockType.CACTUS)))
    assert cacti
    for x, y, z in cacti:
        assert not any((x + dx, y, z + dz) in cacti for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        assert not {(x, y - 1, z), (x, y - 2, z), (x, y - 3, z)} <= cacti      # no máximo 3 de altura
        assert blocks[x, y - 1, z] in (BlockType.SAND, BlockType.CACTUS)


def test_deserto_sem_capim_e_com_arbusto_seco():
    blocks = region(TerrainGenerator(seed=21, biome="deserto", vegetation=True, sea_level=-50))
    assert (blocks == BlockType.DEAD_BUSH).any()
    for plant in (BlockType.SHORT_GRASS, BlockType.POPPY, BlockType.FERN):
        assert not (blocks == plant).any()


def test_taiga_com_samambaias_e_frutinhas():
    blocks = region(TerrainGenerator(seed=21, biome="taiga", vegetation=True, sea_level=-50))
    assert (blocks == BlockType.FERN).any() and (blocks == BlockType.SWEET_BERRY_BUSH).any()
    lower = np.argwhere(blocks == BlockType.LARGE_FERN_LOWER)
    assert len(lower)
    for x, y, z in lower:
        assert blocks[x, y + 1, z] == BlockType.LARGE_FERN_UPPER
    assert not (blocks == BlockType.SHORT_GRASS).any() and not (blocks == BlockType.DEAD_BUSH).any()
