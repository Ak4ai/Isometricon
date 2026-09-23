import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_male_vg_bounds.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

cage = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
res = {{}}
for vg in cage.vertex_groups:
    v_idx = [v.index for v in cage.data.vertices if any(g.group == vg.index for g in v.groups)]
    verts = np.array([cage.matrix_world @ cage.data.vertices[i].co for i in v_idx])
    res[vg.name] = {{
        'min': verts.min(axis=0).tolist(),
        'max': verts.max(axis=0).tolist(),
        'count': len(v_idx)
    }}

with open("{out_path}", "w") as f:
    json.dump(res, f, indent=2)
"""
execute_blender_code(code)
with open("temp_male_vg_bounds.json") as f:
    print(f.read())
