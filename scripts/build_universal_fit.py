"""
Build the Universal Fit using Shape Keys on Roblox_Inner_Cage:
- Basis: Roblox standard cage shape (where clothing is bound 1:1)
- CharacterFit: Conformed to character geometry with smooth regional morph and safe margins
"""
import bpy
import json
import math
import os
from mathutils import Vector, Quaternion, Matrix

arm_obj = bpy.data.objects.get('Armature_Character')
cage = bpy.data.objects.get('Roblox_Inner_Cage')
jacket = bpy.data.objects.get('Jacket_1')

assert arm_obj and cage and jacket

# Put armature in Roblox A-Pose
apose_quats = {
    'UpperArm_L': Quaternion((0.9723699, -0.0585698, 0.0, -0.2259149)),
    'UpperArm_R': Quaternion((0.9723699, -0.0585698, 0.0, 0.2259149)),
}
for pb in arm_obj.pose.bones:
    if pb.name in apose_quats:
        pb.rotation_quaternion = apose_quats[pb.name]
    else:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# Clear modifiers and shape keys from cage
for m in list(cage.modifiers):
    cage.modifiers.remove(m)
if cage.data.shape_keys:
    cage.shape_key_clear()

# Unbind jacket
for m in list(jacket.modifiers):
    if m.type == 'SURFACE_DEFORM':
        if m.is_bound:
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            bpy.ops.object.surfacedeform_bind(modifier=m.name)
        jacket.modifiers.remove(m)

# Restore raw Roblox inner cage from OBJ
cage_obj_path = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\inner_cage.obj'
raw_verts = []
with open(cage_obj_path, 'r') as f:
    for line in f:
        if line.startswith('v '):
            p = line.strip().split()
            raw_verts.append(Vector((float(p[1]), float(p[2]), float(p[3]))))

for i, v in enumerate(cage.data.vertices):
    v.co = raw_verts[i]

cage.location = (0.0, 0.0, 0.91)
cage.rotation_euler = (math.radians(90), 0.0, math.radians(180))
cage.scale = (0.3309, 0.3309, 0.3309)
bpy.context.view_layer.update()

# Set up Jacket transform and material
jacket.parent = None
jacket.location = (0.0, 0.015, 1.16)
jacket.rotation_euler = (math.radians(90), 0.0, math.radians(180))
jacket.scale = (0.52, 0.56, 0.44)

for slot in jacket.material_slots:
    if slot.material:
        mat = slot.material
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'OPAQUE'
        mat.use_backface_culling = False
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED' and 'Alpha' in node.inputs:
                    node.inputs['Alpha'].default_value = 1.0

# 1. Create Shape Keys on Cage: Basis
sk_basis = cage.shape_key_add(name='Basis')
sk_fit = cage.shape_key_add(name='CharacterFit')

# 2. Compute Conformed Vertices for CharacterFit
cage_mat = cage.matrix_world
cage_inv = cage_mat.inverted()
raw_wv = [cage_mat @ v for v in raw_verts]

# Regions segmentation in world space
total_h = max(v.z for v in raw_wv) - min(v.z for v in raw_wv)
min_z = min(v.z for v in raw_wv)
hip_z = min_z + total_h * 0.40
neck_z = min_z + total_h * 0.80
torso_half_w = 0.12

regions = {
    'head': [],
    'torso': [],
    'arm_R': [], # world +X (char Left)
    'arm_L': [], # world -X (char Right)
    'leg_R': [],
    'leg_L': [],
    'hip': [],
}

for i, v in enumerate(raw_wv):
    if v.z > neck_z:
        regions['head'].append(i)
    elif v.z > hip_z and abs(v.x) > torso_half_w:
        if v.x > 0:
            regions['arm_R'].append(i)
        else:
            regions['arm_L'].append(i)
    elif v.z > hip_z:
        regions['torso'].append(i)
    elif v.z <= hip_z and abs(v.x) > 0.01:
        if v.x > 0:
            regions['leg_R'].append(i)
        else:
            regions['leg_L'].append(i)
    else:
        regions['hip'].append(i)

# Target anatomy bounds in A-pose
depsgraph = bpy.context.evaluated_depsgraph_get()
body_map = {
    'torso': ['torso'],
    'hip': ['pelve'],
    'arm_R': ['braco superior esquerdo', 'antebraco esquerdo'],
    'arm_L': ['braco superior direito', 'antebraco direito'],
    'leg_R': ['coxa esquerda', 'canela esquerda'],
    'leg_L': ['coxa direita', 'canela direita'],
}

body_bounds = {}
for rname, pnames in body_map.items():
    pts = []
    for pname in pnames:
        o = bpy.data.objects.get(pname)
        if o:
            oe = o.evaluated_get(depsgraph)
            em = oe.to_mesh()
            pts.extend([oe.matrix_world @ v.co for v in em.vertices])
            oe.to_mesh_clear()
    if pts:
        body_bounds[rname] = {
            'min': Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            'max': Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))),
        }

