import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_modifiers.json").replace("\\", "/")
code = f"""
import bpy, json

mods = {{}}
obj = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
if obj:
    mods[obj.name] = [{{'name': m.name, 'type': m.type}} for m in obj.modifiers]

for o in bpy.data.collections["Cages_Feminino"].objects:
    mods[o.name] = [{{'name': m.name, 'type': m.type}} for m in o.modifiers]

with open("{out_path}", "w") as f:
    json.dump(mods, f, indent=2)
"""
execute_blender_code(code)
with open("temp_modifiers.json") as f:
    print(f.read())
