"""O mapa da neblina de ambientação: a altura do chão e o "perto da água/árvore" de cada coluna."""
import numpy as np

from src.rendering.mist import MistField, mist_map
from src.world.block import BlockType
from src.world.chunk import Chunk3D


def _world():
    ground = Chunk3D(0, 0, 0)
    ground.blocks[:, :5, :] = int(BlockType.GRASS)            # chão em y 0..4: topo em 5
    ground.blocks[10, 5, 10] = int(BlockType.WATER)           # uma poça
    ground.blocks[2, 5:16, 2] = int(BlockType.SPRUCE_LOG)     # um tronco que passa para a camada de cima
    ground.blocks[1:4, 9:12, 1:4] = int(BlockType.SPRUCE_LEAVES)
    above = Chunk3D(0, 1, 0)
    above.blocks[2, 0:4, 2] = int(BlockType.SPRUCE_LOG)
    return {(0, 0, 0): ground, (0, 1, 0): above}


def test_altura_do_chao_sem_tronco_nem_folha():
    chunks = _world()
    m = mist_map(chunks.get, 0, 0, 16, layers=(0, 1))
    assert m.shape == (16, 16, 2) and m.dtype == np.float32
    assert m[0, 0, 0] == 5.0                  # [z, x]
    assert m[2, 2, 0] == 5.0                  # o tronco não é chão
    assert m[2, 1, 0] == 5.0                  # nem as folhas
    assert m[10, 10, 0] == 6.0                # a água é chão


def test_perto_da_agua_e_das_arvores_cai_com_a_distancia():
    m = mist_map(_world().get, 0, 0, 16, layers=(0, 1))
    near = m[:, :, 1]
    assert near[10, 10] == 1.0 and near[2, 2] == 1.0
    assert 0.0 < near[10, 15] < near[10, 12] < 1.0
    assert near[15, 15] < near[10, 13]


def test_coluna_sem_chunk_fica_zerada():
    m = mist_map(_world().get, -16, 0, 32, layers=(0, 1))
    assert (m[:, :16, 0] == 0).all()          # x de -16 a -1: não carregado
    assert m[0, 16, 0] == 5.0


def test_campo_recentra_e_espera_para_refazer():
    chunks = _world()
    field = MistField()
    assert field.update(8.0, 8.0, 1, chunks.get, (0, 1), upload=False)
    assert field.top == 6.0
    assert not field.update(9.0, 9.0, 1, chunks.get, (0, 1), upload=False)    # nada mudou
    assert not field.update(9.0, 9.0, 2, chunks.get, (0, 1), upload=False)    # chunks mudaram há pouco: espera
    assert field.update(200.0, 8.0, 2, chunks.get, (0, 1), upload=False)      # andou longe: recentra já
    assert field.origin[0] == 200 - 64
