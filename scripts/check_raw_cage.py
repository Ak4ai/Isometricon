import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_cage_rest_check.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

cage = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
raw_verts = np.array([v.co for v in cage.data.vertices])

depsgraph = bpy.context.evaluated_depsgraph_get()
eval_cage = cage.evaluated_get(depsgraph)
eval_verts = np.array([v.co for v in eval_cage.data.vertices])

diff = float(np.max(np.abs(eval_verts - raw_verts)))

with open("{out_path}", "w") as f:
    json.dump({{
        'raw_min': raw_verts.min(axis=0).tolist(),
        'raw_max': raw_verts.max(axis=0).tolist(),
        'eval_min': eval_verts.min(axis=0).tolist(),
        'eval_max': eval_verts.max(axis=0).tolist(),
        'diff': diff
    }}, f, indent=2)
"""
res = execute_blender_code(code)
print("Blender res:", res)
if os.path.exists("temp_cage_rest_check.json"):
    with open("temp_cage_rest_check.json") as f:
        print(f.read())
