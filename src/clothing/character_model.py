"""Modelo e montagem do personagem 3D do Isometricon.

Carrega malhas modulares (cabeça arredondada/quadrada, cabelo 3D, roupas Roblox,
membros com cor de pele, texturas de rosto e atlas dinâmicos) para renderização
em tempo real com iluminação e controle de câmera.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

from src.clothing.customization import (
    AvatarCustomization,
    BodyType,
    EyebrowStyle,
    EyeStyle,
    FaceOption,
    HairColor,
    HairStyle,
    HeadAtlasBuilder,
    HeadType,
    IrisColor,
    MouthStyle,
)
from src.math import mat4_identity, mat4_rotate_y, mat4_scale, mat4_translate, vec3


# Diretórios padrão de assets
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(PROJECT_ROOT, "assets", "models")
CLOTHING_DIR = os.path.join(MODELS_DIR, "clothing")


def parse_clean_obj_groups(
    obj_path: str,
    allowed_prefixes: Optional[List[str]] = None,
    default_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    compute_smooth_normals: bool = True,
    vertex_transform: Optional[Any] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:

    """Carrega dados brutos de vértices e índices de um arquivo OBJ no padrão de coordenadas OpenGL.

    Layout por vértice:
        - Pos3 (x, y, z)
        - Normal3 (nx, ny, nz)
        - UV2 (u, 1.0 - v)
        - Color3 (r, g, b)
    Total: 11 floats (44 bytes).
    """
    if not os.path.exists(obj_path):
        return None

    raw_v: List[List[float]] = []
    raw_vt: List[List[float]] = []
    raw_vn: List[List[float]] = []
    faces: List[List[str]] = []

    current_o = None
    include_face = ("" in allowed_prefixes) if allowed_prefixes else True

    with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] in ("o", "g"):
                current_o = parts[1] if len(parts) > 1 else ""
                if allowed_prefixes is not None:
                    include_face = any(current_o.startswith(p) for p in allowed_prefixes)
                else:
                    include_face = True
            elif parts[0] == "v":
                raw_v.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "vt":
                raw_vt.append([float(parts[1]), float(parts[2])])
            elif parts[0] == "vn":
                raw_vn.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "f" and include_face:
                faces.append(parts[1:])

    if not raw_v or not faces:
        return None

    if vertex_transform is not None:
        raw_v = vertex_transform(raw_v)


    # Se normais ausentes e solicitado cálculo suave, acumula normais por vértice
    computed_vn: Dict[int, np.ndarray] = {}
    if not raw_vn and compute_smooth_normals:
        for face in faces:
            v_indices = []
            for token in face:
                sub = token.split("/")
                v_indices.append(int(sub[0]) - 1)
            for i in range(1, len(v_indices) - 1):
                i0, i1, i2 = v_indices[0], v_indices[i], v_indices[i + 1]
                p0 = np.array(raw_v[i0], dtype=np.float32)
                p1 = np.array(raw_v[i1], dtype=np.float32)
                p2 = np.array(raw_v[i2], dtype=np.float32)
                fn = np.cross(p1 - p0, p2 - p0)
                norm_len = float(np.linalg.norm(fn))
                if norm_len > 1e-7:
                    fn_norm = fn / norm_len
                    for idx in (i0, i1, i2):
                        if idx not in computed_vn:
                            computed_vn[idx] = fn_norm.copy()
                        else:
                            computed_vn[idx] += fn_norm

        for idx, n in computed_vn.items():
            l = float(np.linalg.norm(n))
            if l > 1e-7:
                computed_vn[idx] = n / l
            else:
                computed_vn[idx] = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    v_data: List[float] = []
    indices: List[int] = []
    vert_cache: Dict[str, int] = {}

    for face in faces:
        face_indices: List[int] = []
        for token in face:
            if token in vert_cache:
                face_indices.append(vert_cache[token])
                continue

            sub = token.split("/")
            v_idx = int(sub[0]) - 1
            vt_idx = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else -1
            vn_idx = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else -1

            bx, by, bz = raw_v[v_idx]
            pos = [bx, by, bz]

            if vn_idx >= 0 and vn_idx < len(raw_vn):
                norm = [raw_vn[vn_idx][0], raw_vn[vn_idx][1], raw_vn[vn_idx][2]]
            elif v_idx in computed_vn:
                norm = list(computed_vn[v_idx])
            else:
                norm = [0.0, 1.0, 0.0]

            if vt_idx >= 0 and vt_idx < len(raw_vt):
                uv = [raw_vt[vt_idx][0], 1.0 - raw_vt[vt_idx][1]]
            else:
                uv = [0.5, 0.5]

            idx = len(v_data) // 11
            v_data.extend(pos)
            v_data.extend(norm)
            v_data.extend(uv)
            v_data.extend(default_color)
            vert_cache[token] = idx
            face_indices.append(idx)

        for i in range(1, len(face_indices) - 1):
            indices.extend([face_indices[0], face_indices[i], face_indices[i + 1]])

    v_arr = np.array(v_data, dtype=np.float32)
    i_arr = np.array(indices, dtype=np.uint32)
    return v_arr, i_arr


def transform_sleeve_vertices(
    raw_v: List[List[float]],
    width_scale: float = 1.0,
    length_offset: float = 0.0,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
    shift_z: float = 0.0,
) -> List[List[float]]:
    """Aplica ajustes dinâmicos de largura, comprimento e deslocamento horizontal/vertical à ponta das mangas."""
    if (
        width_scale == 1.0
        and length_offset == 0.0
        and shift_x == 0.0
        and shift_y == 0.0
        and shift_z == 0.0
    ):
        return raw_v

    verts = [list(v) for v in raw_v]
    for side_mult in [1, -1]:
        s_idxs = [i for i, v in enumerate(verts) if (v[0] * side_mult) > 0.18 and v[2] < 1.45]
        if not s_idxs:
            continue

        s_zs = [verts[i][2] for i in s_idxs]
        z_min = float(min(s_zs))

        # Centro do anel da ponta da manga (cuff)
        cuff_pts = [verts[i] for i in s_idxs if verts[i][2] < z_min + 0.040]
        if not cuff_pts:
            cuff_pts = [verts[i] for i in s_idxs if verts[i][2] < z_min + 0.080]
        cx = float((min(p[0] for p in cuff_pts) + max(p[0] for p in cuff_pts)) / 2)
        cy = float((min(p[1] for p in cuff_pts) + max(p[1] for p in cuff_pts)) / 2)

        elbow_z = 1.15
        trans_len = 0.16

        for i in s_idxs:
            x, y, z = verts[i]
            # 1. Comprimento da manga (+ desce/alonga, - sobe/encurta)
            if length_offset != 0.0 and z < elbow_z:
                t = max(0.0, min(1.0, (elbow_z - z) / (elbow_z - z_min + 1e-8)))
                z = z - length_offset * t

            # 2. Deslocamento e largura da ponta da manga (suaviza em direção ao cotovelo)
            if z < z_min + trans_len:
                t = max(0.0, min(1.0, (z_min + trans_len - z) / trans_len))
                w = t * t * (3.0 - 2.0 * t)  # Hermite smoothstep

                dx = (shift_x * side_mult) * w
                dy = shift_y * w
                dz = shift_z * w

                curr_cx = cx + dx
                curr_cy = cy + dy

                x = x + dx
                y = y + dy
                z = z + dz

                # Largura da ponta em torno do centro deslocado
                if width_scale != 1.0:
                    scale = 1.0 + (width_scale - 1.0) * (t ** 1.2)
                    x = curr_cx + (x - curr_cx) * scale
                    y = curr_cy + (y - curr_cy) * scale

            verts[i] = [x, y, z]

    return verts


def conform_clothing_to_female_cage(raw_v: List[List[float]], is_bottom: bool = False) -> List[List[float]]:
    """Deprecado: A deformação agora é executada geometricamente de forma nativa pelo RobloxWearEngine."""
    return raw_v


def transform_hip_vertices(
    raw_v: List[List[float]],
    glute_scale: float = 1.0,
    width_scale: float = 1.0,
    waist_height_offset: float = 0.0,
) -> List[List[float]]:
    """Aumenta dinamicamente o relevo e projeção dos glúteos (bunda), largura do quadril e altura da cintura/cós."""
    if glute_scale == 1.0 and width_scale == 1.0 and waist_height_offset == 0.0:
        return raw_v

    verts = [list(v) for v in raw_v]
    if not verts:
        return verts

    # Detecta se os vértices estão em espaço nativo do motor (z=altura, y=profundidade)
    # ou em espaço clean/Blender (y=altura, z=profundidade)
    sample = verts[:min(100, len(verts))]
    max_z = max(v[2] for v in sample)
    max_y = max(v[1] for v in sample)
    is_native = max_z > max_y

    for i, (x, y, z) in enumerate(verts):
        h = z if is_native else y
        d = y if is_native else z

        # Faixa vertical da região do quadril/glúteos: altura entre 0.60m e 0.94m (pelve e topo das coxas)
        if 0.60 < h < 0.94:
            # Curva suave gaussiana em torno do centro anatômico dos glúteos (H ≈ 0.81m)
            tz = float(np.exp(-((h - 0.81) / 0.085) ** 2))

            # 1. Relevo na parte da bunda: exclusivamente posterior
            # - No espaço nativo: +Y é posterior (costas/bunda), -Y é anterior (barriga/frente)
            #   Incrementar Y expande os glúteos para trás (-Z em OpenGL).
            # - No espaço clean: -Z é posterior (costas/bunda), +Z é anterior (barriga/frente)
            #   Decrementar Z expande os glúteos para trás (-Z em OpenGL).
            if glute_scale != 1.0:
                if is_native and d > 0.01:
                    td = min(1.0, d / 0.05)
                    dy = (glute_scale - 1.0) * 0.055 * tz * td
                    y = y + dy
                elif not is_native and d < -0.01:
                    td = min(1.0, abs(d) / 0.05)
                    dz = - (glute_scale - 1.0) * 0.055 * tz * td
                    z = z + dz

            # 2. Largura lateral do quadril (se ajustada)
            if width_scale != 1.0:
                x = x * (1.0 + (width_scale - 1.0) * tz * 0.45)

        # 3. Ajuste de altura da cintura/cós (sobe / desce)
        if waist_height_offset != 0.0 and h > 0.72:
            t_w = max(0.0, min(1.0, (h - 0.72) / (0.98 - 0.72)))
            w_w = t_w * t_w * (3.0 - 2.0 * t_w)  # Hermite smoothstep
            dh = waist_height_offset * w_w
            if is_native:
                z = z + dh
            else:
                y = y + dh

            # Ajuste de largura e profundidade para acompanhar o declive do tronco (taper)
            taper_factor = 1.0 - (0.70 * waist_height_offset * w_w)
            x = x * taper_factor
            if is_native:
                y = y * taper_factor
            else:
                z = z * taper_factor

        verts[i] = [x, y, z]

    return verts


def transform_top_hem_vertices(
    raw_v: List[List[float]],
    hem_offset: float = 0.0,
    effective_waist_z: Optional[float] = None,
    is_female: bool = True,
) -> List[List[float]]:
    """Aplica ajustes na altura da barra da blusa/camisa (sobe/desce/cropped) e encaixa sob o cos alto se sobreposto."""
    if hem_offset == 0.0 and effective_waist_z is None:
        return raw_v

    verts = [list(v) for v in raw_v]
    if not verts:
        return verts

    sample = verts[:min(100, len(verts))]
    max_z = max(v[2] for v in sample)
    max_y = max(v[1] for v in sample)
    is_native = max_z > max_y

    z_anchor = 1.25
    z_min_nominal = 0.985 if is_female else 0.890

    for i, (x, y, z) in enumerate(verts):
        h = z if is_native else y

        # Aplica exclusivamente aos vertices do tronco da blusa (|x| <= 0.32 e abaixo do busto h < 1.30)
        if abs(x) <= 0.32 and h < 1.30:
            # 1. Deslocamento da barra da blusa (sobe / desce / cropped)
            if hem_offset != 0.0 and h < z_anchor:
                t = max(0.0, min(1.0, (z_anchor - h) / (z_anchor - z_min_nominal + 1e-8)))
                w = t * t * (3.0 - 2.0 * t)  # Hermite smoothstep
                dh = hem_offset * w
                if is_native:
                    z = z + dh
                else:
                    y = y + dh

                # Afunilamento no declive da cintura conforme a barra sobe
                taper = 1.0 - (0.45 * hem_offset * w)
                x = x * taper
                if is_native:
                    y = y * taper
                else:
                    z = z * taper

            # 2. Se a calca estiver com cintura alta e ultrapassar a barra da camisa:
            # Encaixa o tecido suavemente para dentro do cos da calca evitando colisao e z-fighting
            if effective_waist_z is not None and h < effective_waist_z:
                t_tuck = max(0.0, min(1.0, (effective_waist_z - h) / 0.05))
                w_tuck = t_tuck * t_tuck * (3.0 - 2.0 * t_tuck)
                scale = 1.0 - 0.08 * w_tuck
                x = x * scale
                if is_native:
                    y = y * scale
                else:
                    z = z * scale

        verts[i] = [x, y, z]

    return verts


def slice_mesh_between_y(
    verts_11: np.ndarray,
    faces_3: np.ndarray,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    waist_tilt_z: float = 0.0,
    tuck_bottom: bool = True,
    tuck_top: bool = True,
    cap_ends: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """Recorta uma malha geometricamente entre o plano do cós (y_min com inclinação pélvica opcional) e a barra da camisa (y_max).

    Fatia triângulos que cruzam os limites planos, calcula as interseções exatas com interpolação
    de normais, UVs e cores de vértice, descarta toda a geometria fora dos limites e gera tampas herméticas.
    Opcionalmente afunila levemente (tuck) as bordas recortadas para eliminar z-fighting com o cós da calça.
    """
    if len(faces_3) == 0 or len(verts_11) == 0:
        return np.empty((0, 11), dtype=np.float32), np.empty((0, 3), dtype=np.uint32)

    v_list = [v.copy() for v in verts_11]
    f_list = [list(f) for f in faces_3]
    bot_segments = []

    # 1. Corte inferior: descarta tudo abaixo do cós (Y + waist_tilt_z * Z >= y_min)
    if y_min is not None:
        def dist_bot(v):
            if waist_tilt_z != 0.0:
                return (v[1] + waist_tilt_z * v[2]) - y_min
            return v[1] - y_min

        kept_faces = []
        for tri in f_list:
            dists = [dist_bot(v_list[idx]) for idx in tri]
            above = [d >= 0.0 for d in dists]
            num_above = sum(above)

            if num_above == 3:
                kept_faces.append(tri)
            elif num_above == 0:
                continue
            elif num_above == 1:
                idx_above = above.index(True)
                i_top = tri[idx_above]
                i_b1 = tri[(idx_above + 1) % 3]
                i_b2 = tri[(idx_above + 2) % 3]

                v_top = v_list[i_top]
                v_b1 = v_list[i_b1]
                v_b2 = v_list[i_b2]

                d_top = dists[idx_above]
                d_b1 = dists[(idx_above + 1) % 3]
                d_b2 = dists[(idx_above + 2) % 3]

                t1 = -d_b1 / (d_top - d_b1 + 1e-9)
                t2 = -d_b2 / (d_top - d_b2 + 1e-9)
                int1 = v_b1 + t1 * (v_top - v_b1)
                int2 = v_b2 + t2 * (v_top - v_b2)

                idx_int1 = len(v_list)
                v_list.append(int1)
                idx_int2 = len(v_list)
                v_list.append(int2)

                kept_faces.append([i_top, idx_int1, idx_int2])
                bot_segments.append([idx_int1, idx_int2])
            elif num_above == 2:
                idx_below = above.index(False)
                i_b = tri[idx_below]
                i_a1 = tri[(idx_below + 1) % 3]
                i_a2 = tri[(idx_below + 2) % 3]

                v_b = v_list[i_b]
                v_a1 = v_list[i_a1]
                v_a2 = v_list[i_a2]

                d_b = dists[idx_below]
                d_a1 = dists[(idx_below + 1) % 3]
                d_a2 = dists[(idx_below + 2) % 3]

                t1 = -d_b / (d_a1 - d_b + 1e-9)
                t2 = -d_b / (d_a2 - d_b + 1e-9)
                int1 = v_b + t1 * (v_a1 - v_b)
                int2 = v_b + t2 * (v_a2 - v_b)

                idx_int1 = len(v_list)
                v_list.append(int1)
                idx_int2 = len(v_list)
                v_list.append(int2)

                kept_faces.append([i_a1, i_a2, idx_int1])
                kept_faces.append([i_a2, idx_int2, idx_int1])
                bot_segments.append([idx_int2, idx_int1])

        # Tampa inferior hermética (Opção 2A: fecha o corte na cintura com sólido preenchido)
        if cap_ends and bot_segments:
            bot_pts = np.array([v_list[s[0]][:3] for s in bot_segments], dtype=np.float32)
            c_pos = bot_pts.mean(axis=0)
            n_down = np.array([0.0, -1.0, -waist_tilt_z], dtype=np.float32)
            n_down /= (np.linalg.norm(n_down) + 1e-8)
            c_vert = v_list[bot_segments[0][0]].copy()
            c_vert[:3] = c_pos
            c_vert[3:6] = n_down
            idx_c = len(v_list)
            v_list.append(c_vert)
            for s0, s1 in bot_segments:
                u = v_list[s0][:3] - c_pos
                w = v_list[s1][:3] - c_pos
                fn = np.cross(u, w)
                if np.dot(fn, n_down) > 0:
                    kept_faces.append([idx_c, s0, s1])
                else:
                    kept_faces.append([idx_c, s1, s0])

        f_list = kept_faces

    # 2. Corte superior: descarta tudo acima de y_max (mantém y <= y_max)
    if y_max is not None:
        kept_faces = []
        top_segments = []
        for tri in f_list:
            v_pts = [v_list[idx] for idx in tri]
            below = [v[1] <= y_max for v in v_pts]
            num_below = sum(below)

            if num_below == 3:
                kept_faces.append(tri)
            elif num_below == 0:
                continue
            elif num_below == 1:
                idx_below = below.index(True)
                i_bot = tri[idx_below]
                i_a1 = tri[(idx_below + 1) % 3]
                i_a2 = tri[(idx_below + 2) % 3]

                v_bot = v_list[i_bot]
                v_a1 = v_list[i_a1]
                v_a2 = v_list[i_a2]

                t1 = (y_max - v_bot[1]) / (v_a1[1] - v_bot[1] + 1e-9)
                t2 = (y_max - v_bot[1]) / (v_a2[1] - v_bot[1] + 1e-9)
                int1 = v_bot + t1 * (v_a1 - v_bot)
                int2 = v_bot + t2 * (v_a2 - v_bot)
                int1[1] = y_max
                int2[1] = y_max

                idx_int1 = len(v_list)
                v_list.append(int1)
                idx_int2 = len(v_list)
                v_list.append(int2)

                kept_faces.append([i_bot, idx_int1, idx_int2])
                top_segments.append([idx_int1, idx_int2])
            elif num_below == 2:
                idx_above = below.index(False)
                i_a = tri[idx_above]
                i_b1 = tri[(idx_above + 1) % 3]
                i_b2 = tri[(idx_above + 2) % 3]

                v_a = v_list[i_a]
                v_b1 = v_list[i_b1]
                v_b2 = v_list[i_b2]

                t1 = (y_max - v_b1[1]) / (v_a[1] - v_b1[1] + 1e-9)
                t2 = (y_max - v_b2[1]) / (v_a[1] - v_b2[1] + 1e-9)
                int1 = v_b1 + t1 * (v_a - v_b1)
                int2 = v_b2 + t2 * (v_a - v_b2)
                int1[1] = y_max
                int2[1] = y_max

                idx_int1 = len(v_list)
                v_list.append(int1)
                idx_int2 = len(v_list)
                v_list.append(int2)

                kept_faces.append([i_b1, i_b2, idx_int1])
                kept_faces.append([i_b2, idx_int2, idx_int1])
                top_segments.append([idx_int1, idx_int2])

        # Tampa superior hermética (Opção 2A: fecha o corte da barra com sólido preenchido)
        if cap_ends and top_segments:
            top_pts = np.array([v_list[s[0]][:3] for s in top_segments], dtype=np.float32)
            c_pos = top_pts.mean(axis=0)
            c_pos[1] = y_max
            n_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            c_vert = v_list[top_segments[0][0]].copy()
            c_vert[:3] = c_pos
            c_vert[3:6] = n_up
            idx_c = len(v_list)
            v_list.append(c_vert)
            for s0, s1 in top_segments:
                u = v_list[s0][:3] - c_pos
                w = v_list[s1][:3] - c_pos
                fn = np.cross(u, w)
                if np.dot(fn, n_up) > 0:
                    kept_faces.append([idx_c, s0, s1])
                else:
                    kept_faces.append([idx_c, s1, s0])

        f_list = kept_faces

    if not f_list:
        return np.empty((0, 11), dtype=np.float32), np.empty((0, 3), dtype=np.uint32)

    used_indices = sorted(list(set(idx for f in f_list for idx in f)))
    old_to_new = {old: new for new, old in enumerate(used_indices)}
    out_verts = np.array([v_list[idx] for idx in used_indices], dtype=np.float32)
    out_faces = np.array([[old_to_new[f[0]], old_to_new[f[1]], old_to_new[f[2]]] for f in f_list], dtype=np.uint32)

    # Inward tuck suave nas bordas de transição para encaixar dentro do vestuário
    if tuck_bottom and y_min is not None:
        tuck_band = 0.035
        dists = (out_verts[:, 1] + waist_tilt_z * out_verts[:, 2]) - y_min if waist_tilt_z != 0.0 else (out_verts[:, 1] - y_min)
        mask = (dists >= -1e-5) & (dists < tuck_band)
        if np.any(mask):
            rel = np.maximum(0.0, dists[mask]) / tuck_band
            factors = 1.0 - 0.15 * (1.0 - rel)
            out_verts[mask, 0] *= factors
            out_verts[mask, 2] *= factors

    if tuck_top and y_max is not None:
        tuck_band = 0.015
        mask = (out_verts[:, 1] <= y_max) & (out_verts[:, 1] > y_max - tuck_band)
        if np.any(mask):
            factors = 1.0 - 0.03 * (1.0 - (y_max - out_verts[mask, 1]) / tuck_band)
            out_verts[mask, 0] *= factors
            out_verts[mask, 2] *= factors

    return out_verts, out_faces


def bevel_torso_corners(
    v_mat: np.ndarray,
    faces: np.ndarray,
    chamfer_m: float = 0.015,
) -> Tuple[np.ndarray, np.ndarray]:
    """Chanfra topologicamente as quinas verticais do torso/pelve estilo Bevel do Blender (Ctrl+B).

    Divide cada aresta vertical de 90° em duas arestas e insere uma nova faceta
    a 45°, transformando o perfil retangular em um cilindro octogonal suave.
    """
    if chamfer_m <= 1e-4:
        return v_mat, faces

    v_mat = v_mat.copy()
    faces_list = list(faces.tolist())

    pos = v_mat[:, :3]
    pos_round = np.round(pos, 4)
    unique_pos, inv_pos = np.unique(pos_round, axis=0, return_inverse=True)

    edge_faces: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for fi, (f0, f1, f2) in enumerate(faces):
        u0, u1, u2 = int(inv_pos[f0]), int(inv_pos[f1]), int(inv_pos[f2])
        for ea, eb in [(u0, u1), (u1, u2), (u2, u0)]:
            edge = (min(ea, eb), max(ea, eb))
            edge_faces[edge].append(fi)

    fnorms = []
    for f0, f1, f2 in faces:
        p0, p1, p2 = pos[f0], pos[f1], pos[f2]
        n = np.cross(p1 - p0, p2 - p0)
        norm = np.linalg.norm(n)
        if norm > 1e-6:
            n /= norm
        fnorms.append(n)
    fnorms = np.array(fnorms)

    z_mid = float((np.min(pos[:, 2]) + np.max(pos[:, 2])) / 2.0)

    for edge, flist in edge_faces.items():
        if len(flist) == 2:
            n0, n1 = fnorms[flist[0]], fnorms[flist[1]]
            u0, u1 = edge
            p0, p1 = unique_pos[u0], unique_pos[u1]
            if max(p0[1], p1[1]) <= 1.26:
                if (abs(n0[0]) > 0.6 and abs(n1[2]) > 0.6) or (abs(n0[2]) > 0.6 and abs(n1[0]) > 0.6):
                    fi_x = flist[0] if abs(n0[0]) > 0.6 else flist[1]
                    fi_z = flist[0] if abs(n0[2]) > 0.6 else flist[1]

                    if p0[1] > p1[1]:
                        utop, ubot = u0, u1
                        ptop, pbot = p0, p1
                    else:
                        utop, ubot = u1, u0
                        ptop, pbot = p1, p0

                    f_x = faces[fi_x]
                    f_z = faces[fi_z]
                    vx_top = [v for v in f_x if inv_pos[v] == utop][0]
                    vx_bot = [v for v in f_x if inv_pos[v] == ubot][0]
                    vz_top = [v for v in f_z if inv_pos[v] == utop][0]
                    vz_bot = [v for v in f_z if inv_pos[v] == ubot][0]

                    sign_x = 1.0 if ptop[0] > 0 else -1.0
                    sign_z = 1.0 if (ptop[2] - z_mid) > 0 else -1.0

                    # Desloca os vértices separando as arestas:
                    # vx pertence à parede X (lateral), desloca em Z
                    v_mat[vx_top, 2] -= sign_z * chamfer_m
                    v_mat[vx_bot, 2] -= sign_z * chamfer_m
                    # vz pertence à parede Z (frontal/traseira), desloca em X
                    v_mat[vz_top, 0] -= sign_x * chamfer_m
                    v_mat[vz_bot, 0] -= sign_x * chamfer_m

                    # Insere o quad chanfrado com normal apontando para fora (sign_x, 0, sign_z)
                    if sign_x * sign_z > 0:
                        faces_list.append([vx_top, vz_top, vz_bot])
                        faces_list.append([vx_top, vz_bot, vx_bot])
                    else:
                        faces_list.append([vz_top, vx_top, vx_bot])
                        faces_list.append([vz_top, vx_bot, vz_bot])

    out_faces = np.array(faces_list, dtype=np.uint32)
    return v_mat, out_faces


def transform_arm_vertices(
    raw_v: List[List[float]],
    width_scale: float = 1.0,
    length_scale: float = 1.0,
    hand_z_offset: float = 0.0,
    is_hand_only: bool = False,
) -> List[List[float]]:
    """Aplica ajustes dinâmicos de largura e comprimento às malhas de braço e antebraço.
    Suporta tanto o espaço nativo do motor (Z=altura, Y=profundidade) quanto o clean OBJ (Y=altura, Z=profundidade).
    """
    if width_scale == 1.0 and length_scale == 1.0 and hand_z_offset == 0.0:
        return raw_v

    verts = [list(v) for v in raw_v]
    if not verts:
        return verts

    sample = verts[:min(100, len(verts))]
    max_z = max(v[2] for v in sample)
    max_y = max(v[1] for v in sample)
    is_native = max_z > max_y

    xs = [v[0] for v in verts]
    cx = float((min(xs) + max(xs)) / 2)
    shoulder_height = 1.482

    if is_native:
        # Espaço nativo do motor: Z é altura, Y é profundidade
        ys = [v[1] for v in verts]
        cy = float((min(ys) + max(ys)) / 2)
        for i in range(len(verts)):
            x, y, z = verts[i]
            if width_scale != 1.0:
                x = cx + (x - cx) * width_scale
                y = cy + (y - cy) * width_scale
            if length_scale != 1.0:
                z = shoulder_height + (z - shoulder_height) * length_scale
            if is_hand_only and hand_z_offset != 0.0:
                z = z - hand_z_offset
            verts[i] = [x, y, z]
    else:
        # Espaço clean OBJ: Y é altura, Z é profundidade
        zs = [v[2] for v in verts]
        cz = float((min(zs) + max(zs)) / 2)
        for i in range(len(verts)):
            x, y, z = verts[i]
            if width_scale != 1.0:
                x = cx + (x - cx) * width_scale
                z = cz + (z - cz) * width_scale
            if length_scale != 1.0:
                y = shoulder_height + (y - shoulder_height) * length_scale
            if is_hand_only and hand_z_offset != 0.0:
                y = y - hand_z_offset
            verts[i] = [x, y, z]

    return verts


def parse_obj_as_mesh(
    obj_path: str,
    default_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    vertex_transform: Optional[Any] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Lê um arquivo .obj simples e extrai vértices e normais para buffers OpenGL [x, z, -y, nx, nz, -ny, u, v, r, g, b]."""
    if not os.path.exists(obj_path):
        return None

    raw_v: List[List[float]] = []
    raw_vt: List[List[float]] = []
    raw_vn: List[List[float]] = []
    faces: List[List[str]] = []

    with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("# Arm hidden") or line.startswith("# Forearm hidden"):
                return None
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == "v":
                raw_v.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "vt":
                raw_vt.append([float(parts[1]), float(parts[2])])
            elif parts[0] == "vn":
                raw_vn.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "f":
                faces.append(parts[1:])

    if not raw_v or not faces:
        return None

    # Aplica transformação dinâmica de vértices se solicitada
    if vertex_transform is not None:
        raw_v = vertex_transform(raw_v)

    # Se normais ausentes, pré-calcula normais suaves por vértice (Gouraud/Phong smooth shading)
    computed_vn: Dict[int, np.ndarray] = {}
    if not raw_vn:
        for face in faces:
            v_indices = []
            for token in face:
                sub = token.split("/")
                v_indices.append(int(sub[0]) - 1)
            for i in range(1, len(v_indices) - 1):
                i0, i1, i2 = v_indices[0], v_indices[i], v_indices[i + 1]
                p0 = np.array(raw_v[i0], dtype=np.float32)
                p1 = np.array(raw_v[i1], dtype=np.float32)
                p2 = np.array(raw_v[i2], dtype=np.float32)
                fn = np.cross(p1 - p0, p2 - p0)
                norm_len = float(np.linalg.norm(fn))
                if norm_len > 1e-7:
                    fn_norm = fn / norm_len
                    for idx in (i0, i1, i2):
                        if idx not in computed_vn:
                            computed_vn[idx] = fn_norm.copy()
                        else:
                            computed_vn[idx] += fn_norm
        for idx, n in computed_vn.items():
            l = float(np.linalg.norm(n))
            if l > 1e-7:
                computed_vn[idx] = n / l
            else:
                computed_vn[idx] = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    v_data: List[float] = []
    indices: List[int] = []

    for face in faces:
        face_tokens = face
        tri_sub_indices = []
        for token in face_tokens:
            sub = token.split("/")
            v_idx = int(sub[0]) - 1
            vt_idx = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else -1
            vn_idx = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else -1

            bx, by, bz = raw_v[v_idx]
            pos = [bx, bz, -by]

            if vn_idx >= 0 and vn_idx < len(raw_vn):
                nx, ny, nz = raw_vn[vn_idx]
                norm = [nx, nz, -ny]
            elif v_idx in computed_vn:
                nx, ny, nz = computed_vn[v_idx]
                norm = [nx, nz, -ny]
            else:
                norm = None

            if vt_idx >= 0 and vt_idx < len(raw_vt):
                uv = [raw_vt[vt_idx][0], 1.0 - raw_vt[vt_idx][1]]
            else:
                uv = [0.5, 0.5]

            tri_sub_indices.append((pos, norm, uv))

        for i in range(1, len(tri_sub_indices) - 1):
            p0, n0, uv0 = tri_sub_indices[0]
            p1, n1, uv1 = tri_sub_indices[i]
            p2, n2, uv2 = tri_sub_indices[i + 1]

            if n0 is None:
                v10 = np.array(p1, dtype=np.float32) - np.array(p0, dtype=np.float32)
                v20 = np.array(p2, dtype=np.float32) - np.array(p0, dtype=np.float32)
                fn = np.cross(v10, v20)
                norm_len = float(np.linalg.norm(fn))
                fn_list = list(fn / norm_len) if norm_len > 1e-7 else [0.0, 1.0, 0.0]
                n0, n1, n2 = fn_list, fn_list, fn_list

            for p, n, u in [(p0, n0, uv0), (p1, n1, uv1), (p2, n2, uv2)]:
                curr_idx = len(v_data) // 11
                v_data.extend(p)
                v_data.extend(n)
                v_data.extend(u)
                v_data.extend(default_color)
                indices.append(curr_idx)

    v_arr = np.array(v_data, dtype=np.float32)
    i_arr = np.array(indices, dtype=np.uint32)
    return v_arr, i_arr


