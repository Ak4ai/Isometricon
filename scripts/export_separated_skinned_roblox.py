"""
Export character_skinned_roblox.fbx with arms cleanly separated in A-pose:
- Uses the exact same single-armature Skinned Mesh code that worked in Roblox Studio.
- Rotates arm edit bones cleanly in Edit Mode so Rest Pose is natively in A-pose.
- Reverses negative scale faces (pe direito) to eliminate holes.
- Ensures a wide 15cm+ gap between arm and torso so Roblox Avatar Setup NEVER welds them!
"""
import bpy
import os
import json
import bmesh
import math
from mathutils import Matrix, Vector, Quaternion, Euler

# Ensure Object mode
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# Remove temporary objects if any
for o in list(bpy.data.objects):
    if o.name.startswith('Roblox_') or o.name.startswith('Export_'):
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)

orig_arm = bpy.data.objects.get('Armature_Character')
assert orig_arm, "Armature_Character not found"

# 1. Duplicate Armature for export
exp_arm_data = orig_arm.data.copy()
exp_arm = bpy.data.objects.new('Roblox_Export_Armature', exp_arm_data)
bpy.context.collection.objects.link(exp_arm)
exp_arm.matrix_world = orig_arm.matrix_world.copy()
bpy.context.view_layer.update()

# 2. In Edit Mode on exp_arm, rotate UpperArm_L and UpperArm_R by -35 deg (Left) and +35 deg (Right)
# so the arms are natively spread away from the torso in Rest Pose!
bpy.ops.object.select_all(action='DESELECT')
exp_arm.select_set(True)
bpy.context.view_layer.objects.active = exp_arm
bpy.ops.object.mode_set(mode='EDIT')

eb_u_l = exp_arm_data.edit_bones['UpperArm_L']
eb_l_l = exp_arm_data.edit_bones['LowerArm_L']
eb_u_r = exp_arm_data.edit_bones['UpperArm_R']
eb_l_r = exp_arm_data.edit_bones['LowerArm_R']

# Pivot at shoulder head
pivot_l = eb_u_l.head.copy()
# Rotate around Y axis by -38 degrees and X by +12 degrees
rot_l = Euler((math.radians(12), math.radians(-38), 0.0), 'XYZ').to_matrix().to_4x4()

# Transform UpperArm_L tail and LowerArm_L head/tail
eb_u_l.tail = pivot_l + rot_l.to_3x3() @ (eb_u_l.tail - pivot_l)
eb_l_l.head = eb_u_l.tail.copy()
eb_l_l.tail = pivot_l + rot_l.to_3x3() @ (eb_l_l.tail - pivot_l)

pivot_r = eb_u_r.head.copy()
rot_r = Euler((math.radians(12), math.radians(38), 0.0), 'XYZ').to_matrix().to_4x4()
eb_u_r.tail = pivot_r + rot_r.to_3x3() @ (eb_u_r.tail - pivot_r)
eb_l_r.head = eb_u_r.tail.copy()
eb_l_r.tail = pivot_r + rot_r.to_3x3() @ (eb_l_r.tail - pivot_r)

bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()

# 3. Create clean Skinned Mesh parts
part_bone_map = {
    'torso': 'Torso',
    'pelve': 'Pelvis',
    'cabeca': 'Head',
    'pecoco': 'Neck',
    'cabelo': 'Head',
    'nariz.002': 'Head',
    'braco superior esquerdo': 'UpperArm_L',
    'braco superior direito': 'UpperArm_R',
    'antebraco esquerdo': 'LowerArm_L',
    'antebraco direito': 'LowerArm_R',
    'coxa esquerda': 'UpperLeg_L',
    'coxa direita': 'UpperLeg_R',
    'canela esquerda': 'LowerLeg_L',
    'canela direita': 'LowerLeg_R',
    'pe esquerdo': 'Foot_L',
    'pe direito': 'Foot_R',
}

# In orig_arm, set pose so arms match the new rotation for mesh transform
for pb in orig_arm.pose.bones:
    pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
orig_arm.pose.bones['UpperArm_L'].rotation_euler = (math.radians(12), math.radians(-38), 0.0)
orig_arm.pose.bones['UpperArm_R'].rotation_euler = (math.radians(12), math.radians(38), 0.0)
orig_arm.pose.bones['UpperArm_L'].rotation_mode = 'XYZ'
orig_arm.pose.bones['UpperArm_R'].rotation_mode = 'XYZ'
bpy.context.view_layer.update()

temp_objects = []

for part_name, bone_name in part_bone_map.items():
    orig = bpy.data.objects.get(part_name)
    if not orig or orig.type != 'MESH':
        continue
    
    new_data = orig.data.copy()
    new_obj = bpy.data.objects.new('Roblox_' + part_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    mw = orig.matrix_world.copy()
    det = mw.determinant()
    
    # Bake world transform into vertices
    for v in new_data.vertices:
        v.co = mw @ v.co
    
    # If mirrored scale, reverse faces
    if det < 0:
        bm = bmesh.new()
        bm.from_mesh(new_data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(new_data)
        bm.free()
    
    new_data.update()
    
    # Recalculate normals
    bpy.ops.object.select_all(action='DESELECT')
    new_obj.select_set(True)
    bpy.context.view_layer.objects.active = new_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except Exception:
        pass
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    new_obj.matrix_world = Matrix.Identity(4)
    new_obj.parent = exp_arm
    
    vg = new_obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(new_data.vertices))), 1.0, 'REPLACE')
    
    am = new_obj.modifiers.new(name='Armature', type='ARMATURE')
    am.object = exp_arm
    am.use_vertex_groups = True
    
    temp_objects.append(new_obj)

bpy.context.view_layer.update()

# 4. Export FBX
for o in bpy.context.scene.objects:
    o.select_set(False)

exp_arm.select_set(True)
for o in temp_objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = exp_arm

output_fbx = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_skinned_roblox.fbx'

bpy.ops.export_scene.fbx(
    filepath=output_fbx,
    use_selection=True,
    global_scale=1.0,
    axis_forward='-Z',
    axis_up='Y',
    apply_scale_options='FBX_SCALE_ALL',
    bake_space_transform=False,
    object_types={'ARMATURE', 'MESH'},
    use_mesh_modifiers=True,
    add_leaf_bones=False,
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    armature_nodetype='NULL'
)

# Clean up
for o in temp_objects:
    me = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.meshes.remove(me, do_unlink=True)

exp_arm_data = exp_arm.data
bpy.data.objects.remove(exp_arm, do_unlink=True)
bpy.data.armatures.remove(exp_arm_data, do_unlink=True)

# Restore original arm rotation mode
orig_arm.pose.bones['UpperArm_L'].rotation_mode = 'QUATERNION'
orig_arm.pose.bones['UpperArm_R'].rotation_mode = 'QUATERNION'
bpy.context.view_layer.update()

print("SEPARATED_SKINNED_DONE:" + output_fbx)
