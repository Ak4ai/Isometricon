"""
Export character_skinned_roblox.fbx in A-Pose:
Uses the exact same robust method as export_skinned_roblox.py that worked in Roblox Studio,
with Armature and all limbs evaluated in A-pose and baked cleanly as Rest Pose.
"""
import bpy
import os
import json
import bmesh
from mathutils import Matrix, Vector, Quaternion

# Ensure Object mode
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# Remove any leftover temporary objects
for o in list(bpy.data.objects):
    if o.name.startswith('Roblox_') or o.name.startswith('Export_') or o.name.startswith('APose_'):
        bpy.data.objects.remove(o, do_unlink=True)

orig_arm = bpy.data.objects.get('Armature_Character')
assert orig_arm, "Armature_Character not found"

# 1. Pose original armature in Roblox A-pose
apose_quats = {
    'UpperArm_L': Quaternion((0.9723699, -0.0585698, 0.0, -0.2259149)),
    'UpperArm_R': Quaternion((0.9723699, -0.0585698, 0.0, 0.2259149)),
}
for pb in orig_arm.pose.bones:
    if pb.name in apose_quats:
        pb.rotation_quaternion = apose_quats[pb.name]
    else:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# 2. Duplicate armature and apply A-pose as the Rest Pose
exp_arm_data = orig_arm.data.copy()
exp_arm = bpy.data.objects.new('Roblox_Armature', exp_arm_data)
bpy.context.collection.objects.link(exp_arm)
exp_arm.matrix_world = orig_arm.matrix_world.copy()
bpy.context.view_layer.update()

for pb in exp_arm.pose.bones:
    if pb.name in apose_quats:
        pb.rotation_quaternion = apose_quats[pb.name]
    else:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# Apply pose as rest pose on exp_arm
for o in bpy.context.scene.objects:
    o.select_set(False)
exp_arm.select_set(True)
bpy.context.view_layer.objects.active = exp_arm
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')

# 3. Create clean Skinned Mesh parts using orig.data.copy()
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

temp_objects = []

for part_name, bone_name in part_bone_map.items():
    orig = bpy.data.objects.get(part_name)
    if not orig or orig.type != 'MESH':
        continue
    
    # Duplicate original mesh data (exact polygons and UVs)
    new_data = orig.data.copy()
    new_obj = bpy.data.objects.new('Roblox_' + part_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    mw = orig.matrix_world.copy()
    det = mw.determinant()
    
    # Transform vertices to world space
    for v in new_data.vertices:
        v.co = mw @ v.co
    
    # If determinant is negative (like mirrored parts), invert polygon winding
    if det < 0:
        bm = bmesh.new()
        bm.from_mesh(new_data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(new_data)
        bm.free()
    
    new_data.update()
    
    # Ensure outward normals
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
    
    # Assign vertex weight 1.0 to its bone
    vg = new_obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(new_data.vertices))), 1.0, 'REPLACE')
    
    # Add Armature Modifier
    am = new_obj.modifiers.new(name='Armature', type='ARMATURE')
    am.object = exp_arm
    am.use_vertex_groups = True
    
    temp_objects.append(new_obj)

bpy.context.view_layer.update()

# 4. Select export armature + parts
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

# Clean up temporary objects
for o in temp_objects:
    me = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.meshes.remove(me, do_unlink=True)

exp_arm_data = exp_arm.data
bpy.data.objects.remove(exp_arm, do_unlink=True)
bpy.data.armatures.remove(exp_arm_data, do_unlink=True)

bpy.context.view_layer.update()

print("SKINNED_APOSE_DONE:" + output_fbx)
