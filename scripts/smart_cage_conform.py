"""
Smart cage conforming: region-based deformation.

Instead of dumb Shrinkwrap, we:
1. Segment cage vertices into body regions (torso, arms, legs, etc.)
2. For each region, find the corresponding character body part bounding box
3. Remap cage vertices to match the character's blocky shape

This is what Roblox body creators do - they make a cage that matches THEIR body shape.
"""
import bpy
import json
import math
from mathutils import Vector, Quaternion
import bmesh

arm_obj = bpy.data.objects.get('Armature_Character')
cage = bpy.data.objects.get('Roblox_Inner_Cage')
jacket = bpy.data.objects.get('Jacket_1')

result = {}

# ============================================================
# STEP 0: Re-import the ORIGINAL cage (undo the bad Shrinkwrap)
# ============================================================

# Remove all modifiers from cage
for m in list(cage.modifiers):
    cage.modifiers.remove(m)

# Unbind jacket if bound
if jacket:
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM' and m.is_bound:
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            bpy.ops.object.surfacedeform_bind(modifier=m.name)

# Re-import original cage from OBJ
import os
cage_obj_path = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\inner_cage.obj'

# Read the original OBJ and restore vertices
# Since the cage object already exists with correct transform (location, rotation, scale),
# we just need to restore the vertex positions from the original OBJ

original_verts = []
with open(cage_obj_path, 'r') as f:
    for line in f:
        if line.startswith('v '):
            parts = line.strip().split()
            original_verts.append(Vector((float(parts[1]), float(parts[2]), float(parts[3]))))

result['original_vert_count'] = len(original_verts)
result['cage_vert_count'] = len(cage.data.vertices)

# Restore original vertex positions (in local/object space)
if len(original_verts) == len(cage.data.vertices):
    for i, v in enumerate(cage.data.vertices):
        v.co = original_verts[i]
    result['step0'] = 'Restored original cage vertices from OBJ'
else:
    result['step0_error'] = f'Vertex count mismatch: {len(original_verts)} vs {len(cage.data.vertices)}'

bpy.context.view_layer.update()

# Verify cage is back to original
cage_mat = cage.matrix_world
wv = [cage_mat @ v.co for v in cage.data.vertices]
xs = [v.x for v in wv]
zs = [v.z for v in wv]
result['cage_restored_bounds'] = {
    'x': [round(min(xs), 4), round(max(xs), 4)],
    'z': [round(min(zs), 4), round(max(zs), 4)],
}

# ============================================================
# STEP 1: Analyze cage body regions in WORLD space
# ============================================================
# The cage is in Roblox A-pose. We need to identify which vertices
# belong to which body part based on their position.

total_height = max(zs) - min(zs)
min_z = min(zs)
max_z = max(zs)
center_x = (min(xs) + max(xs)) / 2  # should be ~0

# Define body regions based on Z-height and X-position thresholds
# These are approximate for the Roblox standard body

# First, let's find key height markers
hip_z = min_z + total_height * 0.40      # ~hip level
waist_z = min_z + total_height * 0.47    # ~waist  
chest_z = min_z + total_height * 0.55    # ~chest
shoulder_z = min_z + total_height * 0.72 # ~shoulder
neck_z = min_z + total_height * 0.80     # ~neck
head_z = min_z + total_height * 0.85     # ~head start

# X threshold for arm vs torso (approx where torso ends and arm begins)
torso_half_width = 0.12  # half-width of torso in cage world space

result['height_markers'] = {
    'hip_z': round(hip_z, 4),
    'waist_z': round(waist_z, 4),
    'chest_z': round(chest_z, 4),
    'shoulder_z': round(shoulder_z, 4),
    'neck_z': round(neck_z, 4),
}

# Segment vertices into regions
regions = {
    'head': [],       # above neck
    'torso': [],      # between hip and neck, |x| < torso_width
    'arm_R': [],      # x > torso_width, z > hip
    'arm_L': [],      # x < -torso_width, z > hip
    'leg_R': [],      # x > 0, z < hip
    'leg_L': [],      # x < 0, z < hip
    'hip': [],        # near hip level, |x| < torso_width
}

for i, v in enumerate(wv):
    vx, vy, vz = v.x, v.y, v.z
    
    if vz > neck_z:
        regions['head'].append(i)
    elif vz > hip_z and abs(vx) > torso_half_width:
        # Arm area - which side?
        if vx > 0:
            regions['arm_R'].append(i)
        else:
            regions['arm_L'].append(i)
    elif vz > hip_z:
        regions['torso'].append(i)
    elif vz <= hip_z and abs(vx) > 0.01:
        if vx > 0:
            regions['leg_R'].append(i)
        else:
            regions['leg_L'].append(i)
    else:
        regions['hip'].append(i)

