import numpy as np
import os
from src.clothing.wear_engine import load_r15_cages, closest_point_on_triangle, SpatialGrid3D

print("=== TESTANDO CANONICAL ROBLOX DUAL CAGE WRAPDEFORMER ===")

# 1. Carrega Source Cages (roblox_source_cages.obj) e Target Cages (female_cages.obj)
src_cages = load_r15_cages('assets/models/clothing/roblox_source_cages.obj')
fem_cages = load_r15_cages('assets/models/clothing/female_cages_apose.obj')

# 2. Carrega a malha original do suéter
raw_sw = []
faces_sw = []
uvs_sw = []
face_uvs_sw = []
with open('assets/models/clothing/Knit_Sweater_-_Black_9240757332.obj', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('v '):
            raw_sw.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('vt '):
            uvs_sw.append([float(x) for x in line.split()[1:3]])
        elif line.startswith('f '):
            toks = line.split()[1:]
            faces_sw.append([int(t.split('/')[0]) - 1 for t in toks])
            if len(toks[0].split('/')) > 1 and toks[0].split('/')[1]:
                face_uvs_sw.append([int(t.split('/')[1]) - 1 for t in toks])

raw_sw = np.array(raw_sw, dtype=np.float64)

# Converte o suéter para o espaço de coordenadas das cages no motor:
# Em roblox_source_cages após load_r15_cages:
# X = X_obj, Y_engine = -Z_obj (profundidade), Z_engine = Y_obj (altura)
# No suéter original:
# X_obj é invertido (-X_obj é Left), Z_obj é invertido (-Z_obj é frente), Y_obj é altura com shift
sw_src = np.zeros_like(raw_sw)
sw_src[:, 0] = -raw_sw[:, 0]
sw_src[:, 1] = raw_sw[:, 2]        # profundidade: -Z_raw -> Y_engine
sw_src[:, 2] = raw_sw[:, 1] + 0.58 # altura: Y_raw + 0.58 -> Z_engine

print(f"[*] Suéter carregado: {len(sw_src)} vértices, {len(faces_sw)} faces.")
print(f"    X = [{sw_src[:,0].min():.2f}, {sw_src[:,0].max():.2f}]")
print(f"    Y = [{sw_src[:,1].min():.2f}, {sw_src[:,1].max():.2f}] (profundidade)")
print(f"    Z = [{sw_src[:,2].min():.2f}, {sw_src[:,2].max():.2f}] (altura)")

# 3. Calcula normais por vértice da roupa para garantir projeção com alinhamento de normais
vn_sw = np.zeros_like(sw_src)
for f in faces_sw:
    p0, p1, p2 = sw_src[f[0]], sw_src[f[1]], sw_src[f[2]]
    fn = np.cross(p1 - p0, p2 - p0)
    for idx in f:
        vn_sw[idx] += fn
vn_len = np.linalg.norm(vn_sw, axis=1, keepdims=True)
vn_len[vn_len < 1e-8] = 1.0
vn_sw /= vn_len

# 4. Configura as partes R15 do tronco e membros superiores
PART_NAMES = ['UpperTorso', 'LowerTorso', 'LeftUpperArm', 'RightUpperArm', 'LeftForearm', 'RightForearm']

# Pré-computa aceleradores e normais para cada parte na source cage
part_data = {}
for name in PART_NAMES:
    s_v = src_cages[name]['verts']
    s_f = src_cages[name]['faces']
    f_v = fem_cages[name]['verts']
    f_f = fem_cages[name]['faces']
    
    # Triângulos e centróides na source cage
    tri_a = s_v[s_f[:, 0]]
    tri_b = s_v[s_f[:, 1]]
    tri_c = s_v[s_f[:, 2]]
    centroids = (tri_a + tri_b + tri_c) / 3.0
    
    # Normais dos triângulos da source cage
    s_norms = np.cross(tri_b - tri_a, tri_c - tri_a)
    s_norms_len = np.linalg.norm(s_norms, axis=1, keepdims=True)
    s_norms_len[s_norms_len < 1e-8] = 1.0
    s_norms /= s_norms_len
    
    grid = SpatialGrid3D(cell_size=0.15)
    grid.build(centroids)
    
    part_data[name] = {
        's_v': s_v, 's_f': s_f,
        'f_v': f_v, 'f_f': f_f,
        's_norms': s_norms,
        'grid': grid
    }

print("[*] Aceleradores de todas as partes configurados.")

def project_to_part(p, p_norm, name):
    d = part_data[name]
    s_v = d['s_v']
    s_f = d['s_f']
    s_norms = d['s_norms']
    f_v = d['f_v']
    f_f = d['f_f']
    grid = d['grid']
    
    cands = grid.query_nearest_candidates(p, 2) or range(len(s_f))
    best_score = float('inf')
    best_t = 0
    best_u, best_v, best_w = 1.0, 0.0, 0.0
    best_q = p
    best_dist = float('inf')
    
    for t in cands:
        a, b, c = s_v[s_f[t, 0]], s_v[s_f[t, 1]], s_v[s_f[t, 2]]
        q, u, v, w = closest_point_on_triangle(p, a, b, c)
        dist = float(np.linalg.norm(p - q))
        
        # Penalidade suave de desalinhamento de normal
        dot = float(np.dot(p_norm, s_norms[t]))
        penalty = (1.0 - dot) * 0.06
        score = dist + penalty
        
        if score < best_score:
            best_score = score
            best_dist = dist
            best_t = t
            best_u, best_v, best_w = u, v, w
            best_q = q
            
    # Avalia na destination cage
    ta = f_v[f_f[best_t, 0]]
    tb = f_v[f_f[best_t, 1]]
    tc = f_v[f_f[best_t, 2]]
    p_dst = best_u * ta + best_v * tb + best_w * tc
    
    # Normal do triângulo de destino
    dn = np.cross(tb - ta, tc - ta)
    dn_len = np.linalg.norm(dn)
    dn = dn / dn_len if dn_len > 1e-8 else np.array([0.0, 0.0, 1.0])
    
    # Normal do triângulo fonte
    sn = s_norms[best_t]
    
    # Offset ao longo da normal na source cage, escalado para metros (escala ~ 0.36)
    offset_src = p - best_q
    n_offset = float(np.dot(offset_src, sn)) * 0.36
    
    return p_dst, dn, best_dist, n_offset

# 5. Para cada vértice, determina a parte dominante e faz blend suave na costura ombro/tronco
deformed = np.zeros_like(sw_src)

for i in range(len(sw_src)):
    p = sw_src[i]
    p_norm = vn_sw[i]
    ax = abs(p[0])
    
    # Membros por lado
    side = 'Left' if p[0] > 0 else 'Right'
    arm_name = f'{side}UpperArm'
    forearm_name = f'{side}Forearm'
    
    # Regiões canônicas em coordenadas de source cage (studs):
    # Antebraço / Mão: ax > 0.85 e Z < 0.70
    if ax > 0.82 and p[2] < 0.75:
        p_dst, dn, dist, n_off = project_to_part(p, p_norm, forearm_name)
        min_puff = 0.016
        deformed[i] = p_dst + max(n_off, min_puff) * dn
    elif ax > 0.65:
        # Braço Superior
        p_dst, dn, dist, n_off = project_to_part(p, p_norm, arm_name)
        min_puff = 0.024 if p_dst[2] > 1.38 else 0.018
        deformed[i] = p_dst + max(n_off, min_puff) * dn
    elif ax < 0.40:
        # Tronco puro (UpperTorso ou LowerTorso dependendo da altura)
        torso_name = 'LowerTorso' if p[2] < 0.15 else 'UpperTorso'
        p_dst, dn, dist, n_off = project_to_part(p, p_norm, torso_name)
        min_puff = 0.012
        deformed[i] = p_dst + max(n_off, min_puff) * dn
    else:
        # Região de transição ombro/costura: ax entre 0.40 e 0.65 studs
        # Blend suave contínuo entre UpperTorso e UpperArm
        p_torso, dn_t, d_t, noff_t = project_to_part(p, p_norm, 'UpperTorso')
        p_arm, dn_a, d_a, noff_a = project_to_part(p, p_norm, arm_name)
        
        # Smoothstep de peso do braço entre 0.40 e 0.65
        t = (ax - 0.40) / 0.25
        w_arm = t * t * (3.0 - 2.0 * t)
        
        puff_t = max(noff_t, 0.014)
        puff_a = max(noff_a, 0.026 if p_arm[2] > 1.38 else 0.018)
        
        res_t = p_torso + puff_t * dn_t
        res_a = p_arm + puff_a * dn_a
        deformed[i] = (1.0 - w_arm) * res_t + w_arm * res_a

# 6. Relaxamento Laplaciano na costura do ombro
adj = {}
for face in faces_sw:
    for fi in range(len(face)):
        i0, i1 = face[fi], face[(fi + 1) % len(face)]
        adj.setdefault(i0, set()).add(i1)
        adj.setdefault(i1, set()).add(i0)

seam_ring = {i for i in range(len(sw_src)) if 0.40 <= abs(sw_src[i, 0]) <= 0.65 and sw_src[i, 2] > 0.80}
disp = deformed - deformed.mean(axis=0)  # displacement relative
smoothed = deformed.copy()
for _ in range(6):
    new_s = smoothed.copy()
    for s_i in seam_ring:
        nbrs = list(adj.get(s_i, []))
        if nbrs:
            new_s[s_i] = 0.65 * smoothed[s_i] + 0.35 * np.mean(smoothed[nbrs], axis=0)
    smoothed = new_s
deformed = smoothed

# 7. Recálculo suave de normais
vn_out = np.zeros_like(deformed)
for f in faces_sw:
    if len(f) >= 3:
        p0, p1, p2 = deformed[f[0]], deformed[f[1]], deformed[f[2]]
        fn = np.cross(p1 - p0, p2 - p0)
        for idx in f:
            vn_out[idx] += fn
vn_len = np.linalg.norm(vn_out, axis=1, keepdims=True)
vn_len[vn_len < 1e-8] = 1.0
vn_out /= vn_len

# 8. Exporta OBJ de teste
out_obj = 'assets/models/character_native_9240757332_female.obj'
with open(out_obj, 'w', encoding='utf-8') as f:
    f.write('# Isometricon Universal Fitted Clothing v3: 9240757332\n')
    for v in deformed:
        f.write(f'v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n')
    for n in vn_out:
        f.write(f'vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n')
    for uv in uvs_sw:
        f.write(f'vt {uv[0]:.6f} {uv[1]:.6f}\n')
    for i, face in enumerate(faces_sw):
        if len(face_uvs_sw) > i:
            f.write('f ' + ' '.join(f'{face[j]+1}/{face_uvs_sw[i][j]+1}/{face[j]+1}' for j in range(len(face))) + '\n')
        else:
            f.write('f ' + ' '.join(f'{idx+1}//{idx+1}' for idx in face) + '\n')

print(f"[SUCESSO] Malha gerada pelo Canonical Dual Cage salva em: {out_obj}")
