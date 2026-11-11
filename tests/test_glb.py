"""Testes do leitor de modelos .glb e do CustomModel (sem OpenGL)."""

import base64
import json
import struct

import numpy as np
import pytest

from src.clothing import glb
from src.clothing.custom_model import CustomModel
from src.clothing.glb import ModelError, load_model, parse_model
from src.clothing.glb_writer import GlbBuilder, box, checker_png, sample_humanoid


def one_box(builder, material=None, **node):
    positions, normals, uvs, indices = box((-0.5, 0.0, -0.5), (0.5, 1.0, 0.5))
    mesh = builder.add_mesh(positions, indices, normals, uvs, material=material)
    return builder.add_node(mesh=mesh, **node)


def build(node_options=None, material=None):
    builder = GlbBuilder()
    node = one_box(builder, material, **(node_options or {}))
    return builder.build([node]), builder


# ---------------------------------------------------------------------------------------------- leitura
def test_reads_the_sample_humanoid():
    model = parse_model(sample_humanoid())
    assert len(model.submeshes) == 7 and model.triangles == 7 * 12
    assert model.submeshes[1].image is not None and model.submeshes[0].image is None      # a camisa tem textura
    assert model.submeshes[0].color[:3] == pytest.approx((1.0, 0.82, 0.68))
    low, high = model.bounds()
    assert low[1] == pytest.approx(0.0) and high[1] == pytest.approx(1.7)
    vertices = model.submeshes[0].vertices
    assert vertices.shape[1] == glb.FLOATS_PER_VERTEX and vertices.dtype == np.float32
    assert np.allclose(np.linalg.norm(vertices[:, 3:6], axis=1), 1.0, atol=1e-5)          # normais unitárias


def test_reads_from_disk_and_reports_a_missing_file(tmp_path):
    path = tmp_path / "boneco.glb"
    path.write_bytes(sample_humanoid())
    assert load_model(str(path)).triangles == 84
    with pytest.raises(ModelError, match="abrir"):
        load_model(str(tmp_path / "nao_existe.glb"))


def test_a_gltf_with_everything_embedded_is_accepted():
    data, _ = build()
    document, blob = glb._split_glb(data)
    document["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(blob).decode()
    assert parse_model(json.dumps(document).encode()).triangles == 12


def test_node_transforms_are_applied():
    data, _ = build({"translation": (2.0, 0.0, 0.0), "scale": (2.0, 2.0, 2.0)})
    low, high = parse_model(data).bounds()
    assert low[0] == pytest.approx(1.0) and high[0] == pytest.approx(3.0) and high[1] == pytest.approx(2.0)


def test_rotation_and_a_column_major_matrix():
    half = np.sqrt(0.5)
    data, _ = build({"rotation": (0.0, half, 0.0, half)})              # 90° em y
    low, high = parse_model(data).bounds()
    assert high[0] - low[0] == pytest.approx(1.0) and high[1] == pytest.approx(1.0)
    matrix = np.identity(4)
    matrix[:3, 3] = (0.0, 5.0, 0.0)
    data, _ = build({"matrix": matrix})
    assert parse_model(data).bounds()[0][1] == pytest.approx(5.0)       # a translação vem na última coluna


def test_nested_nodes_multiply_their_transforms():
    builder = GlbBuilder()
    child = one_box(builder, translation=(0.0, 1.0, 0.0))
    parent = builder.add_node(name="pai", translation=(0.0, 10.0, 0.0), children=[child])
    low, _ = parse_model(builder.build([parent])).bounds()
    assert low[1] == pytest.approx(11.0)


def test_a_mirrored_node_keeps_faces_outwards():
    data, _ = build({"scale": (-1.0, 1.0, 1.0)})
    sub = parse_model(data).submeshes[0]
    tri = sub.vertices[sub.indices[:3], :3]
    geometric = np.cross(tri[1] - tri[0], tri[2] - tri[0])
    assert np.dot(geometric, sub.vertices[sub.indices[0], 3:6]) > 0


def test_a_skinned_node_ignores_its_own_transform():
    builder = GlbBuilder()
    node = one_box(builder, translation=(9.0, 0.0, 0.0), skin=0)
    builder.skins.append({"joints": [node]})
    model = parse_model(builder.build([node]))
    assert model.skins == 1 and model.bounds()[0][0] == pytest.approx(-0.5)


def test_missing_normals_uvs_and_indices_are_filled_in():
    builder = GlbBuilder()
    positions = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0)], dtype=np.float32)
    mesh = builder.add_mesh(positions, None)                                  # sem normais, UV nem índices
    model = parse_model(builder.build([builder.add_node(mesh=mesh)]))
    vertices = model.submeshes[0].vertices
    assert model.triangles == 1 and np.allclose(vertices[:, 3:6], (0, 0, 1))  # a normal da face
    assert np.allclose(vertices[:, 6:8], 0)


def test_interleaved_attributes_are_read_with_the_byte_stride():
    """Posição e normal intercaladas num mesmo buffer (stride 24), como muitos exportadores fazem."""
    vertices = np.array([[0, 0, 0, 0, 0, 1], [1, 0, 0, 0, 0, 1], [0, 1, 0, 0, 0, 1]], dtype=np.float32)
    blob = vertices.tobytes()
    document = {
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}}]}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                      {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": 3, "type": "VEC3"}],
        "bufferViews": [{"buffer": 0, "byteLength": len(blob), "byteStride": 24}],
        "buffers": [{"byteLength": len(blob), "uri": "data:;base64," + base64.b64encode(blob).decode()}],
    }
    sub = parse_model(json.dumps(document).encode()).submeshes[0]
    assert np.allclose(sub.vertices[:, :3], vertices[:, :3]) and np.allclose(sub.vertices[:, 3:6], (0, 0, 1))


