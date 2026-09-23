import bpy
import bmesh
import mathutils
import math
import numpy as np
import os

def export_female_cage():
    obj = bpy.data.objects.get('Roblox_Female_Cage_Universal')
    arm = bpy.data.objects.get('Armature_Character.001')
    cages_col = bpy.data.collections.get('Cages_Feminino')

    if not obj or not arm or not cages_col:
        print("Required objects not found in Blender!")
        return

    # 1. Get triangulated mesh from obj in rest pose
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    rest_verts = np.array([v.co for v in bm.verts], dtype=np.float32)
    faces = np.array([[v.index for v in f.verts] for f in bm.faces], dtype=np.int32)
    print(f"Unified Female Cage: {len(rest_verts)} vertices, {len(faces)} triangulated faces.")

    # 2. Identify arm vertices using the original cages as ground truth
    arm_objs_l = ['LeftUpperArm_OuterCage', 'LeftLowerArm_OuterCage', 'LeftHand_OuterCage']
    arm_objs_r = ['RightUpperArm_OuterCage', 'RightLowerArm_OuterCage', 'RightHand_OuterCage']

    l_arm_pts = []
    for name in arm_objs_l:
        o = cages_col.objects[name]
        mw = o.matrix_world
        l_arm_pts.extend([mw @ v.co for v in o.data.vertices])

    r_arm_pts = []
    for name in arm_objs_r:
        o = cages_col.objects[name]
        mw = o.matrix_world
        r_arm_pts.extend([mw @ v.co for v in o.data.vertices])

    l_arm_verts = []
    r_arm_verts = []
    for idx, v in enumerate(rest_verts):
        min_dl = min(np.linalg.norm(v - pt) for pt in l_arm_pts)
        min_dr = min(np.linalg.norm(v - pt) for pt in r_arm_pts)
        if min_dl < 0.005:
            l_arm_verts.append(idx)
        elif min_dr < 0.005:
            r_arm_verts.append(idx)

    l_arm_set = set(l_arm_verts)
    r_arm_set = set(r_arm_verts)
    print(f"Identified {len(l_arm_verts)} Left Arm verts and {len(r_arm_verts)} Right Arm verts.")

    # 3. Shoulder pivots
    sh_l = np.array([0.204087, 0.003967, 1.476274], dtype=np.float32)
    sh_r = np.array([-0.204087, 0.003967, 1.476274], dtype=np.float32)

    def rotate_arm(verts, idxs, pivot, angle_deg, is_left=True):
        angle = -angle_deg if is_left else angle_deg
        rot_mat = mathutils.Matrix.Rotation(math.radians(angle), 3, 'Y')
        R = np.array(rot_mat, dtype=np.float32)
        p = verts[idxs] - pivot
        return (p @ R.T) + pivot

    # 4. Generate Poses
    # A-Pose: 24.2 degrees rotation (reaching exactly 36.5 deg from vertical, matching Roblox template)
    apose_verts = rest_verts.copy()
    apose_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 24.2, is_left=True)
    apose_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 24.2, is_left=False)

    # T-Pose 75 deg (62.7 deg rotation from rest 12.3 deg)
    tpose_75_verts = rest_verts.copy()
    tpose_75_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 62.7, is_left=True)
    tpose_75_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 62.7, is_left=False)

    # T-Pose 85 deg (77.7 deg rotation from rest 12.3 deg, reaching exactly 90.0 deg horizontal)
    tpose_85_verts = rest_verts.copy()
    tpose_85_verts[l_arm_verts] = rotate_arm(rest_verts, l_arm_verts, sh_l, 77.7, is_left=True)
    tpose_85_verts[r_arm_verts] = rotate_arm(rest_verts, r_arm_verts, sh_r, 77.7, is_left=False)

    # 5. Face groups (0 = Torso/Pelvis/Legs, 1 = Left Arm, 2 = Right Arm)
    face_groups = np.zeros(len(faces), dtype=np.int32)
    for fi, f in enumerate(faces):
        if all(vi in l_arm_set for vi in f):
            face_groups[fi] = 1
        elif all(vi in r_arm_set for vi in f):
            face_groups[fi] = 2

    print(f"Face groups: {np.sum(face_groups == 0)} Torso/Legs, {np.sum(face_groups == 1)} Left Arm, {np.sum(face_groups == 2)} Right Arm.")

    # 6. Extract joint landmarks from armature
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

    # 7. Extract raw body parts for Arm HSR from Collection 6
    col6 = bpy.data.collections.get('Collection 6')
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
    print(f"SUCCESS: Exported female cage data to {out_npz}")
    print(f"Files inside npz: {list(cage_dict.keys())}")
    bm.free()

export_female_cage()
