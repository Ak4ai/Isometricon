"""Testes unitários para o sistema TextureAtlas de blocos."""

import numpy as np
import pytest

from src.rendering.atlas import TextureAtlas
from src.world.block import BlockType
from src.world.chunk import Chunk3D
from src.world.mesher import ChunkMesher


def test_atlas_initialization_cpu_mode():
    """O TextureAtlas deve inicializar na CPU sem exigir contexto gráfico OpenGL."""
    atlas = TextureAtlas(create_gl=False)
    assert atlas.atlas_image.size == (64, 64)
    assert atlas.atlas_image.mode == "RGBA"
    assert atlas.atlas_gl.size == (64, 64)
    assert len(atlas.tile_rects) >= 12


def test_atlas_tables_shapes_and_ranges():
    """As tabelas O(1) de UVs e cores de modulação devem ter os formatos e faixas corretas."""
    atlas = TextureAtlas(create_gl=False)

    max_id = max(int(b) for b in BlockType) + 1
    assert atlas.uv_table.shape == (max_id, 6, 4, 2)
    assert atlas.color_table.shape == (max_id, 6, 3)

    # Coordenadas UV devem estar estritamente dentro do intervalo normalizado [0, 1]
    assert np.all(atlas.uv_table >= 0.0)
    assert np.all(atlas.uv_table <= 1.0)

    # Cores RGB de modulação devem estar dentro de [0, 1]
    assert np.all(atlas.color_table >= 0.0)
    assert np.all(atlas.color_table <= 1.0)


def test_atlas_block_mapping_distinct_textures():
    """Diferentes tipos de blocos e faces devem apontar para regiões de textura distintas no atlas."""
    atlas = TextureAtlas(create_gl=False)

    grass_top_uv = atlas.uv_table[int(BlockType.GRASS), 2]      # Face 2: +Y Top
    grass_side_uv = atlas.uv_table[int(BlockType.GRASS), 0]     # Face 0: +X Side
    stone_side_uv = atlas.uv_table[int(BlockType.STONE), 0]     # Face 0: +X Side
    dirt_uv = atlas.uv_table[int(BlockType.DIRT), 0]

    # As UVs do topo da grama, lado da grama e pedra devem ser distintas
    assert not np.allclose(grass_top_uv, grass_side_uv)
    assert not np.allclose(grass_side_uv, stone_side_uv)
    assert not np.allclose(stone_side_uv, dirt_uv)

    # O fundo da grama (Face 3: -Y) deve usar a textura de terra (dirt)
    grass_bottom_uv = atlas.uv_table[int(BlockType.GRASS), 3]
    # Retângulos de textura devem ser iguais
    assert np.isclose(grass_bottom_uv[:, 0].min(), dirt_uv[:, 0].min())
    assert np.isclose(grass_bottom_uv[:, 1].min(), dirt_uv[:, 1].min())


def test_chunk_mesher_with_atlas_integration():
    """ChunkMesher com atlas deve atribuir as UVs mapeadas do atlas aos vértices da malha."""
    atlas = TextureAtlas(create_gl=False)
    mesher = ChunkMesher(atlas=atlas)

    chunk = Chunk3D()
    chunk.set_block(0, 0, 0, BlockType.STONE)
    chunk.set_block(0, 1, 0, BlockType.GRASS)

    data = mesher.build(chunk)
    assert data.face_count > 0

    # Verifica se os vértices contêm UVs e cores do atlas
    vertices = data.vertices
    # UVs estão nas colunas 6 e 7
    assert np.all(vertices[:, 6] >= 0.0) and np.all(vertices[:, 6] <= 1.0)
    assert np.all(vertices[:, 7] >= 0.0) and np.all(vertices[:, 7] <= 1.0)
    # Cores nas colunas 8, 9, 10
    assert np.all(vertices[:, 8:11] >= 0.0) and np.all(vertices[:, 8:11] <= 1.0)
