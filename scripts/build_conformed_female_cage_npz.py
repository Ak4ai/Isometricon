import bpy
import bmesh
import mathutils
import math
import numpy as np
import os
from mathutils.bvhtree import BVHTree

def export_conformed_female_cage():
    src_obj = bpy.data.objects.get('Roblox_Inner_Cage_Universal')
    dst_obj = bpy.data.objects.get('Roblox_Female_Cage_Universal')
    arm = bpy.data.objects.get('Armature_Character.001')
    col6 = bpy.data.collections.get('Collection 6')

    if not src_obj or not dst_obj or not arm:
        print("ERROR: Required objects not found in Blender!")
        return

    # 1. Regional mapping setup
    region_map = {
        'head': ['Head'],
        'torso_pelvis': ['Torso', 'Pelvis'],
        'arm_l': ['UpperArm_L', 'LowerArm_L'],
        'arm_r': ['UpperArm_R', 'LowerArm_R'],
        'leg_l': ['UpperLeg_L', 'LowerLeg_L', 'Foot_L'],
        'leg_r': ['UpperLeg_R', 'LowerLeg_R', 'Foot_R'],
    }

    vg_to_region = {}
    for rname, vgnames in region_map.items():
        for vg in vgnames:
            vg_to_region[vg] = rname

    # 2. Build BVHTrees for DST (Roblox_Female_Cage_Universal)
    dst_bm = bmesh.new()
    dst_bm.from_mesh(dst_obj.data)
    dst_bm.faces.ensure_lookup_table()
    dst_bm.verts.ensure_lookup_table()
    dvert_lay = dst_bm.verts.layers.deform.verify()

    dst_vert_regions = {}
    for v in dst_bm.verts:
        dvert = v[dvert_lay]
        if dvert:
            best_vg_idx = max(dvert.items(), key=lambda item: item[1])[0]
            best_vg_name = dst_obj.vertex_groups[best_vg_idx].name
            dst_vert_regions[v.index] = vg_to_region.get(best_vg_name, 'torso_pelvis')
        else:
            dst_vert_regions[v.index] = 'torso_pelvis'

    region_bvhs = {}
    for rname in region_map.keys():
        r_faces = [f for f in dst_bm.faces if any(dst_vert_regions[v.index] == rname for v in f.verts)]
        if r_faces:
            verts_coords = [v.co for v in dst_bm.verts]
            poly_indices = [[v.index for v in f.verts] for f in r_faces]
            region_bvhs[rname] = BVHTree.FromPolygons(verts_coords, poly_indices)

    # 3. Conform SRC (Roblox_Inner_Cage_Universal)
    src_bm = bmesh.new()
    src_bm.from_mesh(src_obj.data)
    src_bm.verts.ensure_lookup_table()
    src_faces_raw = [[v.index for v in f.verts] for f in src_bm.faces]
    src_dvert_lay = src_bm.verts.layers.deform.verify()

    vg_names = {g.index: g.name for g in src_obj.vertex_groups}
    l_arm_verts = []
    r_arm_verts = []

    conformed_rest = []
    for v in src_bm.verts:
        dvert = v[src_dvert_lay]
        if dvert:
            best_vg_idx = max(dvert.items(), key=lambda item: item[1])[0]
            best_vg_name = src_obj.vertex_groups[best_vg_idx].name
            rname = vg_to_region.get(best_vg_name, 'torso_pelvis')
            # Check arm group
            for g_idx, weight in dvert.items():
                g_name = vg_names.get(g_idx, '')
                if weight > 0.5:
                    if g_name in ['UpperArm_L', 'LowerArm_L'] and v.index not in l_arm_verts:
                        l_arm_verts.append(v.index)
                    elif g_name in ['UpperArm_R', 'LowerArm_R'] and v.index not in r_arm_verts:
                        r_arm_verts.append(v.index)
        else:
            rname = 'torso_pelvis'

        bvh = region_bvhs.get(rname)
        if bvh:
            loc, norm, idx, dist = bvh.find_nearest(v.co)
            conformed_rest.append(np.array(loc if loc is not None else v.co, dtype=np.float32))
        else:
            conformed_rest.append(np.array(v.co, dtype=np.float32))

    rest_verts = np.array(conformed_rest, dtype=np.float32)
    faces = np.array(src_faces_raw, dtype=np.int32)
    print(f"Conformed Cage: {len(rest_verts)} vertices, {len(faces)} faces.")
    print(f"Identified {len(l_arm_verts)} Left Arm verts, {len(r_arm_verts)} Right Arm verts.")

    # 4. Generate A-Pose and T-Pose
    sh_l = np.array([0.204087, 0.003967, 1.476274], dtype=np.float32)
    sh_r = np.array([-0.204087, 0.003967, 1.476274], dtype=np.float32)

    def rotate_arm(verts, idxs, pivot, angle_deg, is_left=True):
        angle = -angle_deg if is_left else angle_deg
        rot_mat = mathutils.Matrix.Rotation(math.radians(angle), 3, 'Y')
        R = np.array(rot_mat, dtype=np.float32)
        p = verts[idxs] - pivot
        return (p @ R.T) + pivot

    apose_verts = rest_verts.copy()
    apose_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 24.2, is_left=True)
    apose_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 24.2, is_left=False)

    tpose_75_verts = rest_verts.copy()
    tpose_75_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 62.7, is_left=True)
    tpose_75_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 62.7, is_left=False)

    tpose_85_verts = rest_verts.copy()
    tpose_85_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 77.7, is_left=True)
    tpose_85_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 77.7, is_left=False)

    # 5. Face groups
    l_arm_set = set(l_arm_verts)
    r_arm_set = set(r_arm_verts)
    face_groups = np.zeros(len(faces), dtype=np.int32)
    for fi, f in enumerate(faces):
        if any(vi in l_arm_set for vi in f):
            face_groups[fi] = 1
        elif any(vi in r_arm_set for vi in f):
            face_groups[fi] = 2

    print(f"Face groups: {np.sum(face_groups == 0)} Torso/Legs, {np.sum(face_groups == 1)} Left Arm, {np.sum(face_groups == 2)} Right Arm.")

    # 6. Joint landmarks
    pb_sh_l = arm.pose.bones['UpperArm_L']
    pb_sh_r = arm.pose.bones['UpperArm_R']
    pb_el_l = arm.pose.bones['LowerArm_L']
    pb_el_r = arm.pose.bones['LowerArm_R']
    pb_hip_l = arm.pose.bones['UpperLeg_L']
    pb_hip_r = arm.pose.bones['UpperLeg_R']
    pb_knee_l = arm.pose.bones['LowerLeg_L']
    pb_knee_r = arm.pose.bones['LowerLeg_R']
    pb_foot_l = arm.pose.bones['Foot_L']
    pb_foot_r = arm.pose.bones['Foot_R']

    cage_dict = {
        'cage_verts_rest': rest_verts,
        'cage_verts_apose': apose_verts,
        'cage_verts_tpose_75': tpose_75_verts,
        'cage_verts_tpose_85': tpose_85_verts,
        'cage_faces': faces,
        'cage_face_groups': face_groups,
        'shoulder_l_head': np.array(pb_sh_l.head, dtype=np.float32),
        'shoulder_l_tail': np.array(pb_sh_l.tail, dtype=np.float32),
        'shoulder_r_head': np.array(pb_sh_r.head, dtype=np.float32),
        'shoulder_r_tail': np.array(pb_sh_r.tail, dtype=np.float32),
        'elbow_l': np.array(pb_el_l.head, dtype=np.float32),
        'elbow_r': np.array(pb_el_r.head, dtype=np.float32),
        'wrist_l': np.array(pb_el_l.tail, dtype=np.float32),
        'wrist_r': np.array(pb_el_r.tail, dtype=np.float32),
        'hip_l': np.array(pb_hip_l.head, dtype=np.float32),
        'hip_r': np.array(pb_hip_r.head, dtype=np.float32),
        'knee_l': np.array(pb_knee_l.head, dtype=np.float32),
        'knee_r': np.array(pb_knee_r.head, dtype=np.float32),
        'ankle_l': np.array(pb_foot_l.head, dtype=np.float32),
        'ankle_r': np.array(pb_foot_r.head, dtype=np.float32),
    }

    # 7. HSR body parts from Collection 6
    if col6:
        body_mapping = {
            'braco superior esquerdo': 'Export_braco_superior_esquerdo.001',
            'braco superior direito': 'Export_braco_superior_direito.001',
            'antebraco esquerdo': 'Export_antebraco_esquerdo.001',
            'antebraco direito': 'Export_antebraco_direito.001',
            'torso': 'Export_torso.001',
            'pelve': 'Export_pelve.001',
        }
        for eng_name, b_name in body_mapping.items():
            b_obj = col6.objects.get(b_name)
            if b_obj:
                bm_b = bmesh.new()
                bm_b.from_mesh(b_obj.data)
                bmesh.ops.triangulate(bm_b, faces=bm_b.faces)
                bm_b.verts.ensure_lookup_table()
                bm_b.faces.ensure_lookup_table()
                b_verts = np.array([v.co for v in bm_b.verts], dtype=np.float32)
                b_faces = np.array([[v.index for v in f.verts] for f in bm_b.faces], dtype=np.int32)
                bm_b.free()
                cage_dict[f"{eng_name}_verts"] = b_verts
                cage_dict[f"{eng_name}_faces"] = b_faces
                cage_dict[f"{eng_name}_matrix_world"] = np.array(b_obj.matrix_world, dtype=np.float32)
                print(f"  Added HSR part: {eng_name} ({len(b_verts)} verts, {len(b_faces)} tris)")

    base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
    out_npz = os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz")
    np.savez(out_npz, **cage_dict)
    print(f"SUCCESS: Exported 1711-vertex female cage data to {out_npz}")
    dst_bm.free()
    src_bm.free()

export_conformed_female_cage()