# Generous margins to eliminate cube clipping completely
margins = {
    'torso': Vector((0.028, 0.030, 0.018)),
    'hip': Vector((0.025, 0.025, 0.018)),
    'arm_R': Vector((0.028, 0.028, 0.025)),
    'arm_L': Vector((0.028, 0.028, 0.025)),
    'leg_R': Vector((0.018, 0.018, 0.018)),
    'leg_L': Vector((0.018, 0.018, 0.018)),
}

for rname, indices in regions.items():
    if not indices or rname == 'head' or rname not in body_bounds:
        for idx in indices:
            sk_fit.data[idx].co = raw_verts[idx]
        continue
    
    c_pts = [raw_wv[i] for i in indices]
    c_min = Vector((min(p.x for p in c_pts), min(p.y for p in c_pts), min(p.z for p in c_pts)))
    c_max = Vector((max(p.x for p in c_pts), max(p.y for p in c_pts), max(p.z for p in c_pts)))
    c_size = c_max - c_min
    c_cen = (c_min + c_max) / 2
    
    mar = margins.get(rname, Vector((0.02, 0.02, 0.02)))
    b_min = body_bounds[rname]['min'] - mar
    b_max = body_bounds[rname]['max'] + mar
    b_size = b_max - b_min
    b_cen = (b_min + b_max) / 2
    
    for idx in indices:
        ow = raw_wv[idx]
        nx = max(-1.15, min(1.15, (ow.x - c_cen.x) / max(c_size.x / 2, 0.001)))
        ny = max(-1.15, min(1.15, (ow.y - c_cen.y) / max(c_size.y / 2, 0.001)))
        nz = max(-1.15, min(1.15, (ow.z - c_cen.z) / max(c_size.z / 2, 0.001)))
        
        nw = Vector((
            b_cen.x + nx * (b_size.x / 2),
            b_cen.y + ny * (b_size.y / 2),
            b_cen.z + nz * (b_size.z / 2),
        ))
        sk_fit.data[idx].co = cage_inv @ nw

# 3. Bind Jacket to Cage at Basis (value = 0.0)
sk_fit.value = 0.0
bpy.context.view_layer.update()

sd_mod = jacket.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')
sd_mod.target = cage

bpy.ops.object.select_all(action='DESELECT')
jacket.select_set(True)
bpy.context.view_layer.objects.active = jacket
bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)

# 4. Now Dial CharacterFit to 1.0!
sk_fit.value = 1.0
bpy.context.view_layer.update()

# 5. Add Armature Modifier to Cage (rigging)
# Create vertex groups based on conformed coordinates
cage.vertex_groups.clear()
bone_eval_defs = {}
for pb in arm_obj.pose.bones:
    bone_eval_defs[pb.name] = {
        'head': arm_obj.matrix_world @ pb.head,
        'tail': arm_obj.matrix_world @ pb.tail
    }
    cage.vertex_groups.new(name=pb.name)

def seg_dist(p, a, b):
    ab = b - a
    ap = p - a
    t = max(0.0, min(1.0, ap.dot(ab) / max(ab.dot(ab), 1e-10)))
    return (p - (a + ab * t)).length

region_allowed = {
    'torso': ['Torso', 'Neck', 'Pelvis'],
    'hip': ['Pelvis', 'Torso'],
    'arm_R': ['UpperArm_L', 'LowerArm_L', 'Torso'],
    'arm_L': ['UpperArm_R', 'LowerArm_R', 'Torso'],
    'leg_R': ['UpperLeg_L', 'LowerLeg_L', 'Foot_L', 'Pelvis'],
    'leg_L': ['UpperLeg_R', 'LowerLeg_R', 'Foot_R', 'Pelvis'],
    'head': ['Head', 'Neck'],
}

for rname, indices in regions.items():
    allowed = region_allowed.get(rname, [b.name for b in arm_obj.data.bones])
    for idx in indices:
        p = cage_mat @ sk_fit.data[idx].co
        dists = [(seg_dist(p, bone_eval_defs[bn]['head'], bone_eval_defs[bn]['tail']), bn) for bn in allowed]
        dists.sort(key=lambda x: x[0])
        
        d0, b0 = dists[0]
        w_dict = {b0: 1.0 / max(d0, 0.01) ** 2}
        if len(dists) > 1 and dists[1][0] < d0 * 2.5 and dists[1][0] < 0.25:
            w_dict[dists[1][1]] = 1.0 / max(dists[1][0], 0.01) ** 2
        
        tot = sum(w_dict.values())
        for bn, w in w_dict.items():
            cage.vertex_groups[bn].add([idx], w / tot, 'REPLACE')

arm_mod = cage.modifiers.new(name='Armature', type='ARMATURE')
arm_mod.object = arm_obj
arm_mod.use_vertex_groups = True

bpy.context.view_layer.update()
bpy.ops.wm.save_mainfile()

print("UNIVERSAL_FIT_DONE:is_bound=" + str(sd_mod.is_bound))
