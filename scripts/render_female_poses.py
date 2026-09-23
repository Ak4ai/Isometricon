import bpy
import mathutils
import math
import numpy as np
import os

def render_female_poses_clean():
    scene = bpy.context.scene
    obj = bpy.data.objects['Roblox_Female_Cage_Universal']

    # Unhide collections
    for c in bpy.data.collections:
        c.hide_render = False
        c.hide_viewport = False

    # Hide EVERY object from render except Roblox_Female_Cage_Universal
    for o in bpy.data.objects:
        if o.name == 'Roblox_Female_Cage_Universal':
            o.hide_render = False
            o.hide_viewport = False
            o.show_wire = True
            o.show_all_edges = True
        elif o.type == 'CAMERA':
            o.hide_render = False
        else:
            o.hide_render = True
            o.hide_viewport = True

    # Camera setup
    cam = bpy.data.objects.get('Crotch_Cam')
    if not cam:
        cam_data = bpy.data.cameras.new('Crotch_Cam')
        cam = bpy.data.objects.new('Crotch_Cam', cam_data)
        scene.collection.objects.link(cam)
    scene.camera = cam

    scene.render.resolution_x = 800
    scene.render.resolution_y = 750
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = True

    # Read base vertices of Roblox_Female_Cage_Universal (Rest Pose)
    mesh = obj.data
    rest_verts = np.array([v.co for v in mesh.vertices], dtype=np.float32)

    cages_col = bpy.data.collections.get('Cages_Feminino')
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

    # Pivot points (heads of UpperArm_L and UpperArm_R)
    sh_l = np.array([0.204087, 0.003967, 1.476274], dtype=np.float32)
    sh_r = np.array([-0.204087, 0.003967, 1.476274], dtype=np.float32)

    def rotate_arm_matrix(verts, idxs, pivot, angle_deg, is_left=True):
        angle = -angle_deg if is_left else angle_deg
        rot_mat = mathutils.Matrix.Rotation(math.radians(angle), 3, 'Y')
        R = np.array(rot_mat, dtype=np.float32)
        p = verts[idxs] - pivot
        return (p @ R.T) + pivot

    artifact_dir = r"C:\Users\Henrique\.gemini\antigravity-cli\brain\b12a4ec6-59d8-4b95-b402-045e7dddf299"
    poses = [
        ("female_cage_clean_rest.png", "female_cage_clean_rest_3q.png", 0),
        ("female_cage_clean_apose.png", "female_cage_clean_apose_3q.png", 24.2), # 24.2 deg rotation -> 36.5 deg A-pose
        ("female_cage_clean_tpose.png", "female_cage_clean_tpose_3q.png", 77.7), # 77.7 deg rotation -> 90.0 deg T-pose
    ]

    for filename_front, filename_3q, angle in poses:
        deformed = rest_verts.copy()
        if angle > 0:
            deformed[l_arm_verts] = rotate_arm_matrix(rest_verts, l_arm_verts, sh_l, angle, is_left=True)
            deformed[r_arm_verts] = rotate_arm_matrix(rest_verts, r_arm_verts, sh_r, angle, is_left=False)

        # Apply to mesh
        for idx, v in enumerate(mesh.vertices):
            v.co = deformed[idx]
        mesh.update()
        bpy.context.view_layer.update()

        # 1. Front view
        cam.location = mathutils.Vector((0.0, -2.3, 0.95))
        dir_v = mathutils.Vector((0.0, 0.0, 0.95)) - cam.location
        cam.rotation_euler = dir_v.to_track_quat('-Z', 'Y').to_euler()

        out_path = os.path.join(artifact_dir, filename_front)
        scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {filename_front}")

        # 2. 3/4 Perspective view
        cam.location = mathutils.Vector((-1.6, -1.8, 1.15))
        dir_3q = mathutils.Vector((0.0, 0.0, 0.95)) - cam.location
        cam.rotation_euler = dir_3q.to_track_quat('-Z', 'Y').to_euler()

        out_path_3q = os.path.join(artifact_dir, filename_3q)
        scene.render.filepath = out_path_3q
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {filename_3q}")

    # Restore Rest Pose on mesh
    for idx, v in enumerate(mesh.vertices):
        v.co = rest_verts[idx]
    mesh.update()
    bpy.context.view_layer.update()

    # Restore visibility
    for o in bpy.data.objects:
        o.hide_render = False
        o.hide_viewport = False

render_female_poses_clean()
