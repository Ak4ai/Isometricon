"""Testes unitários para PlayerToken, movimentação e WorldManager."""

import math
import numpy as np
import pytest

from src.interactive.token_system import PlayerToken
from src.world import TerrainGenerator, WorldManager


def test_player_token_initialization():
    token = PlayerToken(start_x=5.5, start_z=10.5, speed=4.0, create_mesh=False)
    assert token.position[0] == 5.5
    assert token.position[2] == 10.5
    assert token.speed == 4.0
    assert token.yaw == 0.0
    assert not token.is_moving

    matrix = token.get_model_matrix()
    assert matrix.shape == (4, 4)
    assert matrix.dtype == np.float32


def test_player_token_get_current_block():
    token = PlayerToken(start_x=3.7, start_z=-2.3, create_mesh=False)
    token.position[1] = 9.0  # token está em Y=9.0 (base em Y=9.0)
    
    # Bloco abaixo é em Y=8, X=3, Z=-3 (floor de -2.3 é -3)
    bx, by, bz = token.get_current_block()
    assert bx == 3
    assert bz == -3
    assert by == 8


def test_player_token_movement_and_rotation():
    import glfw

    token = PlayerToken(start_x=0.0, start_z=0.0, speed=10.0, create_mesh=False)
    fwd = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    right = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    def mock_height(x, z):
        return 5

    # Simula pressionar W (andar para frente) por 0.1 segundos
    keys = {glfw.KEY_W: True}
    token.update(0.1, keys, fwd, right, mock_height)

    assert token.is_moving
    assert token.position[2] > 0.0  # moveu para frente no Z
    assert token.position[0] == 0.0

    # Altura deve convergir em direção a surface + 1 = 6.0
    assert abs(token.position[1] - 6.0) < 5.0


def test_player_token_yaw_alignment():
    import glfw

    token = PlayerToken(start_x=0.0, start_z=0.0, speed=5.0, create_mesh=False)
    fwd = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    right = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    def mock_height(x, z):
        return 0

    # Pressionar D (andar para direita: +X)
    keys = {glfw.KEY_D: True}
    token.update(0.2, keys, fwd, right, mock_height)

    # O ângulo deve girar para a direita (+X, ou seja, pi/2 radianos)
    assert token.position[0] > 0.0
    assert token.yaw > 0.0


def test_world_manager_chunk_streaming_logic():
    gen = TerrainGenerator(seed=42, enable_caves=False)
    manager = WorldManager(generator=gen, render_distance=1, create_gl_meshes=False)

    # Atualiza foco na origem (0, 0)
    manager.update(0.0, 0.0)
    assert len(manager.chunks) == 9  # Grade 3x3 (render_distance=1)


    initial_keys = set(manager.chunks.keys())
    assert (0, 0, 0) in initial_keys
    assert (1, 0, 1) in initial_keys

    # Move o foco 100 blocos para frente no X (longe do inicial)
    manager.update(100.0, 0.0)

    # Chunks antigos devem ter sido descarregados
    new_keys = set(manager.chunks.keys())
    assert (0, 0, 0) not in new_keys
    assert any(k[0] >= 5 for k in new_keys)

    manager.delete()
    assert len(manager.chunks) == 0
    assert len(manager.meshes) == 0


def test_token_mesh_winding_and_normals():
    """Valida que os triângulos do token têm enrolamento CCW voltado para fora (evita culling indevido)."""
    from src.interactive.token_system import _build_cylinder, _build_disc

    v_data = []
    i_data = []
    slices = 8
    color = (0.2, 0.2, 0.2)

    # 1. Testa cilindro
    _build_cylinder(1.0, 1.0, 0.0, 1.0, slices, color, v_data, i_data)
    vertices = np.array(v_data)

    for idx in range(0, len(i_data), 3):
        i0, i1, i2 = i_data[idx], i_data[idx + 1], i_data[idx + 2]
        p0 = vertices[i0, 0:3]
        p1 = vertices[i1, 0:3]
        p2 = vertices[i2, 0:3]
        normal = np.cross(p1 - p0, p2 - p0)
        center = (p0 + p1 + p2) / 3.0
        # A normal deve apontar no mesmo sentido que o centro radial (para fora)
        assert np.dot(normal[:3], [center[0], 0.0, center[2]]) > 0.0

    # 2. Testa tampa superior
    v_disc = []
    i_disc = []
    _build_disc(1.0, 1.0, slices, 1.0, color, v_disc, i_disc)
    v_disc_arr = np.array(v_disc)
    for idx in range(0, len(i_disc), 3):
        i0, i1, i2 = i_disc[idx], i_disc[idx + 1], i_disc[idx + 2]
        p0 = v_disc_arr[i0, 0:3]
        p1 = v_disc_arr[i1, 0:3]
        p2 = v_disc_arr[i2, 0:3]
        normal = np.cross(p1 - p0, p2 - p0)
        # Normal deve apontar para +Y
        assert normal[1] > 0.0