_WAISTBAND_CACHE: Dict[str, Dict[str, float]] = {}

def detect_bottom_waistband_geometry(obj_path: str) -> Optional[Dict[str, float]]:
    """Detecta dinamicamente a geometria, altura e inclinação exatas do cós da calça ativa (Opção 1A)."""
    if not os.path.exists(obj_path):
        return None
    if obj_path in _WAISTBAND_CACHE:
        return _WAISTBAND_CACHE[obj_path]
    try:
        data = parse_obj_as_mesh(obj_path)
        if not data:
            return None
        v = data[0].reshape(-1, 11)
        top_y = float(v[:, 1].max())
        rim = v[v[:, 1] > top_y - 0.045]
        if len(rim) == 0:
            return None
        front = rim[rim[:, 2] > 0.03]
        back = rim[rim[:, 2] < -0.03]
        f_z_max = float(front[:, 2].max()) if len(front) else 0.08
        f_center = front[front[:, 2] > f_z_max - 0.035] if len(front) else front
        f_y = float(f_center[:, 1].mean()) if len(f_center) else top_y
        f_z = float(f_center[:, 2].mean()) if len(f_center) else 0.08
        b_y = float(back[:, 1].mean()) if len(back) else top_y
        b_z = float(back[:, 2].mean()) if len(back) else -0.08
        tilt = float((b_y - f_y) / (f_z - b_z + 1e-6))
        c_waist = float(f_y + tilt * f_z)
        res = {
            "top_y": top_y,
            "f_y": f_y,
            "f_z": f_z,
            "b_y": b_y,
            "b_z": b_z,
            "tilt": max(0.0, min(0.35, tilt)),
            "c_waist": c_waist,
            "f_max_z": f_z_max,
            "max_x": float(rim[:, 0].max()),
        }
        _WAISTBAND_CACHE[obj_path] = res
        return res
    except Exception:
        return None


