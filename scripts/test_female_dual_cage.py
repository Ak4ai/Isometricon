import numpy as np
import os
from src.clothing.wear_engine import (
    RobloxWearEngine,
    load_r15_female_cages,
    closest_point_on_triangle,
    SpatialGrid3D,
    smoothstep
)

print("=== INICIANDO TESTE DO SISTEMA DUAL-CAGE PADRÃO ROBLOX ===")

engine = RobloxWearEngine(body_type='female')
meta = engine.fetch_asset(9240757332)
verts, faces, uvs, face_uvs = engine.load_obj(meta['obj_path'])
sleeve_idx, torso_idx = engine.analyze_topology(verts, faces)

y_min_orig = float(np.min(verts[:, 1]))
y_max_orig = float(np.max(verts[:, 1]))
total_y_span = y_max_orig - y_min_orig
uniform_scale = 0.54 * (1.80 / total_y_span if total_y_span > 2.0 else 1.0)
target_shoulder_z = 1.475
sh_mask = (np.abs(verts[:, 0]) >= 0.35) & (np.abs(verts[:, 0]) <= 0.75) & (verts[:, 1] > 0)
shoulder_y = float(np.max(verts[sh_mask, 1])) if np.any(sh_mask) else y_max_orig
loc_z = target_shoulder_z - shoulder_y * uniform_scale
loc_y = -0.051  # Centro de profundidade da cage feminina

# Ajuste suave da profundidade das mangas no A-pose
adj_verts = verts.copy()
if sleeve_idx:
    s_list = list(sleeve_idx)
    raw_sleeve_z_mean = float(np.mean(adj_verts[s_list, 2]))
    s_xs = np.abs(adj_verts[s_list, 0])
    min_sx = float(np.min(s_xs))
    max_sx = float(np.max(s_xs))
    trans_len = max_sx - min_sx + 1e-8
    for idx in s_list:
        t = max(0.0, min(1.0, (abs(adj_verts[idx, 0]) - min_sx) / trans_len))
        w = t * t * (3.0 - 2.0 * t)
        adj_verts[idx, 2] -= raw_sleeve_z_mean * w

apose_verts = np.zeros_like(adj_verts)
apose_verts[:, 0] = -adj_verts[:, 0] * uniform_scale
apose_verts[:, 1] = adj_verts[:, 2] * uniform_scale + loc_y
apose_verts[:, 2] = adj_verts[:, 1] * uniform_scale + loc_z

# Carrega Cages
cages = load_r15_female_cages('assets/models/clothing/female_cages.obj')
src_roblox = load_r15_female_cages('assets/models/clothing/roblox_source_cages.obj')

def get_R(v1, v2):
    v1 = v1 / np.linalg.norm(v1)
    v2 = v2 / np.linalg.norm(v2)
    axis = np.cross(v1, v2)
    axis_l = np.linalg.norm(axis)
    if axis_l < 1e-6: return np.eye(3, dtype=np.float32)
    axis /= axis_l
    angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]], dtype=np.float32)
    return np.eye(3, dtype=np.float32) + np.sin(angle)*K + (1.0 - np.cos(angle))*(K@K)

def build_part(name, side_sign=1.0):
    # Base do membro
    v_dst = cages[name]['verts'].copy()
    f_dst = cages[name]['faces'].copy()
    
    if side_sign < 0:
        # Espelha perfeitamente para o lado direito
        v_dst[:, 0] = -v_dst[:, 0]
        # Inverte enrolamento das faces para manter normais externas
        f_dst = f_dst[:, [0, 2, 1]]
        
    return v_dst, f_dst

# 1. Torso: UpperTorso e LowerTorso
v_ut_dst, f_ut_dst = build_part('UpperTorso')
v_lt_dst, f_lt_dst = build_part('LowerTorso')
v_ut_src = v_ut_dst.copy()
v_lt_src = v_lt_dst.copy()

