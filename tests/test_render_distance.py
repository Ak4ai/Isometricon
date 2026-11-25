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


def test_quadrado_carregado_acompanha_a_distancia():
    """A névoa da borda fecha antes do fim do que está carregado: o quadrado segue o raio na hora."""
    manager = WorldManager(TerrainGenerator(seed=1, enable_caves=False), render_distance=1, create_gl_meshes=False,
                           async_loading=False)
    assert manager.loaded_rect(8.0, 8.0) == (-16, -16, 32, 32)
    manager.render_distance = 3
    assert manager.loaded_rect(8.0, -1.0) == (-48, -64, 64, 48)


def test_nevoa_na_borda_e_opcao_ligada_por_padrao():
    from src.core.game_storage import GRAPHICS
    from src.interactive.settings_screen import value_text
    assert GRAPHICS['edge_fog'][0] is True
    assert value_text('edge_fog', False) == 'Não'
