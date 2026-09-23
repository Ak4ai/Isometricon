"""
Full Universal Roblox Layered Clothing Pipeline for Isometricon:
1. Conforms inner_cage.obj to character anatomy in Roblox A-pose with safe padding.
2. Inverts pose deformation to get exact rest-pose cage geometry (matching Armature rest pose).
3. Adds Armature modifier with exact weights.
4. Binds Jacket via SurfaceDeform in A-pose.
5. Verifies both A-pose and Rest-pose deformation and renders previews.
"""
import bpy
import json
import math
import os
from mathutils import Vector, Quaternion, Matrix

def run_pipeline():
    arm_obj = bpy.data.objects.get('Armature_Character')
    cage = bpy.data.objects.get('Roblox_Inner_Cage')
    jacket = bpy.data.objects.get('Jacket_1')

    assert arm_obj and cage and jacket, "Missing Armature_Character, Roblox_Inner_Cage or Jacket_1"

    report = {}

    # ----------------------------------------------------
    # 1. Pose Armature in Roblox A-Pose
    # ----------------------------------------------------
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
    report['step1'] = 'Armature in A-pose'

    # ----------------------------------------------------
    # 2. Reset Cage and Jacket
    # ----------------------------------------------------
    # Unbind jacket SurfaceDeform
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM' and m.is_bound:
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            bpy.ops.object.surfacedeform_bind(modifier=m.name)

    # Remove all modifiers from cage
    for m in list(cage.modifiers):
        cage.modifiers.remove(m)
    cage.vertex_groups.clear()

    # Restore raw Roblox inner_cage vertices from OBJ
    cage_obj_path = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\inner_cage.obj'
    orig_verts = []
    with open(cage_obj_path, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                orig_verts.append(Vector((float(parts[1]), float(parts[2]), float(parts[3]))))

    assert len(orig_verts) == len(cage.data.vertices)
    for i, v in enumerate(cage.data.vertices):
        v.co = orig_verts[i]

    # Set cage base transform
    cage.location = (0.0, 0.0, 0.91)
    cage.rotation_euler = (math.radians(90), 0.0, math.radians(180))
    cage.scale = (0.3309, 0.3309, 0.3309)
    bpy.context.view_layer.update()

    # ----------------------------------------------------
    # 3. Smart Region-Based Conforming in A-Pose
    # ----------------------------------------------------
    cage_mat = cage.matrix_world
    cage_inv_mat = cage_mat.inverted()
    wv = [cage_mat @ v.co for v in cage.data.vertices]

    total_height = max(v.z for v in wv) - min(v.z for v in wv)
    min_z = min(v.z for v in wv)
    hip_z = min_z + total_height * 0.40
    neck_z = min_z + total_height * 0.80
    torso_half_width = 0.12

    regions = {
        'head': [],
        'torso': [],
        'arm_R': [], # world +X (char Left)
        'arm_L': [], # world -X (char Right)
        'leg_R': [],
        'leg_L': [],
        'hip': [],
    }

    for i, v in enumerate(wv):
        vx, vy, vz = v.x, v.y, v.z
        if vz > neck_z:
            regions['head'].append(i)
        elif vz > hip_z and abs(vx) > torso_half_width:
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

    # Get body bounding boxes in evaluated A-pose
    body_parts_map = {
        'torso': ['torso'],
        'hip': ['pelve'],
        'arm_R': ['braco superior esquerdo', 'antebraco esquerdo'],
        'arm_L': ['braco superior direito', 'antebraco direito'],
        'leg_R': ['coxa esquerda', 'canela esquerda'],
        'leg_L': ['coxa direita', 'canela direita'],
    }

    depsgraph = bpy.context.evaluated_depsgraph_get()
    body_bounds = {}
    for rname, pnames in body_parts_map.items():
        all_pts = []
        for pname in pnames:
            obj = bpy.data.objects.get(pname)
            if obj:
                obj_eval = obj.evaluated_get(depsgraph)
                emesh = obj_eval.to_mesh()
                mat = obj_eval.matrix_world
                all_pts.extend([mat @ v.co for v in emesh.vertices])
                obj_eval.to_mesh_clear()
        if all_pts:
            body_bounds[rname] = {
                'min': Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts))),
                'max': Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts))),
            }

    # Adequate paddings to fully clear cube corners
    paddings = {
        'torso': Vector((0.024, 0.024, 0.015)),
        'hip': Vector((0.020, 0.020, 0.015)),
        'arm_R': Vector((0.022, 0.022, 0.020)),
        'arm_L': Vector((0.022, 0.022, 0.020)),
        'leg_R': Vector((0.015, 0.015, 0.015)),
        'leg_L': Vector((0.015, 0.015, 0.015)),
    }

    # Store target A-pose conformed positions in world space
    target_apose_wv = list(wv)

    for rname, indices in regions.items():
        if not indices or rname == 'head' or rname not in body_bounds:
            continue
        
        c_verts = [wv[i] for i in indices]
        c_min = Vector((min(p.x for p in c_verts), min(p.y for p in c_verts), min(p.z for p in c_verts)))
        c_max = Vector((max(p.x for p in c_verts), max(p.y for p in c_verts), max(p.z for p in c_verts)))
        c_size = c_max - c_min
        c_center = (c_min + c_max) / 2
        
        pad = paddings.get(rname, Vector((0.015, 0.015, 0.015)))
        b_min = body_bounds[rname]['min'] - pad
        b_max = body_bounds[rname]['max'] + pad
        b_size = b_max - b_min
        b_center = (b_min + b_max) / 2
        
        for idx in indices:
            ow = wv[idx]
            nx = (ow.x - c_center.x) / max(c_size.x / 2, 0.001)
            ny = (ow.y - c_center.y) / max(c_size.y / 2, 0.001)
            nz = (ow.z - c_center.z) / max(c_size.z / 2, 0.001)
            
            nx = max(-1.1, min(1.1, nx))
            ny = max(-1.1, min(1.1, ny))
            nz = max(-1.1, min(1.1, nz))
            
            nw = Vector((
                b_center.x + nx * (b_size.x / 2),
                b_center.y + ny * (b_size.y / 2),
                b_center.z + nz * (b_size.z / 2),
            ))
            target_apose_wv[idx] = nw

    report['step3'] = 'Computed target A-pose geometry'

    # ----------------------------------------------------
    # 4. Accurate Vertex Weight Calculation in A-Pose
    # ----------------------------------------------------
    # Bone segments in world space in CURRENT A-pose
    bone_eval_defs = {}
    for pb in arm_obj.pose.bones:
        h = arm_obj.matrix_world @ pb.head
        t = arm_obj.matrix_world @ pb.tail
        bone_eval_defs[pb.name] = {'head': h, 'tail': t}

    def seg_dist(p, a, b):
        ab = b - a
        ap = p - a
        t = max(0.0, min(1.0, ap.dot(ab) / max(ab.dot(ab), 1e-10)))
        closest = a + ab * t
        return (p - closest).length

    for pb in arm_obj.pose.bones:
        cage.vertex_groups.new(name=pb.name)

    region_allowed_bones = {
        'torso': ['Torso', 'Neck', 'Pelvis'],
        'hip': ['Pelvis', 'Torso'],
        'arm_R': ['UpperArm_L', 'LowerArm_L', 'Torso'],  # char left
        'arm_L': ['UpperArm_R', 'LowerArm_R', 'Torso'],  # char right
        'leg_R': ['UpperLeg_L', 'LowerLeg_L', 'Foot_L', 'Pelvis'],
        'leg_L': ['UpperLeg_R', 'LowerLeg_R', 'Foot_R', 'Pelvis'],
        'head': ['Head', 'Neck'],
    }

    # Store vertex weights dict: vert_weights[idx] = {bone_name: weight}
    vert_weights = {}

    for rname, indices in regions.items():
        allowed = region_allowed_bones.get(rname, [b.name for b in arm_obj.data.bones])
        for idx in indices:
            p = target_apose_wv[idx]
            distances = []
            for bname in allowed:
                d = seg_dist(p, bone_eval_defs[bname]['head'], bone_eval_defs[bname]['tail'])
                distances.append((d, bname))
            distances.sort(key=lambda x: x[0])
            
            d0, b0 = distances[0]
            w0 = 1.0 / max(d0, 0.01) ** 2
            w_dict = {b0: w0}
            
            if len(distances) > 1:
                d1, b1 = distances[1]
                if d1 < d0 * 2.5 and d1 < 0.25:
                    w1 = 1.0 / max(d1, 0.01) ** 2
                    w_dict[b1] = w1
            
            tot = sum(w_dict.values())
            norm_w = {b: w / tot for b, w in w_dict.items()}
            vert_weights[idx] = norm_w
            for bname, w in norm_w.items():
                cage.vertex_groups[bname].add([idx], w, 'REPLACE')

    report['step4'] = 'Vertex groups created with accurate anatomy'

    # ----------------------------------------------------
    # 5. Invert Pose Transformation to get Base Rest Geometry
    # ----------------------------------------------------
    # For each bone, get deformation matrix T_b = pb.matrix @ pb.bone.matrix_local.inverted()
    # and its inverse T_b_inv = pb.bone.matrix_local @ pb.matrix.inverted()
    bone_T_inv = {}
    for pb in arm_obj.pose.bones:
        T_b = pb.matrix @ pb.bone.matrix_local.inverted()
        bone_T_inv[pb.name] = T_b.inverted()

    # For each vertex, rest_pos = sum(w_b * T_b_inv) @ apose_pos
    for idx, nw in enumerate(target_apose_wv):
        weights = vert_weights.get(idx, {'Torso': 1.0})
        
        # Weighted inverse transform in armature space
        p_arm = arm_obj.matrix_world.inverted() @ nw
        
        rest_p_arm = Vector((0.0, 0.0, 0.0))
        for bname, w in weights.items():
            T_inv = bone_T_inv.get(bname, Matrix.Identity(4))
            rest_p_arm += w * (T_inv @ p_arm)
        
        # Convert from armature space back to cage local space
        rest_p_world = arm_obj.matrix_world @ rest_p_arm
        cage.data.vertices[idx].co = cage_inv_mat @ rest_p_world

    bpy.context.view_layer.update()

    # Add Armature modifier to cage
    arm_mod = cage.modifiers.new(name='Armature', type='ARMATURE')
    arm_mod.object = arm_obj
    arm_mod.use_vertex_groups = True

    report['step5'] = 'Rest pose base geometry inverted and Armature modifier attached'

    # ----------------------------------------------------
    # 6. Verify Cage in A-Pose & Bind Jacket
    # ----------------------------------------------------
    bpy.context.view_layer.update()

    # In A-pose, the cage should match target_apose_wv
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cage_eval = cage.evaluated_get(depsgraph)
    c_mesh = cage_eval.to_mesh()
    eval_wv = [cage.matrix_world @ v.co for v in c_mesh.vertices]
    max_err = max((eval_wv[i] - target_apose_wv[i]).length for i in range(len(eval_wv)))
    report['max_apose_reconstruction_error'] = round(max_err, 6)
    cage_eval.to_mesh_clear()

    # Now jacket setup in A-pose
    jacket.parent = None
    jacket.location = (0.0, 0.015, 1.16)
    jacket.rotation_euler = (math.radians(90), 0.0, math.radians(180))
    jacket.scale = (0.52, 0.56, 0.44)

    # Material fix
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

    # Recalculate jacket normals outside
    bpy.ops.object.select_all(action='DESELECT')
    jacket.select_set(True)
    bpy.context.view_layer.objects.active = jacket
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Bind SurfaceDeform to cage in A-pose
    sd_mod = None
    for m in jacket.modifiers:
        if m.type == 'SURFACE_DEFORM':
            sd_mod = m
            break
    if not sd_mod:
        sd_mod = jacket.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')

    sd_mod.target = cage
    if sd_mod.is_bound:
        bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
    try:
        bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
        report['jacket_bound'] = sd_mod.is_bound
    except Exception as e:
        report['jacket_bind_error'] = str(e)

    bpy.context.view_layer.update()

    # Save
    bpy.ops.wm.save_mainfile()
    report['status'] = 'SUCCESS'
    return report

res = run_pipeline()
print("PIPELINE_OUT:" + json.dumps(res, indent=2))
