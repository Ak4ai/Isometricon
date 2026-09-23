import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_compare_topology.json").replace("\\", "/")
code = f"""
import bpy, json

fem_cages = bpy.data.collections["Cages_Feminino"].objects
res = {{}}
for o in fem_cages:
    res[o.name] = {{
        'v_count': len(o.data.vertices),
        'p_count': len(o.data.polygons),
        'edge_count': len(o.data.edges)
    }}

with open("{out_path}", "w") as f:
    json.dump(res, f, indent=2)
"""
execute_blender_code(code)
with open("temp_compare_topology.json") as f:
    print(f.read())
