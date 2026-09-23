import os
import sys
base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import numpy as np
from src.clothing.wear_engine import RobloxWearEngine


base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
fem_npz = os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz")

# Test engine initialization with female cage
engine = RobloxWearEngine(cage_data_path=fem_npz, body_type="female")
print(f"Engine initialized with female cage: {engine.cage_verts_rest.shape} verts, {engine.cage_faces.shape} faces")
print(f"Grid apose: {len(engine.grid_apose.centroids)} centroids")
print(f"Grid tpose: {len(engine.grid_tpose.centroids)} centroids")

# Test wearing Sweater 9240757332
print("\n--- Testing Sweater 9240757332 ---")
top_path = os.path.join(base_dir, "assets", "models", "clothing", "Knit_Sweater_-_Black_9240757332.obj")
if os.path.exists(top_path):
    verts, faces, uvs, face_uvs = engine.load_obj(top_path)
    sleeve_idx, torso_idx = engine.analyze_topology(verts, faces)
    apose_verts, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(verts, faces, sleeve_idx, torso_idx)
    deformed = engine.deform_top_mesh(apose_verts, faces, sleeve_idx, torso_idx)
    print(f"Sweater deformed successfully: {len(deformed)} verts. Z bounds: [{deformed[:, 2].min():.3f}, {deformed[:, 2].max():.3f}]")

# Test wearing Jeans 109837605892174
print("\n--- Testing Jeans 109837605892174 ---")
bot_path = os.path.join(base_dir, "assets", "models", "clothing", "Black_Distressed_Designer_Jeans_w__Boots_109837605892174.obj")
if os.path.exists(bot_path):
    verts_b, faces_b, uvs_b, face_uvs_b = engine.load_obj(bot_path)
    tpose_verts_b = engine.fit_bottom_clothing(verts_b)
    deformed_b = engine.deform_mesh(tpose_verts_b, engine.cage_verts_tpose_85, engine.cage_verts_rest, engine.grid_tpose)
    print(f"Jeans deformed successfully: {len(deformed_b)} verts. Z bounds: [{deformed_b[:, 2].min():.3f}, {deformed_b[:, 2].max():.3f}]")
    print(f"Jeans Y bounds (front/back): [{deformed_b[:, 1].min():.3f}, {deformed_b[:, 1].max():.3f}]")
    print(f"Jeans X bounds (width): [{deformed_b[:, 0].min():.3f}, {deformed_b[:, 0].max():.3f}]")