# Report region counts
for rname, indices in regions.items():
    if indices:
        rverts = [wv[i] for i in indices]
        rxs = [v.x for v in rverts]
        rzs = [v.z for v in rverts]
        result[f'region_{rname}'] = {
            'count': len(indices),
            'x': [round(min(rxs), 4), round(max(rxs), 4)],
            'z': [round(min(rzs), 4), round(max(rzs), 4)],
        }

# ============================================================
# STEP 2: Get character body part bounding boxes (in A-pose)
# ============================================================
body_parts_map = {
    'torso': ['torso'],
    'hip': ['pelve'],
    'arm_R': ['braco superior esquerdo', 'antebraco esquerdo'],  # char left = world +X = cage right
    'arm_L': ['braco superior direito', 'antebraco direito'],    # char right = world -X = cage left
    'leg_R': ['coxa esquerda', 'canela esquerda'],
    'leg_L': ['coxa direita', 'canela direita'],
}

body_bounds = {}
for region_name, part_names in body_parts_map.items():
    all_verts = []
    for pname in part_names:
        obj = bpy.data.objects.get(pname)
        if obj and obj.type == 'MESH':
            mat = obj.matrix_world
            for v in obj.data.vertices:
                all_verts.append(mat @ v.co)
    
    if all_verts:
        bxs = [v.x for v in all_verts]
        bys = [v.y for v in all_verts]
        bzs = [v.z for v in all_verts]
        body_bounds[region_name] = {
            'min': Vector((min(bxs), min(bys), min(bzs))),
            'max': Vector((max(bxs), max(bys), max(bzs))),
            'center': Vector(((min(bxs)+max(bxs))/2, (min(bys)+max(bys))/2, (min(bzs)+max(bzs))/2)),
        }
        result[f'body_{region_name}'] = {
            'x': [round(min(bxs), 4), round(max(bxs), 4)],
            'y': [round(min(bys), 4), round(max(bys), 4)],
            'z': [round(min(bzs), 4), round(max(bzs), 4)],
        }

# ============================================================
# STEP 3: For each region, compute the transform to map cage → body
# ============================================================
# For each region:
# - Find the bounding box of cage vertices in that region
# - Find the bounding box of the corresponding body parts
# - Compute scale + offset to map cage bbox → body bbox
# - Apply to each vertex, with some padding for clothing offset

cage_inv_mat = cage.matrix_world.inverted()
padding = 0.008  # small padding so cage sits slightly outside body

transforms_applied = {}

for region_name, indices in regions.items():
    if not indices or region_name == 'head':
        continue  # skip head (no clothing there for jacket)
    
    if region_name not in body_bounds:
        continue
    
    # Cage region bounding box (world space)
    cage_region_verts = [wv[i] for i in indices]
    cage_min = Vector((
        min(v.x for v in cage_region_verts),
        min(v.y for v in cage_region_verts),
        min(v.z for v in cage_region_verts),
    ))
    cage_max = Vector((
        max(v.x for v in cage_region_verts),
        max(v.y for v in cage_region_verts),
        max(v.z for v in cage_region_verts),
    ))
    cage_size = cage_max - cage_min
    cage_center = (cage_min + cage_max) / 2
    
    # Body region bounding box (world space)
    bb = body_bounds[region_name]
    body_min = bb['min'] - Vector((padding, padding, padding))
    body_max = bb['max'] + Vector((padding, padding, padding))
    body_size = body_max - body_min
    body_center = (body_min + body_max) / 2
    
    # Scale factors
    sx = body_size.x / max(cage_size.x, 0.001)
    sy = body_size.y / max(cage_size.y, 0.001)
    sz = body_size.z / max(cage_size.z, 0.001)
    
    transforms_applied[region_name] = {
        'scale': [round(sx, 4), round(sy, 4), round(sz, 4)],
        'cage_center': [round(x, 4) for x in cage_center],
        'body_center': [round(x, 4) for x in body_center],
        'vertex_count': len(indices),
    }
    
    # Apply transform: for each vertex in this region
    # new_world_pos = body_center + (old_world_pos - cage_center) * scale
    for idx in indices:
        old_world = wv[idx]
        
        # Normalize to [-1, 1] range within cage bbox
        nx = (old_world.x - cage_center.x) / max(cage_size.x / 2, 0.001)
        ny = (old_world.y - cage_center.y) / max(cage_size.y / 2, 0.001)
        nz = (old_world.z - cage_center.z) / max(cage_size.z / 2, 0.001)
        
        # Map to body bbox
        new_world = Vector((
            body_center.x + nx * (body_size.x / 2),
            body_center.y + ny * (body_size.y / 2),
            body_center.z + nz * (body_size.z / 2),
        ))
        
        # Convert back to cage local space
        new_local = cage_inv_mat @ new_world
        cage.data.vertices[idx].co = new_local

