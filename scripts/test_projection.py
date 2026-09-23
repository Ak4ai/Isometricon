import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_project_test.json").replace("\\", "/")
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

depsgraph = bpy.context.evaluated_depsgraph_get()
bvhs = {{}}
for target_name in cages_col.objects.keys():
    t_obj = bpy.data.objects[target_name]
    t_eval = t_obj.evaluated_get(depsgraph)
    mesh = t_eval.to_mesh()
    verts = [list(t_obj.matrix_world @ v.co) for v in mesh.vertices]
    polys = [[v for v in p.vertices] for p in mesh.polygons]
    bvhs[target_name] = BVHTree.FromPolygons(verts, polys)
    t_eval.to_mesh_clear()

orig_verts = np.array([cage_obj.matrix_world @ v.co for v in cage_obj.data.vertices])
proj_verts = orig_verts.copy()

for vg_name, target_names in vg_to_cages.items():
    vg = cage_obj.vertex_groups.get(vg_name)
    if not vg:
        continue
    v_indices = [v.index for v in cage_obj.data.vertices if any(g.group == vg.index for g in v.groups)]
    for vi in v_indices:
        p = orig_verts[vi]
        best_loc = None
        min_d = float('inf')
        for t_name in target_names:
            loc, norm, idx, dist = bvhs[t_name].find_nearest(Vector(p))
            if dist is not None and dist < min_d:
                min_d = dist
                best_loc = loc
        if best_loc is not None:
            proj_verts[vi] = np.array(best_loc)

# Check face normal flips or degeneracies
faces = np.array([[v for v in p.vertices] for p in cage_obj.data.polygons])
tri_a = proj_verts[faces[:, 0]]
tri_b = proj_verts[faces[:, 1]]
tri_c = proj_verts[faces[:, 2]]
cross = np.cross(tri_b - tri_a, tri_c - tri_a)
areas = 0.5 * np.linalg.norm(cross, axis=1)

degen = int(np.sum(areas < 1e-6))
min_area = float(np.min(areas))
mean_area = float(np.mean(areas))

with open("{out_path}", "w") as f:
    json.dump({{
        'degenerate_faces': degen,
        'min_area': min_area,
        'mean_area': mean_area,
        'total_faces': len(faces)
    }}, f, indent=2)
"""
res = execute_blender_code(code)
print("Blender res:", res)
if os.path.exists("temp_project_test.json"):
    with open("temp_project_test.json") as f:
        print(f.read())
