import os
import sys
import numpy as np

base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
sys.path.insert(0, base_dir)

from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle, SpatialGrid3D

def test_conform():
    male_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz"))
    fem_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz"))

    src_apose = male_data["cage_verts_apose"]
    dst_rest = fem_data["cage_verts_rest"]
    faces = male_data["cage_faces"]
    face_groups = fem_data["cage_face_groups"]

    print(f"SRC Apose: {src_apose.shape}, DST Rest: {dst_rest.shape}, Faces: {faces.shape}")

    # Test top deformation on sweater or shirt
    engine = RobloxWearEngine(body_type="male") # use base methods
    shirt_obj = os.path.join(base_dir, "assets", "models", "clothing", "-_office_shirt__BLACK_133331049150205.obj")
    if not os.path.exists(shirt_obj):
        print(f"Shirt obj not found: {shirt_obj}")
        return

    verts, sh_faces, uvs, face_uvs = engine.load_obj(shirt_obj)
    sleeve_idx, torso_idx = engine.analyze_topology(verts, sh_faces)
    print(f"Loaded shirt: {len(verts)} verts. Sleeves: {len(sleeve_idx)}, Torso: {len(torso_idx)}")

    world_apose, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(verts, sh_faces, sleeve_idx, torso_idx)
    print(f"World Apose bounds: X [{world_apose[:,0].min():.3f}, {world_apose[:,0].max():.3f}], Y [{world_apose[:,1].min():.3f}, {world_apose[:,1].max():.3f}], Z [{world_apose[:,2].min():.3f}, {world_apose[:,2].max():.3f}]")

    # Deform using src_apose -> dst_rest
    g0_tris = np.where(face_groups == 0)[0]
    g1_tris = np.where(face_groups == 1)[0]
    g2_tris = np.where(face_groups == 2)[0]

    tri_a = src_apose[faces[:, 0]]
    tri_b = src_apose[faces[:, 1]]
    tri_c = src_apose[faces[:, 2]]
    dst_a = dst_rest[faces[:, 0]]
    dst_b = dst_rest[faces[:, 1]]
    dst_c = dst_rest[faces[:, 2]]

    grid_g0 = SpatialGrid3D(0.10)
    grid_g0.build((tri_a[g0_tris] + tri_b[g0_tris] + tri_c[g0_tris]) / 3.0)

    grid_g1 = SpatialGrid3D(0.10)
    grid_g1.build((tri_a[g1_tris] + tri_b[g1_tris] + tri_c[g1_tris]) / 3.0)

    grid_g2 = SpatialGrid3D(0.10)
    grid_g2.build((tri_a[g2_tris] + tri_b[g2_tris] + tri_c[g2_tris]) / 3.0)

    def deform_pt(p, grid, subset_idx):
        cands = grid.query_nearest_candidates(p, 1) or grid.query_nearest_candidates(p, 2) or range(len(subset_idx))
        best_d = float("inf")
        best_u, best_v, best_w = 1.0, 0.0, 0.0
        best_t = subset_idx[0]
        best_offset = np.zeros(3)

        for l_idx in cands:
            t = subset_idx[l_idx]
            a, b, c = tri_a[t], tri_b[t], tri_c[t]
            q, u, v, w = closest_point_on_triangle(p, a, b, c)
            d = float(np.linalg.norm(p - q))
            if d < best_d:
                best_d = d
                best_u, best_v, best_w = u, v, w
                best_t = t
                best_offset = p - q

        ta, tb, tc = dst_a[best_t], dst_b[best_t], dst_c[best_t]
        src_u = tri_b[best_t] - tri_a[best_t]
        src_u /= (np.linalg.norm(src_u) + 1e-8)
        src_norm = np.cross(src_u, tri_c[best_t] - tri_a[best_t])
        src_norm /= (np.linalg.norm(src_norm) + 1e-8)
        src_v = np.cross(src_norm, src_u)
        dst_u = tb - ta
        dst_u /= (np.linalg.norm(dst_u) + 1e-8)
        dst_norm = np.cross(dst_u, tc - ta)
        dst_norm /= (np.linalg.norm(dst_norm) + 1e-8)
        dst_v = np.cross(dst_norm, dst_u)
        R = np.column_stack([dst_u, dst_v, dst_norm]) @ np.column_stack([src_u, src_v, src_norm]).T
        p_t = best_u * ta + best_v * tb + best_w * tc
        return p_t + R @ best_offset

    deformed = np.zeros_like(world_apose)
    for i in sleeve_idx:
        p = world_apose[i]
        if p[0] > 0:
            deformed[i] = deform_pt(p, grid_g1, g1_tris)
        else:
            deformed[i] = deform_pt(p, grid_g2, g2_tris)

    for i in torso_idx:
        p = world_apose[i]
        deformed[i] = deform_pt(p, grid_g0, g0_tris)

    print("Deformed shirt successfully!")
    print(f"Deformed bounds: X [{deformed[:,0].min():.3f}, {deformed[:,0].max():.3f}], Y [{deformed[:,1].min():.3f}, {deformed[:,1].max():.3f}], Z [{deformed[:,2].min():.3f}, {deformed[:,2].max():.3f}]")

    # Check chest and waist profile
    chest = deformed[(deformed[:, 2] > 1.20) & (deformed[:, 2] < 1.35) & (np.abs(deformed[:, 0]) < 0.12)]
    print(f"Chest front Y min (most forward): {chest[:, 1].min():.4f}")
    waist = deformed[(deformed[:, 2] > 0.90) & (deformed[:, 2] < 1.05)]
    print(f"Waist X span: {waist[:, 0].max() - waist[:, 0].min():.4f}")

    # Export test OBJ
    test_out = os.path.join(base_dir, "assets", "models", "test_conformed_shirt.obj")
    with open(test_out, "w") as f:
        for v in deformed:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for vt in uvs:
            f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
        if len(face_uvs) == len(sh_faces):
            for fi in range(len(sh_faces)):
                fv = sh_faces[fi]
                ft = face_uvs[fi]
                f.write(f"f {fv[0]+1}/{ft[0]+1} {fv[1]+1}/{ft[1]+1} {fv[2]+1}/{ft[2]+1}\n")
        else:
            for fv in sh_faces:
                f.write(f"f {fv[0]+1} {fv[1]+1} {fv[2]+1}\n")
    print(f"Saved test conformed shirt to {test_out}")

test_conform()