def upload_texture_rgba(img: Image.Image) -> int:
    """Faz upload de imagem PIL para textura OpenGL 2D com filtro linear e clamp."""
    import OpenGL.GL as gl

    img = img.convert("RGBA")
    img_data = np.array(img, dtype=np.uint8)

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
        img.width, img.height, 0,
        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
    )
    return tex_id


def arm_mesh_to_gl(
    verts: np.ndarray,
    faces: np.ndarray,
    skin_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> Tuple[np.ndarray, np.ndarray]:
    """Converte vértices e faces no espaço A-Pose mundo para layout de vértice OpenGL [x, z, -y, nx, nz, -ny, u, v, r, g, b]."""
    if len(verts) == 0 or len(faces) == 0:
        return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.uint32)

    # Cálculo suave de normais
    v_norms = np.zeros_like(verts)
    for f in faces:
        p0, p1, p2 = verts[f[0]], verts[f[1]], verts[f[2]]
        fn = np.cross(p1 - p0, p2 - p0)
        norm_len = np.linalg.norm(fn)
        if norm_len > 1e-7:
            fn /= norm_len
            for idx in f:
                v_norms[idx] += fn

    lens = np.linalg.norm(v_norms, axis=1, keepdims=True)
    lens[lens < 1e-7] = 1.0
    v_norms /= lens

    # Conversão de eixos: [x, z, -y] (OpenGL com +Y como cima)
    v_data: List[float] = []
    indices: List[int] = []
    for idx, (v, n) in enumerate(zip(verts, v_norms)):
        pos = [float(v[0]), float(v[2]), float(-v[1])]
        norm = [float(n[0]), float(n[2]), float(-n[1])]
        uv = [0.5, 0.5]
        v_data.extend(pos)
        v_data.extend(norm)
        v_data.extend(uv)
        v_data.extend(skin_color)

    for f in faces:
        indices.extend([int(x) for x in f])

    return np.array(v_data, dtype=np.float32), np.array(indices, dtype=np.uint32)


