import os, json
import numpy as np

# Load original male cage
m_npz = np.load("assets/models/roblox_cage_data.npz")
verts_m = m_npz["cage_verts_rest"]
faces = m_npz["cage_faces"]

# Load female cages directly from assets/models/clothing/female_cages.obj
def load_obj_groups(path):
    groups = {}
    current_g = "default"
    verts = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.strip().split()[1:4]])
            elif line.startswith("o ") or line.startswith("g "):
                current_g = line.strip().split(None, 1)[1]
                if current_g not in groups:
                    groups[current_g] = {"faces": []}
            elif line.startswith("f "):
                # OBJ 1-indexed
                f_idx = [int(p.split("/")[0]) - 1 for p in line.strip().split()[1:4]]
                groups[current_g]["faces"].append(f_idx)
    all_v = np.array(verts, dtype=np.float32)
    # Convert OpenGL OBJ [-Y, Z, etc] to Blender coords if needed
    # female_cages.obj: let's check bounding box
    return all_v, groups

fem_v, fem_groups = load_obj_groups("assets/models/clothing/female_cages.obj")
print(f"female_cages.obj loaded: {len(fem_v)} vertices, {len(fem_groups)} groups:")
for gname, gdata in fem_groups.items():
    print(f"  {gname:25s}: {len(gdata['faces'])} faces")
