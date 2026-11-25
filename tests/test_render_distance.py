"""Configurações > Gráficos > Distância de render: a troca vale na hora, sem andar nem reabrir o mundo."""

from src.world.terrain import TerrainGenerator
from src.world.manager import WorldManager


def _columns(manager):
    return {(k[0], k[2]) for k in manager.chunks}


def test_trocar_distancia_carrega_e_descarrega_sem_mover():
    manager = WorldManager(TerrainGenerator(seed=1, enable_caves=False), render_distance=1, create_gl_meshes=False, async_loading=False)
    manager.load_initial_region(8.0, 8.0)
    manager.update(8.0, 8.0)
    assert len(_columns(manager)) == 9

    manager.render_distance = 2
    manager.update(8.0, 8.0)
    assert len(_columns(manager)) == 25

    manager.render_distance = 1
    manager.update(8.0, 8.0)
    assert len(_columns(manager)) == 9
