import os
import json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_blender_cage.json").replace("\\", "/")
code = f"""
import bpy, json
obj = bpy.data.objects.get('Roblox_Inner_Cage_Universal')
res = {{}}
if obj:
    res['name'] = obj.name
    res['v_count'] = len(obj.data.vertices)
    res['f_count'] = len(obj.data.polygons)
    res['vertex_groups'] = [vg.name for vg in obj.vertex_groups]
    res['matrix_world'] = [list(row) for row in obj.matrix_world]
with open("{out_path}", "w", encoding="utf-8") as f:
    json.dump(res, f)
"""
execute_blender_code(code)
with open("temp_blender_cage.json", "r", encoding="utf-8") as f:
    print(json.load(f))
