import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_surfacedeform_test.json").replace("\\", "/")
code = f"""
import bpy, json

# Check if surface deform works
cage = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
torso_cage = bpy.data.objects.get("UpperTorso_OuterCage")

res = {{'cage': cage.name, 'torso': torso_cage.name}}
with open("{out_path}", "w") as f:
    json.dump(res, f)
"""
execute_blender_code(code)
with open("temp_surfacedeform_test.json") as f:
    print(f.read())
