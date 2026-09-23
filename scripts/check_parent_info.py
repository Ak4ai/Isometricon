import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_parent_info.json").replace("\\", "/")
code = f"""
import bpy, json

info = {{}}
for o in bpy.data.collections["Cages_Feminino"].objects:
    info[o.name] = {{
        'parent': o.parent.name if o.parent else None,
        'parent_type': o.parent_type,
        'parent_bone': o.parent_bone
    }}

with open("{out_path}", "w") as f:
    json.dump(info, f, indent=2)
"""
execute_blender_code(code)
with open("temp_parent_info.json") as f:
    print(f.read())
