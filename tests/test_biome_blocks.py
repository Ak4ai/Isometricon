"""Os blocos do deserto e da taiga: sólido, opaco, folhagem, textura e malha."""
import os

import numpy as np
import pytest

from src.world.block import (FOLIAGE, OPAQUE_BLOCKS, SURFACE_BLOCKS, BlockType, is_opaque, is_shaped, is_solid)
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMesher

HAS_TEXTURES = os.path.isfile(os.path.join("assets", "textures", "blocks", "sand.png"))


def test_blocos_dos_biomas():
    assert is_solid(BlockType.CACTUS) and is_shaped(BlockType.CACTUS)
    assert not is_solid(BlockType.DEAD_BUSH) and not is_solid(BlockType.FERN)
    assert is_opaque(BlockType.SAND) and not is_opaque(BlockType.SPRUCE_LEAVES)
    assert BlockType.SPRUCE_LEAVES in FOLIAGE and BlockType.PODZOL in SURFACE_BLOCKS
    assert BlockType.TAIGA_GRASS in OPAQUE_BLOCKS
    assert int(BlockType.SAND) == 18 and int(BlockType.SWEET_BERRY_BUSH) == 29
    assert max(BlockType) < 256


@pytest.mark.skipif(not HAS_TEXTURES, reason="texturas da Mojang só na máquina de quem tem o jogo")
def test_atlas_tem_textura_de_cada_bloco_novo():
    from src.rendering.atlas import TextureAtlas
    atlas = TextureAtlas(create_gl=False)
    blank = atlas.tile_rects["white_concrete"]
    for block in (BlockType.SAND, BlockType.SANDSTONE, BlockType.SPRUCE_LOG, BlockType.SPRUCE_LEAVES,
                  BlockType.PODZOL, BlockType.TAIGA_GRASS):
        for face in range(6):
            rect = atlas.uv_table[int(block), face]
            assert (rect.min(axis=0) != blank[:2]).any(), (block, face)
    for name in ("cactus_side", "cactus_top", "dead_bush", "fern", "large_fern_top", "sweet_berry_bush_stage3"):
        assert name in atlas.tile_rects


@pytest.mark.skipif(not HAS_TEXTURES, reason="texturas da Mojang só na máquina de quem tem o jogo")
def test_cacto_usa_lado_e_topo():
    from src.rendering.atlas import TextureAtlas
    from src.world.mesher import _shaped_template
    atlas = TextureAtlas(create_gl=False)
    verts = _shaped_template(BlockType.CACTUS, atlas)
    us = {(round(float(u), 4), round(float(v), 4)) for u, v in verts[:, 6:8]}

    def inside(name):
        u0, v0, u1, v1 = atlas.tile_rects[name]
        return any(min(u0, u1) <= u <= max(u0, u1) and min(v0, v1) <= v <= max(v0, v1) for u, v in us)
    assert inside("cactus_side") and inside("cactus_top")


def test_areia_esconde_a_face_entre_dois_blocos():
    blocks = np.zeros((16, 16, 16), dtype=np.uint8)
    blocks[4, 4, 4] = blocks[5, 4, 4] = BlockType.SAND
    one = np.zeros_like(blocks)
    one[4, 4, 4] = BlockType.SAND
    mesher = ChunkMesher()
    two = mesher.build(Chunk3D(0, 0, 0, blocks=blocks))
    single = mesher.build(Chunk3D(0, 0, 0, blocks=one))
    assert two.index_count == 2 * single.index_count - 2 * 6


def test_folha_de_pinheiro_nao_esconde_a_vizinha():
    # a pedra mantém as 6 faces ao lado da folha, como ao lado da folha de carvalho
    mesher = ChunkMesher()

    def count(leaf):
        blocks = np.zeros((16, 16, 16), dtype=np.uint8)
        blocks[4, 4, 4] = BlockType.STONE
        blocks[5, 4, 4] = leaf
        return mesher.build(Chunk3D(0, 0, 0, blocks=blocks)).index_count
    alone = np.zeros((16, 16, 16), dtype=np.uint8)
    alone[4, 4, 4] = BlockType.STONE
    assert count(BlockType.SPRUCE_LEAVES) == count(BlockType.LEAVES) > mesher.build(Chunk3D(0, 0, 0, blocks=alone)).index_count + 5 * 6 - 1
