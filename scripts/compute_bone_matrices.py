import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_bone_matrices.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

arm_m = bpy.data.objects["Armature_Character"]
arm_f = bpy.data.objects["Armature_Character.001"]

res = {{}}
for b_name in arm_m.data.bones.keys():
    bm = arm_m.data.bones[b_name]
    bf = arm_f.data.bones[b_name]
    
    # World matrix of bone
    mat_m = arm_m.matrix_world @ bm.matrix_local
    mat_f = arm_f.matrix_world @ bf.matrix_local
    
    rel = mat_f @ mat_m.inverted()
    res[b_name] = {{
        'mat_m': [list(r) for r in mat_m],
        'mat_f': [list(r) for r in mat_f],
        'rel': [list(r) for r in rel]
    }}

with open("{out_path}", "w") as f:
    json.dump(res, f, indent=2)
"""
execute_blender_code(code)
with open("temp_bone_matrices.json") as f:
    print(f.read()[:500])