def create_solid_texture(color_rgb_255: Tuple[int, int, int], alpha: int = 255) -> int:
    """Cria uma textura OpenGL 16x16 de cor sólida RGBA."""
    img = Image.new("RGBA", (16, 16), color_rgb_255 + (alpha,))
    return upload_texture_rgba(img)


def find_clothing_texture(asset_id: Union[int, str]) -> Optional[str]:
    """Localiza a textura PNG de uma peça de roupa a partir do seu ID numérico."""
    id_str = str(asset_id)
    if os.path.exists(CLOTHING_DIR):
        for fname in os.listdir(CLOTHING_DIR):
            if fname.lower().endswith(".png") and id_str in fname:
                return os.path.join(CLOTHING_DIR, fname)
    return None


def is_valid_v2_obj(path: str) -> bool:
    """Verifica se o arquivo OBJ conformativo foi gerado pelo pipeline universal v2 ou v3."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(5):
                line = f.readline()
                if "Universal Fitted Clothing v21" in line:
                    return True
                if any(f"Universal Fitted Clothing v{k}" in line for k in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)):
                    return False  # Regenerate fits made before the geometric HSR fallback.
        return False
    except Exception:
        return False


@dataclass
class CharacterPart:
    """Representa uma parte montada do personagem pronta para renderização."""
    name: str
    mesh: Any  # TexturedMesh
    texture_id: int
    transform: Optional[np.ndarray] = None


class CharacterModel:
    """Modelo modular completo do personagem 3D montado para visualização em tempo real."""

    def __init__(
        self,
        customization: Optional[AvatarCustomization] = None,
        top_id: Optional[Union[int, str]] = 9240757332,
        bottom_id: Optional[Union[int, str]] = 109837605892174,
        tool_id: Optional[Union[int, str]] = None,
        hair_id: Optional[Union[int, str]] = None,
        create_mesh: bool = True,
        waist_height_offset: float = 0.0,
        top_hem_offset: Optional[float] = None,
        waist_radius_offset: float = 0.0,
        waist_chamfer: float = 0.015,
        head_z_offset: Optional[float] = None,
        hair_offset_x: Optional[float] = None,
        hair_offset_y: Optional[float] = None,
        hair_offset_z: Optional[float] = None,
        hair_scale_x: Optional[float] = None,
        hair_scale_y: Optional[float] = None,
        hair_scale_z: Optional[float] = None,
    ) -> None:
        self.customization = customization if customization is not None else AvatarCustomization(
            head_type=HeadType.ROUNDED,
            mouth_style=MouthStyle.ANIME_ORIGINAL,
        )
        self.top_id = top_id
        self.bottom_id = bottom_id
        self.tool_id = tool_id
        self.hair_id = hair_id
        if self.hair_id is not None:
            hair_str = str(self.hair_id).strip()
            if hair_str.lower() in ("none", "0", "false", "sem", "careca", "bald"):
                self.customization.custom_hair_obj = None
                self.customization.custom_hair_tex = None
                self.customization.hair_style = HairStyle.BALD
            else:
                hair_obj_path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{hair_str}.obj")
                if not os.path.exists(hair_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="female" if self.customization.is_female else "male")
                        engine.equip_hair(hair_str)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: falha ao equipar cabelo {hair_str}: {e}")
                if os.path.exists(hair_obj_path):
                    self.customization.custom_hair_obj = hair_obj_path
                    tex_path = find_clothing_texture(hair_str)
                    if tex_path:
                        self.customization.custom_hair_tex = tex_path
        self.create_mesh = create_mesh

        # Ajustes dinâmicos de proporção de mangas e braços controláveis via chat/CLI
        self.sleeve_width_scale: float = 1.0    # 1.0 = normal; >1.0 mais larga, <1.0 mais estreita
        self.sleeve_length_offset: float = 0.0  # 0.0 = normal; + desce/alonga, - sobe/encurta (em metros)
        self.sleeve_shift_x: float = 0.0        # Horizontal lateral: + fora, - dentro (em metros)
        self.sleeve_shift_y: float = 0.0        # Horizontal profundidade: + frente, - trás (em metros)
        self.sleeve_shift_z: float = 0.0        # Vertical: + sobe, - desce (em metros)
        self.arm_width_scale: float = 1.0       # 1.0 = normal; >1.0 mais largo, <1.0 mais fino
        self.arm_length_scale: float = 1.0      # 1.0 = normal; >1.0 mais longo, <1.0 mais curto
        self.hip_glute_scale: float = 1.0       # 1.0 = normal; >1.0 mais relevo na bunda, <1.0 menos
        self.hip_width_scale: float = 1.0       # 1.0 = normal; >1.0 mais largo, <1.0 mais estreito
        self.waist_height_offset: float = float(waist_height_offset)  # Deslocamento vertical do cós da calça (+ sobe, - desce em metros)
        # Deslocamento vertical da barra da camisa (+ sobe, - desce em metros; padrão masculino: -2cm / -0.02m)
        if top_hem_offset is not None:
            self.top_hem_offset: float = float(top_hem_offset)
        else:
            self.top_hem_offset: float = 0.0 if self.customization.is_female else -0.02
        self.waist_radius_offset: float = float(waist_radius_offset)  # Deslocamento radial do torso na cintura (+ alarga, - afunila em metros)
        self.waist_chamfer: float = float(waist_chamfer)              # Largura do chanfro das quinas do torso em metros (0.0 = quadrado, 0.015 = 1.5cm padrão, até 0.05)
        if head_z_offset is not None:
            self.head_z_offset: float = float(head_z_offset)
        else:
            self.head_z_offset: float = 0.0

        # Ajustes de posição e escala manual do cabelo (+/- em metros e fator multiplicador)
        self.hair_offset_x: float = float(hair_offset_x) if hair_offset_x is not None else float(getattr(self.customization, "hair_offset_x", 0.0))
        self.hair_offset_y: float = float(hair_offset_y) if hair_offset_y is not None else float(getattr(self.customization, "hair_offset_y", 0.0))
        self.hair_offset_z: float = float(hair_offset_z) if hair_offset_z is not None else float(getattr(self.customization, "hair_offset_z", 0.0))
        self.hair_scale_x: float = float(hair_scale_x) if hair_scale_x is not None else float(getattr(self.customization, "hair_scale_x", 1.0))
        self.hair_scale_y: float = float(hair_scale_y) if hair_scale_y is not None else float(getattr(self.customization, "hair_scale_y", 1.0))
        self.hair_scale_z: float = float(hair_scale_z) if hair_scale_z is not None else float(getattr(self.customization, "hair_scale_z", 1.0))

        self.parts: List[CharacterPart] = []
        self.textures: List[int] = []
        self.white_tex_id: Optional[int] = None
        self.show_cage: bool = False
        self.cage_debug_mesh: Optional[Any] = None

        if self.create_mesh:
            self._build()

    def set_sleeve_width(self, scale: float) -> None:
        """Ajusta a largura/espessura da ponta da manga em tempo real."""
        self.sleeve_width_scale = max(0.4, min(2.5, float(scale)))
        self.reload()

    def set_sleeve_length(self, offset_m: float) -> None:
        """Ajusta o comprimento da ponta da manga em metros em tempo real (+ desce, - sobe)."""
        self.sleeve_length_offset = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_sleeve_shift_x(self, offset_m: float) -> None:
        """Ajusta o deslocamento horizontal lateral da ponta da manga (+ fora, - dentro em metros)."""
        self.sleeve_shift_x = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_sleeve_shift_y(self, offset_m: float) -> None:
        """Ajusta o deslocamento horizontal profundidade da ponta da manga (+ frente, - trás em metros)."""
        self.sleeve_shift_y = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_sleeve_shift_z(self, offset_m: float) -> None:
        """Ajusta o deslocamento vertical da ponta da manga (+ sobe, - desce em metros)."""
        self.sleeve_shift_z = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_sleeve_offset(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
    ) -> None:
        """Ajusta múltiplos eixos de deslocamento da ponta da manga de uma só vez."""
        if x is not None:
            self.sleeve_shift_x = max(-0.25, min(0.25, float(x)))
        if y is not None:
            self.sleeve_shift_y = max(-0.25, min(0.25, float(y)))
        if z is not None:
            self.sleeve_shift_z = max(-0.25, min(0.25, float(z)))
        self.reload()

    def set_arm_width(self, scale: float) -> None:
        """Ajusta a largura/espessura do braço e antebraço em tempo real."""
        self.arm_width_scale = max(0.4, min(2.5, float(scale)))
        self.reload()

    def set_arm_length(self, scale: float) -> None:
        """Ajusta o comprimento do braço em tempo real."""
        self.arm_length_scale = max(0.5, min(1.8, float(scale)))
        self.reload()

    def reset_sleeve_adjustments(self) -> None:
        """Restaura a largura, comprimento e deslocamento da manga para o padrão."""
        self.sleeve_width_scale = 1.0
        self.sleeve_length_offset = 0.0
        self.sleeve_shift_x = 0.0
        self.sleeve_shift_y = 0.0
        self.sleeve_shift_z = 0.0
        self.reload()

    def reset_arm_adjustments(self) -> None:
        """Restaura a largura e o comprimento do braço para o padrão."""
        self.arm_width_scale = 1.0
        self.arm_length_scale = 1.0
        self.reload()

    def set_quadril(self, glute_scale: float = 1.0, width_scale: Optional[float] = None) -> None:
        """Ajusta o relevo da parte da bunda (glúteos) e a largura dos quadris em tempo real."""
        self.hip_glute_scale = max(0.5, min(3.0, float(glute_scale)))
        if width_scale is not None:
            self.hip_width_scale = max(0.5, min(2.5, float(width_scale)))
        self.reload()

    def reset_quadril_adjustments(self) -> None:
        """Restaura o relevo e largura do quadril para os valores padrão (1.0x)."""
        self.hip_glute_scale = 1.0
        self.hip_width_scale = 1.0
        self.reload()

    def set_waist_height(self, offset_m: float) -> None:
        """Ajusta o deslocamento vertical da cintura/cós da calça em metros em tempo real (+ sobe, - desce)."""
        self.waist_height_offset = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_waist_z(self, target_z: float) -> None:
        """Define a altura absoluta do cós da calça (ex: 1.00m meio do declive, 1.07m alta, 0.94m baixa)."""
        base_z = 1.00 if self.customization.is_female else 0.935
        self.set_waist_height(float(target_z) - base_z)

    def reset_waist_adjustments(self) -> None:
        """Restaura a altura do cós da calça, o raio da cintura e o chanfro para o padrão."""
        self.waist_height_offset = 0.0
        self.waist_radius_offset = 0.0
        self.waist_chamfer = 0.015
        self.reload()

    def set_waist_radius(self, offset_m: float) -> None:
        """Ajusta o raio/afunilamento radial do torso na cintura em tempo real (+ alarga, - afunila em metros)."""
        self.waist_radius_offset = max(-0.06, min(0.08, float(offset_m)))
        self.reload()

    def reset_waist_radius(self) -> None:
        """Restaura o raio da cintura para o padrão (0.0m de deslocamento)."""
        self.waist_radius_offset = 0.0
        self.reload()

    def set_waist_chamfer(self, amount: float) -> None:
        """Ajusta a largura do chanfro das 4 quinas do torso em metros (0.0 = quadrado, 0.015 = 1.5cm padrão, até 0.05)."""
        self.waist_chamfer = max(0.0, min(0.05, float(amount)))
        self.reload()

    def reset_waist_chamfer(self) -> None:
        """Restaura o chanfro das quinas do torso para o padrão suave (0.015m / 1.5cm)."""
        self.waist_chamfer = 0.015
        self.reload()

    def set_top_hem(self, offset_m: float) -> None:
        """Ajusta o deslocamento vertical da barra da blusa em metros em tempo real (+ sobe, - desce)."""
        self.top_hem_offset = max(-0.25, min(0.25, float(offset_m)))
        self.reload()

    def set_top_hem_z(self, target_z: float) -> None:
        """Define a altura absoluta da barra da blusa (ex: 0.985m normal feminino, 0.890m normal masculino)."""
        base_z = 0.985 if self.customization.is_female else 0.890
        self.set_top_hem(float(target_z) - base_z)

    def reset_top_hem(self) -> None:
        """Restaura a altura da barra da blusa para o padrão (-0.02m no masculino, 0.0m no feminino)."""
        self.top_hem_offset = 0.0 if self.customization.is_female else -0.02
        self.reload()

    def set_head_z_offset(self, offset_m: float) -> None:
        """Ajusta o deslocamento sagital da cabeça e pescoço no eixo Z (+ frente, - trás em metros)."""
        self.head_z_offset = max(-0.10, min(0.10, float(offset_m)))
        self.reload()

    def reset_head_z_offset(self) -> None:
        """Restaura o alinhamento postural da cabeça para o padrão (0.0)."""
        self.head_z_offset = 0.0
        self.reload()

    def set_hair_offset(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
    ) -> None:
        """Ajusta o deslocamento de posição do cabelo em metros (+/- 0.50m)."""
        if x is not None:
            self.hair_offset_x = max(-0.50, min(0.50, float(x)))
            if hasattr(self.customization, "hair_offset_x"):
                self.customization.hair_offset_x = self.hair_offset_x
        if y is not None:
            self.hair_offset_y = max(-0.50, min(0.50, float(y)))
            if hasattr(self.customization, "hair_offset_y"):
                self.customization.hair_offset_y = self.hair_offset_y
        if z is not None:
            self.hair_offset_z = max(-0.50, min(0.50, float(z)))
            if hasattr(self.customization, "hair_offset_z"):
                self.customization.hair_offset_z = self.hair_offset_z
        self.reload()

    def set_hair_position(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
    ) -> None:
        """Sinônimo de set_hair_offset para ajuste de posição."""
        self.set_hair_offset(x=x, y=y, z=z)

    def set_hair_scale(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
    ) -> None:
        """Ajusta o tamanho/escala do cabelo nos eixos X, Y e Z (de 0.2x a 3.0x)."""
        if x is not None and y is None and z is None:
            # Escala uniforme nos 3 eixos se apenas 1 valor for fornecido
            sx = max(0.2, min(3.0, float(x)))
            self.hair_scale_x = sx
            self.hair_scale_y = sx
            self.hair_scale_z = sx
        else:
            if x is not None:
                self.hair_scale_x = max(0.2, min(3.0, float(x)))
            if y is not None:
                self.hair_scale_y = max(0.2, min(3.0, float(y)))
            if z is not None:
                self.hair_scale_z = max(0.2, min(3.0, float(z)))

        if hasattr(self.customization, "hair_scale_x"):
            self.customization.hair_scale_x = self.hair_scale_x
            self.customization.hair_scale_y = self.hair_scale_y
            self.customization.hair_scale_z = self.hair_scale_z
        self.reload()

    def reset_hair_position(self) -> None:
        """Restaura o deslocamento de posição do cabelo para (0.0, 0.0, 0.0)."""
        self.hair_offset_x = 0.0
        self.hair_offset_y = 0.0
        self.hair_offset_z = 0.0
        if hasattr(self.customization, "hair_offset_x"):
            self.customization.hair_offset_x = 0.0
            self.customization.hair_offset_y = 0.0
            self.customization.hair_offset_z = 0.0
        self.reload()

    def reset_hair_scale(self) -> None:
        """Restaura a escala do cabelo para (1.0x, 1.0x, 1.0x)."""
        self.hair_scale_x = 1.0
        self.hair_scale_y = 1.0
        self.hair_scale_z = 1.0
        if hasattr(self.customization, "hair_scale_x"):
            self.customization.hair_scale_x = 1.0
            self.customization.hair_scale_y = 1.0
            self.customization.hair_scale_z = 1.0
        self.reload()

    def reset_hair_adjustments(self) -> None:
        """Restaura tanto a posição quanto o tamanho/escala do cabelo para os padrões originais."""
        self.hair_offset_x = 0.0
        self.hair_offset_y = 0.0
        self.hair_offset_z = 0.0
        self.hair_scale_x = 1.0
        self.hair_scale_y = 1.0
        self.hair_scale_z = 1.0
        if hasattr(self.customization, "hair_offset_x"):
            self.customization.hair_offset_x = 0.0
            self.customization.hair_offset_y = 0.0
            self.customization.hair_offset_z = 0.0
            self.customization.hair_scale_x = 1.0
            self.customization.hair_scale_y = 1.0
            self.customization.hair_scale_z = 1.0
        self.reload()

    def _load_arm_parts(self, skin_color: Tuple[float, float, float]) -> List[CharacterPart]:
        """Carrega malhas de braços e antebraços com HSR adaptativo por vestuário ativo."""
        from src.rendering.mesh import TexturedMesh
        parts: List[CharacterPart] = []

        is_fem = self.customization.is_female
        arm_suffix = "_female.obj" if is_fem else ".obj"
        clean_file = "character_female_clean_apose_stage2.obj" if (is_fem and os.path.exists(os.path.join(MODELS_DIR, "character_female_clean_apose_stage2.obj"))) else ("character_female_clean_apose.obj" if is_fem else "character_clean.obj")
        clean_path = os.path.join(MODELS_DIR, clean_file)
        side_map = {"left": "esquerdo", "right": "direito"}

        top_str = str(self.top_id).lower() if self.top_id is not None else "none"
        is_none_top = self.top_id is None or top_str in ("none", "0", "false", "sem", "naked")

        def arm_tf(raw_v):
            return transform_arm_vertices(raw_v, self.arm_width_scale, self.arm_length_scale, is_hand_only=False)

        def hand_tf(raw_v):
            return transform_arm_vertices(
                raw_v,
                self.arm_width_scale,
                self.arm_length_scale,
                hand_z_offset=self.sleeve_length_offset,
                is_hand_only=True
            )

        # 1. Sem camisa: carrega braços e antebraços completos do modelo limpo
        if is_none_top:
            for side in ("left", "right"):
                pt_side = side_map[side]
                arm_data = parse_clean_obj_groups(clean_path, [f"Export_braco_superior_{pt_side}"], default_color=skin_color)
                if arm_data:
                    parts.append(CharacterPart(f"arm_{side}", TexturedMesh(arm_data[0], arm_data[1]), self.white_tex_id))
                ab_data = parse_clean_obj_groups(clean_path, [f"Export_antebraco_{pt_side}"], default_color=skin_color)
                if ab_data:
                    parts.append(CharacterPart(f"forearm_{side}", TexturedMesh(ab_data[0], ab_data[1]), self.white_tex_id))
                hand_data = parse_clean_obj_groups(clean_path, [f"Export_mao_{pt_side}"], default_color=skin_color)
                if hand_data:
                    parts.append(CharacterPart(f"hand_{side}", TexturedMesh(hand_data[0], hand_data[1]), self.white_tex_id))
            return parts

        # 2. Resolução Adaptativa Universal por lado (left e right independentes)
        top_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.top_id}{arm_suffix}")
        if not os.path.exists(top_obj_path):
            top_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.top_id}.obj")

        top_pts = []
        if os.path.exists(top_obj_path):
            with open(top_obj_path, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if line.startswith("v "):
                        top_pts.append([float(x) for x in line.strip().split()[1:4]])

        from src.clothing.wear_engine import slice_mesh_below_z
        for side_mult, side in [(1, "left"), (-1, "right")]:
            pt_side = side_map[side]

            # Identificação anatômica estrita de vértices da manga (não confunde a barra da cintura com manga)
            side_pts = [
                p for p in top_pts
                if (p[0] * side_mult) > (0.28 if p[2] < 1.10 else 0.20) and p[2] < 1.45
            ]
            min_z = min(p[2] for p in side_pts) if side_pts else 2.0
            side_shoulder_pts = [p for p in top_pts if (p[0] * side_mult) > 0.18 and p[2] > 1.35]
            side_sleeveless = (len(side_pts) < 15 or min_z > 1.32)
            side_long = (min_z <= 0.76) and not side_sleeveless
            side_short = not side_sleeveless and not side_long

            # Resolução anatômica com HSR adaptativo por comprimento de manga
            if is_fem:
                upper_arm_visible = not side_long
                forearm_visible = not side_long
                hand_visible = True
            else:
                upper_arm_visible = True
                forearm_visible = True
                hand_visible = False

            def make_side_arm_tf(is_bare):
                def side_arm_tf(raw_v):
                    return transform_arm_vertices(raw_v, self.arm_width_scale, self.arm_length_scale, is_hand_only=False)
                return side_arm_tf

            if upper_arm_visible:
                arm_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_braco_superior_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=make_side_arm_tf(side_sleeveless)
                )
                if arm_data:
                    parts.append(CharacterPart(f"arm_{side}", TexturedMesh(arm_data[0], arm_data[1]), self.white_tex_id))

            # Antebraço (visível em sem manga ou manga curta)
            if forearm_visible:
                ab_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_antebraco_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=make_side_arm_tf(side_sleeveless)
                )
                if ab_data:
                    v_arr, i_arr = ab_data
                    parts.append(CharacterPart(f"forearm_{side}", TexturedMesh(v_arr, i_arr), self.white_tex_id))

            # Mão (separada no modelo feminino A-pose, com gênero gramatical correto: esquerda/direita)
            if hand_visible:
                hand_side = "esquerda" if side == "left" else "direita"
                hand_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_mao_{hand_side}", f"Export_mao_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=make_side_arm_tf(side_sleeveless)
                )
                if hand_data:
                    v_h, i_h = hand_data
                    parts.append(CharacterPart(f"hand_{side}", TexturedMesh(v_h, i_h), self.white_tex_id))
        return parts

    def _load_trunk_skin(
        self,
        clean_obj: str,
        skin_color: Tuple[float, float, float],
        is_fem: bool,
        is_none_top: bool,
        is_none_bottom: bool,
        eff_waist: float,
        eff_hem: float,
        waist_tilt: float = 0.0,
        waist_geo: Optional[Dict[str, float]] = None,
        is_open_top: bool = False,
    ) -> Optional[CharacterPart]:
        """Carrega a pele anatomica do tronco (torso e pelve) com recorte adaptativo, tampas herméticas e silhueta suavizada."""
        from src.rendering.mesh import TexturedMesh

        # Se camisa e calca estao ambas presentes e se sobrepoem completamente (e nao e top aberto/biquini), nao ha pele exposta
        if not is_none_top and not is_none_bottom and not is_open_top and eff_hem <= (eff_waist - 0.005):
            return None

        trunk_data = parse_clean_obj_groups(clean_obj, ["Export_torso", "Export_pelve"], default_color=skin_color)
        if not trunk_data:
            return None

        v_arr, i_arr = trunk_data
        v_mat = v_arr.reshape(-1, 11).copy()
        faces = i_arr.reshape(-1, 3).copy()

        # Relevo de gluteos e largura do quadril se aplicavel no torso/pelve antes do corte
        if self.hip_glute_scale != 1.0 or self.hip_width_scale != 1.0:
            for i in range(len(v_mat)):
                y = v_mat[i, 1]
                z = v_mat[i, 2]
                if y < 0.94:
                    tz = float(np.exp(-((y - 0.81) / 0.085) ** 2))
                    if self.hip_glute_scale != 1.0 and z < -0.01:
                        td = min(1.0, abs(z) / 0.05)
                        v_mat[i, 2] -= (self.hip_glute_scale - 1.0) * 0.055 * tz * td
                    if self.hip_width_scale != 1.0:
                        v_mat[i, 0] *= (1.0 + (self.hip_width_scale - 1.0) * tz * 0.45)

        z_mid = float((np.min(v_mat[:, 2]) + np.max(v_mat[:, 2])) / 2.0)

        # Chanfro geométrico real (Bevel estilo Blender Ctrl+B) das 4 quinas verticais do torso (comando /cintura chanfro)
        if self.waist_chamfer > 1e-4:
            v_mat, faces = bevel_torso_corners(v_mat, faces, chamfer_m=self.waist_chamfer)

        # Ajuste radial do torso na cintura (comando /cintura radius)
        if abs(self.waist_radius_offset) > 1e-5:
            r0 = 0.09
            dr = self.waist_radius_offset
            for i in range(len(v_mat)):
                y = v_mat[i, 1]
                if y >= 1.25 or y <= 0.78:
                    continue
                if 0.90 <= y <= 1.05:
                    wy = 1.0
                elif y > 1.05:
                    t = (1.25 - y) / 0.20
                    wy = float(t * t * (3.0 - 2.0 * t))
                else:  # 0.78 < y < 0.90
                    t = (y - 0.78) / 0.12
                    wy = float(t * t * (3.0 - 2.0 * t))

                s_rad = 1.0 + (dr / r0) * wy
                v_mat[i, 0] *= s_rad
                v_mat[i, 2] = z_mid + (v_mat[i, 2] - z_mid) * s_rad

        # Limite frontal adaptativo baseado na calça ativa para evitar conflito/vazamento no cós (Opção 1A)
        if waist_geo is not None and not is_none_bottom:
            f_limit = waist_geo["f_max_z"] - 0.003
            for i in range(len(v_mat)):
                if v_mat[i, 1] < (eff_waist + 0.02) and v_mat[i, 2] > f_limit:
                    v_mat[i, 2] = f_limit

        # Contenção suave dos seios sob biquíni ou top aberto para evitar que o ápice fure o tecido
        if is_open_top and is_fem:
            for i in range(len(v_mat)):
                if 1.15 <= v_mat[i, 1] <= 1.38 and v_mat[i, 2] > 0.160:
                    v_mat[i, 2] = 0.160 + (v_mat[i, 2] - 0.160) * 0.40

        y_top_bound = (1.4566 if is_fem else 1.4830) if (is_none_top or is_open_top) else (eff_hem + 0.010)
        tilt = waist_tilt if not is_none_bottom else 0.0
        y_bot_bound = (0.7769 if is_fem else 0.8003) if is_none_bottom else (eff_waist - 0.015)

        if not is_open_top and y_top_bound <= (y_bot_bound - 0.020):
            return None

        cut_y_min = y_bot_bound if not is_none_bottom else None
        cut_y_max = None if (is_none_top or is_open_top) else y_top_bound

        sliced_v, sliced_f = slice_mesh_between_y(
            v_mat,
            faces,
            y_min=cut_y_min,
            y_max=cut_y_max,
            waist_tilt_z=tilt,
            tuck_bottom=(not is_none_bottom),
            tuck_top=(not is_none_top and not is_open_top),
            cap_ends=True,
        )

        if len(sliced_v) == 0 or len(sliced_f) == 0:
            return None

        # Re-normaliza normais das faces recortadas
        norms = sliced_v[:, 3:6]
        norm_lens = np.linalg.norm(norms, axis=1, keepdims=True)
        norm_lens[norm_lens < 1e-7] = 1.0
        sliced_v[:, 3:6] /= norm_lens

        mesh = TexturedMesh(sliced_v.flatten().astype(np.float32), sliced_f.flatten().astype(np.uint32))
        return CharacterPart("trunk_skin", mesh, self.white_tex_id)

    SKIN_PART_NAMES = ("arm_left", "arm_right", "forearm_left", "forearm_right",
                       "hand_left", "hand_right", "trunk_skin", "legs_skin")

    def _apply_hsr_skin(self, clean_obj, skin_color, top_obj_path, bottom_obj_path,
                        is_none_top, is_none_bottom) -> bool:
        """Replace the rule-based skin cuts with Roblox HSR culling when every worn garment has a mask."""
        from src.clothing.hsr import cull_hidden_triangles, sidecar_path, subdivide
        from src.rendering.mesh import TexturedMesh

        worn = [path for path, none in ((top_obj_path, is_none_top), (bottom_obj_path, is_none_bottom)) if not none]
        if not self.customization.is_female or not worn:
            return False
        masks = []
        for path in worn:
            sidecar = sidecar_path(path) if path else None
            if not sidecar or not os.path.exists(sidecar):
                return False  # a garment without HSR data keeps the rule-based cuts
            with np.load(sidecar) as data:
                masks.append((data["cage_points"], data["hidden"]))
                cage_faces = data["cage_faces"] if "cage_faces" in data else None
        cage_points = masks[0][0]
        if any(len(hidden) != len(cage_points) for _, hidden in masks):
            return False
        hidden = np.logical_or.reduce([mask for _, mask in masks])

        def hip_tf(raw_v):
            return transform_hip_vertices(raw_v, self.hip_glute_scale, self.hip_width_scale, self.waist_height_offset)

        def arm_tf(raw_v):
            return transform_arm_vertices(raw_v, self.arm_width_scale, self.arm_length_scale, is_hand_only=False)

        groups = [("trunk_skin", ["Export_torso", "Export_pelve"], hip_tf),
                  ("legs_skin", ["Export_coxa_esquerda", "Export_coxa_direita", "Export_canela_esquerda",
                                 "Export_canela_direita", "Export_pe_esquerdo", "Export_pe_direito"], hip_tf)]
        for side, pt_side, hand in (("left", "esquerdo", "esquerda"), ("right", "direito", "direita")):
            groups += [(f"arm_{side}", [f"Export_braco_superior_{pt_side}"], arm_tf),
                       (f"forearm_{side}", [f"Export_antebraco_{pt_side}"], arm_tf),
                       (f"hand_{side}", [f"Export_mao_{hand}", f"Export_mao_{pt_side}"], arm_tf)]

        new_parts = []
        for name, prefixes, transform in groups:
            data = parse_clean_obj_groups(clean_obj, prefixes, default_color=skin_color, vertex_transform=transform)
            if not data:
                continue
            vertices, indices = data
            faces = indices.reshape(-1, 3)
            # Hands stay whole: long sleeves mark the wrist cage points, and the few
            # vertices of our block hands all map to them, which would cut the hands.
            if not name.startswith("hand_"):
                rows, faces = subdivide(vertices.reshape(-1, 11), faces, levels=2)
                vertices = rows.ravel()
                faces = cull_hidden_triangles(rows[:, :3], faces, cage_points, hidden, cage_faces)
            if len(faces):
                new_parts.append(CharacterPart(name, TexturedMesh(vertices.astype(np.float32), faces.astype(np.uint32).ravel()),
                                               self.white_tex_id))
        for part in [p for p in self.parts if p.name in self.SKIN_PART_NAMES]:
            part.mesh.delete()
            self.parts.remove(part)
        self.parts.extend(new_parts)
        print(f"[HSR] Pele recortada pelas máscaras de {len(worn)} peça(s): {int(hidden.sum())} pontos da cage cobertos")
        return True

    def _build(self) -> None:
        """Carrega e monta todas as malhas e texturas do personagem."""
        from src.rendering.mesh import TexturedMesh

        # 1. Textura neutra branca (1x1) para membros com vertex color
        white_img = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
        self.white_tex_id = upload_texture_rgba(white_img)
        self.textures.append(self.white_tex_id)

        is_fem = self.customization.is_female
        clean_filename = "character_female_clean_apose_stage2.obj" if (is_fem and os.path.exists(os.path.join(MODELS_DIR, "character_female_clean_apose_stage2.obj"))) else ("character_female_clean_apose.obj" if is_fem else "character_clean.obj")
        clean_obj = os.path.join(MODELS_DIR, clean_filename)
        skin_color = list(self.customization.skin_color_rgb)

        # 1.1 Resolução de Cabelo Customizado por ID Roblox
        if self.hair_id is not None:
            hair_str = str(self.hair_id).strip()
            if hair_str.lower() in ("none", "0", "false", "sem", "careca", "bald"):
                self.customization.custom_hair_obj = None
                self.customization.custom_hair_tex = None
                self.customization.hair_style = HairStyle.BALD
            else:
                hair_obj_path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{hair_str}.obj")
                if not os.path.exists(hair_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="female" if is_fem else "male")
                        engine.equip_hair(hair_str)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: falha ao equipar cabelo {hair_str}: {e}")
                if os.path.exists(hair_obj_path):
                    self.customization.custom_hair_obj = hair_obj_path
                    tex_path = find_clothing_texture(hair_str)
                    if tex_path:
                        self.customization.custom_hair_tex = tex_path

        # 2. Textura Atlas dinâmica da cabeça (Rosto, olhos, boca e franja 2D)
        atlas_builder = HeadAtlasBuilder()
        head_img = atlas_builder.build_atlas(self.customization)
        head_tex_id = upload_texture_rgba(head_img)
        self.textures.append(head_tex_id)

        # Transformação completa de cabelo: escala nos eixos X, Y, Z ao redor do centro da cabeça (0, 1.70, 0),
        # soma dos offsets manuais do usuário (X, Y, Z) e compatibilização anatômica com modelo feminino
        def hair_custom_tf(verts):
            pivot_x = 0.0
            pivot_y = 1.70
            pivot_z = 0.0
            fem_dy = 0.0
            fem_dz = self.head_z_offset if is_fem else 0.0

            sx = self.hair_scale_x
            sy = self.hair_scale_y
            sz = self.hair_scale_z
            ox = self.hair_offset_x
            oy = self.hair_offset_y
            oz = self.hair_offset_z

            if not is_fem and sx == 1.0 and sy == 1.0 and sz == 1.0 and ox == 0.0 and oy == 0.0 and oz == 0.0:
                return verts

            out = []
            for v in verts:
                vx = pivot_x + (v[0] - pivot_x) * sx + ox
                vy = pivot_y + (v[1] - pivot_y) * sy + oy + fem_dy
                vz = pivot_z + (v[2] - pivot_z) * sz + oz + fem_dz
                out.append([vx, vy, vz])
            return out

        # 3. Cabeça 3D
        if is_fem:
            # Cabeça feminina exportada diretamente de Collection 6 (com alinhamento postural no eixo Z)
            head_data = parse_clean_obj_groups(clean_obj, ["Export_cabeca"])
            if head_data:
                v_h = head_data[0].reshape(-1, 11).copy()
                if abs(self.head_z_offset) > 1e-5:
                    v_h[:, 2] += self.head_z_offset
                mesh = TexturedMesh(v_h.flatten().astype(np.float32), head_data[1])
                self.parts.append(CharacterPart("head", mesh, head_tex_id))

            if self.customization.should_render_3d_hair and not self.customization.custom_hair_obj and self.hair_id is None:
                default_fitted = os.path.join(CLOTHING_DIR, "Hair_fitted_116773763268018.obj")
                if os.path.exists(default_fitted):
                    self.customization.custom_hair_obj = default_fitted
        elif self.customization.is_rounded_head:
            rounded_head_obj = os.path.join(MODELS_DIR, "character_head_rounded.obj")
            head_data = parse_clean_obj_groups(rounded_head_obj, [""])
            if head_data:
                mesh = TexturedMesh(head_data[0], head_data[1])
                self.parts.append(CharacterPart("head", mesh, head_tex_id))

            if self.customization.should_render_3d_nose:
                nose_data = parse_clean_obj_groups(clean_obj, ["Export_nariz"])
                if nose_data:
                    mesh = TexturedMesh(nose_data[0], nose_data[1])
                    self.parts.append(CharacterPart("nose", mesh, head_tex_id))

            if self.customization.should_render_3d_hair and not self.customization.custom_hair_obj and self.hair_id is None:
                # Se não fornecido cabelo 3D explícito para rounded, usa o cabelo fitted dedicado se disponível
                default_fitted = os.path.join(CLOTHING_DIR, "Hair_fitted_116773763268018.obj")
                if os.path.exists(default_fitted):
                    self.customization.custom_hair_obj = default_fitted
                else:
                    hair_data = parse_clean_obj_groups(clean_obj, ["Export_cabelo"], vertex_transform=hair_custom_tf)
                    if hair_data:
                        mesh = TexturedMesh(hair_data[0], hair_data[1])
                        self.parts.append(CharacterPart("hair", mesh, head_tex_id))
        else:
            allowed = ["Export_cabeca"]
            if self.customization.should_render_3d_hair and not self.customization.custom_hair_obj and self.hair_id is None:
                allowed.append("Export_cabelo")
            if self.customization.should_render_3d_nose:
                allowed.append("Export_nariz")
            head_data = parse_clean_obj_groups(clean_obj, allowed)
            if head_data:
                mesh = TexturedMesh(head_data[0], head_data[1])
                self.parts.append(CharacterPart("head_blocky", mesh, head_tex_id))

        # 4. Cabelo 3D Customizado / Fitted
        if self.customization.custom_hair_obj and os.path.exists(self.customization.custom_hair_obj):
            hair_data = parse_clean_obj_groups(self.customization.custom_hair_obj, [""], vertex_transform=hair_custom_tf)
            if hair_data:
                hair_tex_path = getattr(self.customization, "custom_hair_tex", None)
                if hair_tex_path and os.path.exists(hair_tex_path):
                    hair_tex_id = upload_texture_rgba(Image.open(hair_tex_path))
                else:
                    hair_rgb = getattr(self.customization, "hair_rgb_255", (92, 62, 54))
                    hair_tex_id = create_solid_texture(hair_rgb)
                self.textures.append(hair_tex_id)
                mesh = TexturedMesh(hair_data[0], hair_data[1])
                self.parts.append(CharacterPart("hair_3d", mesh, hair_tex_id))


        # 5. Pescoço (com coloração de pele e alinhamento postural no eixo Z)
        neck_data = parse_clean_obj_groups(clean_obj, ["Export_pecoco"], default_color=skin_color)
        if neck_data:
            v_n = neck_data[0].reshape(-1, 11).copy()
            if is_fem and abs(self.head_z_offset) > 1e-5:
                v_n[:, 2] += self.head_z_offset
            mesh = TexturedMesh(v_n.flatten().astype(np.float32), neck_data[1])
            self.parts.append(CharacterPart("neck", mesh, self.white_tex_id))

        # 6. Braços e Antebraços (HSR adaptativo por vestuário ativo)
        arm_parts = self._load_arm_parts(skin_color)
        self.parts.extend(arm_parts)

        # 7. Top (Camisa / Suéter / Jaqueta) e Pele Exposta do Tronco
        top_str = str(self.top_id).lower() if self.top_id is not None else "none"
        is_none_top = self.top_id is None or top_str in ("none", "0", "false", "sem", "naked")
        bottom_str = str(self.bottom_id).lower() if self.bottom_id is not None else "none"
        is_none_bottom = self.bottom_id is None or bottom_str in ("none", "0", "false", "sem", "naked")

        # Resolução antecipada da calça ativa e auto-detecção do cós
        waist_geo = None
        bottom_obj_path = None
        if not is_none_bottom:
            if is_fem:
                bottom_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.bottom_id}_female.obj")
                if not is_valid_v2_obj(bottom_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="female")
                        engine.wear(self.bottom_id, output_obj=bottom_obj_path)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: gerando bottom feminino com cage: {e}")
                        bottom_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.bottom_id}.obj")
            else:
                bottom_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.bottom_id}.obj")
                if not is_valid_v2_obj(bottom_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="male")
                        engine.wear(self.bottom_id, output_obj=bottom_obj_path)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: gerando bottom masculino com cage: {e}")

            if bottom_obj_path and os.path.exists(bottom_obj_path):
                waist_geo = detect_bottom_waistband_geometry(bottom_obj_path)

        if waist_geo is not None:
            eff_waist = waist_geo["c_waist"] + self.waist_height_offset
            waist_tilt = waist_geo["tilt"]
        else:
            eff_waist = (1.00 if is_fem else 0.935) + self.waist_height_offset
            waist_tilt = 0.18 if is_fem else 0.15

        # Resolução antecipada do Top com geração automática v2
        top_obj_path = None
        if not is_none_top:
            if is_fem:
                top_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.top_id}_female.obj")
                if not is_valid_v2_obj(top_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="female")
                        engine.wear(self.top_id, output_obj=top_obj_path)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: gerando top feminino com cage: {e}")
                        top_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.top_id}.obj")
            else:
                top_obj_path = os.path.join(MODELS_DIR, f"character_native_{self.top_id}.obj")
                if not is_valid_v2_obj(top_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="male")
                        engine.wear(self.top_id, output_obj=top_obj_path)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: gerando top masculino com cage: {e}")

        eff_hem = (0.985 if is_fem else 0.890) + self.top_hem_offset
        is_open_top = False

        if not is_none_top and top_obj_path and os.path.exists(top_obj_path):
            top_str = str(self.top_id).lower()
            if os.path.exists(CLOTHING_DIR):
                for _cf in os.listdir(CLOTHING_DIR):
                    if str(self.top_id) in _cf:
                        top_str = f"{top_str} {_cf.lower()}"
                        break

            is_bikini_name = any(k in top_str for k in ["bikini", "biquini", "swimsuit", "swim", "bra", "tube", "strapless", "strappy", "regata", "jersey"])
            is_crop_name = any(k in top_str for k in ["crop", "cropped", "tied", "short", "halter", "corset", "cutout", "strap"])
            _hem_zs = []
            _top_verts = []
            with open(top_obj_path, "r", encoding="utf-8", errors="ignore") as _fp:
                for _l in _fp:
                    if _l.startswith("v "):
                        _p = [float(x) for x in _l.strip().split()[1:4]]
                        _top_verts.append(_p)
                        if abs(_p[0]) < 0.15 and _p[2] > 0.50:
                            _hem_zs.append(_p[2])
            if _top_verts:
                _v_arr = np.array(_top_verts)
                _collar_v = len(_v_arr[(_v_arr[:, 2] > 1.40) & (abs(_v_arr[:, 0]) < 0.12)])
                is_open_top = is_bikini_name or (_collar_v < 15)

            if _hem_zs:
                _front_zs = [_p[2] for _p in _top_verts if abs(_p[0]) < 0.15 and _p[1] < 0 and _p[2] > 0.50]
                _front_min = float(min(_front_zs)) if _front_zs else float(min(_hem_zs))
                _det_min = float(min(_hem_zs))
                if is_crop_name or _front_min > 1.01:
                    eff_hem = _front_min + self.top_hem_offset
                else:
                    eff_hem = _det_min + self.top_hem_offset

        if not is_none_top and top_obj_path and os.path.exists(top_obj_path):
                waist_for_tuck = eff_waist if (not is_none_bottom and self.waist_height_offset > 0.02) else None
                def top_tf(raw_v):
                    v1 = transform_sleeve_vertices(
                        raw_v,
                        self.sleeve_width_scale,
                        self.sleeve_length_offset,
                        self.sleeve_shift_x,
                        self.sleeve_shift_y,
                        self.sleeve_shift_z,
                    )
                    return transform_top_hem_vertices(
                        v1,
                        hem_offset=self.top_hem_offset,
                        effective_waist_z=waist_for_tuck,
                        is_female=is_fem,
                    )

                top_data = parse_obj_as_mesh(top_obj_path, vertex_transform=top_tf)
                top_tex_path = find_clothing_texture(self.top_id)
                top_tex_id = upload_texture_rgba(Image.open(top_tex_path)) if top_tex_path else self.white_tex_id
                if top_tex_id != self.white_tex_id:
                    self.textures.append(top_tex_id)
                if top_data:
                    mesh = TexturedMesh(top_data[0], top_data[1])
                    self.parts.append(CharacterPart("top", mesh, top_tex_id))

        # 8. Pele exposta do tronco (Torso e Pelve) com tampas herméticas e auto-detecção
        trunk_part = self._load_trunk_skin(
            clean_obj, skin_color, is_fem, is_none_top, is_none_bottom, eff_waist, eff_hem,
            waist_tilt=waist_tilt, waist_geo=waist_geo, is_open_top=is_open_top
        )
        if trunk_part is not None:
            self.parts.append(trunk_part)

        # 9. Bottom (Calça jeans + botas) ou Pernas se sem calça
        if not is_none_bottom and bottom_obj_path and os.path.exists(bottom_obj_path):
            def hip_tf(raw_v):
                return transform_hip_vertices(
                    raw_v,
                    self.hip_glute_scale,
                    self.hip_width_scale,
                    self.waist_height_offset,
                )

            bottom_data = parse_obj_as_mesh(bottom_obj_path, vertex_transform=hip_tf)
            bottom_tex_path = find_clothing_texture(self.bottom_id)
            bottom_tex_id = upload_texture_rgba(Image.open(bottom_tex_path)) if bottom_tex_path else self.white_tex_id
            if bottom_tex_id != self.white_tex_id:
                self.textures.append(bottom_tex_id)
            if bottom_data:
                mesh = TexturedMesh(bottom_data[0], bottom_data[1])
                self.parts.append(CharacterPart("bottom", mesh, bottom_tex_id))

        else:
            def hip_tf(raw_v):
                return transform_hip_vertices(
                    raw_v,
                    self.hip_glute_scale,
                    self.hip_width_scale,
                    self.waist_height_offset,
                )

            leg_groups = [
                "Export_coxa_esquerda", "Export_coxa_direita",
                "Export_canela_esquerda", "Export_canela_direita",
                "Export_pe_esquerdo", "Export_pe_direito"
            ]
            legs_data = parse_clean_obj_groups(clean_obj, leg_groups, default_color=skin_color, vertex_transform=hip_tf)
            if legs_data:
                mesh = TexturedMesh(legs_data[0], legs_data[1])
                self.parts.append(CharacterPart("legs_skin", mesh, self.white_tex_id))

        # 9.1 HSR do Roblox: com a máscara de todas as peças vestidas, a pele inteira
        # é desenhada e só os triângulos cobertos pelas roupas são removidos.
        self._apply_hsr_skin(clean_obj, skin_color, top_obj_path, bottom_obj_path,
                             is_none_top, is_none_bottom)

        # 9. Tool / Katana / Acessório opcional
        if self.tool_id is not None:
            tool_obj_path = os.path.join(MODELS_DIR, f"character_native_tool_{self.tool_id}.obj")
            if not os.path.exists(tool_obj_path):
                tool_obj_path = os.path.join(MODELS_DIR, f"character_native_katana_{self.tool_id}.obj")
            if not os.path.exists(tool_obj_path):
                try:
                    from src.clothing.wear_engine import RobloxWearEngine
                    engine = RobloxWearEngine()
                    engine.equip_tool(self.tool_id, output_obj=tool_obj_path)
                except Exception as e:
                    print(f"[CharacterModel] Aviso: falha ao gerar tool: {e}")
            tool_data = parse_obj_as_mesh(tool_obj_path)
            tool_tex_path = find_clothing_texture(self.tool_id)
            tool_tex_id = upload_texture_rgba(Image.open(tool_tex_path)) if tool_tex_path else self.white_tex_id
            if tool_tex_id != self.white_tex_id:
                self.textures.append(tool_tex_id)
            if tool_data:
                mesh = TexturedMesh(tool_data[0], tool_data[1])
                self.parts.append(CharacterPart("tool", mesh, tool_tex_id))

        # 10. Constrói malha de depuração da cage (para visualização wireframe em tempo real)
        try:
            from src.rendering.mesh import TexturedMesh
            if is_fem:
                female_cages_path_stage2 = os.path.join(MODELS_DIR, "female_cages_apose_stage2.obj")
                female_cages_path_old = os.path.join(MODELS_DIR, "clothing", "female_cages_apose.obj")
                female_cages_path = female_cages_path_stage2 if os.path.exists(female_cages_path_stage2) else female_cages_path_old
                if os.path.exists(female_cages_path):
                    v_arr = []
                    i_arr = []
                    cage_color = [0.0, 1.0, 0.85]  # Ciano para cages femininas R15 manuais
                    with open(female_cages_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("v "):
                                parts_coord = [float(x) for x in line.split()[1:4]]
                                # female_cages.obj já está em coordenadas OpenGL (X, Y_altura, Z_profundidade)
                                v_arr.extend([parts_coord[0], parts_coord[1], parts_coord[2], 0.0, 1.0, 0.0, 0.0, 0.0, cage_color[0], cage_color[1], cage_color[2]])
                            elif line.startswith("f "):
                                tokens = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                                if len(tokens) == 3:
                                    i_arr.extend(tokens)
                                elif len(tokens) > 3:
                                    for i in range(1, len(tokens) - 1):
                                        i_arr.extend([tokens[0], tokens[i], tokens[i + 1]])
                    v_np = np.array(v_arr, dtype=np.float32)
                    i_np = np.array(i_arr, dtype=np.uint32)
                    self.cage_debug_mesh = TexturedMesh(v_np, i_np)
                else:
                    self.cage_debug_mesh = None
            else:
                cage_path = os.path.join(MODELS_DIR, "roblox_cage_data.npz")
                if os.path.exists(cage_path):
                    cage_data = np.load(cage_path)
                    c_verts = cage_data["cage_verts_rest"]  # (1711, 3)
                    c_faces = cage_data["cage_faces"]       # (2690, 3)
                    v_arr = []
                    cage_color = [0.2, 0.7, 1.0]  # Azul para cage masculina
                    for v in c_verts:
                        # Coordenadas Blender -> OpenGL: (x, z, -y)
                        v_arr.extend([float(v[0]), float(v[2]), float(-v[1]), 0.0, 1.0, 0.0, 0.0, 0.0, cage_color[0], cage_color[1], cage_color[2]])
                    i_arr = []
                    for f in c_faces:
                        i_arr.extend([int(f[0]), int(f[1]), int(f[2])])
                    v_np = np.array(v_arr, dtype=np.float32)
                    i_np = np.array(i_arr, dtype=np.uint32)
                    self.cage_debug_mesh = TexturedMesh(v_np, i_np)
                else:
                    self.cage_debug_mesh = None
        except Exception as e:
            print(f"[CharacterModel] Erro criando malha de depuração da cage: {e}")
            self.cage_debug_mesh = None


    def draw(self, shader: Any, base_model: np.ndarray) -> None:
        """Desenha todas as submalhas do personagem na GPU."""
        import OpenGL.GL as gl

        gl.glDisable(gl.GL_CULL_FACE)
        for part in self.parts:
            part_model = base_model if part.transform is None else base_model @ part.transform
            shader.set_mat4("u_Model", part_model)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, part.texture_id)
            part.mesh.draw()

        # Renderização da Cage em modo Wireframe (Depuração Visual)
        if self.show_cage and self.cage_debug_mesh is not None:
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
            shader.set_mat4("u_Model", base_model)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.white_tex_id if self.white_tex_id else 0)
            self.cage_debug_mesh.draw()
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

        gl.glEnable(gl.GL_CULL_FACE)

    def delete(self) -> None:
        """Libera todos os buffers e texturas OpenGL alocados."""
        import OpenGL.GL as gl

        for part in self.parts:
            if hasattr(part.mesh, "delete"):
                part.mesh.delete()
        self.parts.clear()

        if self.cage_debug_mesh and hasattr(self.cage_debug_mesh, "delete"):
            self.cage_debug_mesh.delete()
            self.cage_debug_mesh = None

        if self.textures:
            try:
                gl.glDeleteTextures(len(self.textures), self.textures)
            except Exception:
                pass
            self.textures.clear()

    def reload(self) -> None:
        """Recarrega todas as malhas e texturas do modelo aplicando a customização atual."""
        self.delete()
        if self.create_mesh:
            self._build()

    def update_customization(
        self,
        customization: Optional[AvatarCustomization] = None,
        top_id: Optional[Union[int, str]] = None,
        bottom_id: Optional[Union[int, str]] = None,
        tool_id: Optional[Union[int, str]] = None,
        hair_id: Optional[Union[int, str]] = None,
    ) -> None:
        """Atualiza a configuração do personagem e recarrega seus recursos na GPU em tempo real."""
        if customization is not None:
            self.customization = customization
            if hasattr(customization, "hair_offset_x"):
                self.hair_offset_x = float(customization.hair_offset_x)
                self.hair_offset_y = float(customization.hair_offset_y)
                self.hair_offset_z = float(customization.hair_offset_z)
                self.hair_scale_x = float(customization.hair_scale_x)
                self.hair_scale_y = float(customization.hair_scale_y)
                self.hair_scale_z = float(customization.hair_scale_z)
        if top_id is not None:
            self.top_id = top_id
        if bottom_id is not None:
            self.bottom_id = bottom_id
        if tool_id is not None:
            self.tool_id = tool_id if tool_id not in ("none", 0, "0", False) else None
        if hair_id is not None:
            self.hair_id = hair_id
            hair_str = str(hair_id).strip()
            if hair_str.lower() in ("none", "0", "false", "sem", "careca", "bald"):
                self.customization.custom_hair_obj = None
                self.customization.custom_hair_tex = None
                self.customization.hair_style = HairStyle.BALD
            else:
                hair_obj_path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{hair_str}.obj")
                if not os.path.exists(hair_obj_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        engine = RobloxWearEngine(body_type="female" if self.customization.is_female else "male")
                        engine.equip_hair(hair_str)
                    except Exception as e:
                        print(f"[CharacterModel] Aviso: falha ao equipar cabelo {hair_str}: {e}")
                if os.path.exists(hair_obj_path):
                    self.customization.custom_hair_obj = hair_obj_path
                    tex_path = find_clothing_texture(hair_str)
                    if tex_path:
                        self.customization.custom_hair_tex = tex_path
        self.reload()


SKIN_PRESETS: Dict[str, Tuple[float, float, float]] = {
    "pale": (0.94, 0.83, 0.76),
    "fair": (0.98, 0.88, 0.82),
    "tan": (0.82, 0.65, 0.52),
    "dark": (0.40, 0.28, 0.22),
    "ebony": (0.25, 0.17, 0.14),
}

OUTFIT_PRESETS: Dict[str, int] = {
    "sweater": 9240757332,
    "knit": 9240757332,
    "boxy": 89475537632859,
    "shirt": 89475537632859,
    "jersey": 97346273111638,
    "regata": 97346273111638,
    "bomber": 72628400373948,
    "office": 133331049150205,
    "social": 133331049150205,
    "brooklyn": 16809419146,
    "cropblack": 101748354579961,
    "crop_black": 101748354579961,
    "tied_crop": 18219837478,
    "dark_brown_crop": 18219837478,
    "kemeja": 85433169602842,
    "kemeja_boxy": 85433169602842,
    "bikini": 96314281401899,
    "tank_top": 137915688957785,
    "strappy": 137915688957785,
    "cross_shirt": 94197227825305,
    "cross": 94197227825305,
    "white_sweater": 16185652164,
    "bow_sweater": 16185652164,
    "dress": 114590471167431,
}

BOTTOM_PRESETS: Dict[str, int] = {
    # 1. Calça jeans preta com botas original (Black Distressed Designer Jeans w/ Boots)
    "jeans": 109837605892174,
    "black_jeans": 109837605892174,
    "dark_jeans": 109837605892174,
    "botas": 109837605892174,
    "boots": 109837605892174,
    "designer": 109837605892174,
    "padrao": 109837605892174,
    "default": 109837605892174,
    "109837605892174": 109837605892174,
    # 2. Nova calça skater baggy azul clara (Vintage Baggy Skater Pants - Light Blue)
    "skater": 137146416353285,
    "skater_pants": 137146416353285,
    "vintage": 137146416353285,
    "baggy": 137146416353285,
    "baggy_jeans": 137146416353285,
    "skate": 137146416353285,
    "azul": 137146416353285,
    "blue": 137146416353285,
    "light_blue": 137146416353285,
    "137146416353285": 137146416353285,
}


def parse_character_cli_args(args: List[str]) -> Tuple[AvatarCustomization, int, int, Optional[int], bool]:
    """Interpreta flags de linha de comando para configuração dinâmica do personagem."""
    body_type = BodyType.MALE
    head_type = HeadType.ROUNDED
    face_opt = FaceOption.ANIME_BLUE
    mouth_style = MouthStyle.ANIME_ORIGINAL
    eye_style = EyeStyle.ANIME
    iris_color = IrisColor.BLUE
    hair_style = HairStyle.ANIME_LONG
    hair_color = HairColor.BRUNETTE
    skin_color = SKIN_PRESETS["pale"]
    top_id = OUTFIT_PRESETS["sweater"]
    bottom_id = 109837605892174
    tool_id: Optional[int] = None
    custom_hair_obj: Optional[str] = None
    custom_hair_tex: Optional[str] = None
    auto_spin = True

    i = 0
    while i < len(args):
        arg = args[i].lower()
        val = args[i + 1].lower() if i + 1 < len(args) and not args[i + 1].startswith("--") else ""

        if arg in ("--female", "--fem", "--woman", "--mulher"):
            body_type = BodyType.FEMALE
            i += 1
            continue
        elif arg in ("--male", "--man", "--homem", "--masculino"):
            body_type = BodyType.MALE
            i += 1
            continue

        if arg in ("--body", "--corpo", "--model") and val:
            if val in ("fem", "female", "feminino", "woman", "mulher"):
                body_type = BodyType.FEMALE
            else:
                body_type = BodyType.MALE
            i += 2
            continue

        elif arg == "--head" and val:
            if "block" in val:
                head_type = HeadType.BLOCKY
            else:
                head_type = HeadType.ROUNDED
            i += 2
            continue

        elif arg == "--mouth" and val:
            for m in MouthStyle:
                if m.value.lower() == val:
                    mouth_style = m
                    break
            i += 2
            continue

        elif arg == "--eyes" and val:
            for e in EyeStyle:
                if e.value.lower() == val:
                    eye_style = e
                    break
            i += 2
            continue

        elif arg == "--iris" and val:
            for c in IrisColor:
                if c.value.lower() == val:
                    iris_color = c
                    break
            i += 2
            continue

        elif arg == "--hair-color" and val:
            for h in HairColor:
                if h.value.lower() == val:
                    hair_color = h
                    break
            i += 2
            continue

        elif arg == "--hair" and val:
            if "bald" in val or "careca" in val:
                hair_style = HairStyle.BALD
            elif "buzz" in val:
                hair_style = HairStyle.BUZZ_CUT
            elif val.isdigit():
                hair_style = HairStyle.ANIME_LONG
                fitted_path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{val}.obj")
                if not os.path.exists(fitted_path):
                    try:
                        from src.clothing.wear_engine import RobloxWearEngine
                        RobloxWearEngine(body_type="female" if body_type == BodyType.FEMALE else "male").equip_hair(val)
                    except Exception:
                        pass
                if os.path.exists(fitted_path):
                    custom_hair_obj = fitted_path
                    custom_hair_tex = find_clothing_texture(val)
            else:
                hair_style = HairStyle.ANIME_LONG
            i += 2
            continue

        elif arg == "--skin" and val:
            if val in SKIN_PRESETS:
                skin_color = SKIN_PRESETS[val]
            i += 2
            continue

        elif arg == "--top" and val:
            if val in ("none", "sem", "naked", "tirar", "0"):
                top_id = None
            elif val in OUTFIT_PRESETS:
                top_id = OUTFIT_PRESETS[val]
            else:
                try:
                    top_id = int(val)
                except ValueError:
                    pass
            i += 2
            continue

        elif arg in ("--bottom", "--calca", "--pants") and val:
            if val in ("none", "sem", "naked", "tirar", "0"):
                bottom_id = None
            elif val in BOTTOM_PRESETS:
                bottom_id = BOTTOM_PRESETS[val]
            else:
                try:
                    bottom_id = int(val)
                except ValueError:
                    pass
            i += 2
            continue


        elif arg == "--tool" and val:
            if val in ("katana", "sword", "ronin"):
                tool_id = 12187348
            else:
                try:
                    tool_id = int(val)
                except ValueError:
                    pass
            i += 2
            continue

        elif arg in ("--no-spin", "--static"):
            auto_spin = False
            i += 1
            continue

        elif arg == "--spin":
            auto_spin = True
            i += 1
            continue

        i += 1

    customization = AvatarCustomization(
        body_type=body_type,
        head_type=head_type,
        face=face_opt,
        hair_style=hair_style,
        hair_color=hair_color,
        skin_color_rgb=skin_color,
        eye_style=eye_style,
        iris_color=iris_color,
        mouth_style=mouth_style,
        custom_hair_obj=custom_hair_obj,
        custom_hair_tex=custom_hair_tex,
    )

    return customization, top_id, bottom_id, tool_id, auto_spin