# 2. Braços: R15 com rotação Rodrigues precisa para A-pose
def build_arm(side):
    sign = 1.0 if side == 'left' else -1.0
    prefix = 'Left'
    v_ua_dst, f_ua_dst = build_part(f'{prefix}UpperArm', side_sign=sign)
    v_la_dst, f_la_dst = build_part(f'{prefix}LowerArm', side_sign=sign)
    v_ha_dst, f_ha_dst = build_part(f'{prefix}Hand', side_sign=sign)
    
    dst_v = np.vstack([v_ua_dst, v_la_dst, v_ha_dst])
    dst_f = np.vstack([
        f_ua_dst,
        f_la_dst + len(v_ua_dst),
        f_ha_dst + len(v_ua_dst) + len(v_la_dst)
    ])
    
    # Pivôs anatômicos femininos
    s_rest = np.array([sign * 0.2041, -0.0100, 1.4763], dtype=np.float32)
    e_rest = np.array([sign * 0.2558,  0.0271, 1.1544], dtype=np.float32)
    w_rest = np.array([sign * 0.3859,  0.0212, 0.7980], dtype=np.float32)
    s_apose = np.array([sign * 0.2041, -0.0100, 1.4763], dtype=np.float32)
    e_apose = np.array([sign * 0.4038,  0.0260, 0.9847], dtype=np.float32)
    w_apose = np.array([sign * 0.7323, -0.0382, 0.6128], dtype=np.float32)

    R_ua = get_R(e_rest - s_rest, e_apose - s_apose)
    R_fa = get_R(w_rest - e_rest, w_apose - e_apose)

    src_ua = ((v_ua_dst - s_rest) @ R_ua.T) + s_apose
    src_la = ((v_la_dst - e_rest) @ R_fa.T) + e_apose
    src_ha = ((v_ha_dst - e_rest) @ R_fa.T) + e_apose

    src_v = np.vstack([src_ua, src_la, src_ha])
    return src_v, dst_v, dst_f

src_arm_l, dst_arm_l, f_arm_l = build_arm('left')
src_arm_r, dst_arm_r, f_arm_r = build_arm('right')

# Monta o cage superior completo integrado (Torso + Braços L e R)
# Para evitar descontinuidades na costura, cada parte tem sua deformação por região baricêntrica
grid_arm_l = SpatialGrid3D(cell_size=0.08)
grid_arm_l.build((src_arm_l[f_arm_l[:, 0]] + src_arm_l[f_arm_l[:, 1]] + src_arm_l[f_arm_l[:, 2]]) / 3.0)

grid_arm_r = SpatialGrid3D(cell_size=0.08)
grid_arm_r.build((src_arm_r[f_arm_r[:, 0]] + src_arm_r[f_arm_r[:, 1]] + src_arm_r[f_arm_r[:, 2]]) / 3.0)

# Torso integrado (UpperTorso + LowerTorso)
v_torso_src = np.vstack([v_ut_src, v_lt_src])
v_torso_dst = np.vstack([v_ut_dst, v_lt_dst])
f_torso = np.vstack([f_ut_dst, f_lt_dst + len(v_ut_dst)])

grid_torso = SpatialGrid3D(cell_size=0.08)
grid_torso.build((v_torso_src[f_torso[:, 0]] + v_torso_src[f_torso[:, 1]] + v_torso_src[f_torso[:, 2]]) / 3.0)

def deform_barycentric(p, src_v, dst_v, faces, grid, is_arm=False):
    cands = grid.query_nearest_candidates(p, 2) or range(len(faces))
    best_d = float('inf')
    best_t = 0
    best_u, best_v, best_w = 1.0, 0.0, 0.0
    best_offset = np.zeros(3)
    for t in cands:
        a, b, c = src_v[faces[t, 0]], src_v[faces[t, 1]], src_v[faces[t, 2]]
        q, u, v, w = closest_point_on_triangle(p, a, b, c)
        d = float(np.linalg.norm(p - q))
        if d < best_d:
            best_d = d; best_t = t; best_u, best_v, best_w = u, v, w
            best_offset = p - q
            
    ta, tb, tc = dst_v[faces[best_t, 0]], dst_v[faces[best_t, 1]], dst_v[faces[best_t, 2]]
    su = src_v[faces[best_t, 1]] - src_v[faces[best_t, 0]]; su /= (np.linalg.norm(su) + 1e-8)
    sn = np.cross(su, src_v[faces[best_t, 2]] - src_v[faces[best_t, 0]]); sn /= (np.linalg.norm(sn) + 1e-8)
    sv = np.cross(sn, su)
    
    du = tb - ta; du /= (np.linalg.norm(du) + 1e-8)
    dn = np.cross(du, tc - ta); dn /= (np.linalg.norm(dn) + 1e-8)
    dv = np.cross(dn, du)
    
    p_t = best_u * ta + best_v * tb + best_w * tc
    R = np.column_stack([du, dv, dn]) @ np.column_stack([su, sv, sn]).T
    rot_offset = R @ best_offset
    n_dist = float(np.dot(rot_offset, dn))
    tan_vec = rot_offset - n_dist * dn
    
    # Puffiness padrão Roblox: garante que o tecido flutua para fora da pele
    min_puff = (0.028 if p_t[2] > 1.38 else 0.018) if is_arm else 0.012
    d_n = max(n_dist, min_puff)
        
    return p_t + d_n * dn + tan_vec

