"""
Export character in rest pose to FBX formatted specifically for Roblox Studio 3D Importer / Avatar Setup.
"""
import bpy
import os
import json
from mathutils import Quaternion

# Ensure Object mode
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

arm_obj = bpy.data.objects.get('Armature_Character')

# Put armature in rest pose (0 rotation)
if arm_obj:
    for pb in arm_obj.pose.bones:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
        pb.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()

# Deselect all manually through objects collection
for obj in bpy.context.scene.objects:
    obj.select_set(False)

char_parts = [
    'Armature_Character',
    'torso', 'pelve', 'cabeca', 'pecoco', 'cabelo', 'nariz.002',
    'braco superior esquerdo', 'braco superior direito',
    'antebraco esquerdo', 'antebraco direito',
    'coxa esquerda', 'coxa direita',
    'canela esquerda', 'canela direita',
    'pe esquerdo', 'pe direito'
]

selected = []
for name in char_parts:
    obj = bpy.data.objects.get(name)
    if obj:
        obj.select_set(True)
        selected.append(obj.name)

if arm_obj:
    bpy.context.view_layer.objects.active = arm_obj

output_fbx = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_for_roblox.fbx'
output_obj = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_for_roblox.obj'

# Export FBX
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

# Export OBJ as fallback
bpy.ops.wm.obj_export(
    filepath=output_obj,
    export_selected_objects=True,
    global_scale=1.0,
    forward_axis='NEGATIVE_Z',
    up_axis='Y'
)

print("EXPORT_FOR_ROBLOX_DONE:" + json.dumps({
    'fbx': output_fbx,
    'obj': output_obj,
    'selected_count': len(selected)
}, indent=2))
