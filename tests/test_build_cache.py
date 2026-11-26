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
    cage = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    hidden = np.array([0.2, 0.5, 0.0], dtype=np.float32)
    triangle = np.array([[0, 1, 2]], dtype=np.int32)
    parts = [
        CharacterPart("head", TexturedMesh(vertices, np.array([0, 1, 2], dtype=np.uint32)), -2,
                      transform=np.eye(4, dtype=np.float32)),
        CharacterPart("top", TexturedMesh(vertices * 2.0), -1, source_obj="top.obj"),
    ]
    model = SimpleNamespace(
        customization=AvatarCustomization(), top_id=1, bottom_id=2, outer_top_id=None, shoes_id=None,
        hair_id=None, tool_id=None, extra_ids=[], hair_offset_x=0.0, hair_offset_y=0.0, hair_offset_z=0.0,
        hair_scale_x=1.0, hair_scale_y=1.0, hair_scale_z=1.0, outer_top_gap_mm=5.0, outer_top_pull_mm=15.0,
        show_cage=False, hsr_edit=False,
        parts=parts, textures=[-1, -2], white_tex_id=-1, cage_debug_mesh=None,
        _garment_buffers={"top": (vertices, triangle.astype(np.uint32).ravel())}, _hide_feet=False,
        hsr_cage=(cage, hidden.copy(), triangle), hsr_hidden=hidden,
        hsr_skin=(cage[:1], triangle, np.array([[0.4, 0.6, 0.0]])),
        _hsr_call=("body.obj", [1.0, 0.9, 0.8], "top.obj", None, False, True, ()),
        _edges={"top": (("top.obj", 12.0), (0.8, 1.0))},
        built_nose_style=("nenhum", False), tail_root=None, wing_root=(0.0, 1.2, -0.1), hair_fades=False,
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
    assert np.array_equal(fresh.hsr_cage[0], model.hsr_cage[0]) and fresh.wing_root == (0.0, 1.2, -0.1)
    assert np.array_equal(fresh.hsr_skin[1], model.hsr_skin[1]) and fresh._edges == model._edges
    assert np.array_equal(fresh.parts[0].transform, model.parts[0].transform)
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


def test_legacy_cache_is_ignored_and_the_build_is_regenerated(tmp_path, monkeypatch, deferred):
    import pickle

    model, images = fake_model()
    key = build_cache.build_key(model)
    old_file = tmp_path / "personagem_montado.pkl"
    old_bytes = pickle.dumps({"chave": key})
    old_file.write_bytes(old_bytes)

    calls = []
    monkeypatch.setattr(pickle, "load", lambda *args: calls.append(args))
    fresh = blank_like(model)
    assert build_cache.load(fresh, key, tmp_path) is None
    assert calls == [] and fresh.parts == []
    assert build_cache.save(model, images, key, tmp_path)
    assert build_cache.load(fresh, key, tmp_path) is not None
    assert old_file.read_bytes() == old_bytes and calls == []


@pytest.mark.parametrize(("field", "invalid"), [
    ("textures", {"unexpected_type": "inofensivo"}),
    ("white_tex_id", False),
    ("_garment_buffers", {"dict": {"top": {"tuple": [None, None]}}}),
    ("_edges", {"dict": {"top": {"tuple": [{"tuple": ["top.obj", 12.0]}]}}}),
    ("hsr_cage", {"tuple": [None, None, None]}),
    ("_hsr_call", {"tuple": ["body.obj"]}),
])
def test_cache_rejects_invalid_nested_members_without_changing_model(tmp_path, deferred, field, invalid):
    import json
    from zipfile import ZipFile

    model, images = fake_model()
    key = build_cache.build_key(model)
    assert build_cache.save(model, images, key, tmp_path)
    filename = tmp_path / build_cache.FILE_NAME
    with ZipFile(filename) as archive:
        members = {entry: archive.read(entry) for entry in archive.namelist()}
    manifest = json.loads(members["manifest.json"])
    manifest["estado"][field] = invalid
    members["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(filename, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)

    fresh = blank_like(model)
    assert build_cache.load(fresh, key, tmp_path) is None
    assert fresh.parts == [] and fresh.textures == [] and fresh.white_tex_id is None


def test_frozen_resource_path_is_resolved_again_when_cache_is_read(tmp_path, monkeypatch, deferred):
    old_bundle, new_bundle = tmp_path / "_MEIold", tmp_path / "_MEInew"
    monkeypatch.setattr(build_cache, "RESOURCE_ROOT", old_bundle)
    model, images = fake_model()
    model.parts[0].source_obj = str(old_bundle / "assets" / "models" / "old.obj")
    assert build_cache.save(model, images, "frozen-key", tmp_path)
    monkeypatch.setattr(build_cache, "RESOURCE_ROOT", new_bundle)
    fresh = blank_like(model)
    assert build_cache.load(fresh, "frozen-key", tmp_path) is not None
    assert fresh.parts[0].source_obj == str(new_bundle / "assets" / "models" / "old.obj")


def test_cache_names_accept_maximum_saved_npc_id_without_path_components(tmp_path, deferred):
    model, images = fake_model()
    model.cache_name = "npc_" + "x" * 96
    assert build_cache.save(model, images, "npc-key", tmp_path)
    assert build_cache.load(blank_like(model), "npc-key", tmp_path) is not None
    model.cache_name = "../npc"
    assert build_cache.load(blank_like(model), "npc-key", tmp_path) is None


def test_cache_rejects_non_finite_part_transform(tmp_path, deferred):
    model, images = fake_model()
    model.parts[0].transform[0, 0] = np.nan
    assert build_cache.save(model, images, "transform", tmp_path)
    fresh = blank_like(model)
    assert build_cache.load(fresh, "transform", tmp_path) is None
    assert fresh.parts == []
