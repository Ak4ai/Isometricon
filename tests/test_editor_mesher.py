import numpy as np

from src.editor.material_atlas import MaterialAtlas
from src.editor.object_mesher import build_mesh_data
from src.editor.voxel_object import VoxelObject


def _single_voxel():
    obj = VoxelObject((3, 3, 3))
    material = obj.material_index((255, 128, 0), "bricks")
    obj.set(1, 1, 1, material)
    return obj


def test_single_voxel_has_six_faces_and_eleven_float_stride():
    data = build_mesh_data(_single_voxel(), MaterialAtlas())
    assert data.face_count == 6
    assert data.vertex_count == 24
    assert data.index_count == 36
    assert data.vertices.shape == (24, 11)
    assert data.indices.max() < data.vertex_count
    assert np.all(data.vertices[:, 8:11] == np.array([1.0, 128 / 255, 0.0], dtype=np.float32))


def test_adjacent_voxels_hide_the_shared_face():
    obj = VoxelObject((3, 3, 3))
    material = obj.material_index((255, 255, 255), "stone")
    obj.set(0, 1, 1, material)
    obj.set(1, 1, 1, material)
    data = build_mesh_data(obj, MaterialAtlas())
    assert data.face_count == 10
    assert data.vertex_count == 40


def test_empty_object_has_no_geometry():
    data = build_mesh_data(VoxelObject((2, 2, 2)), MaterialAtlas())
    assert data.face_count == 0
    assert data.vertex_count == 0
    assert data.index_count == 0


def test_uvs_stay_inside_the_material_tile():
    obj = _single_voxel()
    atlas = MaterialAtlas()
    data = build_mesh_data(obj, atlas)
    u0, v0, u1, v1 = atlas.uv_for("bricks")
    uvs = data.vertices[:, 6:8]
    assert np.all(uvs[:, 0] >= u0 - 1e-6) and np.all(uvs[:, 0] <= u1 + 1e-6)
    assert np.all(uvs[:, 1] >= v0 - 1e-6) and np.all(uvs[:, 1] <= v1 + 1e-6)


def test_unknown_texture_falls_back_to_white_tile():
    obj = VoxelObject((2, 2, 2))
    material = obj.material_index((10, 20, 30), "nao_existe")
    obj.set(0, 0, 0, material)
    atlas = MaterialAtlas()
    data = build_mesh_data(obj, atlas)
    assert data.face_count == 6
    u0, v0, u1, v1 = atlas.uv_for("white_concrete")
    uvs = data.vertices[:, 6:8]
    assert np.all(uvs[:, 0] >= u0 - 1e-6) and np.all(uvs[:, 0] <= u1 + 1e-6)
    assert np.all(uvs[:, 1] >= v0 - 1e-6) and np.all(uvs[:, 1] <= v1 + 1e-6)
