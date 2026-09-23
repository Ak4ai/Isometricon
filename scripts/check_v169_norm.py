import os
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_v169_norm.txt").replace("\\", "/")
code = f"""
import bpy
cage = bpy.data.objects['Roblox_Inner_Cage_Universal']
v = cage.data.vertices[169]
with open("{out_path}", "w") as f:
    f.write(f"co: {{v.co}}, norm: {{v.normal}}")
"""
execute_blender_code(code)
with open("temp_v169_norm.txt") as f:
    print(f.read())
