"""
Calculate and apply the EXACT bone rotation to match Inner Cage arm direction.

The key insight:
- The bone's REST direction is the direction it points when rotation = (0,0,0)
- We need to find a rotation that transforms the REST direction into the TARGET direction
- The TARGET direction = Inner Cage arm direction in Blender world space

For UpperArm_L:
  REST direction: [0.212, 0.085, -0.974] (mostly straight down)
  TARGET direction: [0.588, -0.128, -0.798] (outward and down at ~53 degrees)

We compute: rotation = quaternion that rotates REST_dir onto TARGET_dir
But this must be applied in the bone's LOCAL space (relative to parent bone Torso).
"""
import bpy
import json
import math
from mathutils import Vector, Matrix, Quaternion, Euler

arm_obj = bpy.data.objects.get('Armature_Character')

# === INNER CAGE TARGET DIRECTION ===
# From the analysis: shoulder_center → hand_center (shoulder/hand region method)
# direction = [0.588266, -0.128202, -0.798441]
# This is in WORLD SPACE (Blender coordinates)
target_dir_world_R = Vector((0.588266, -0.128202, -0.798441)).normalized()
target_dir_world_L = Vector((-0.588266, -0.128202, -0.798441)).normalized()  # mirrored

info = {
    'target_R': [round(x,6) for x in target_dir_world_R],
    'target_L': [round(x,6) for x in target_dir_world_L],
}

# === METHOD: Use Blender's bone math properly ===
# In Blender, a pose bone's final world direction depends on:
# 1. The armature's world matrix
# 2. The parent bone chain's rest + pose transforms
# 3. The bone's own rest transform
# 4. The bone's pose rotation

# For a bone with parent, the effective world matrix is:
# world_mat = armature.matrix_world @ parent.matrix @ bone.matrix
# where parent.matrix already includes the chain of rest+pose transforms

# The bone's REST matrix (from bone.matrix_local) defines its rest orientation
# The pose rotation is applied ON TOP of the rest orientation

# Since armature is at origin with identity transform, world = armature space

# For UpperArm_L:
# The bone points from head to tail in rest pose
# In rest: direction = tail_local - head_local = [0.0826, 0.0332, -0.3796]
# Normalized: [0.212, 0.085, -0.974]

# The parent (Torso) has NO pose rotation (identity), so the parent chain is just rest transforms.

# To find the correct pose quaternion, I need:
# 1. The bone's rest matrix in parent space
# 2. Compute what rotation makes the bone point in the target direction

