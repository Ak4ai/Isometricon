import bpy
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils import Vector

def run_test():
    src_obj = bpy.data.objects.get('Roblox_Inner_Cage_Universal')
    dst_obj = bpy.data.objects.get('Roblox_Female_Cage_Universal')

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

    # Map DST vertices to regions
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

    # Build a BVHTree for each region in DST
    region_bvhs = {}
    for rname in region_map.keys():
        r_faces = []
        for f in dst_bm.faces:
            if any(dst_vert_regions[v.index] == rname for v in f.verts):
                r_faces.append(f)
        
        if r_faces:
            verts_coords = [v.co for v in dst_bm.verts]
            poly_indices = [[v.index for v in f.verts] for f in r_faces]
            bvh = BVHTree.FromPolygons(verts_coords, poly_indices)
            region_bvhs[rname] = bvh
            print(f'Region {rname}: {len(r_faces)} faces in BVH')

    # Map SRC vertices to regions
    src_bm = bmesh.new()
    src_bm.from_mesh(src_obj.data)
    src_bm.verts.ensure_lookup_table()
    src_dvert_lay = src_bm.verts.layers.deform.verify()

    src_vert_regions = {}
    for v in src_bm.verts:
        dvert = v[src_dvert_lay]
        if dvert:
            best_vg_idx = max(dvert.items(), key=lambda item: item[1])[0]
            best_vg_name = src_obj.vertex_groups[best_vg_idx].name
            src_vert_regions[v.index] = vg_to_region.get(best_vg_name, 'torso_pelvis')
        else:
            src_vert_regions[v.index] = 'torso_pelvis'

    # Project each vertex in SRC onto its region BVHTree
    conformed_verts = []
    for v in src_bm.verts:
        rname = src_vert_regions[v.index]
        bvh = region_bvhs.get(rname)
        if bvh:
            loc, norm, idx, dist = bvh.find_nearest(v.co)
            if loc is not None:
                conformed_verts.append(loc)
            else:
                conformed_verts.append(v.co)
        else:
            conformed_verts.append(v.co)

    print(f'Successfully conformed {len(conformed_verts)} vertices!')
    c_arr = np.array(conformed_verts)
    chest = c_arr[(c_arr[:, 2] > 1.15) & (c_arr[:, 2] < 1.40) & (np.abs(c_arr[:, 0]) < 0.05)]
    print(f'Conformed chest Y min/max: {chest[:, 1].min():.4f} {chest[:, 1].max():.4f}')
    pelvis = c_arr[(c_arr[:, 2] > 0.75) & (c_arr[:, 2] < 0.90) & (np.abs(c_arr[:, 0]) < 0.25)]
    print(f'Conformed pelvis X span: {pelvis[:, 0].max() - pelvis[:, 0].min():.4f} Y min/max: {pelvis[:, 1].min():.4f} {pelvis[:, 1].max():.4f}')
    thigh_l = c_arr[(c_arr[:, 2] > 0.50) & (c_arr[:, 2] < 0.70) & (c_arr[:, 0] > 0.02)]
    print(f'Conformed Left Thigh X mean: {thigh_l[:, 0].mean():.4f} min/max: {thigh_l[:, 0].min():.4f} {thigh_l[:, 0].max():.4f}')

run_test()
