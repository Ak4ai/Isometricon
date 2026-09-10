"""Testes CPU para a geometria e semântica da grade tática."""

import numpy as np

from src.integration import VoxelGridProvider
from src.interaction import is_tactical_column, is_tactical_surface
from src.interactive.grid_overlay import (
    SURFACE_EPSILON,
    GridOverlayRenderer,
    build_surface_grid_vertices,
)
from src.world import BlockType, Chunk3D, TerrainGenerator, WorldManager


def chunk(x=0, y=0, z=0):
    return Chunk3D(x, y, z)


def line_count(vertices):
    assert vertices.ndim == 2 and vertices.shape[1] == 3
    return len(vertices) // 2


def test_empty_geometry_is_float32_and_has_no_vertices():
    vertices = build_surface_grid_vertices({})
    assert vertices.dtype == np.float32
    assert vertices.shape == (0, 3)


def test_one_cell_is_aligned_to_voxel_top_with_epsilon():
    source = chunk()
    source.set_block(2, 5, 3, BlockType.GRASS)
    vertices = build_surface_grid_vertices({(0, 0, 0): source})

    assert vertices.dtype == np.float32
    assert line_count(vertices) == 4
    np.testing.assert_allclose(vertices[:, 1], 6.0 + SURFACE_EPSILON)
    assert set(vertices[:, 0]) == {2.0, 3.0}
    assert set(vertices[:, 2]) == {3.0, 4.0}


def test_adjacent_flat_cells_share_their_common_line():
    source = chunk()
    source.set_block(0, 2, 0, BlockType.STONE)
    source.set_block(1, 2, 0, BlockType.DIRT)
    vertices = build_surface_grid_vertices({(0, 0, 0): source})

    # Dois quadrados possuem 8 lados, mas compartilham um: 7 segmentos.
    assert line_count(vertices) == 7


def test_height_difference_keeps_each_cell_on_its_own_top_face():
    source = chunk()
    source.set_block(0, 1, 0, BlockType.STONE)
    source.set_block(1, 4, 0, BlockType.STONE)
    vertices = build_surface_grid_vertices({(0, 0, 0): source})

    assert line_count(vertices) == 8
    # Nenhum segmento inclina verticalmente entre os dois níveis.
    segments = vertices.reshape(-1, 2, 3)
    assert all(segment[0, 1] == segment[1, 1] for segment in segments)
    np.testing.assert_allclose(
        np.unique(vertices[:, 1]),
        [2.0 + SURFACE_EPSILON, 5.0 + SURFACE_EPSILON],
    )


def test_negative_coordinates_and_multiple_chunks_are_global():
    left = chunk(-1, 0, -1)
    right = chunk(0, 0, -1)
    left.set_block(15, 3, 15, BlockType.WOOD)
    right.set_block(0, 7, 15, BlockType.DIRT)
    vertices = build_surface_grid_vertices({(-1, 0, -1): left, (0, 0, -1): right})

    assert line_count(vertices) == 8
    assert -1.0 in vertices[:, 0]
    assert 0.0 in vertices[:, 0]
    assert 1.0 in vertices[:, 0]
    assert -1.0 in vertices[:, 2]


def test_water_blocks_grid_over_the_submerged_support_and_leaves_do_not_create_cells():
    source = chunk()
    source.set_block(0, 2, 0, BlockType.STONE)
    source.set_block(0, 8, 0, BlockType.WATER)
    source.set_block(1, 6, 0, BlockType.LEAVES)
    vertices = build_surface_grid_vertices({(0, 0, 0): source})

    # Água acima da pedra também exclui o leito; folhas isoladas não geram grade.
    assert line_count(vertices) == 0
    assert is_tactical_surface(BlockType.WOOD)
    assert not is_tactical_surface(BlockType.WATER)
    assert not is_tactical_surface(BlockType.LEAVES)
    assert not is_tactical_column(BlockType.STONE, BlockType.WATER)
    assert is_tactical_column(BlockType.STONE, BlockType.LEAVES)


def test_highest_support_across_vertical_chunks_is_used():
    lower = chunk(0, 0, 0)
    upper = chunk(0, 1, 0)
    lower.set_block(3, 15, 4, BlockType.STONE)
    upper.set_block(3, 2, 4, BlockType.GRASS)
    vertices = build_surface_grid_vertices({(0, 0, 0): lower, (0, 1, 0): upper})

    np.testing.assert_allclose(vertices[:, 1], 19.0 + SURFACE_EPSILON)


def test_added_and_removed_chunks_change_only_loaded_geometry():
    first = chunk()
    first.set_block(0, 1, 0, BlockType.STONE)
    second = chunk(1, 0, 0)
    second.set_block(0, 1, 0, BlockType.STONE)
    before = build_surface_grid_vertices({(0, 0, 0): first, (1, 0, 0): second})
    after = build_surface_grid_vertices({(0, 0, 0): first})

    assert line_count(before) == 8
    assert line_count(after) == 4


def test_voxel_provider_chunks_are_usable_without_graphics_context():
    source = chunk()
    source.set_block(4, 3, 5, BlockType.GRASS)
    provider = VoxelGridProvider({(0, 0, 0): source})
    vertices = build_surface_grid_vertices(provider.chunks)

    assert line_count(vertices) == 4


def test_world_manager_snapshot_revision_changes_with_streaming():
    manager = WorldManager(
        generator=TerrainGenerator(seed=7, enable_caves=False),
        render_distance=0,
        create_gl_meshes=False,
        async_loading=False,
    )
    revision_before, chunks_before = manager.get_loaded_chunks_snapshot()
    manager.update(0.0, 0.0)
    revision_after, chunks_after = manager.get_loaded_chunks_snapshot()

    assert revision_after > revision_before
    assert not chunks_before
    assert (0, 0, 0) in chunks_after
    manager.update(32.0, 0.0)
    revision_moved, chunks_moved = manager.get_loaded_chunks_snapshot()
    assert revision_moved > revision_after
    assert (0, 0, 0) not in chunks_moved
    manager.delete()
    revision_deleted, chunks_deleted = manager.get_loaded_chunks_snapshot()
    assert revision_deleted > revision_moved
    assert not chunks_deleted


def test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context():
    # O estado é independente de VAO/VBO; constrói só o objeto necessário ao
    # contrato de visibilidade para manter o teste CPU-only.
    renderer = object.__new__(GridOverlayRenderer)
    renderer.visible = True
    renderer._chunk_revision = 4

    assert renderer.needs_sync(5)
    assert renderer.toggle_visibility() is False
    assert not renderer.needs_sync(5)
    assert renderer.toggle_visibility() is True
    assert renderer.needs_sync(5)
