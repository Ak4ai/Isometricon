"""
Complete setup for the Roblox clothing system:

1. Auto-weight paint the Inner Cage to the character armature
2. Add Armature modifier to the cage
3. Remove old Shrinkwrap from cage (it was just for initial conforming)
4. Unbind and re-bind the jacket's Surface Deform to the cage

The cage should deform with the armature, and the jacket follows the cage.
When we go back to rest pose, the cage returns to its original shape,
and the jacket returns to its original fit.
"""
import bpy
import json
import math
from mathutils import Vector, Quaternion

arm_obj = bpy.data.objects.get('Armature_Character')
cage = bpy.data.objects.get('Roblox_Inner_Cage')
jacket = bpy.data.objects.get('Jacket_1')

result = {}

if not all([arm_obj, cage, jacket]):
    print('SETUP_RESULT:' + json.dumps({'error': 'Missing objects'}))
else:
    # === STEP 1: Remove old modifiers from cage ===
    # Remove Shrinkwrap (it served its purpose for initial positioning)
    for m in list(cage.modifiers):
        if m.type == 'SHRINKWRAP':
            cage.modifiers.remove(m)
    result['step1'] = 'Removed old Shrinkwrap from cage'
    
    # === STEP 2: Create vertex groups on cage for each bone ===
    # Clear existing vertex groups
    cage.vertex_groups.clear()
    
    # For each bone, assign cage vertices based on proximity
    # We need to map cage vertices to the closest bone
    
    # First, put armature in REST pose to do the weight assignment
    # Save current pose
    saved_pose = {}
    for pb in arm_obj.pose.bones:
        saved_pose[pb.name] = pb.rotation_quaternion.copy()
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
    bpy.context.view_layer.update()
    
    # Define bone influence regions based on bone positions
    # Each bone controls vertices near it
    bone_defs = {}
    for bone in arm_obj.data.bones:
        head = Vector(bone.head_local)
        tail = Vector(bone.tail_local)
        center = (head + tail) / 2
        length = (tail - head).length
        direction = (tail - head).normalized()
        bone_defs[bone.name] = {
            'head': head,
            'tail': tail,
            'center': center,
            'length': length,
            'direction': direction,
        }
    
    # Get cage vertices in world space (armature space since armature is at origin)
    cage_mat = cage.matrix_world
    cage_verts_world = [cage_mat @ v.co for v in cage.data.vertices]
    
    # For each vertex, find the closest bone segment
    def point_to_segment_dist(p, a, b):
        """Distance from point p to line segment a-b, and the closest point parameter t."""
        ab = b - a
        ap = p - a
        t = max(0, min(1, ap.dot(ab) / max(ab.dot(ab), 1e-10)))
        closest = a + ab * t
        return (p - closest).length, t
    
    # Assign each vertex to the closest bone
    vertex_bone_weights = {}  # vertex_idx -> {bone_name: weight}
    
    for vi, vw in enumerate(cage_verts_world):
        distances = []
        for bname, bd in bone_defs.items():
            dist, t = point_to_segment_dist(vw, bd['head'], bd['tail'])
            distances.append((dist, bname))
        
        # Sort by distance
        distances.sort(key=lambda x: x[0])
        
        # Use the closest bone with full weight
        # But also blend with nearby bones for smooth deformation
        closest_dist = distances[0][0]
        
        weights = {}
        for dist, bname in distances[:3]:  # Consider top 3 closest bones
            if dist < closest_dist * 3.0 and dist < 0.3:  # Within 3x distance and reasonable range
                # Weight inversely proportional to distance
                w = 1.0 / max(dist, 0.001)
                weights[bname] = w
        
        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            for bname in weights:
                weights[bname] /= total
        
        vertex_bone_weights[vi] = weights
    
    # Create vertex groups and assign weights
    for bone in arm_obj.data.bones:
        vg = cage.vertex_groups.new(name=bone.name)
        for vi, weights in vertex_bone_weights.items():
            if bone.name in weights:
                vg.add([vi], weights[bone.name], 'REPLACE')
    
    result['step2'] = f'Created {len(arm_obj.data.bones)} vertex groups on cage'
    result['vertex_count'] = len(cage.data.vertices)
    
    # Count vertices per group
    vg_counts = {}
    for vg in cage.vertex_groups:
        count = 0
        for vi in range(len(cage.data.vertices)):
            try:
                w = vg.weight(vi)
                if w > 0.01:
                    count += 1
            except RuntimeError:
                pass
        vg_counts[vg.name] = count
    result['vertices_per_group'] = vg_counts
    
    # === STEP 3: Add Armature modifier to cage ===
    # Check if already exists
    arm_mod = None
    for m in cage.modifiers:
        if m.type == 'ARMATURE':
            arm_mod = m
            break
    
    if not arm_mod:
        arm_mod = cage.modifiers.new(name='Armature', type='ARMATURE')
    
    arm_mod.object = arm_obj
    arm_mod.use_vertex_groups = True
    result['step3'] = 'Added Armature modifier to cage'
    
    # === STEP 4: Restore the pose ===
    for pb in arm_obj.pose.bones:
        if pb.name in saved_pose:
            pb.rotation_quaternion = saved_pose[pb.name]
    bpy.context.view_layer.update()
    result['step4'] = 'Restored arm pose'
    
    # === STEP 5: Unbind and re-bind jacket's Surface Deform ===
    sd_mod = None
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM':
            sd_mod = m
            break
    
    if sd_mod:
        # Need to unbind first
        if sd_mod.is_bound:
            # Select the jacket
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            
            try:
                bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
                result['unbind'] = 'Unbound Surface Deform'
            except Exception as e:
                result['unbind_error'] = str(e)
        
        # Now re-bind
        sd_mod.target = cage
        bpy.ops.object.select_all(action='DESELECT')
        jacket.select_set(True)
        bpy.context.view_layer.objects.active = jacket
        
        try:
            bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
            result['bind'] = 'Re-bound Surface Deform'
            result['bind_success'] = sd_mod.is_bound
        except Exception as e:
            result['bind_error'] = str(e)
    
    # === STEP 6: Verify - check jacket bounds with the pose applied ===
    bpy.context.view_layer.update()
    
    # Evaluate jacket with modifiers
    depsgraph = bpy.context.evaluated_depsgraph_get()
    jacket_eval = jacket.evaluated_get(depsgraph)
    jacket_mesh = jacket_eval.to_mesh()
    
    jacket_mat = jacket_eval.matrix_world
    jverts = [jacket_mat @ v.co for v in jacket_mesh.vertices]
    
    if jverts:
        xs = [v.x for v in jverts]
        ys = [v.y for v in jverts]
        zs = [v.z for v in jverts]
        result['jacket_final_bounds'] = {
            'x': [round(min(xs), 4), round(max(xs), 4)],
            'y': [round(min(ys), 4), round(max(ys), 4)],
            'z': [round(min(zs), 4), round(max(zs), 4)],
        }
    
    jacket_eval.to_mesh_clear()
    
    # Also check cage bounds after armature deformation
    cage_eval = cage.evaluated_get(depsgraph)
    cage_mesh = cage_eval.to_mesh()
    cage_mat_w = cage_eval.matrix_world
    cverts = [cage_mat_w @ v.co for v in cage_mesh.vertices]
    
    if cverts:
        xs = [v.x for v in cverts]
        ys = [v.y for v in cverts]
        zs = [v.z for v in cverts]
        result['cage_deformed_bounds'] = {
            'x': [round(min(xs), 4), round(max(xs), 4)],
            'y': [round(min(ys), 4), round(max(ys), 4)],
            'z': [round(min(zs), 4), round(max(zs), 4)],
        }
    
    cage_eval.to_mesh_clear()

print('SETUP_RESULT:' + json.dumps(result))
