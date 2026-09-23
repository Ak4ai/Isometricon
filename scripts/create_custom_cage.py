"""
Complete pipeline to create the character's custom Inner Cage:

1. Ensure armature is in A-pose (matching Roblox cage pose)
2. Create temporary combined body mesh from all body parts
3. Remove existing modifiers from cage
4. Shrinkwrap cage to combined body mesh
5. Apply Shrinkwrap to freeze the conformed shape
6. Delete temp body mesh
7. Add vertex groups + Armature modifier to conformed cage
8. Re-bind jacket Surface Deform to conformed cage
"""
import bpy
import json
import math
import bmesh
from mathutils import Vector, Quaternion

arm_obj = bpy.data.objects.get('Armature_Character')
cage = bpy.data.objects.get('Roblox_Inner_Cage')
jacket = bpy.data.objects.get('Jacket_1')

result = {}

# ============================================================
# STEP 0: Verify A-pose is applied on armature
# ============================================================
# The cage is in Roblox A-pose position
# The character arms should be posed to match
# (This was done in fix_arm_rotation.py)

# Check current arm direction
for bname in ['UpperArm_L', 'UpperArm_R']:
    pb = arm_obj.pose.bones.get(bname)
    if pb:
        wh = arm_obj.matrix_world @ pb.head
        wt = arm_obj.matrix_world @ pb.tail
        d = (wt - wh).normalized()
        result[f'{bname}_dir'] = [round(x, 4) for x in d]

bpy.context.view_layer.update()

# ============================================================
# STEP 1: Create temporary combined body mesh
# ============================================================
# List all body parts that the jacket should conform to
body_part_names = [
    'torso',
    'pelve', 
    'braco superior esquerdo',
    'braco superior direito',
    'antebraco esquerdo',
    'antebraco direito',
    'coxa esquerda',
    'coxa direita',
    'canela esquerda',
    'canela direita',
]

# Deselect all
bpy.ops.object.select_all(action='DESELECT')

# We need to create a new mesh that combines all body parts in their CURRENT world position
# (which is the A-pose since the armature is posed)

# Create a new empty mesh
combined_mesh = bpy.data.meshes.new('Temp_Combined_Body')
combined_obj = bpy.data.objects.new('Temp_Combined_Body', combined_mesh)
bpy.context.collection.objects.link(combined_obj)

# Use bmesh to combine all body parts
bm = bmesh.new()

found_parts = []
for name in body_part_names:
    obj = bpy.data.objects.get(name)
    if obj and obj.type == 'MESH':
        # Get the evaluated mesh (with armature deformation applied)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(depsgraph)
        temp_mesh = obj_eval.to_mesh()
        
        # Transform vertices to world space
        bm_temp = bmesh.new()
        bm_temp.from_mesh(temp_mesh)
        
        # Apply world transform
        bm_temp.transform(obj_eval.matrix_world)
        
        # Merge into combined bmesh
        # We need to add vertices and faces manually
        vert_map = {}
        for v in bm_temp.verts:
            new_v = bm.verts.new(v.co)
            vert_map[v.index] = new_v
        
        bm.verts.ensure_lookup_table()
        
        for f in bm_temp.faces:
            try:
                new_verts = [vert_map[v.index] for v in f.verts]
                bm.faces.new(new_verts)
            except ValueError:
                pass  # Skip duplicate faces
        
        bm_temp.free()
        obj_eval.to_mesh_clear()
        found_parts.append(name)

bm.to_mesh(combined_mesh)
bm.free()

result['step1'] = f'Created combined body mesh from {len(found_parts)} parts'
result['found_parts'] = found_parts
result['combined_verts'] = len(combined_mesh.vertices)
result['combined_faces'] = len(combined_mesh.polygons)

# ============================================================
# STEP 2: Clean up cage - remove ALL existing modifiers
# ============================================================
for m in list(cage.modifiers):
    cage.modifiers.remove(m)
result['step2'] = 'Removed all modifiers from cage'

