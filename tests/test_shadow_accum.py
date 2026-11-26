"""A contabilidade da sombra acumulada (o histórico, a matriz do quadro anterior, o tamanho), sem placa de vídeo."""

import itertools
from unittest import mock

import numpy as np
import pytest

from src.rendering import shadow_accum


class FakeShader:
    def __init__(self):
        self.values = {}

    def set_bool(self, name, value):
        self.values[name] = bool(value)

    def set_int(self, name, value):
        self.values[name] = int(value)

    def set_mat4(self, name, value):
        self.values[name] = np.array(value)


@pytest.fixture
def fake_gl(monkeypatch):
    gl = mock.MagicMock()
    names = itertools.count(1)
    gl.glGenTextures.side_effect = lambda n: next(names)
    gl.glGenFramebuffers.side_effect = lambda n: next(names)
    gl.glGetIntegerv.return_value = 7
    monkeypatch.setattr(shadow_accum, "gl", gl)
    return gl


def frame(accum, shader, size, clip):
    accum.begin(shader, size, clip)
    accum.end()


def test_first_frame_has_no_history_then_carries_the_previous_matrix(fake_gl):
    accum, shader = shadow_accum.ShadowAccumulator(), FakeShader()
    first, second = np.eye(4) * 2.0, np.eye(4) * 3.0
    frame(accum, shader, (64, 32), first)
    assert shader.values["u_AccumHistory"] is False
    accum.begin(shader, (64, 32), second)
    assert shader.values["u_AccumHistory"] is True
    assert np.allclose(shader.values["u_AccumPrevClip"], first)


def test_resizing_forgets_the_history(fake_gl):
    accum, shader = shadow_accum.ShadowAccumulator(), FakeShader()
    frame(accum, shader, (64, 32), np.eye(4))
    accum.begin(shader, (80, 32), np.eye(4))
    assert shader.values["u_AccumHistory"] is False
    assert fake_gl.glDeleteTextures.called


def test_reads_last_frames_pair_and_writes_the_other(fake_gl):
    accum, shader = shadow_accum.ShadowAccumulator(), FakeShader()
    written = []
    fake_gl.glBindImageTexture.side_effect = lambda unit, texture, *rest: written.append((unit, texture))
    for _ in range(3):
        frame(accum, shader, (8, 8), np.eye(4))
    out = [texture for unit, texture in written if unit == shadow_accum.OUT_IMAGE]
    assert out[0] != out[1] and out[0] == out[2]


def test_clearing_keeps_the_scene_framebuffer_bound(fake_gl):
    accum, shader = shadow_accum.ShadowAccumulator(), FakeShader()
    accum.begin(shader, (8, 8), np.eye(4))
    last = fake_gl.glBindFramebuffer.call_args_list[-1]
    assert last.args == (fake_gl.GL_DRAW_FRAMEBUFFER, 7)
    assert not fake_gl.glClearColor.called


def test_reset_starts_over(fake_gl):
    accum, shader = shadow_accum.ShadowAccumulator(), FakeShader()
    frame(accum, shader, (8, 8), np.eye(4))
    accum.reset()
    accum.begin(shader, (8, 8), np.eye(4))
    assert shader.values["u_AccumHistory"] is False
