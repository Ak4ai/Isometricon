import os
import numpy as np
import pytest
from src.clothing.wear_engine import RobloxWearEngine, slice_mesh_below_z, SpatialGrid3D

def test_cage_reference_load():
    engine = RobloxWearEngine()
    assert engine.cage_verts_apose.shape == (1711, 3)
    assert engine.cage_verts_rest.shape == (1711, 3)
    assert engine.cage_faces.shape == (2690, 3)
    assert engine.elbow_z > 0.9

def test_spatial_grid_acceleration():
    engine = RobloxWearEngine()
    test_pt = np.array([0.25, 0.0, 1.30])
    cands = engine.grid_apose.query_nearest_candidates(test_pt, k_neighbors=1)
    assert len(cands) > 0

def test_slice_mesh_watertight():
    # Simple cube or tetrahedron
    verts = np.array([
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 1.0],
        [0.0, 1.0, 1.0],
        [0.0, 0.0, 2.0]
    ], dtype=np.float32)
    faces = np.array([
        [0, 1, 2],
        [0, 1, 3],
        [1, 2, 3],
        [2, 0, 3]
    ], dtype=np.int32)
    
    sliced_v, sliced_f = slice_mesh_below_z(verts, faces, 1.5)
    assert len(sliced_v) > 0
    assert np.all(sliced_v[:, 2] <= 1.50001)

def test_shoulder_deltoid_volume_preservation():
    engine = RobloxWearEngine()
    obj_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "models", "clothing", "-_office_shirt__BLACK_133331049150205.obj"
    )
    if not os.path.exists(obj_path):
        pytest.skip("Asset file not found")
        
    v, f, _, _ = engine.load_obj(obj_path)
    s_idx, t_idx = engine.analyze_topology(v, f)
    apose_v, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(v, f, s_idx, t_idx)
    
    assert is_short is True
    # Verify shoulder top height is not collapsed below 1.44m at the deltoid
    deltoid_mask = (np.abs(apose_v[:, 0]) > 0.22) & (np.abs(apose_v[:, 0]) < 0.32) & (apose_v[:, 2] > 1.35)
    assert np.sum(deltoid_mask) > 0
    deltoid_top_z = np.max(apose_v[deltoid_mask, 2])
    assert deltoid_top_z >= 1.45, f"Deltoid height {deltoid_top_z} should be at least 1.45m"

def test_boxy_shirt_universal_fit():
    engine = RobloxWearEngine()
    engine.dual_cage_ready = False  # the barycentric fallback for garments without cages
    obj_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "models", "clothing", "Boxy_Shirt_Y2K_-_BLACK_89475537632859.obj"
    )
    if not os.path.exists(obj_path):
        pytest.skip("Asset file not found")

    v, f, _, _ = engine.load_obj(obj_path)
    s_idx, t_idx = engine.analyze_topology(v, f)
    assert len(s_idx) >= 500, "Sleeves should contain both front and back sleeve panels"
    assert len(t_idx) > 1000, "Torso should contain torso front, back, and collar"

    apose_v, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(v, f, s_idx, t_idx)
    assert is_short is True, "Boxy T-shirt must be classified as short sleeve"
    assert is_long is False

    # Test limb-partitioned continuous deformation
    deformed_v = engine.deform_top_mesh(apose_v, f, s_idx, t_idx)
    assert deformed_v.shape == apose_v.shape

    # Verify no edge tearing on dorsal/back shoulder region
    back_mask = (np.abs(deformed_v[:, 0]) > 0.15) & (np.abs(deformed_v[:, 0]) < 0.35) & (deformed_v[:, 1] < 0) & (deformed_v[:, 2] > 1.20) & (deformed_v[:, 2] < 1.45)
    max_edge = 0.0
    for face in f:
        if any(back_mask[idx] for idx in face):
            for i in range(3):
                e_len = np.linalg.norm(deformed_v[face[i]] - deformed_v[face[(i+1)%3]])
                if e_len > max_edge:
                    max_edge = e_len
    assert max_edge < 0.12, f"Back shoulder edge stretched too much: {max_edge:.3f}m"

def test_sleeveless_jersey_universal_fit():
    engine = RobloxWearEngine()
    obj_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "models", "clothing", "76ers_Basketball_Jersey_97346273111638.obj"
    )
    if not os.path.exists(obj_path):
        pytest.skip("Asset file not found")

    v, f, _, _ = engine.load_obj(obj_path)
    s_idx, t_idx = engine.analyze_topology(v, f)
    assert len(s_idx) == 0, "Basketball jersey must have 0 sleeve vertices"
    assert len(t_idx) == len(v), "All vertices must be classified as torso"

    apose_v, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(v, f, s_idx, t_idx)
    assert is_sleeveless is True, "Must be classified as sleeveless / regata"
    assert is_short is False
    assert is_long is False

    deformed_v = engine.deform_top_mesh(apose_v, f, s_idx, t_idx)
    assert deformed_v.shape == apose_v.shape

def test_filemesh_v1_decode_and_equip_katana():
    from scripts.import_roblox_clothing import decode_roblox_mesh_to_obj
    engine = RobloxWearEngine()

    # FileMesh v1 ASCII payload test
    raw_v1 = b"version 1.00\r\n2\r\n[0,0,0][0,1,0][0,0,0][1,0,0][0,1,0][1,0,0][0,0,1][0,1,0][0,1,0][1,0,0][0,1,0][1,0,0][1,1,0][0,1,0][1,1,0][0,0,1][0,1,0][0,1,0]"
    tmp_obj = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "models", "test_v1_mesh.obj"
    )
    decode_roblox_mesh_to_obj(raw_v1, tmp_obj)
    assert os.path.exists(tmp_obj)
    
    verts, faces, uvs, _ = engine.load_obj(tmp_obj)
    assert len(verts) == 6
    assert len(faces) == 2
    if os.path.exists(tmp_obj):
        os.remove(tmp_obj)

    # Test Katana tool equip
    res = engine.equip_tool(12187348, hand="right")
    assert res["name"] == "RoninKatana" or "Katana" in res["name"]
    assert os.path.exists(res["output_obj"])
    assert res["tex_path"] is not None
    assert os.path.exists(res["tex_path"])

    v_k, f_k, _, _ = engine.load_obj(res["output_obj"])
    assert len(v_k) > 100
    # Center around right hand X ~ -0.345
    assert np.isclose(np.mean(v_k[:, 0]), -0.345, atol=0.20)



