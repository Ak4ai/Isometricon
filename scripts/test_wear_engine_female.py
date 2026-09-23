import os, json
import numpy as np
from src.clothing.wear_engine import RobloxWearEngine, TOP_ASSET_TYPES

base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"

# Load the generated female cage verts
with open("temp_full_fem_cage_test.json", "r") as f:
    data = json.load(f)

fem_rest = np.array(data["fem_verts"], dtype=np.float32)

# Load existing roblox_cage_data.npz
male_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz"))

# Create roblox_female_cage_data.npz
fem_data_dict = dict(male_data)
fem_data_dict["cage_verts_rest"] = fem_rest

# Update skeletal joints for female
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
print(f"Saved female cage data to {fem_npz_path}")

# Now test RobloxWearEngine with female cage!
engine_fem = RobloxWearEngine(cage_data_path=fem_npz_path)

# Test deforming top (Sweater 9240757332)
top_raw_path = os.path.join(base_dir, "assets", "models", "clothing", "Knit_Sweater_-_Black_9240757332.obj")
verts, faces, uvs, face_uvs = engine_fem.load_obj(top_raw_path)
sleeve_idx, torso_idx = engine_fem.analyze_topology(verts, faces)
apose_verts, cuff_z, is_sleeveless, is_short, is_long = engine_fem.fit_top_clothing(verts, faces, sleeve_idx, torso_idx)
deformed_top = engine_fem.deform_top_mesh(apose_verts, faces, sleeve_idx, torso_idx)

out_top_fem = os.path.join(base_dir, "assets", "models", "character_native_9240757332_female.obj")
with open(out_top_fem, "w", encoding="utf-8") as f:
    f.write("# Isometricon Native Deformed Female Top\n")
    for v in deformed_top:
        f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
    for vt in uvs:
        f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
    for f_idx, face in enumerate(faces):
        uv_f = face_uvs[f_idx]
        face_str = " ".join([f"{vi+1}/{uvi+1}" for vi, uvi in zip(face, uv_f)])
        f.write(f"f {face_str}\n")
print(f"Exported female top to {out_top_fem}")

# Test deforming bottom (Jeans 109837605892174)
bot_raw_path = os.path.join(base_dir, "assets", "models", "clothing", "Black_Distressed_Designer_Jeans_w__Boots_109837605892174.obj")
verts_b, faces_b, uvs_b, face_uvs_b = engine_fem.load_obj(bot_raw_path)
tpose_verts_b = engine_fem.fit_bottom_clothing(verts_b)
deformed_bot = engine_fem.deform_mesh(tpose_verts_b, engine_fem.cage_verts_tpose_85, engine_fem.cage_verts_rest, engine_fem.grid_tpose)

out_bot_fem = os.path.join(base_dir, "assets", "models", "character_native_109837605892174_female.obj")
with open(out_bot_fem, "w", encoding="utf-8") as f:
    f.write("# Isometricon Native Deformed Female Bottom\n")
    for v in deformed_bot:
        f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
    for vt in uvs_b:
        f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
    for f_idx, face in enumerate(faces_b):
        uv_f = face_uvs_b[f_idx]
        face_str = " ".join([f"{vi+1}/{uvi+1}" for vi, uvi in zip(face, uv_f)])
        f.write(f"f {face_str}\n")
print(f"Exported female bottom to {out_bot_fem}")
