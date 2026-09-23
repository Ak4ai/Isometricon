import os
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_cage_bounds.txt").replace("\\", "/")
code = f"""
import bpy, numpy as np
obj = bpy.data.objects.get('Roblox_Inner_Cage_Universal')
verts = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
with open("{out_path}", "w") as f:
    f.write(f"min: {{verts.min(axis=0)}}, max: {{verts.max(axis=0)}}")
"""
execute_blender_code(code)
with open("temp_cage_bounds.txt") as f:
    print(f.read())
