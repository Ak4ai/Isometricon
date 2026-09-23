import os, json
import numpy as np
from src.clothing.wear_engine import RobloxWearEngine

base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"

# Load the conformed vertices
with open("temp_nearest_test.json", "r") as f:
    d = json.load(f)

v = np.array(d['fem_verts'], dtype=np.float32)
m_npz = np.load(os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz"))
faces = m_npz['cage_faces']
v_orig = m_npz['cage_verts_rest']

edges = set()
for f in faces:
    for i in range(3):
        edges.add(tuple(sorted([f[i], f[(i+1)%3]])))

for i0, i1 in edges:
    dist = np.linalg.norm(v[i0] - v[i1])
    orig_d = np.linalg.norm(v_orig[i0] - v_orig[i1])
    if dist < 0.005 and orig_d > 0.005:
        dir_vec = (v_orig[i0] - v_orig[i1]) / orig_d
        mid = 0.5 * (v[i0] + v[i1])
        target_d = min(orig_d * 0.8, 0.015)
        v[i0] = mid + 0.5 * target_d * dir_vec
        v[i1] = mid - 0.5 * target_d * dir_vec

# Save roblox_female_cage_data.npz
fem_data_dict = dict(m_npz)
fem_data_dict["cage_verts_rest"] = v
fem_data_dict["shoulder_l_head"] = np.array([0.204087, 0.003967, 1.476274], dtype=np.float32)
fem_data_dict["shoulder_l_tail"] = np.array([0.306928, 0.018708, 1.167635], dtype=np.float32)
fem_data_dict["shoulder_r_head"] = np.array([-0.204087, 0.003967, 1.476274], dtype=np.float32)
fem_data_dict["shoulder_r_tail"] = np.array([-0.306928, 0.018708, 1.167635], dtype=np.float32)
fem_data_dict["elbow_l"] = np.array([0.306928, 0.018708, 1.167635], dtype=np.float32)
fem_data_dict["elbow_r"] = np.array([-0.306928, 0.018708, 1.167635], dtype=np.float32)
fem_data_dict["wrist_l"] = np.array([0.333062, 0.021355, 0.682131], dtype=np.float32)
fem_data_dict["wrist_r"] = np.array([-0.333062, 0.021355, 0.682131], dtype=np.float32)

fem_npz_path = os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz")
np.savez(fem_npz_path, **fem_data_dict)
print(f"Saved refined female cage data to {fem_npz_path}")

# Run deformation for top (sweater) and bottom (jeans)
engine_fem = RobloxWearEngine(cage_data_path=fem_npz_path)

# Top
top_res = engine_fem.wear("9240757332", body_type="female")
print(f"Top wear complete: {top_res['output_obj']}")

# Bottom
bot_res = engine_fem.wear("109837605892174", body_type="female")
print(f"Bottom wear complete: {bot_res['output_obj']}")