# Deformação com blend suave contínuo na costura ombro/torso
sh_start = 0.13
sh_end = 0.20

deformed = np.zeros_like(apose_verts)
for i in range(len(apose_verts)):
    p = apose_verts[i]
    ax = abs(p[0])
    
    # Ponto deformado pelo braço correspondente
    if p[0] > 0:
        p_arm = deform_barycentric(p, src_arm_l, dst_arm_l, f_arm_l, grid_arm_l, is_arm=True)
    else:
        p_arm = deform_barycentric(p, src_arm_r, dst_arm_r, f_arm_r, grid_arm_r, is_arm=True)
        
    # Ponto deformado pelo torso
    p_torso = deform_barycentric(p, v_torso_src, v_torso_dst, f_torso, grid_torso, is_arm=False)
    
    if i in sleeve_idx:
        if ax > sh_end:
            deformed[i] = p_arm
        else:
            w = smoothstep(sh_start, sh_end, ax)
            deformed[i] = (1.0 - w) * p_torso + w * p_arm
    else:
        if ax > sh_start and p[2] > 1.15:
            w = smoothstep(sh_start, sh_end, ax) * 0.90
            deformed[i] = (1.0 - w) * p_torso + w * p_arm
        else:
            deformed[i] = p_torso

# Relaxamento Laplaciano suave na costura
adj = {}
for face in faces:
    for fi in range(len(face)):
        i0, i1 = face[fi], face[(fi + 1) % len(face)]
        adj.setdefault(i0, set()).add(i1)
        adj.setdefault(i1, set()).add(i0)

seam_ring = {i for i in range(len(apose_verts)) if sh_start <= abs(apose_verts[i, 0]) <= sh_end and apose_verts[i, 2] > 1.12}
disp = deformed - apose_verts
smoothed_disp = disp.copy()
for _ in range(8):
    new_disp = smoothed_disp.copy()
    for s_i in seam_ring:
        nbrs = list(adj.get(s_i, []))
        if nbrs:
            new_disp[s_i] = 0.60 * smoothed_disp[s_i] + 0.40 * np.mean(smoothed_disp[nbrs], axis=0)
    smoothed_disp = new_disp

res_verts = apose_verts + smoothed_disp

# Recálculo suave de normais
vn = np.zeros_like(res_verts)
for f in faces:
    if len(f) >= 3:
        p0, p1, p2 = res_verts[f[0]], res_verts[f[1]], res_verts[f[2]]
        fn = np.cross(p1 - p0, p2 - p0)
        for idx in f:
            vn[idx] += fn
vn_len = np.linalg.norm(vn, axis=1, keepdims=True)
vn_len[vn_len < 1e-8] = 1.0
vn /= vn_len

out_obj = 'assets/models/character_native_9240757332_female.obj'
with open(out_obj, 'w', encoding='utf-8') as f:
    f.write('# Isometricon Universal Fitted Clothing v3: 9240757332\n')
    for v in res_verts:
        f.write(f'v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n')
    for n in vn:
        f.write(f'vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n')
    for uv in uvs:
        f.write(f'vt {uv[0]:.6f} {uv[1]:.6f}\n')
    for i, face in enumerate(faces):
        if len(face_uvs) > i:
            f.write('f ' + ' '.join(f'{face[j]+1}/{face_uvs[i][j]+1}/{face[j]+1}' for j in range(len(face))) + '\n')
        else:
            f.write('f ' + ' '.join(f'{idx+1}//{idx+1}' for idx in face) + '\n')

print("SUCESSO: Malha deformada com Dual-Cage e Puffiness gerada com sucesso!")
