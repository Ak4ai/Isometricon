"""The world token walks the dressed avatar with its own steps."""
from types import SimpleNamespace

import numpy as np

from src.interactive.token_system import PlayerToken
from tests.test_character_animation import MemoryMesh

W = 87  # glfw.KEY_W


def make_token():
    skin = MemoryMesh([[-.02, .9, .0], [.02, .9, .0], [0, .94, .0]])
    cloth = MemoryMesh([[.12, .5, .05], [.14, .5, .05], [.13, .3, .05]])
    parts = [SimpleNamespace(name="legs_skin", mesh=skin, transform=None, source_obj=None),
             SimpleNamespace(name="bottom", mesh=cloth, transform=None, source_obj="missing.obj")]
    avatar = SimpleNamespace(body="female", parts=parts, draw=lambda shader, matrix: None, delete=lambda: None)
    return PlayerToken(avatar=avatar), cloth


def test_avatar_walks_while_the_token_moves_and_rests_when_it_stops():
    token, cloth = make_token()
    ground = lambda x, z: 0
    forward, right = np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])
    token.update(1 / 60, {}, forward, right, ground)
    rest = cloth.read_vertices()[:, :3].copy()
    assert token.animator.walking is False
    for _ in range(20):
        token.update(1 / 60, {W: True}, forward, right, ground)
    assert token.animator.walking is True
    assert token.animator.walk_time == token.walk_time
    assert np.abs(cloth.read_vertices()[:, :3] - rest).max() > 1e-3  # the leg moved
    token.update(1 / 60, {}, forward, right, ground)
    assert token.animator.walking is False
    eased = np.abs(cloth.read_vertices()[:, :3] - rest).max()
    assert eased > 1e-4  # it does not snap back to rest
    for _ in range(60):
        token.update(1 / 60, {}, forward, right, ground)
    np.testing.assert_allclose(cloth.read_vertices()[:, :3], rest, atol=1e-6)


def test_token_without_avatar_keeps_the_old_doll():
    token = PlayerToken(create_mesh=False)
    assert token.avatar is None and token.animator is None
