"""A água que se espalha sozinha junta as mudanças e refaz no máximo a cada ``water_remesh_interval``."""

from src.world import BlockType, Chunk3D, TerrainGenerator, WorldManager


def flat_world():
    manager = WorldManager(TerrainGenerator(base_height=4, amplitude=0, sea_level=-20),
                           create_gl_meshes=False, async_loading=False)
    for cx in (-1, 0):
        for cz in (-1, 0):
            chunk = Chunk3D(cx, 0, cz)
            chunk.blocks[:, :4, :] = int(BlockType.STONE)
            manager.chunks[(cx, 0, cz)] = chunk
    return manager


def run(manager, frames):
    revisions = []
    for frame in range(frames):
        before = manager._chunk_revision
        manager._simulate_water(0.0, 0.0)
        if manager._chunk_revision != before:
            revisions.append(frame)
    return revisions


def test_flowing_water_refreshes_at_most_twice_a_second_and_ends_complete():
    manager = flat_world()
    assert manager.place_water(0, 4, 0)
    bumps = run(manager, 60 * 4)                       # 4 s: a fonte espalha 7 blocos em ~7 ondas
    assert len(bumps) >= 2
    gaps = [b - a for a, b in zip(bumps, bumps[1:])]
    assert min(gaps) >= 30                             # ondas a cada 0,25 s viram no máximo 2 refazeres por segundo
    assert not manager._water_pending                  # nada ficou para trás quando a água parou
    wet = sum(int((c.blocks == int(BlockType.WATER)).sum()) for c in manager.chunks.values())
    assert wet > 100                                    # a poça se formou


def test_player_edit_takes_pending_water_along_right_away():
    manager = flat_world()
    manager.place_water(0, 4, 0)
    for _ in range(200):
        manager._simulate_water(0.0, 0.0)
        if manager._water_pending:
            break
    assert manager._water_pending
    before = manager._chunk_revision
    manager.place_block(5, 4, 5, BlockType.STONE)
    assert manager._chunk_revision == before + 1 and not manager._water_pending
