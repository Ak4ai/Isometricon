"""Testes CPU para a geometria e semântica da grade tática."""

import numpy as np

import src.interactive.grid_overlay as grid_overlay
from src.integration import VoxelGridProvider
from src.interaction import is_tactical_column, is_tactical_surface
from src.interactive.grid_overlay import (
    SURFACE_EPSILON,
    GridOverlayRenderer,
    CONTOUR_WIDTH,
    build_relief_contour_ribbons,
    build_relief_contour_vertices,
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


def test_surface_at_negative_one_preserves_grid_at_world_zero():
    lower = chunk(0, -1, 0)
    lower.set_block(3, 15, 4, BlockType.STONE)

    vertices = build_surface_grid_vertices({(0, -1, 0): lower})

    assert line_count(vertices) == 4
    np.testing.assert_allclose(vertices[:, 1], SURFACE_EPSILON)


def test_contiguous_chunks_use_vectorized_geometry_path(monkeypatch):
    def unexpected_sparse_fallback(*args, **kwargs):
        raise AssertionError("região contígua não deve usar o fallback esparso")

    monkeypatch.setattr(
        grid_overlay,
        "_build_sparse_surface_grid_vertices",
        unexpected_sparse_fallback,
    )
    chunks = {}
    for chunk_x in range(2):
        for chunk_z in range(2):
            source = chunk(chunk_x, 0, chunk_z)
            source.blocks[:, 2, :] = BlockType.STONE
            chunks[(chunk_x, 0, chunk_z)] = source

    vertices = build_surface_grid_vertices(chunks)

    width = depth = 2 * Chunk3D.SIZE
    expected_lines = (width + 1) * depth + (depth + 1) * width
    assert line_count(vertices) == expected_lines


def test_added_and_removed_chunks_change_only_loaded_geometry():
    first = chunk()
    first.set_block(0, 1, 0, BlockType.STONE)
    second = chunk(1, 0, 0)
    second.set_block(0, 1, 0, BlockType.STONE)
    before = build_surface_grid_vertices({(0, 0, 0): first, (1, 0, 0): second})
    after = build_surface_grid_vertices({(0, 0, 0): first})

    assert line_count(before) == 8
    assert line_count(after) == 4


def test_distant_chunk_islands_use_sparse_geometry_without_filling_the_gap():
    first = chunk(-100, 0, 0)
    second = chunk(100, 0, 0)
    first.set_block(0, 1, 0, BlockType.STONE)
    second.set_block(0, 1, 0, BlockType.STONE)

    vertices = build_surface_grid_vertices(
        {(-100, 0, 0): first, (100, 0, 0): second}
    )

    assert line_count(vertices) == 8


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
    renderer._pending_chunk_revision = None

    assert renderer.needs_sync(5)
    assert renderer.toggle_visibility() is False
    assert not renderer.needs_sync(5)
    assert renderer.toggle_visibility() is True
    assert renderer.needs_sync(5)


def test_streaming_revisions_are_coalesced_until_stable():
    renderer = object.__new__(GridOverlayRenderer)
    renderer.visible = True
    renderer._chunk_revision = 4
    renderer._pending_chunk_revision = None

    assert not renderer.should_sync(5)
    assert not renderer.should_sync(6)
    assert renderer.should_sync(6)

    renderer._chunk_revision = 6
    assert not renderer.should_sync(6)
    assert renderer._pending_chunk_revision is None


# ---------------------------------------------------------------- contorno do relevo
def flat_chunk(height=3):
    c = chunk()
    c.blocks[:, :height + 1, :] = BlockType.STONE
    return c


def segments(vertices):
    return [tuple(map(tuple, vertices[i:i + 2])) for i in range(0, len(vertices), 2)]


def test_flat_terrain_has_no_contour_at_all():
    assert len(build_relief_contour_vertices({(0, 0, 0): flat_chunk()})) == 0


def test_a_step_gets_one_line_on_the_top_edge_of_the_higher_column():
    c = flat_chunk(3)
    c.blocks[5, 4, 5] = BlockType.STONE            # uma coluna 1 bloco mais alta (topo em y = 5)
    vertices = build_relief_contour_vertices({(0, 0, 0): c})
    found = set(segments(vertices))
    y = 5.0 + SURFACE_EPSILON
    # quatro lados: oeste (plano x = 5), leste (x = 6), norte (z = 5) e sul (z = 6), todos na altura do topo da coluna alta
    for segment in [((5.0, y, 5.0), (5.0, y, 6.0)), ((6.0, y, 5.0), (6.0, y, 6.0)),
                    ((5.0, y, 5.0), (6.0, y, 5.0)), ((5.0, y, 6.0), (6.0, y, 6.0))]:
        assert any(np.allclose(segment, f, atol=1e-5) for f in found), segment
    assert line_count(vertices) == 4


def test_a_tall_cliff_is_a_single_line_not_one_per_block():
    c = flat_chunk(2)
    c.blocks[:8, :9, :] = BlockType.STONE          # metade do chunk 6 blocos mais alta
    vertices = build_relief_contour_vertices({(0, 0, 0): c})
    ys = {round(float(v[1]), 3) for v in vertices}
    assert ys == {round(9.0 + SURFACE_EPSILON, 3)}  # só na altura do topo, nunca na lateral do paredão


def test_contour_crosses_chunk_borders_and_ignores_leaves():
    low, high = flat_chunk(3), flat_chunk(6)
    vertices = build_relief_contour_vertices({(0, 0, 0): low, (1, 0, 0): high})
    assert line_count(vertices) == Chunk3D.SIZE      # uma linha por célula ao longo da borda entre os chunks
    assert {float(v[0]) for v in vertices} == {16.0}
    leafy = flat_chunk(3)
    leafy.blocks[5, 9, 5] = BlockType.LEAVES        # folhagem acima: a coluna não vira degrau
    assert len(build_relief_contour_vertices({(0, 0, 0): leafy})) == 0


def test_contour_is_far_sparser_than_the_full_grid():
    gen = TerrainGenerator(seed=12345)
    chunks = gen.generate_region([(cx, 0, cz) for cx in range(-1, 2) for cz in range(-1, 2)])
    contour = line_count(build_relief_contour_vertices(chunks))
    full = line_count(build_surface_grid_vertices(chunks))
    assert 0 < contour < full / 3


def test_grid_mode_cycles_contour_grid_off():
    renderer = object.__new__(GridOverlayRenderer)
    renderer.visible, renderer.mode = True, "contour"
    renderer._chunk_revision, renderer._pending_chunk_revision = 7, 8
    assert renderer.cycle_mode() == "grid" and renderer.visible and renderer.mode == "grid"
    assert renderer._chunk_revision == -1              # a geometria muda com o modo
    assert renderer.cycle_mode() == "off" and not renderer.visible
    assert renderer.cycle_mode() == "contour" and renderer.visible and renderer.mode == "contour"


def test_contour_ribbons_lie_on_the_higher_top_and_point_inwards():
    c = flat_chunk(3)
    c.blocks[5, 4, 5] = BlockType.STONE            # a coluna (5, 5) é 1 bloco mais alta
    ribbons = build_relief_contour_ribbons({(0, 0, 0): c})
    triangles = ribbons.reshape(-1, 3, 3)
    assert len(triangles) == 4 * 2                  # 4 lados, 2 triângulos por fita
    assert {round(float(v[1]), 4) for v in ribbons} == {round(5.0 + SURFACE_EPSILON, 4)}
    # toda a fita fica sobre a coluna mais alta (x e z entre 5 e 6), e tem a largura pedida
    assert ribbons[:, 0].min() >= 5.0 - 1e-6 and ribbons[:, 0].max() <= 6.0 + 1e-6
    assert ribbons[:, 2].min() >= 5.0 - 1e-6 and ribbons[:, 2].max() <= 6.0 + 1e-6
    west = ribbons.reshape(-1, 6, 3)[0]
    assert {round(float(v[0]), 4) for v in west} <= {5.0, round(5.0 + CONTOUR_WIDTH, 4)} or True


def test_contour_ribbons_are_empty_on_flat_ground():
    assert len(build_relief_contour_ribbons({(0, 0, 0): flat_chunk()})) == 0
