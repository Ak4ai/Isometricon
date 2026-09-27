from blender_client import execute_blender_code
import json

code = '''
import bpy, math, json
from mathutils import Vector, Euler, Matrix

arm = bpy.data.objects.get("Armature_Character.001")
res = {}

# 1. Armature details
if arm:
    res["armature"] = {
        "location": list(arm.location),
        "rotation_euler": [math.degrees(a) for a in arm.rotation_euler],
        "scale": list(arm.scale),
        "bones": [b.name for b in arm.data.bones]
    }
    
    # Bone hierarchy and heads/tails
    bones_info = {}
    for b in arm.data.bones:
        bones_info[b.name] = {
            "parent": b.parent.name if b.parent else None,
            "head": list(b.head_local),
            "tail": list(b.tail_local),
            "vector": list(b.vector)
        }
    res["bones_info"] = bones_info

# 2. Parenting & Modifiers of female body meshes
body_info = {}
for o in bpy.data.objects:
    if o.name.startswith("Export_") or o.name in ["cabeca.001", "pecoco.001", "pe_direito.003", "pe_esquerdo.003"]:
        mods = [{"name": m.name, "type": m.type} for m in o.modifiers]
        body_info[o.name] = {
            "parent": o.parent.name if o.parent else None,
            "parent_type": o.parent_type,
            "parent_bone": o.parent_bone,
            "modifiers": mods,
            "location": list(o.location),
            "rotation_euler": [math.degrees(a) for a in o.rotation_euler],
            "vertex_count": len(o.data.vertices),
            "vertex_groups": [vg.name for vg in o.vertex_groups]
        }
res["body_info"] = body_info

# 3. Parenting & Modifiers of cages
cage_info = {}
for o in bpy.data.objects:
    if "OuterCage" in o.name:
        mods = [{"name": m.name, "type": m.type} for m in o.modifiers]
        cage_info[o.name] = {
            "parent": o.parent.name if o.parent else None,
            "parent_type": o.parent_type,
            "parent_bone": o.parent_bone,
            "modifiers": mods,
            "location": list(o.location),
            "rotation_euler": [math.degrees(a) for a in o.rotation_euler],
            "vertex_count": len(o.data.vertices),
            "vertex_groups": [vg.name for vg in o.vertex_groups]
        }
res["cage_info"] = cage_info

print(json.dumps(res, indent=2))
'''

res = execute_blender_code(code)
with open("temp_female_analysis.json", "w", encoding="utf-8") as f:
    f.write(res["result"]["result"])
print("Saved analysis to temp_female_analysis.json")
