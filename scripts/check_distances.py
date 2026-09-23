import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_vg_mapping_check.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

cage_obj = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
cages_col = bpy.data.collections.get("Cages_Feminino")

vg_to_cages = {{
    "Torso": ["UpperTorso_OuterCage"],
    "Pelvis": ["LowerTorso_OuterCage"],
    "Head": ["Head_OuterCage"],
    "UpperArm_L": ["LeftUpperArm_OuterCage"],
    "LowerArm_L": ["LeftLowerArm_OuterCage", "LeftHand_OuterCage"],
    "UpperArm_R": ["RightUpperArm_OuterCage"],
    "LowerArm_R": ["RightLowerArm_OuterCage", "RightHand_OuterCage"],
    "UpperLeg_L": ["LeftUpperLeg_OuterCage"],
    "LowerLeg_L": ["LeftLowerLeg_OuterCage"],
    "Foot_L": ["LeftFoot_OuterCage"],
    "UpperLeg_R": ["RightUpperLeg_OuterCage"],
    "LowerLeg_R": ["RightLowerLeg_OuterCage"],
    "Foot_R": ["RightFoot_OuterCage"],
}}

# Build BVH trees for each female cage
bvhs = {{}}
depsgraph = bpy.context.evaluated_depsgraph_get()
for target_name in cages_col.objects.keys():
    t_obj = bpy.data.objects[target_name]
    t_eval = t_obj.evaluated_get(depsgraph)
    mesh = t_eval.to_mesh()
    verts = [list(t_obj.matrix_world @ v.co) for v in mesh.vertices]
    polys = [[v for v in p.vertices] for p in mesh.polygons]
    bvhs[target_name] = BVHTree.FromPolygons(verts, polys)
    t_eval.to_mesh_clear()

diffs = {{}}
cage_verts = [cage_obj.matrix_world @ v.co for v in cage_obj.data.vertices]

for vg_name, target_names in vg_to_cages.items():
    vg = cage_obj.vertex_groups.get(vg_name)
    if not vg:
        continue
    v_indices = [v.index for v in cage_obj.data.vertices if any(g.group == vg.index for g in v.groups)]
    distances = []
    for vi in v_indices:
        p = cage_verts[vi]
        min_d = float('inf')
        for t_name in target_names:
            location, normal, index, dist = bvhs[t_name].find_nearest(p)
            if dist is not None and dist < min_d:
                min_d = dist
        distances.append(min_d)
    diffs[vg_name] = {{
        'count': len(v_indices),
        'mean_dist': float(np.mean(distances)),
        'max_dist': float(np.max(distances)),
        'min_dist': float(np.min(distances))
    }}

with open("{out_path}", "w") as f:
    json.dump(diffs, f, indent=2)
"""
res = execute_blender_code(code)
print("Blender response:", res)
if os.path.exists("temp_vg_mapping_check.json"):
    with open("temp_vg_mapping_check.json") as f:
        print(f.read())
