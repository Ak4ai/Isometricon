"""
Export clean, solid character in Roblox A-Pose to FBX (and OBJ) for Roblox Studio.
The A-pose is baked into the rest pose so Roblox Studio opens it directly in A-pose.
"""
import bpy
import os
import json
from mathutils import Matrix, Vector, Quaternion

# Ensure Object mode
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# Remove leftover export objects if any
for o in list(bpy.data.objects):
    if o.name.startswith('Export_') or o.name.startswith('APose_'):
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)

orig_arm = bpy.data.objects.get('Armature_Character')
assert orig_arm, "Armature_Character not found!"

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

# 2. Duplicate Armature for export and apply A-pose as Rest Pose
exp_arm_data = orig_arm.data.copy()
exp_arm_obj = bpy.data.objects.new('Export_Armature_APose', exp_arm_data)
bpy.context.collection.objects.link(exp_arm_obj)
exp_arm_obj.matrix_world = orig_arm.matrix_world.copy()
bpy.context.view_layer.update()

# Set pose on export armature
for pb in exp_arm_obj.pose.bones:
    if pb.name in apose_quats:
        pb.rotation_quaternion = apose_quats[pb.name]
    else:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# Apply pose as rest pose on export armature
for o in bpy.context.scene.objects:
    o.select_set(False)
exp_arm_obj.select_set(True)
bpy.context.view_layer.objects.active = exp_arm_obj
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')

# 3. Create clean Skinned Mesh parts in A-pose
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

depsgraph = bpy.context.evaluated_depsgraph_get()
temp_objects = []

for part_name, bone_name in part_bone_map.items():
    orig = bpy.data.objects.get(part_name)
    if not orig or orig.type != 'MESH':
        continue
    
    # Get evaluated mesh in current A-pose
    orig_eval = orig.evaluated_get(depsgraph)
    eval_mesh = orig_eval.to_mesh()
    
    new_data = bpy.data.meshes.new('APose_' + part_name)
    new_obj = bpy.data.objects.new('APose_' + part_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    # Copy vertices transformed to world space
    mw = orig_eval.matrix_world.copy()
    verts = [mw @ v.co for v in eval_mesh.vertices]
    faces = [[v for v in p.vertices] for p in eval_mesh.polygons]
    new_data.from_pydata(verts, [], faces)
    new_data.update()
    
    orig_eval.to_mesh_clear()
    
    # Recalculate outside normals
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
    new_obj.parent = exp_arm_obj
    
    # Add vertex group with 1.0 weight to bone
    vg = new_obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(new_data.vertices))), 1.0, 'REPLACE')
    
    # Add Armature modifier
    am = new_obj.modifiers.new(name='Armature', type='ARMATURE')
    am.object = exp_arm_obj
    am.use_vertex_groups = True
    
    temp_objects.append(new_obj)

bpy.context.view_layer.update()

# 4. Select Export Armature + Skinned parts
for o in bpy.context.scene.objects:
    o.select_set(False)

exp_arm_obj.select_set(True)
for o in temp_objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = exp_arm_obj

output_apose_fbx = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_apose_roblox.fbx'
output_apose_obj = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_apose_roblox.obj'

# Export FBX
bpy.ops.export_scene.fbx(
    filepath=output_apose_fbx,
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

# Export OBJ as fallback
for o in temp_objects:
    o.select_set(True)
exp_arm_obj.select_set(False)

bpy.ops.wm.obj_export(
    filepath=output_apose_obj,
    export_selected_objects=True,
    global_scale=1.0,
    forward_axis='NEGATIVE_Z',
    up_axis='Y'
)

# 5. Clean up temporary export objects
for o in temp_objects:
    me = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.meshes.remove(me, do_unlink=True)

exp_arm_data = exp_arm_obj.data
bpy.data.objects.remove(exp_arm_obj, do_unlink=True)
bpy.data.armatures.remove(exp_arm_data, do_unlink=True)

bpy.context.view_layer.update()

print("APOSE_EXPORT_DONE:" + json.dumps({
    'fbx': output_apose_fbx,
    'obj': output_apose_obj,
    'parts_count': len(part_bone_map)
}, indent=2))