result['transforms'] = transforms_applied

bpy.context.view_layer.update()

# ============================================================
# STEP 4: Verify the conformed cage
# ============================================================
cage_verts_final = [cage.matrix_world @ v.co for v in cage.data.vertices]
fxs = [v.x for v in cage_verts_final]
fzs = [v.z for v in cage_verts_final]
result['cage_final_bounds'] = {
    'x': [round(min(fxs), 4), round(max(fxs), 4)],
    'z': [round(min(fzs), 4), round(max(fzs), 4)],
}

# Check arm region specifically
arm_r_final = [cage_verts_final[i] for i in regions.get('arm_R', [])]
if arm_r_final:
    arxs = [v.x for v in arm_r_final]
    arzs = [v.z for v in arm_r_final]
    result['cage_arm_R_final'] = {
        'x': [round(min(arxs), 4), round(max(arxs), 4)],
        'z': [round(min(arzs), 4), round(max(arzs), 4)],
    }

# ============================================================
# STEP 5: Add vertex groups + Armature modifier
# ============================================================
cage.vertex_groups.clear()

# Reset pose for weight assignment
saved_pose = {}
for pb in arm_obj.pose.bones:
    saved_pose[pb.name] = pb.rotation_quaternion.copy()
    pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# Get cage verts in world (now in rest-like pose for the conformed shape)
# Actually, the cage shape was frozen in A-pose. That's fine - the armature 
# weights should be computed based on bone rest positions.

cage_verts_w = [cage.matrix_world @ v.co for v in cage.data.vertices]

def point_to_segment_dist(p, a, b):
    ab = b - a
    ap = p - a
    t = max(0, min(1, ap.dot(ab) / max(ab.dot(ab), 1e-10)))
    closest = a + ab * t
    return (p - closest).length, t

bone_defs = {}
for bone in arm_obj.data.bones:
    bone_defs[bone.name] = {
        'head': Vector(bone.head_local),
        'tail': Vector(bone.tail_local),
    }

for bone in arm_obj.data.bones:
    vg = cage.vertex_groups.new(name=bone.name)
    for vi, vw in enumerate(cage_verts_w):
        distances = []
        for bname, bd in bone_defs.items():
            dist, t = point_to_segment_dist(vw, bd['head'], bd['tail'])
            distances.append((dist, bname))
        
        distances.sort(key=lambda x: x[0])
        closest_dist = distances[0][0]
        
        if distances[0][1] == bone.name:
            weight = 1.0
        elif len(distances) > 1 and distances[1][1] == bone.name:
            # Second closest
            ratio = distances[0][0] / max(distances[1][0], 0.001)
            weight = max(0, ratio * 0.5) if distances[1][0] < closest_dist * 2.5 else 0
        else:
            weight = 0
            for dist, bname in distances[:3]:
                if bname == bone.name and dist < closest_dist * 3.0 and dist < 0.3:
                    weight = (1.0 / max(dist, 0.001))
                    # Normalize later
        
        if weight > 0.01:
            vg.add([vi], weight, 'REPLACE')

# Normalize weights per vertex
for vi in range(len(cage.data.vertices)):
    total_w = 0
    weights_vi = {}
    for vg in cage.vertex_groups:
        try:
            w = vg.weight(vi)
            weights_vi[vg.name] = w
            total_w += w
        except RuntimeError:
            pass
    
    if total_w > 0:
        for vg_name, w in weights_vi.items():
            cage.vertex_groups[vg_name].add([vi], w / total_w, 'REPLACE')

# Add Armature modifier
arm_mod = cage.modifiers.new(name='Armature', type='ARMATURE')
arm_mod.object = arm_obj
arm_mod.use_vertex_groups = True

result['step5'] = 'Added vertex groups + Armature modifier'

# ============================================================
# STEP 6: Restore A-pose and re-bind jacket
# ============================================================
for pb in arm_obj.pose.bones:
    if pb.name in saved_pose:
        pb.rotation_quaternion = saved_pose[pb.name]
bpy.context.view_layer.update()

# Re-bind jacket
if jacket:
    sd_mod = None
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM':
            sd_mod = m
            break
    if not sd_mod:
        sd_mod = jacket.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')
    
    sd_mod.target = cage
    
    bpy.ops.object.select_all(action='DESELECT')
    jacket.select_set(True)
    bpy.context.view_layer.objects.active = jacket
    
    try:
        if sd_mod.is_bound:
            bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)  # unbind
        bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)  # bind
        result['jacket_bound'] = sd_mod.is_bound
    except Exception as e:
        result['jacket_bind_error'] = str(e)

# Save
bpy.ops.wm.save_mainfile()

print('SMART_RESULT:' + json.dumps(result))
