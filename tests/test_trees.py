"""Os pinheiros da taiga: a forma, o lugar pela seed e a borda dos chunks."""
import numpy as np

from src.world.block import BlockType
from src.world.terrain import TerrainGenerator
from src.world.trees import spruce_shape


def test_forma_do_pinheiro():
    for h in (6, 8, 10):
        shape = spruce_shape(h)
        logs = [p for p in shape if p[3] == BlockType.SPRUCE_LOG]
        leaves = [p for p in shape if p[3] == BlockType.SPRUCE_LEAVES]
        assert sorted(p[1] for p in logs) == list(range(h)) and all(p[0] == p[2] == 0 for p in logs)
        assert max(p[1] for p in shape) == h                     # uma folha em cima do tronco
        assert max(max(abs(p[0]), abs(p[2])) for p in leaves) <= 3
        assert min(p[1] for p in leaves) >= 2
        # cone: a camada mais larga fica embaixo da mais estreita
        width = {y: max(max(abs(p[0]), abs(p[2])) for p in leaves if p[1] == y) for y in {p[1] for p in leaves}}
        assert width[h] == 0 and max(width.values()) > width[h - 1]


def test_pinheiro_igual_dentro_e_fora_da_borda():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50)
    keys = [(cx, cy, cz) for cx in (0, 1) for cz in (0, 1) for cy in range(0, 2)]
    together = gen.generate_region(keys)
    assert any((c.blocks == BlockType.SPRUCE_LOG).any() for c in together.values())
    for key in keys:
        alone = gen.generate_region([key, (key[0], key[1] + 1, key[2])] if key[1] == 0 else [(key[0], 0, key[2]), key])
        assert np.array_equal(alone[key].blocks, together[key].blocks), key


def test_taiga_tem_arvores_e_os_outros_nao():
    for biome, expected in (("taiga", True), ("planicie", False), ("deserto", False)):
        gen = TerrainGenerator(seed=7, biome=biome, vegetation=True, sea_level=-50)
        chunks = gen.generate_region([(cx, cy, cz) for cx in range(3) for cz in range(3) for cy in range(0, 2)])
        assert any((c.blocks == BlockType.SPRUCE_LOG).any() for c in chunks.values()) is expected, biome


def test_tronco_em_cima_do_chao():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50)
    chunks = gen.generate_region([(cx, cy, cz) for cx in range(3) for cz in range(3) for cy in range(-1, 2)])

    def at(x, y, z):
        c = chunks.get((x // 16, y // 16, z // 16))
        return None if c is None else c.blocks[x % 16, y % 16, z % 16]
    bases = 0
    for (cx, cy, cz), c in chunks.items():
        for lx, ly, lz in np.argwhere(c.blocks == BlockType.SPRUCE_LOG):
            x, y, z = cx * 16 + lx, cy * 16 + ly, cz * 16 + lz
            if at(x, y - 1, z) != BlockType.SPRUCE_LOG:
                assert at(x, y - 1, z) in (BlockType.TAIGA_GRASS, BlockType.PODZOL)
                bases += 1
    assert bases > 0