# ---------------------------------------------------------------------------------------------- segurança
def test_external_uris_are_refused():
    data, _ = build()
    document, _ = glb._split_glb(data)
    document["buffers"][0]["uri"] = "../../segredo.bin"
    with pytest.raises(ModelError, match="arquivo externo"):
        parse_model(json.dumps(document).encode())
    builder = GlbBuilder()
    material = builder.add_material()
    builder.images.append({"uri": "C:/Windows/algo.png"})
    builder.textures.append({"source": 0})
    builder.materials[material]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
    node = one_box(builder, material)
    with pytest.raises(ModelError, match="arquivo externo"):
        parse_model(builder.build([node]))


def test_limits_on_triangles_texture_and_file_size(monkeypatch, tmp_path):
    data, _ = build()
    monkeypatch.setattr(glb, "MAX_TRIANGLES", 5)
    with pytest.raises(ModelError, match="triângulos"):
        parse_model(data)
    monkeypatch.undo()
    monkeypatch.setattr(glb, "MAX_TEXTURE_SIDE", 8)
    builder = GlbBuilder()
    node = one_box(builder, builder.add_material(png=checker_png(16)))
    with pytest.raises(ModelError, match="textura"):
        parse_model(builder.build([node]))
    monkeypatch.undo()
    path = tmp_path / "grande.glb"
    path.write_bytes(data)
    monkeypatch.setattr(glb, "MAX_FILE_BYTES", 16)
    with pytest.raises(ModelError, match="MB|passa"):
        load_model(str(path))


def test_broken_files_become_model_errors_not_crashes():
    data, _ = build()
    for bad in (b"", b"isto nao e um modelo", data[:30], data[: len(data) // 2], b"glTF" + b"\0" * 40):
        with pytest.raises(ModelError):
            parse_model(bad)
    document, blob = glb._split_glb(data)
    document["asset"]["version"] = "1.0"
    with pytest.raises(ModelError, match="2.0"):
        parse_model(json.dumps(document).encode())
    document["asset"]["version"] = "2.0"
    document["meshes"][0]["primitives"][0]["indices"] = 999                       # accessor que não existe
    with pytest.raises(ModelError):
        parse_model(json.dumps(document).encode())


def test_an_index_past_the_vertices_is_refused():
    builder = GlbBuilder()
    positions = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0)], dtype=np.float32)
    mesh = builder.add_mesh(positions, [0, 1, 7])
    with pytest.raises(ModelError, match="índice"):
        parse_model(builder.build([builder.add_node(mesh=mesh)]))


def test_a_model_without_triangles_is_refused():
    builder = GlbBuilder()
    node = builder.add_node(name="vazio")
    with pytest.raises(ModelError, match="malha"):
        parse_model(builder.build([node]))


# ---------------------------------------------------------------------------------------------- normalizar
def test_normalize_puts_feet_on_the_ground_centres_and_scales():
    data, _ = build({"translation": (7.0, 3.0, -4.0), "scale": (3.0, 3.0, 3.0)})
    model = parse_model(data).normalize(1.8)
    low, high = model.bounds()
    assert low[1] == pytest.approx(0.0) and high[1] == pytest.approx(1.8)
    assert (low[0] + high[0]) / 2 == pytest.approx(0.0) and (low[2] + high[2]) / 2 == pytest.approx(0.0)


def test_normalize_can_turn_the_model_to_face_another_way():
    model = parse_model(sample_humanoid())
    nose = model.submeshes[6].vertices[:, :3].mean(axis=0)
    assert nose[2] > 0 and abs(nose[0]) < 1e-6                     # o nariz está em +z
    turned = parse_model(sample_humanoid()).normalize(1.7, yaw_turns=1)
    turned_nose = turned.submeshes[6].vertices[:, :3].mean(axis=0)
    assert turned_nose[0] > 0 and abs(turned_nose[2]) < 1e-6        # um quarto de volta: agora em +x
    normal = turned.submeshes[6].vertices[:, 3:6]
    assert np.allclose(np.linalg.norm(normal, axis=1), 1.0, atol=1e-5)


def test_a_flat_model_cannot_be_normalized():
    builder = GlbBuilder()
    positions = np.array([(0, 0, 0), (1, 0, 0), (0, 0, 1)], dtype=np.float32)
    mesh = builder.add_mesh(positions, [0, 1, 2])
    with pytest.raises(ModelError, match="altura"):
        parse_model(builder.build([builder.add_node(mesh=mesh)])).normalize(1.8)


# ---------------------------------------------------------------------------------------------- CustomModel
def test_custom_model_without_a_gpu():
    model = CustomModel.from_bytes(sample_humanoid(), height=1.5, create_gl=False, name="amostra")
    low, high = model.bounds()
    assert model.name == "amostra" and model.triangles == 84 and model.parts == []
    assert high[1] - low[1] == pytest.approx(1.5) and model.is_loading is False