# Also unbind jacket's Surface Deform if bound
if jacket:
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM' and m.is_bound:
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            bpy.ops.object.surfacedeform_bind(modifier=m.name)
            result['jacket_unbound'] = True

# ============================================================
# STEP 3: Add Shrinkwrap to cage targeting combined body
# ============================================================
sw_mod = cage.modifiers.new(name='Shrinkwrap_To_Body', type='SHRINKWRAP')
sw_mod.target = combined_obj
sw_mod.wrap_method = 'NEAREST_SURFACEPOINT'
sw_mod.wrap_mode = 'ON_SURFACE'
sw_mod.offset = 0.005  # Small offset so cage sits slightly outside body

bpy.context.view_layer.update()
result['step3'] = 'Added Shrinkwrap modifier to cage'

# ============================================================
# STEP 4: Check the result before applying
# ============================================================
# Get the evaluated cage to see the conformed shape
depsgraph = bpy.context.evaluated_depsgraph_get()
cage_eval = cage.evaluated_get(depsgraph)
cage_mesh_eval = cage_eval.to_mesh()
cage_mat = cage_eval.matrix_world

eval_verts = [cage_mat @ v.co for v in cage_mesh_eval.vertices]
xs = [v.x for v in eval_verts]
ys = [v.y for v in eval_verts]
zs = [v.z for v in eval_verts]

result['cage_conformed_bounds'] = {
    'x': [round(min(xs), 4), round(max(xs), 4)],
    'y': [round(min(ys), 4), round(max(ys), 4)],
    'z': [round(min(zs), 4), round(max(zs), 4)],
}

# Compare with body bounds
body_verts = [combined_obj.matrix_world @ v.co for v in combined_mesh.vertices]
bxs = [v.x for v in body_verts]
bys = [v.y for v in body_verts]
bzs = [v.z for v in body_verts]

result['body_bounds'] = {
    'x': [round(min(bxs), 4), round(max(bxs), 4)],
    'y': [round(min(bys), 4), round(max(bys), 4)],
    'z': [round(min(bzs), 4), round(max(bzs), 4)],
}

cage_eval.to_mesh_clear()

# ============================================================
# STEP 5: Apply the Shrinkwrap modifier
# ============================================================
bpy.ops.object.select_all(action='DESELECT')
cage.select_set(True)
bpy.context.view_layer.objects.active = cage

# Apply the shrinkwrap
bpy.ops.object.modifier_apply(modifier='Shrinkwrap_To_Body')
result['step5'] = 'Applied Shrinkwrap - cage shape is now frozen'

# Verify applied shape
cage_verts_after = [cage.matrix_world @ v.co for v in cage.data.vertices]
axs = [v.x for v in cage_verts_after]
ays = [v.y for v in cage_verts_after]
azs = [v.z for v in cage_verts_after]

result['cage_applied_bounds'] = {
    'x': [round(min(axs), 4), round(max(axs), 4)],
    'y': [round(min(ays), 4), round(max(ays), 4)],
    'z': [round(min(azs), 4), round(max(azs), 4)],
}

# ============================================================
# STEP 6: Delete temp combined body mesh
# ============================================================
bpy.data.objects.remove(combined_obj, do_unlink=True)
bpy.data.meshes.remove(combined_mesh)
result['step6'] = 'Deleted temporary combined body mesh'

# Also delete old Temp_Body_Target if it exists
old_target = bpy.data.objects.get('Temp_Body_Target')
if old_target:
    old_mesh = old_target.data
    bpy.data.objects.remove(old_target, do_unlink=True)
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    result['deleted_old_target'] = True

# ============================================================
# STEP 7: Add vertex groups + Armature modifier to conformed cage
# ============================================================

# Reset pose to REST for proper weight assignment
saved_pose = {}
for pb in arm_obj.pose.bones:
    saved_pose[pb.name] = pb.rotation_quaternion.copy()
    pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# Clear existing vertex groups
cage.vertex_groups.clear()

# Helper: distance from point to line segment
def point_to_segment_dist(p, a, b):
    ab = b - a
    ap = p - a
    t = max(0, min(1, ap.dot(ab) / max(ab.dot(ab), 1e-10)))
    closest = a + ab * t
    return (p - closest).length, t

