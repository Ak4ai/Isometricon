import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_vg_info.json").replace("\\", "/")
code = f"""
import bpy, json

obj = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
info = {{}}
if obj:
    for vg in obj.vertex_groups:
        verts_in_vg = [v.index for v in obj.data.vertices if any(g.group == vg.index for g in v.groups)]
        info[vg.name] = len(verts_in_vg)

with open("{out_path}", "w") as f:
    json.dump(info, f, indent=2)
"""
execute_blender_code(code)
with open("temp_vg_info.json") as f:
    print(f.read())
