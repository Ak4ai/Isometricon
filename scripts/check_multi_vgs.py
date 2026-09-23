import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_multi_vgs.json").replace("\\", "/")
code = f"""
import bpy, json

cage_obj = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
multi = []
for v in cage_obj.data.vertices:
    groups = [cage_obj.vertex_groups[g.group].name for g in v.groups if g.weight > 0.01]
    if len(groups) > 1:
        multi.append((v.index, groups))

with open("{out_path}", "w") as f:
    json.dump({{'count': len(multi), 'samples': multi[:20]}}, f, indent=2)
"""
execute_blender_code(code)
with open("temp_multi_vgs.json") as f:
    print(f.read())
