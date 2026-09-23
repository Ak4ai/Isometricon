import os, json
from scripts.blender_client import execute_blender_code

out_path = os.path.abspath("temp_shrinkwrap_test.json").replace("\\", "/")
code = f"""
import bpy, json, numpy as np

cage_obj = bpy.data.objects.get("Roblox_Inner_Cage_Universal")

# Create duplicate for testing
test_mesh = cage_obj.data.copy()
test_obj = bpy.data.objects.new("Cage_Test_Shrinkwrap", test_mesh)
bpy.context.collection.objects.link(test_obj)
test_obj.matrix_world = cage_obj.matrix_world.copy()

# Add shrinkwrap for UpperTorso
mod = test_obj.modifiers.new("SW_Torso", "SHRINKWRAP")
mod.target = bpy.data.objects["UpperTorso_OuterCage"]
mod.vertex_group = "Torso"
mod.wrap_method = "NEAREST_SURFACEPOINT"

# Apply modifier
bpy.context.view_layer.objects.active = test_obj
bpy.ops.object.modifier_apply(modifier="SW_Torso")

# Check torso faces
verts = np.array([v.co for v in test_obj.data.vertices])
vg = test_obj.vertex_groups["Torso"]
torso_v_indices = set(v.index for v in test_obj.data.vertices if any(g.group == vg.index for g in v.groups))

torso_faces = [p for p in test_obj.data.polygons if all(vi in torso_v_indices for vi in p.vertices)]
tri_a = verts[[p.vertices[0] for p in torso_faces]]
tri_b = verts[[p.vertices[1] for p in torso_faces]]
tri_c = verts[[p.vertices[2] for p in torso_faces]]
areas = 0.5 * np.linalg.norm(np.cross(tri_b - tri_a, tri_c - tri_a), axis=1)

degen = int(np.sum(areas < 1e-6))
min_a = float(np.min(areas))

# Remove test obj
bpy.data.objects.remove(test_obj, do_unlink=True)
bpy.data.meshes.remove(test_mesh)

with open("{out_path}", "w") as f:
    json.dump({{
        'torso_faces_count': len(torso_faces),
        'degen_faces': degen,
        'min_area': min_a
    }}, f, indent=2)
"""
res = execute_blender_code(code)
print("Blender res:", res)
if os.path.exists("temp_shrinkwrap_test.json"):
    with open("temp_shrinkwrap_test.json") as f:
        print(f.read())
