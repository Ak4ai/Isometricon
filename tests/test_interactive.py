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
