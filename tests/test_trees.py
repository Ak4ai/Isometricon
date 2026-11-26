"""Os pinheiros da taiga: a forma, o lugar pela seed e a borda dos chunks."""
import numpy as np

from src.world.block import BlockType
from src.world.terrain import TerrainGenerator
from src.world.trees import (MARGIN, MAX_TOP, PINE, PINE_HEIGHT, ROOT_DEPTH, SEQUOIA, SEQUOIA_HEIGHT,
                             _trees_near, tree_shape)


def _parts(shape, block):
    return shape[shape[:, 3] == int(block)]


def test_formas_cabem_na_margem_e_tem_tronco_nu_embaixo():
    for kind, heights, widths, log in ((PINE, PINE_HEIGHT, (1, 2), BlockType.SPRUCE_LOG),
                                       (SEQUOIA, SEQUOIA_HEIGHT, (2, 4), BlockType.SEQUOIA_LOG)):
        for h in heights:
            for w in widths:
                for variant in (0, 17, 63):
                    shape = tree_shape(kind, h, w, variant)
                    leaves, logs = _parts(shape, BlockType.SPRUCE_LEAVES), _parts(shape, log)
                    assert len(logs) and len(leaves)
                    assert np.abs(shape[:, [0, 2]]).max() <= MARGIN
                    assert shape[:, 1].max() <= MAX_TOP and shape[:, 1].min() >= -ROOT_DEPTH
                    assert leaves[:, 1].min() >= int(h * 0.3)         # a copa fica no alto
                    assert leaves[:, 1].max() >= h               # e chega na ponta
                    # o tronco sobe inteiro, da raiz até a altura
                    trunk = {(int(x), int(z)) for x, _, z, _ in logs if all(
                        ((x, y, z) in {tuple(p[:3]) for p in logs}) for y in range(-ROOT_DEPTH, h))}
                    assert len(trunk) >= w * w
                    # afina para cima: a metade de cima da copa é mais estreita que a de baixo
                    mid = (leaves[:, 1].min() + leaves[:, 1].max()) / 2
                    low, high = leaves[leaves[:, 1] < mid], leaves[leaves[:, 1] >= mid]
                    assert np.abs(low[:, [0, 2]]).max() > np.abs(high[:, [0, 2]]).max() - 1


def test_alturas_novas():
    assert PINE_HEIGHT[0] >= 14 and SEQUOIA_HEIGHT[1] >= 30


def test_taiga_tem_mais_camadas_e_os_outros_nao():
    assert len(TerrainGenerator(seed=1, biome="taiga", vegetation=True).column_layers()) >= 3
    assert TerrainGenerator(seed=1, biome="planicie", vegetation=True).column_layers() == (0,)
    assert TerrainGenerator(seed=1, biome="taiga", vegetation=False).column_layers() == (0,)


def test_tem_sequoias_e_pinheiros_altos():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50)
    trees = _trees_near(gen, -64, -64, 64, 64)
    assert {t[3] for t in trees} == {PINE, SEQUOIA}
    layers = gen.column_layers()
    chunks = gen.generate_region([(cx, cy, cz) for cx in range(-2, 2) for cz in range(-2, 2) for cy in layers])
    assert any((c.blocks == BlockType.SEQUOIA_LOG).any() for c in chunks.values())
    top = max(cy * 16 + int(np.nonzero((c.blocks == BlockType.SPRUCE_LEAVES).any(axis=(0, 2)))[0].max())
              for (_, cy, _), c in chunks.items() if (c.blocks == BlockType.SPRUCE_LEAVES).any())
    assert top >= 30


def test_pinheiro_igual_dentro_e_fora_da_borda():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50)
    keys = [(cx, cy, cz) for cx in (0, 1) for cz in (0, 1) for cy in gen.column_layers()]
    together = gen.generate_region(keys)
    assert any((c.blocks == BlockType.SPRUCE_LOG).any() for c in together.values())
    for key in keys:
        alone = gen.generate_region([key])
        assert np.array_equal(alone[key].blocks, together[key].blocks), key


