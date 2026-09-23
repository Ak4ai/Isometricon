import bpy
import bmesh
import mathutils
import math
import os

def test_rigging_and_poses():
    obj = bpy.data.objects.get('Roblox_Female_Cage_Universal')
    arm = bpy.data.objects.get('Armature_Character.001')
    cages_col = bpy.data.collections.get('Cages_Feminino')
    
    if not obj or not arm or not cages_col:
        print("Required objects not found!")
        return

    part_to_bone = {
        'Head_OuterCage': 'Head',
        'UpperTorso_OuterCage': 'Torso',
        'LowerTorso_OuterCage': 'Pelvis',
        'LeftUpperArm_OuterCage': 'UpperArm_L',
        'LeftLowerArm_OuterCage': 'LowerArm_L',
        'LeftHand_OuterCage': 'LowerArm_L',
        'RightUpperArm_OuterCage': 'UpperArm_R',
        'RightLowerArm_OuterCage': 'LowerArm_R',
        'RightHand_OuterCage': 'LowerArm_R',
        'LeftUpperLeg_OuterCage': 'UpperLeg_L',
        'LeftLowerLeg_OuterCage': 'LowerLeg_L',
        'LeftFoot_OuterCage': 'Foot_L',
        'RightUpperLeg_OuterCage': 'UpperLeg_R',
        'RightLowerLeg_OuterCage': 'LowerLeg_R',
        'RightFoot_OuterCage': 'Foot_R',
    }

    # Ensure all bone vertex groups exist on obj
    for bone_name in set(part_to_bone.values()):
        if bone_name not in obj.vertex_groups:
            obj.vertex_groups.new(name=bone_name)

    # For each vertex in obj, find which original part(s) it is closest to
    # Precompute vertices of all original parts
    part_verts = {}
    for part_obj in cages_col.objects:
        mw = part_obj.matrix_world
        verts_world = [mw @ v.co for v in part_obj.data.vertices]
        part_verts[part_obj.name] = (part_to_bone[part_obj.name], verts_world)

    mesh = obj.data
    vg_map = {vg.name: vg for vg in obj.vertex_groups}

    # Clear existing weights
    for v in mesh.vertices:
        for vg in obj.vertex_groups:
            vg.remove([v.index])

    # Assign weights based on proximity to original parts
    for v in mesh.vertices:
        p = v.co
        # Find distance to each part
        dists = {}
        for part_name, (bone_name, p_verts) in part_verts.items():
            min_d = min((pv - p).length for pv in p_verts)
            if bone_name not in dists or min_d < dists[bone_name]:
                dists[bone_name] = min_d

        # Consider bones within threshold
        # If very close to one bone (< 3mm), assign 1.0
        sorted_bones = sorted(dists.items(), key=lambda x: x[1])
        closest_bone, closest_d = sorted_bones[0]
        second_bone, second_d = sorted_bones[1]

        if second_d < 0.015 and (second_d - closest_d) < 0.008:
            # Shared boundary vertex: blend 50/50
            vg_map[closest_bone].add([v.index], 0.5, 'REPLACE')
            vg_map[second_bone].add([v.index], 0.5, 'REPLACE')
        else:
            vg_map[closest_bone].add([v.index], 1.0, 'REPLACE')

    print("Vertex groups assigned to Roblox_Female_Cage_Universal!")

    # Add Armature Modifier to obj if not present
    arm_mod = None
    for m in obj.modifiers:
        if m.type == 'ARMATURE':
            arm_mod = m
            break
    if not arm_mod:
        arm_mod = obj.modifiers.new(name='Armature', type='ARMATURE')
    arm_mod.object = arm
    arm_mod.use_vertex_groups = True

    # Ensure Armature is in Rest Pose initially
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()

    print("Armature modifier attached and verified in Rest Pose!")

test_rigging_and_poses()