def test_world_manager_load_initial_region():
    """Valida que load_initial_region carrega síncronamente a vizinhança inicial no spawn."""
    gen = TerrainGenerator(seed=123, enable_caves=False)
    manager = WorldManager(generator=gen, render_distance=1, create_gl_meshes=False, async_loading=False)

    manager.load_initial_region(0.0, 0.0)
    # render_distance=1 gera grade 3x3 = 9 colunas
    assert len(manager.chunks) == 9
    assert (0, 0, 0) in manager.chunks

    manager.delete()
    assert len(manager.chunks) == 0


def test_world_manager_pending_deletions_amortization():
    """Valida que a deleção de malhas na GPU é amortizada por frame e limpa no shutdown."""
    gen = TerrainGenerator(seed=123, enable_caves=False)
    manager = WorldManager(generator=gen, render_distance=1, create_gl_meshes=False, async_loading=False)

    deleted_count = 0

    class MockMesh:
        def delete(self):
            nonlocal deleted_count
            deleted_count += 1

    # Adiciona 3 malhas falsas à fila de deleção pendente
    m1, m2, m3 = MockMesh(), MockMesh(), MockMesh()
    manager._pending_mesh_deletions.extend([m1, m2, m3])
    assert len(manager._pending_mesh_deletions) == 3

    # update() consome 1 por frame
    manager.update(0.0, 0.0)
    assert deleted_count == 1
    assert len(manager._pending_mesh_deletions) == 2

    # Próximo update consome mais 1
    manager.update(0.0, 0.0)
    assert deleted_count == 2
    assert len(manager._pending_mesh_deletions) == 1

    # delete() limpa todos os restantes
    manager.delete()
    assert deleted_count == 3
    assert len(manager._pending_mesh_deletions) == 0


def test_world_manager_result_queue_safe_without_gl():
    """Valida que itens na _result_queue são consumidos sem erro quando create_gl_meshes=False."""
    gen = TerrainGenerator(seed=123, enable_caves=False)
    manager = WorldManager(generator=gen, render_distance=1, create_gl_meshes=False, async_loading=False)

    from src.world.chunk import Chunk3D
    from src.world.mesher import ChunkMeshData
    dummy_data = ChunkMeshData(np.empty((0, 11), dtype=np.float32), np.empty(0, dtype=np.uint32))
    dummy_chunk = Chunk3D(0, 0, 0)
    manager.chunks[(0, 0, 0)] = dummy_chunk
    manager._in_progress.add((0, 0, 0))
    manager._result_queue.put(((0, 0, 0), dummy_chunk, dummy_data))

    manager.delete()


def test_world_manager_reports_each_pending_streaming_stage():
    manager = WorldManager(
        generator=TerrainGenerator(seed=123, enable_caves=False),
        render_distance=1,
        create_gl_meshes=False,
        async_loading=False,
    )
    assert not manager.has_pending_streaming_work()

    manager._in_progress.add((0, 0, 0))
    assert manager.has_pending_streaming_work()
    manager._in_progress.clear()

    manager._request_queue.put([(0, 0, 0)])
    assert manager.has_pending_streaming_work()
    manager._request_queue.get_nowait()
    manager._request_queue.task_done()

    manager._worker_busy.set()
    assert manager.has_pending_streaming_work()
    manager._worker_busy.clear()

    manager._result_queue.put(object())
    assert manager.has_pending_streaming_work()
    manager._result_queue.get_nowait()
    manager._result_queue.task_done()

    assert not manager.has_pending_streaming_work()
    manager.delete()


