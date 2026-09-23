import os
import json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_cages_info.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

col = bpy.data.collections.get("Cages_Feminino")
info = {{}}
if col:
    for obj in col.objects:
        verts = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
        info[obj.name] = {{
            'v_count': len(obj.data.vertices),
            'f_count': len(obj.data.polygons),
            'min': verts.min(axis=0).tolist(),
            'max': verts.max(axis=0).tolist()
        }}

with open("{out_path}", "w") as f:
    json.dump(info, f, indent=2)
"""
execute_blender_code(code)
with open("temp_cages_info.json") as f:
    print(f.read())