def test_taiga_tem_arvores_e_os_outros_nao():
    for biome, expected in (("taiga", True), ("planicie", False), ("deserto", False)):
        gen = TerrainGenerator(seed=7, biome=biome, vegetation=True, sea_level=-50)
        chunks = gen.generate_region([(cx, cy, cz) for cx in range(3) for cz in range(3) for cy in range(0, 2)])
        assert any((c.blocks == BlockType.SPRUCE_LOG).any() for c in chunks.values()) is expected, biome


def test_tronco_em_cima_do_chao():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50, enable_caves=False)
    layers = gen.column_layers()
    chunks = gen.generate_region([(cx, cy, cz) for cx in range(3) for cz in range(3) for cy in (-1, *layers)])

    def at(x, y, z):
        c = chunks.get((x // 16, y // 16, z // 16))
        return None if c is None else c.blocks[x % 16, y % 16, z % 16]
    logs = (BlockType.SPRUCE_LOG, BlockType.SEQUOIA_LOG)
    checked = 0
    for x, y, z, kind, height, width, _ in _trees_near(gen, 8, 8, 40, 40):
        lo = -((width - 1) // 2)
        for dx in range(lo, lo + width):
            for dz in range(lo, lo + width):
                bottom = y + height - 1
                assert at(x + dx, bottom, z + dz) in logs
                while at(x + dx, bottom - 1, z + dz) in logs:
                    bottom -= 1
                assert at(x + dx, bottom - 1, z + dz) not in (BlockType.AIR, None)   # desce até o chão: não flutua
        assert at(x, y - 1, z) in (BlockType.TAIGA_GRASS, BlockType.PODZOL)
        checked += 1
    assert checked > 0


def test_nenhuma_folha_solta():
    for kind, h, w in ((PINE, 17, 1), (PINE, 20, 2), (SEQUOIA, 30, 2), (SEQUOIA, 36, 4)):
        for variant in range(0, 64, 9):
            shape = tree_shape(kind, h, w, variant)
            cells = {tuple(int(v) for v in p[:3]): int(p[3]) for p in shape}
            seen = {p for p, b in cells.items() if b != int(BlockType.SPRUCE_LEAVES)}
            frontier = list(seen)
            while frontier:
                x, y, z = frontier.pop()
                for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                    if n in cells and n not in seen:
                        seen.add(n)
                        frontier.append(n)
            assert seen == set(cells), (kind, h, w, variant)


def test_tronco_grosso_comeca_em_coordenada_par():
    gen = TerrainGenerator(seed=7, biome="taiga", vegetation=True, sea_level=-50)
    wide = [t for t in _trees_near(gen, -96, -96, 96, 96) if t[5] > 1]
    assert wide
    for x, _, z, _, _, width, _ in wide:
        lo = -((width - 1) // 2)
        assert (x + lo) % 2 == 0 and (z + lo) % 2 == 0


def test_galhos_deitados():
    """Os galhos são troncos deitados no eixo para onde saem: nenhum tronco em pé fora da coluna do tronco."""
    lying = {int(b) for b in (BlockType.SPRUCE_LOG_X, BlockType.SPRUCE_LOG_Z, BlockType.SEQUOIA_LOG_X,
                              BlockType.SEQUOIA_LOG_Z)}
    for kind, h, w, log in ((PINE, 18, 1, BlockType.SPRUCE_LOG), (SEQUOIA, 32, 2, BlockType.SEQUOIA_LOG),
                            (SEQUOIA, 36, 4, BlockType.SEQUOIA_LOG)):
        shape = tree_shape(kind, h, w, 5)
        assert any(int(p[3]) in lying for p in shape)
        lo = -((w - 1) // 2)
        trunk = {(dx, dz) for dx in range(lo, lo + w) for dz in range(lo, lo + w)}
        for dx, dy, dz, b in shape:
            if int(b) == int(log) and dy >= 2:          # acima das raízes, o tronco em pé só na coluna do tronco
                assert (int(dx), int(dz)) in trunk