def test_world_manager_frustum_culling_rendering():
    """Valida que render() com view_projection aplica Frustum Culling e descarta chunks fora da tela."""
    gen = TerrainGenerator(seed=123, enable_caves=False)
    manager = WorldManager(generator=gen, render_distance=2, create_gl_meshes=False, async_loading=False)

    drawn = []

    class MockMesh:
        def __init__(self, name):
            self.name = name
        def draw(self):
            drawn.append(self.name)

    class MockShader:
        def set_mat4(self, name, mat):
            pass

    from src.math import mat4_translate
    # Adiciona 1 chunk na origem e 1 chunk muito distante
    manager.meshes[(0, 0, 0)] = (MockMesh("near"), mat4_translate(0, 0, 0))
    manager.meshes[(100, 0, 100)] = (MockMesh("far"), mat4_translate(1600, 0, 1600))

    # Câmera focada na origem
    from src.camera.camera import IsometricCamera
    from src.math import vec3, mat4_identity
    cam = IsometricCamera(target=vec3(0.0, 0.0, 0.0), ortho_size=4.0)
    vp = cam.get_projection_matrix(1280, 720) @ cam.get_view_matrix()

    # Sem view_projection: desenha todos (2)
    count_all = manager.render(MockShader(), mat4_identity())
    assert count_all == 2
    assert len(drawn) == 2

    # Com view_projection: descarta o chunk distante a 1600 blocos
    drawn.clear()
    count_culled = manager.render(MockShader(), mat4_identity(), view_projection=vp)
    assert count_culled == 1
    assert drawn == ["near"]

    manager.delete()


def test_modular_character_loading_and_fk():
    """Valida o carregamento da hierarquia modular e avaliação FK a partir do JSON."""
    import os
    from src.interactive.token_system import ModularCharacter

    json_path = os.path.join("assets", "models", "character_modular.json")
    if not os.path.exists(json_path):
        pytest.skip("character_modular.json não encontrado")

    char = ModularCharacter(json_path, create_mesh=False)
    assert len(char.parts) == 14
    assert "pelve" in char.parts
    assert "torso" in char.parts
    assert "coxa esquerda" in char.parts
    assert "canela esquerda" in char.parts

    # Garante que 'pelve' (raiz) é processada antes de 'torso' e 'coxas'
    pelve_idx = char.topological_order.index("pelve")
    torso_idx = char.topological_order.index("torso")
    coxa_e_idx = char.topological_order.index("coxa esquerda")
    assert pelve_idx < torso_idx
    assert pelve_idx < coxa_e_idx

    # Matrizes de mundo devem ter formato (4, 4) e tipo float32
    for part in char.parts.values():
        assert part.world_matrix.shape == (4, 4)
        assert part.world_matrix.dtype == np.float32

    char.delete()
    assert len(char.parts) == 0


def test_modular_character_walk_cycle_animation():
    """Valida a alteração dos ângulos articulares durante a passada e retorno ao repouso."""
    import os
    from src.interactive.token_system import ModularCharacter

    json_path = os.path.join("assets", "models", "character_modular.json")
    if not os.path.exists(json_path):
        pytest.skip("character_modular.json não encontrado")

    char = ModularCharacter(json_path, create_mesh=False)

    # Estado de repouso inicial
    coxa_e = char.parts["coxa esquerda"]
    assert abs(coxa_e.local_rot[0]) < 1e-4

    # Simula passada andando no ápice do avanço do quadril (walk_time = 0)
    char.update_animation(dt=0.1, is_moving=True, walk_time=0.0)
    assert abs(coxa_e.local_rot[0]) > 0.05

    # Simula passada no ápice da flexão do joelho ao avançar a perna (fase swing: 1.5 * pi)
    canela_e = char.parts["canela esquerda"]
    char.update_animation(dt=0.1, is_moving=True, walk_time=1.5 * math.pi)
    assert canela_e.local_rot[0] > 0.1

    # Simula parada (repouso) por vários frames
    for _ in range(30):
        char.update_animation(dt=0.05, is_moving=False, walk_time=0.0)

    # Ângulo do quadril deve amortecer de volta para perto de zero
    assert abs(coxa_e.local_rot[0]) < 0.05

    char.delete()