if arm_obj:
    # First clear all pose rotations to start fresh
    for bname in ['UpperArm_L', 'LowerArm_L', 'UpperArm_R', 'LowerArm_R']:
        pb = arm_obj.pose.bones.get(bname)
        if pb:
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    
    # Update the scene to apply the reset
    bpy.context.view_layer.update()
    
    # Now check: with identity pose, what direction does the bone point?
    for bname in ['UpperArm_L', 'UpperArm_R']:
        pb = arm_obj.pose.bones.get(bname)
        wh = arm_obj.matrix_world @ pb.head
        wt = arm_obj.matrix_world @ pb.tail
        rest_world_dir = (wt - wh).normalized()
        info[f'{bname}_rest_world_dir'] = [round(x, 6) for x in rest_world_dir]
    
    # === COMPUTE ROTATION FOR UpperArm_L ===
    pb_L = arm_obj.pose.bones['UpperArm_L']
    pb_R = arm_obj.pose.bones['UpperArm_R']
    
    # The bone's rest direction in world (with identity pose) 
    wh_L = arm_obj.matrix_world @ pb_L.head
    wt_L = arm_obj.matrix_world @ pb_L.tail
    rest_dir_L = (wt_L - wh_L).normalized()
    
    wh_R = arm_obj.matrix_world @ pb_R.head
    wt_R = arm_obj.matrix_world @ pb_R.tail
    rest_dir_R = (wt_R - wh_R).normalized()
    
    # The rotation in WORLD space that transforms rest_dir to target_dir:
    rot_world_L = rest_dir_L.rotation_difference(target_dir_world_L)
    rot_world_R = rest_dir_R.rotation_difference(target_dir_world_R)
    
    info['rot_world_L'] = [round(x, 6) for x in rot_world_L]
    info['rot_world_R'] = [round(x, 6) for x in rot_world_R]
    
    # But we need the rotation in the BONE'S LOCAL space, not world space!
    # The bone's local space is defined by:
    # bone_world_mat = armature_world @ (parent_chain_rest * parent_chain_pose) @ bone_rest
    # Since armature is identity and parent (Torso) has no pose rotation:
    # bone_world_mat = parent_rest_mat @ bone_rest_mat_local
    
    # The pose rotation is applied in the bone's rest space
    # So: final_world_dir = bone_world_rest_mat @ pose_quat @ (0, bone_length, 0)
    # Actually in Blender, bones point along their Y axis in bone space.
    
    # The bone's rest matrix transforms bone-local coords to armature coords
    # bone.matrix_local = the 4x4 matrix mapping bone space to armature space (in rest)
    # The bone's Y axis in rest maps to the bone direction
    
    # For the pose rotation to work correctly, we need to convert the world rotation
    # into the bone's rest coordinate frame.
    
    # Method: 
    # rest_basis = bone.matrix_local.to_3x3()  (rest orientation in armature space)
    # Since armature is at origin with no rotation, armature space = world space
    # pose_quat = rest_basis.inverted() @ rot_world_quat.to_matrix() @ rest_basis
    
    # Actually the simpler way: the pose bone's matrix channel is in parent bone space
    # For UpperArm_L, parent is Torso:
    
    parent_L = pb_L.bone.parent
    parent_R = pb_R.bone.parent
    
    # Parent's rest matrix in armature space
    parent_rest_L = parent_L.matrix_local.to_3x3() if parent_L else Matrix.Identity(3)
    parent_rest_R = parent_R.matrix_local.to_3x3() if parent_R else Matrix.Identity(3)
    
    # Bone's own rest matrix (local, relative to parent)
    # bone_local = parent.matrix_local.inverted() @ bone.matrix_local
    bone_local_L = (parent_L.matrix_local.inverted() @ pb_L.bone.matrix_local).to_3x3()
    bone_local_R = (parent_R.matrix_local.inverted() @ pb_R.bone.matrix_local).to_3x3()
    
    info['bone_local_L_y_axis'] = [round(x, 6) for x in bone_local_L @ Vector((0, 1, 0))]
    info['bone_local_R_y_axis'] = [round(x, 6) for x in bone_local_R @ Vector((0, 1, 0))]
    
    # The rest direction in parent space:
    # rest_dir_in_parent = bone_local @ (0, 1, 0)  [because bones point along Y]
    rest_dir_parent_L = (bone_local_L @ Vector((0, 1, 0))).normalized()
    rest_dir_parent_R = (bone_local_R @ Vector((0, 1, 0))).normalized()
    
    # The target direction in parent space:
    # target_in_parent = parent_world_mat.inverted() @ target_world
    # parent_world_mat = armature_world @ parent_rest (since parent has no pose)
    parent_world_L = (arm_obj.matrix_world @ parent_L.matrix_local).to_3x3()
    parent_world_R = (arm_obj.matrix_world @ parent_R.matrix_local).to_3x3()
    
    target_parent_L = (parent_world_L.inverted() @ target_dir_world_L).normalized()
    target_parent_R = (parent_world_R.inverted() @ target_dir_world_R).normalized()
    
    info['rest_dir_parent_L'] = [round(x, 6) for x in rest_dir_parent_L]
    info['target_parent_L'] = [round(x, 6) for x in target_parent_L]
    
    # Now the pose rotation in parent space:
    # We need: pose_rot @ rest_dir_parent = target_parent
    # But actually, the pose rotation is applied in the bone's OWN rest frame,
    # not in the parent's frame.
    
    # Let me use the simpler direct approach:
    # In Blender, pose_bone.matrix represents the bone's final matrix in armature space
    # We want: pose_bone.matrix = parent.matrix @ bone_local_rest @ pose_rotation_matrix
    # With no pose rotation: pose_bone.matrix = parent.matrix @ bone_local_rest
    # We want the bone's Y axis (direction) to match target_dir in armature space
    
    # Current bone Y axis in armature space (no pose):
    current_mat_L = pb_L.matrix.to_3x3()
    current_y_L = (current_mat_L @ Vector((0, 1, 0))).normalized()
    
    current_mat_R = pb_R.matrix.to_3x3()
    current_y_R = (current_mat_R @ Vector((0, 1, 0))).normalized()
    
    info['current_bone_y_L'] = [round(x, 6) for x in current_y_L]
    info['current_bone_y_R'] = [round(x, 6) for x in current_y_R]
    
    # Since armature is identity, target in armature space = target in world space
    # Rotation in armature space: current_y → target
    rot_armature_L = current_y_L.rotation_difference(target_dir_world_L)
    rot_armature_R = current_y_R.rotation_difference(target_dir_world_R)
    
    # Convert this to bone-local rotation:
    # The bone's rest basis in armature space is pb.bone.matrix_local.to_3x3()
    # pose_local = rest_basis.inverted() @ rot_armature @ rest_basis
    
    rest_basis_L = pb_L.bone.matrix_local.to_3x3()
    rest_basis_R = pb_R.bone.matrix_local.to_3x3()
    
    # Convert rotation to bone local space
    # final_mat_armature = rot_armature.to_matrix() @ current_rest_mat
    # = (parent_mat @ bone_local_rest @ pose_mat)
    # So: pose_mat = bone_local_rest.inv() @ parent_mat.inv() @ rot_armature.to_matrix() @ current_rest_mat
    # Since current_rest_mat = parent_mat @ bone_local_rest:
    # pose_mat = bone_local_rest.inv() @ parent_mat.inv() @ rot_armature.to_matrix() @ parent_mat @ bone_local_rest
    
    # Actually the simplest correct approach in Blender:
    # We directly set the bone's matrix to achieve the desired direction
    
    # Target matrix for UpperArm_L:
    # We want the Y axis to be target_dir_world_L
    # We can construct a proper rotation matrix:
    target_y_L = target_dir_world_L
    # Choose an X axis perpendicular to Y
    temp_up = Vector((0, 0, 1))
    if abs(target_y_L.dot(temp_up)) > 0.9:
        temp_up = Vector((1, 0, 0))
    target_x_L = target_y_L.cross(temp_up).normalized()
    target_z_L = target_x_L.cross(target_y_L).normalized()
    
    target_mat_L = Matrix((
        (target_x_L.x, target_y_L.x, target_z_L.x),
        (target_x_L.y, target_y_L.y, target_z_L.y),
        (target_x_L.z, target_y_L.z, target_z_L.z),
    ))
    
    # For R
    target_y_R = target_dir_world_R
    target_x_R = target_y_R.cross(temp_up).normalized()
    target_z_R = target_x_R.cross(target_y_R).normalized()
    
    target_mat_R = Matrix((
        (target_x_R.x, target_y_R.x, target_z_R.x),
        (target_x_R.y, target_y_R.y, target_z_R.y),
        (target_x_R.z, target_y_R.z, target_z_R.z),
    ))
    
    # The pose rotation = rest_basis.inverted() @ target_mat
    pose_rot_L = rest_basis_L.inverted() @ target_mat_L
    pose_rot_R = rest_basis_R.inverted() @ target_mat_R
    
    pose_quat_L = pose_rot_L.to_quaternion()
    pose_quat_R = pose_rot_R.to_quaternion()
    
    info['pose_quat_L'] = [round(x, 6) for x in pose_quat_L]
    info['pose_quat_R'] = [round(x, 6) for x in pose_quat_R]
    
    # APPLY the rotation
    pb_L.rotation_quaternion = pose_quat_L
    pb_R.rotation_quaternion = pose_quat_R
    
    bpy.context.view_layer.update()
    
    # Verify: check the new direction
    wh_L2 = arm_obj.matrix_world @ pb_L.head
    wt_L2 = arm_obj.matrix_world @ pb_L.tail
    new_dir_L = (wt_L2 - wh_L2).normalized()
    
    wh_R2 = arm_obj.matrix_world @ pb_R.head
    wt_R2 = arm_obj.matrix_world @ pb_R.tail
    new_dir_R = (wt_R2 - wh_R2).normalized()
    
    info['VERIFY_new_dir_L'] = [round(x, 6) for x in new_dir_L]
    info['VERIFY_new_dir_R'] = [round(x, 6) for x in new_dir_R]
    info['VERIFY_target_L'] = [round(x, 6) for x in target_dir_world_L]
    info['VERIFY_target_R'] = [round(x, 6) for x in target_dir_world_R]
    
    # Check angle error
    angle_err_L = math.degrees(new_dir_L.angle(target_dir_world_L))
    angle_err_R = math.degrees(new_dir_R.angle(target_dir_world_R))
    info['angle_error_L_deg'] = round(angle_err_L, 4)
    info['angle_error_R_deg'] = round(angle_err_R, 4)
    
    # Also check where the body parts ended up
    for bname in ['braco superior esquerdo', 'braco superior direito',
                   'antebraco esquerdo', 'antebraco direito']:
        obj = bpy.data.objects.get(bname)
        if obj:
            mat = obj.matrix_world
            mesh = obj.data
            wv = [mat @ v.co for v in mesh.vertices]
            xs = [v.x for v in wv]
            ys = [v.y for v in wv]
            zs = [v.z for v in wv]
            info[f'{bname}_new_bounds'] = {
                'x': [round(min(xs), 4), round(max(xs), 4)],
                'y': [round(min(ys), 4), round(max(ys), 4)],
                'z': [round(min(zs), 4), round(max(zs), 4)],
            }

print('APPLY_RESULT:' + json.dumps(info))