# Get bone positions (rest pose)
bone_defs = {}
for bone in arm_obj.data.bones:
    head = Vector(bone.head_local)
    tail = Vector(bone.tail_local)
    bone_defs[bone.name] = {'head': head, 'tail': tail}

# Cage vertices in world space (now conformed to character shape)
cage_mat = cage.matrix_world
cage_verts_w = [cage_mat @ v.co for v in cage.data.vertices]

# Assign weights
vertex_weights = {}
for vi, vw in enumerate(cage_verts_w):
    distances = []
    for bname, bd in bone_defs.items():
        dist, t = point_to_segment_dist(vw, bd['head'], bd['tail'])
        distances.append((dist, bname))
    
    distances.sort(key=lambda x: x[0])
    closest_dist = distances[0][0]
    
    weights = {}
    for dist, bname in distances[:3]:
        if dist < closest_dist * 3.0 and dist < 0.3:
            w = 1.0 / max(dist, 0.001)
            weights[bname] = w
    
    total = sum(weights.values())
    if total > 0:
        for bname in weights:
            weights[bname] /= total
    
    vertex_weights[vi] = weights

# Create vertex groups
for bone in arm_obj.data.bones:
    vg = cage.vertex_groups.new(name=bone.name)
    for vi, weights in vertex_weights.items():
        if bone.name in weights:
            vg.add([vi], weights[bone.name], 'REPLACE')

result['step7_vgroups'] = len(cage.vertex_groups)

# Add Armature modifier
arm_mod = cage.modifiers.new(name='Armature', type='ARMATURE')
arm_mod.object = arm_obj
arm_mod.use_vertex_groups = True

result['step7'] = 'Added vertex groups + Armature modifier to conformed cage'

# ============================================================
# STEP 8: Restore A-pose and re-bind jacket
# ============================================================
for pb in arm_obj.pose.bones:
    if pb.name in saved_pose:
        pb.rotation_quaternion = saved_pose[pb.name]
bpy.context.view_layer.update()

# Re-bind jacket's Surface Deform
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
        bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
        result['step8_bound'] = sd_mod.is_bound
    except Exception as e:
        result['step8_error'] = str(e)
    
    result['step8'] = 'Re-bound jacket Surface Deform to conformed cage'

# ============================================================
# STEP 9: Verify final result
# ============================================================
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()

# Jacket final bounds
jacket_eval = jacket.evaluated_get(depsgraph)
jmesh = jacket_eval.to_mesh()
jmat = jacket_eval.matrix_world
jverts = [jmat @ v.co for v in jmesh.vertices]

if jverts:
    xs = [v.x for v in jverts]
    ys = [v.y for v in jverts]
    zs = [v.z for v in jverts]
    result['jacket_final'] = {
        'x': [round(min(xs), 4), round(max(xs), 4)],
        'y': [round(min(ys), 4), round(max(ys), 4)],
        'z': [round(min(zs), 4), round(max(zs), 4)],
    }
    
    # Right sleeve
    right = [v for v in jverts if v.x > 0.2]
    if right:
        rxs = [v.x for v in right]
        rys = [v.y for v in right]
        rzs = [v.z for v in right]
        result['right_sleeve_final'] = {
            'x': [round(min(rxs), 4), round(max(rxs), 4)],
            'centroid_x': round(sum(rxs)/len(rxs), 4),
        }

jacket_eval.to_mesh_clear()

# Body arm for comparison
for name in ['braco superior esquerdo', 'antebraco esquerdo']:
    obj = bpy.data.objects.get(name)
    if obj:
        mat = obj.matrix_world
        wv = [mat @ v.co for v in obj.data.vertices]
        xs = [v.x for v in wv]
        result[f'{name}_x'] = [round(min(xs), 4), round(max(xs), 4)]

# Save
bpy.ops.wm.save_mainfile()

print('PIPELINE_RESULT:' + json.dumps(result))
