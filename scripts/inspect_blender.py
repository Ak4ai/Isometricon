import os
import json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_blender_out.json").replace("\\", "/")
code = f"""
import bpy, json
cages = [o.name for o in bpy.data.objects if 'cage' in o.name.lower()]
collections = [c.name for c in bpy.data.collections]
all_objs = [o.name for o in bpy.data.objects]
with open("{out_path}", "w", encoding="utf-8") as f:
    json.dump({{"cages": cages, "collections": collections, "all_objs": all_objs}}, f)
"""
res = execute_blender_code(code)
print("Execute res:", res)
if os.path.exists("temp_blender_out.json"):
    with open("temp_blender_out.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Collections:", data["collections"])
    print("Cages:", data["cages"])
    print("Total objects:", len(data["all_objs"]))
