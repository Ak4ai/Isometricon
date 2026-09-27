python -c "
# Test female shoulder blend zone: ax in [0.12, 0.20] instead of [0.18, 0.28]
import numpy as np
from src.clothing.wear_engine import RobloxWearEngine, smoothstep

engine = RobloxWearEngine(body_type='female')
meta = engine.fetch_asset(9240757332)
verts, faces, uvs, face_uvs = engine.load_obj(meta['obj_path'])
sleeve_idx, torso_idx = engine.analyze_topology(verts, faces)
apose_verts, cuff_z, is_sleeveless, is_short, is_long = engine.fit_top_clothing(
    verts, faces, sleeve_idx, torso_idx, is_jacket=False, is_dress=False
)

# Custom test with female-tuned shoulder transition
sh_start = 0.13 if engine.is_female else 0.18
sh_end   = 0.22 if engine.is_female else 0.28

# Let us run the dual cage deformation with this shoulder transition:
tri_a = engine.cage_verts_apose[engine.cage_faces[:, 0]]
tri_b = engine.cage_verts_apose[engine.cage_faces[:, 1]]
tri_c = engine.cage_verts_apose[engine.cage_faces[:, 2]]
dst_a = engine.cage_verts_rest[engine.cage_faces[:, 0]]
dst_b = engine.cage_verts_rest[engine.cage_faces[:, 1]]
dst_c = engine.cage_verts_rest[engine.cage_faces[:, 2]]

from src.clothing.wear_engine import closest_point_on_triangle

def def_pt(p, grid, subset_idx, is_sleeve=False):
    cands = grid.query_nearest_candidates(p, 1) or grid.query_nearest_candidates(p, 2) or range(len(subset_idx))
    best_d = float('inf')
    best_t = subset_idx[0]
    best_u, best_v, best_w = 1.0, 0.0, 0.0
    best_offset = np.zeros(3)
    for l_idx in cands:
        t = subset_idx[l_idx]
        a, b, c = tri_a[t], tri_b[t], tri_c[t]
        q, u, v, w = closest_point_on_triangle(p, a, b, c)
        d = float(np.linalg.norm(p - q))
        if d < best_d:
            best_d = d; best_t = t; best_u, best_v, best_w = u, v, w
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
    p_t = best_u * ta + best_v * tb + best_w * tc
    R = np.column_stack([dst_u, dst_v, dst_norm]) @ np.column_stack([src_u, src_v, src_norm]).T
    rot_offset = R @ best_offset
    n_dist = float(np.dot(rot_offset, dst_norm))
    tan_vec = rot_offset - n_dist * dst_norm
    d_n = max(n_dist, 0.008)
    return p_t + d_n * dst_norm + tan_vec

deformed = apose_verts.copy()
for i in range(len(apose_verts)):
    p = apose_verts[i]
    ax = abs(p[0])
    if i in sleeve_idx:
        grid_arm = engine.grid_apose_g1 if p[0] > 0 else engine.grid_apose_g2
        tris_arm = engine.g1_tris if p[0] > 0 else engine.g2_tris
        if ax > sh_end:
            deformed[i] = def_pt(p, grid_arm, tris_arm, is_sleeve=True)
        else:
            w = smoothstep(sh_start, sh_end, ax)
            p_t = def_pt(p, engine.grid_apose_g0, engine.g0_tris, is_sleeve=False)
            p_a = def_pt(p, grid_arm, tris_arm, is_sleeve=True)
            deformed[i] = (1.0 - w) * p_t + w * p_a
    else:
        if ax > sh_start and p[2] > 1.15:
            w = smoothstep(sh_start, sh_end, ax) * 0.85
            p_t = def_pt(p, engine.grid_apose_g0, engine.g0_tris, is_sleeve=False)
            grid_arm = engine.grid_apose_g1 if p[0] > 0 else engine.grid_apose_g2
            tris_arm = engine.g1_tris if p[0] > 0 else engine.g2_tris
            p_a = def_pt(p, grid_arm, tris_arm, is_sleeve=True)
            deformed[i] = (1.0 - w) * p_t + w * p_a
        else:
            deformed[i] = def_pt(p, engine.grid_apose_g0, engine.g0_tris, is_sleeve=False)

# Check piercing:
with open('assets/models/character_female_clean.obj') as f:
    ua_pts = []
    curr = None
    for line in f:
        if line.startswith('o ') or line.startswith('g '):
            curr = line.strip().split()[1]
        elif line.startswith('v ') and curr == 'Export_braco_superior_esquerdo':
            ua_pts.append([float(x) for x in line.strip().split()[1:4]])
ua_pts = np.array(ua_pts)

def_gl = np.column_stack([deformed[:, 0], deformed[:, 2], -deformed[:, 1]])
pierce_count = 0
for idx, bv in enumerate(ua_pts):
    dists = np.sqrt((def_gl[:, 0] - bv[0])**2 + (def_gl[:, 1] - bv[1])**2)
    near = np.where(dists < 0.04)[0]
    if len(near) > 0:
        max_d = def_gl[near, 2].max()
        pierce = bv[2] - max_d
        if pierce > 0:
            pierce_count += 1
            print(f'Body UA {idx} pierces by {pierce*1000:.1f} mm')
print(f'Total piercings with female-tuned shoulder: {pierce_count} / {len(ua_pts)}')
"