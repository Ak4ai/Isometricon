import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_blender_all_objects.json").replace("\\", "/")
code = f"""
import bpy, json

info = []
for o in bpy.data.objects:
    info.append({{
        'name': o.name,
        'type': o.type,
        'collections': [c.name for c in o.users_collection],
        'parent': o.parent.name if o.parent else None
    }})

with open("{out_path}", "w") as f:
    json.dump(info, f, indent=2)
"""
execute_blender_code(code)
with open("temp_blender_all_objects.json") as f:
    objs = json.load(f)
    for o in objs:
        if 'cage' in o['name'].lower() or 'roblox' in o['name'].lower() or 'corpo' in o['name'].lower() or 'fem' in o['name'].lower():
            print(o)
