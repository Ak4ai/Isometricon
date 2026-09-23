import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_full_fem_cage_test.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

# Duplicate cage
src_cage = bpy.data.objects["Roblox_Inner_Cage_Universal"]
test_mesh = src_cage.data.copy()
test_obj = bpy.data.objects.new("Female_Universal_Cage", test_mesh)
bpy.context.collection.objects.link(test_obj)
test_obj.matrix_world = src_cage.matrix_world.copy()

# Create combined targets for forearm+hand
depsgraph = bpy.context.evaluated_depsgraph_get()

def create_combined(name, obj_names):
    bm = None
    combined_mesh = bpy.data.meshes.new(name + "_mesh")
    verts = []
    faces = []
    v_offset = 0
    for oname in obj_names:
        o = bpy.data.objects[oname]
        m = o.evaluated_get(depsgraph).to_mesh()
        for v in m.vertices:
            w_co = o.matrix_world @ v.co
            verts.append(list(w_co))
        for p in m.polygons:
            faces.append([vi + v_offset for vi in p.vertices])
        v_offset += len(m.vertices)
    combined_mesh.from_pydata(verts, [], faces)
    combined_mesh.update()
    combined_obj = bpy.data.objects.new(name, combined_mesh)
    bpy.context.collection.objects.link(combined_obj)
    return combined_obj

left_arm_target = create_combined("Temp_LeftArm_Target", ["LeftLowerArm_OuterCage", "LeftHand_OuterCage"])
right_arm_target = create_combined("Temp_RightArm_Target", ["RightLowerArm_OuterCage", "RightHand_OuterCage"])

mapping = [
    ("Torso", bpy.data.objects["UpperTorso_OuterCage"]),
    ("Pelvis", bpy.data.objects["LowerTorso_OuterCage"]),
    ("Head", bpy.data.objects["Head_OuterCage"]),
    ("UpperArm_L", bpy.data.objects["LeftUpperArm_OuterCage"]),
    ("UpperArm_R", bpy.data.objects["RightUpperArm_OuterCage"]),
    ("LowerArm_L", left_arm_target),
    ("LowerArm_R", right_arm_target),
    ("UpperLeg_L", bpy.data.objects["LeftUpperLeg_OuterCage"]),
    ("LowerLeg_L", bpy.data.objects["LeftLowerLeg_OuterCage"]),
    ("Foot_L", bpy.data.objects["LeftFoot_OuterCage"]),
    ("UpperLeg_R", bpy.data.objects["RightUpperLeg_OuterCage"]),
    ("LowerLeg_R", bpy.data.objects["RightLowerLeg_OuterCage"]),
    ("Foot_R", bpy.data.objects["RightFoot_OuterCage"]),
]

bpy.context.view_layer.objects.active = test_obj

for vg_name, target_obj in mapping:
    mod = test_obj.modifiers.new(f"SW_{{vg_name}}", "SHRINKWRAP")
    mod.target = target_obj
    mod.vertex_group = vg_name
    mod.wrap_method = "PROJECT"
    mod.use_negative_direction = True
    mod.use_positive_direction = True
    bpy.ops.object.modifier_apply(modifier=mod.name)

# 1-iteration gentle smooth
s_mod = test_obj.modifiers.new("GentleSmooth", "SMOOTH")
s_mod.factor = 0.2
s_mod.iterations = 1
bpy.ops.object.modifier_apply(modifier=s_mod.name)

# Verify all 2690 faces
verts = np.array([v.co for v in test_obj.data.vertices])
faces = np.array([[v for v in p.vertices] for p in test_obj.data.polygons])

tri_a = verts[faces[:, 0]]
tri_b = verts[faces[:, 1]]
tri_c = verts[faces[:, 2]]
areas = 0.5 * np.linalg.norm(np.cross(tri_b - tri_a, tri_c - tri_a), axis=1)

degen = int(np.sum(areas < 1e-6))
min_area = float(np.min(areas))
mean_area = float(np.mean(areas))

# Save the conformed vertices
fem_verts_list = verts.tolist()

# Cleanup temp objects
bpy.data.objects.remove(left_arm_target, do_unlink=True)
bpy.data.objects.remove(right_arm_target, do_unlink=True)
bpy.data.objects.remove(test_obj, do_unlink=True)
bpy.data.meshes.remove(test_mesh)

with open("{out_path}", "w") as f:
    json.dump({{
        'total_faces': len(faces),
        'degen_faces': degen,
        'min_area': min_area,
        'mean_area': mean_area,
        'fem_verts': fem_verts_list
    }}, f)
"""
res = execute_blender_code(code)
print("Blender res:", res)
if os.path.exists("temp_full_fem_cage_test.json"):
    with open("temp_full_fem_cage_test.json") as f:
        data = json.load(f)
    print("Total faces:", data["total_faces"])
    print("Degen faces:", data["degen_faces"])
    print("Min area:", data["min_area"])
    print("Mean area:", data["mean_area"])
    print("Conformed verts count:", len(data["fem_verts"]))
