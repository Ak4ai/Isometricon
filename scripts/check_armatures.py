import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_blender_armatures.json").replace("\\", "/")
code = f"""
import bpy, json

arms = {{}}
for o in bpy.data.objects:
    if o.type == "ARMATURE":
        arms[o.name] = [b.name for b in o.data.bones]

with open("{out_path}", "w") as f:
    json.dump(arms, f, indent=2)
"""
execute_blender_code(code)
with open("temp_blender_armatures.json") as f:
    print(f.read())
