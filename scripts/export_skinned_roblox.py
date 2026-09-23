"""
Create a 100% Roblox-compliant Skinned Mesh FBX:
1. Duplicates character meshes into a clean combined/skinned model.
2. Assigns 100% rigid vertex weights to each corresponding bone.
3. Uses Armature modifier instead of legacy Bone Parenting.
4. Exports FBX with standard settings so Roblox Studio 3D Importer imports it perfectly assembled.
"""
import bpy
import os
import json
from mathutils import Matrix, Vector, Quaternion

# Ensure Object Mode
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

arm_obj = bpy.data.objects.get('Armature_Character')

# Map body objects to bone names
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

# Put armature in rest pose
if arm_obj:
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pb.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()

# Create a temporary clean export scene or duplicate objects
temp_objects = []
for part_name, bone_name in part_bone_map.items():
    orig = bpy.data.objects.get(part_name)
    if not orig or orig.type != 'MESH':
        continue
    
    # Duplicate object
    new_data = orig.data.copy()
    new_obj = bpy.data.objects.new('Roblox_' + part_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    # Bake world transform into mesh vertices so object origin is at (0,0,0)
    # matching the Armature space
    mw = orig.matrix_world.copy()
    for v in new_data.vertices:
        v.co = mw @ v.co
    
    new_obj.matrix_world = Matrix.Identity(4)
    new_obj.parent = arm_obj
    
    # Assign vertex weight 1.0 to its bone
    vg = new_obj.vertex_groups.new(name=bone_name)
    all_indices = list(range(len(new_data.vertices)))
    vg.add(all_indices, 1.0, 'REPLACE')
    
    # Add Armature Modifier
    am = new_obj.modifiers.new(name='Armature', type='ARMATURE')
    am.object = arm_obj
    am.use_vertex_groups = True
    
    temp_objects.append(new_obj)

bpy.context.view_layer.update()

# Select Armature + temporary skinned objects
for o in bpy.context.scene.objects:
    o.select_set(False)

arm_obj.select_set(True)
for o in temp_objects:
    o.select_set(True)

bpy.context.view_layer.objects.active = arm_obj

output_skinned_fbx = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_skinned_roblox.fbx'

bpy.ops.export_scene.fbx(
    filepath=output_skinned_fbx,
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

bpy.context.view_layer.update()

print("SKINNED_FBX_DONE:" + output_skinned_fbx)
