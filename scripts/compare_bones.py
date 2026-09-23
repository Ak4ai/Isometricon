import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_bones_compare.json").replace("\\", "/")
code = f"""
import bpy, json

def get_bones(arm_name):
    arm = bpy.data.objects[arm_name]
    res = {{}}
    for b in arm.data.bones:
        res[b.name] = {{
            'head': list(arm.matrix_world @ b.head_local),
            'tail': list(arm.matrix_world @ b.tail_local),
            'length': b.length
        }}
    return res

data = {{
    'male': get_bones('Armature_Character'),
    'female': get_bones('Armature_Character.001')
}}

with open("{out_path}", "w") as f:
    json.dump(data, f, indent=2)
"""
execute_blender_code(code)
with open("temp_bones_compare.json") as f:
    print(f.read())
