import os, json
import numpy as np

base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
cage_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz"))
rest_male = cage_data["cage_verts_rest"].copy()
faces = cage_data["cage_faces"]

# Load female cages bounds and vertices from Blender
with open("temp_cages_info.json", "r") as f:
    fem_info = json.load(f)

# Load vertex group mapping from Blender
with open("temp_vg_info.json", "r") as f:
    vg_counts = json.load(f)

print("Female cages info loaded:")
for k, v in fem_info.items():
    print(f"  {k:25s}: min {np.round(v['min'], 3)}, max {np.round(v['max'], 3)}")
