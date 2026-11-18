"""Cache do personagem montado: guardar, ler de volta e não reaproveitar o que mudou (sem OpenGL)."""

import copy
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from src.clothing import build_cache
from src.clothing.character_model import CharacterPart
from src.clothing.customization import AvatarCustomization, IrisColor
from src.rendering.mesh import DEFERRED, TexturedMesh


@pytest.fixture
def deferred():
    DEFERRED.on = True        # malhas só com os dados, como na thread de fundo
    yield
    DEFERRED.on = False


def fake_model():
    """O que a montagem deixa no modelo: as partes, as texturas (marcadores negativos) e o que ela descobriu."""
    vertices = np.arange(3 * 11, dtype=np.float32)
    parts = [
        CharacterPart("head", TexturedMesh(vertices, np.array([0, 1, 2], dtype=np.uint32)), -2),
        CharacterPart("top", TexturedMesh(vertices * 2.0), -1, source_obj="top.obj"),
    ]
    model = SimpleNamespace(
        customization=AvatarCustomization(), top_id=1, bottom_id=2, outer_top_id=None, shoes_id=None,
        hair_id=None, tool_id=None, extra_ids=[], hair_offset_x=0.0, hair_offset_y=0.0, hair_offset_z=0.0,
        hair_scale_x=1.0, hair_scale_y=1.0, hair_scale_z=1.0, outer_top_gap_mm=5.0, outer_top_pull_mm=15.0,
        show_cage=False, hsr_edit=False,
        parts=parts, textures=[-1, -2], white_tex_id=-1, cage_debug_mesh=None,
        _garment_buffers={"top": (vertices, None)}, _hide_feet=False, hsr_cage=np.ones(4), hsr_hidden=None,
        hsr_skin=None, _hsr_call=("body.obj", [1.0, 0.9, 0.8], None, None, True, True, ()), _edges={},
        built_nose_style="nenhum", tail_root=None, wing_root=(0.0, 1.2, -0.1), hair_fades=False,
    )
    images = {-1: Image.new("RGBA", (4, 4), (255, 255, 255, 255)), -2: Image.new("RGBA", (8, 8), (10, 20, 30, 255))}
    return model, images


def blank_like(model):
    """O modelo como a thread de fundo o recebe: sem nada montado."""
    other = copy.copy(model)
    other.customization = copy.copy(model.customization)
    other.parts, other.textures, other.white_tex_id = [], [], None
    return other


def test_saved_build_comes_back(tmp_path, deferred):
    model, images = fake_model()
    key = build_cache.build_key(model)
    build_cache.save(model, images, key, tmp_path)
    fresh = blank_like(model)
    loaded = build_cache.load(fresh, key, tmp_path)
    assert loaded is not None
    assert [p.name for p in fresh.parts] == ["head", "top"]
    assert [p.texture_id for p in fresh.parts] == [-2, -1] and fresh.textures == [-1, -2] and fresh.white_tex_id == -1
    assert fresh.parts[1].source_obj == "top.obj"
    assert np.array_equal(fresh.parts[0].mesh.read_vertices(), model.parts[0].mesh.read_vertices())
    assert np.array_equal(fresh.parts[0].mesh.read_indices(), [0, 1, 2]) and fresh.parts[0].mesh.index_count == 3
    assert np.array_equal(fresh.hsr_cage, np.ones(4)) and fresh.wing_root == (0.0, 1.2, -0.1)
    assert set(loaded) == {-1, -2} and loaded[-2].size == (8, 8) and loaded[-2].getpixel((0, 0)) == (10, 20, 30, 255)


def test_what_the_build_chose_for_the_hair_comes_back(tmp_path, deferred):
    """A montagem acha o cabelo ajustado ao corpo e o anota na aparência: lido do cache, a anotação volta junto."""
    model, images = fake_model()
    key = build_cache.build_key(model)
    model.customization.custom_hair_obj = "Hair_fitted_123_female.obj"
    build_cache.save(model, images, key, tmp_path)
    fresh = blank_like(model)
    fresh.customization.custom_hair_obj = None
    assert build_cache.load(fresh, key, tmp_path) is not None
    assert fresh.customization.custom_hair_obj == "Hair_fitted_123_female.obj"


@pytest.mark.parametrize("change", [
    lambda m: setattr(m.customization, "iris_color", IrisColor.GREEN if m.customization.iris_color != IrisColor.GREEN
                      else IrisColor.BLUE),
    lambda m: setattr(m, "top_id", 99),
    lambda m: setattr(m, "hair_offset_y", 0.01),
    lambda m: setattr(m, "outer_top_gap_mm", 8.0),
])
def test_any_change_to_the_character_misses_the_cache(tmp_path, deferred, change):
    model, images = fake_model()
    key = build_cache.build_key(model)
    build_cache.save(model, images, key, tmp_path)
    change(model)
    other = build_cache.build_key(model)
    assert other != key
    assert build_cache.load(blank_like(model), other, tmp_path) is None


def test_a_change_in_the_assets_or_the_code_misses_the_cache(tmp_path, monkeypatch, deferred):
    model, _ = fake_model()
    key = build_cache.build_key(model)
    monkeypatch.setattr(build_cache, "_assets_fingerprint", lambda: "outro")
    assert build_cache.build_key(model) != key
    monkeypatch.undo()
    monkeypatch.setattr(build_cache, "_code_fingerprint", lambda: "outro")
    assert build_cache.build_key(model) != key


def test_a_missing_or_broken_cache_is_a_miss(tmp_path, deferred):
    model, _ = fake_model()
    key = build_cache.build_key(model)
    assert build_cache.load(blank_like(model), key, tmp_path) is None
    (tmp_path / build_cache.FILE_NAME).write_bytes(b"lixo")
    assert build_cache.load(blank_like(model), key, tmp_path) is None
