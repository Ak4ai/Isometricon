"""Modelo e montagem do personagem 3D do Isometricon.

Carrega malhas modulares (cabeça arredondada/quadrada, cabelo 3D, roupas Roblox,
membros com cor de pele, texturas de rosto e atlas dinâmicos) para renderização
em tempo real com iluminação e controle de câmera.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import math
import hashlib
import os
import threading
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
# Clean A-pose mesh of each body. Both have the same groups, pose and cage topology,
# so skin, HSR and clothing work the same on either (the cages are in wear_engine.BODY_CAGES).
BODY_MESHES = {"female": "character_female_clean_apose_stage2.obj", "male": "character_male_clean_apose.obj"}


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


# Width (m) of the bevel on the torso's four vertical corners, as Blender's Ctrl+B.
TORSO_CHAMFER = 0.015


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


# Results of the heavy geometric steps of a build (layering, HSR), by a hash of their inputs:
# rebuilding after a change that does not touch them (hair, colours, another garment) is quick.
_MEMO: Dict[Tuple[str, str], Any] = {}


def _memo(tag: str, inputs, compute):
    digest = hashlib.sha1()
    for value in inputs:
        if isinstance(value, np.ndarray):
            digest.update(np.ascontiguousarray(value).tobytes())
        elif isinstance(value, (tuple, list)):
            for item in value:
                digest.update(np.ascontiguousarray(item).tobytes() if isinstance(item, np.ndarray) else repr(item).encode())
        else:
            digest.update(repr(value).encode())
    key = (tag, digest.hexdigest())
    if key not in _MEMO:
        if len(_MEMO) >= 64:
            _MEMO.pop(next(iter(_MEMO)))
        _MEMO[key] = compute()
    return _MEMO[key]


# Images of the textures created by a background build (thread-local ``images`` dict):
# they get a placeholder id there and are uploaded on the main thread afterwards.
_DEFERRED_TEXTURES = threading.local()


def upload_texture_rgba(img: Image.Image) -> int:
    """Faz upload de imagem PIL para textura OpenGL 2D com filtro linear e clamp."""
    import OpenGL.GL as gl

    img = img.convert("RGBA")
    pending = getattr(_DEFERRED_TEXTURES, "images", None)
    if pending is not None:
        placeholder = -(len(pending) + 1)
        pending[placeholder] = img
        return placeholder
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
                if "Universal Fitted Clothing v34" in line:
                    return True
                if any(f"Universal Fitted Clothing v{k}" in line for k in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28)):
                    return False  # Regenerate fits made before the geometric HSR fallback.
        return False
    except Exception:
        return False


# Outer top over the other garments: default pull of what still pokes through it (mm)
# and hiding of fully covered triangles. Both the pull and the gap between the layers
# can be changed per character (/skin jaqueta puxar, /skin jaqueta folga).
LAYER_PULL_MM = 15.0
# 5 mm between the layers clears most lapel collisions (trench coat, lab coat) with no visible change.
LAYER_GAP_MM = 5.0
CULL_COVERED = True
DEFAULT_HAIR_ID = "116773763268018"
# Head (with neck and hair) moved forward (m) on each body, plus head_z_offset.
# Relative to the top of its torso the female head sits 2.5 cm further back than the male one.
BODY_HEAD_FORWARD = {"female": 0.025, "male": 0.0}


@dataclass
class CharacterPart:
    """Representa uma parte montada do personagem pronta para renderização."""
    name: str
    mesh: Any  # TexturedMesh
    texture_id: int
    transform: Optional[np.ndarray] = None
    source_obj: Optional[str] = None  # fitted garment OBJ, for the animation's bone binding


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
        hair_offset_x: Optional[float] = None,
        hair_offset_y: Optional[float] = None,
        hair_offset_z: Optional[float] = None,
        hair_scale_x: Optional[float] = None,
        hair_scale_y: Optional[float] = None,
        hair_scale_z: Optional[float] = None,
        outer_top_id: Optional[Union[int, str]] = None,
        shoes_id: Optional[Union[int, str, tuple]] = None,
        async_loading: bool = False,
    ) -> None:
        # With ``async_loading`` every (re)build runs on a background thread and the result is
        # swapped in by ``poll()`` on the main thread, so fitting clothes never freezes the UI.
        self.async_loading = bool(async_loading)
        self.loading_status: str = ""  # shown by the HUD while a build is running
        self._dirty = False
        self._worker = None
        self._worker_result = None
        self.customization = customization if customization is not None else AvatarCustomization(
            head_type=HeadType.ROUNDED,
            mouth_style=MouthStyle.ANIME_ORIGINAL,
        )
        self.top_id = top_id
        self.bottom_id = bottom_id
        # A second top worn over the first (a jacket over a shirt).
        self.outer_top_id = outer_top_id
        self.outer_top_gap_mm = LAYER_GAP_MM  # extra room between the layers: refits the outer top
        # Layered shoes: a bundle id, "left,right" asset ids or one asset id.
        self.shoes_id = shoes_id
        self.outer_top_pull_mm = LAYER_PULL_MM  # pull of what still pokes through it: runtime only
        self.tool_id = tool_id
        self.hair_id = hair_id
        self._resolve_hair()
        self.create_mesh = create_mesh

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
            self.reload()

    def _fitted_hair(self, hair_id) -> Optional[str]:
        """``hair_id`` fitted to this body's head (fitted on first use), or None."""
        from src.clothing.wear_engine import hair_fitted_path
        path = hair_fitted_path(hair_id, self.body)
        if not os.path.exists(path):
            try:
                from src.clothing.wear_engine import RobloxWearEngine
                RobloxWearEngine(body_type=self.body).equip_hair(hair_id)
            except Exception as e:
                print(f"[CharacterModel] Aviso: falha ao equipar cabelo {hair_id}: {e}")
        if not os.path.exists(path):
            # Hairs fitted by hand (no .rbxm) are shared by both bodies.
            path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{hair_id}.obj")
        return path if os.path.exists(path) else None

    def _resolve_hair(self) -> None:
        """Point the customization at ``hair_id`` fitted to this body's head, fitting it on first use."""
        if self.hair_id is None:
            return
        hair_str = str(self.hair_id).strip()
        if hair_str.lower() in ("none", "0", "false", "sem", "careca", "bald"):
            self.customization.custom_hair_obj = None
            self.customization.custom_hair_tex = None
            self.customization.hair_style = HairStyle.BALD
            return
        hair_obj_path = self._fitted_hair(hair_str)
        if hair_obj_path:
            self.customization.custom_hair_obj = hair_obj_path
            tex_path = find_clothing_texture(hair_str)
            if tex_path:
                self.customization.custom_hair_tex = tex_path

    @property
    def head_forward(self) -> float:
        """Forward shift of the head, neck and hair: the body's posture plus /postura."""
        return BODY_HEAD_FORWARD[self.body]

    @property
    def body(self) -> str:
        """'female' or 'male': picks the body mesh, its cages and the fitted-garment caches."""
        return "female" if self.customization.is_female else "male"

    @property
    def clean_obj(self) -> str:
        """Clean A-pose mesh of the current body."""
        return os.path.join(MODELS_DIR, BODY_MESHES[self.body])

    def fitted_path(self, asset_id, suffix: str = "") -> str:
        """Cache of ``asset_id`` fitted to the current body."""
        return os.path.join(MODELS_DIR, f"character_native_{asset_id}{suffix}_{self.body}.obj")

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

        clean_path = self.clean_obj
        side_map = {"left": "esquerdo", "right": "direito"}

        top_str = str(self.top_id).lower() if self.top_id is not None else "none"
        is_none_top = self.top_id is None or top_str in ("none", "0", "false", "sem", "naked")


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
        top_obj_path = self.fitted_path(self.top_id)

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
            upper_arm_visible = not side_long
            forearm_visible = not side_long
            hand_visible = True


            if upper_arm_visible:
                arm_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_braco_superior_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=None
                )
                if arm_data:
                    parts.append(CharacterPart(f"arm_{side}", TexturedMesh(arm_data[0], arm_data[1]), self.white_tex_id))

            # Antebraço (visível em sem manga ou manga curta)
            if forearm_visible:
                ab_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_antebraco_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=None
                )
                if ab_data:
                    v_arr, i_arr = ab_data
                    parts.append(CharacterPart(f"forearm_{side}", TexturedMesh(v_arr, i_arr), self.white_tex_id))

            # Mão (separada no modelo A-pose, com gênero gramatical correto: esquerda/direita)
            if hand_visible:
                hand_side = "esquerda" if side == "left" else "direita"
                hand_data = parse_clean_obj_groups(
                    clean_path,
                    [f"Export_mao_{hand_side}", f"Export_mao_{pt_side}"],
                    default_color=skin_color,
                    vertex_transform=None
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
        v_mat, faces = bevel_torso_corners(v_mat, faces, chamfer_m=TORSO_CHAMFER)

        # Ajuste radial do torso na cintura (sem comando no chat)
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

        y_top_bound = 1.4566 if (is_none_top or is_open_top) else (eff_hem + 0.010)
        tilt = waist_tilt if not is_none_bottom else 0.0
        y_bot_bound = 0.7769 if is_none_bottom else (eff_waist - 0.015)

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
                       "hand_left", "hand_right", "trunk_skin", "legs_skin", "feet_skin")

    def _apply_hsr_skin(self, clean_obj, skin_color, top_obj_path, bottom_obj_path,
                        is_none_top, is_none_bottom, extra_obj_paths=()) -> bool:
        """Replace the rule-based skin cuts with Roblox HSR culling when every worn garment has a mask."""
        from src.clothing.hsr import cull_hidden_triangles, sidecar_path, subdivide
        from src.rendering.mesh import TexturedMesh

        worn = [path for path, none in ((top_obj_path, is_none_top), (bottom_obj_path, is_none_bottom)) if not none]
        worn += [path for path in extra_obj_paths if path]
        if not worn:
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
        from src.clothing.hsr import close_wrapped_limbs
        hidden = np.logical_or.reduce([
            _memo("limbs", (mask, self.body, path, os.path.getmtime(path)),
                  lambda mask=mask, path=path: close_wrapped_limbs(mask.astype(bool), self.body, path))
            for path, (_, mask) in zip(worn, masks)])

        hip_tf = arm_tf = None

        groups = [("trunk_skin", ["Export_torso", "Export_pelve"], hip_tf),
                  ("legs_skin", ["Export_coxa_esquerda", "Export_coxa_direita", "Export_canela_esquerda",
                                 "Export_canela_direita"]
                   + ([] if getattr(self, "_hide_feet", False) else ["Export_pe_esquerdo", "Export_pe_direito"]), hip_tf)]
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
                faces = _memo("hsr", (rows[:, :3], faces, cage_points, hidden, cage_faces),
                              lambda: cull_hidden_triangles(rows[:, :3], faces, cage_points, hidden, cage_faces))
            if len(faces):
                new_parts.append(CharacterPart(name, TexturedMesh(vertices.astype(np.float32), faces.astype(np.uint32).ravel()),
                                               self.white_tex_id))
        for part in [p for p in self.parts if p.name in self.SKIN_PART_NAMES]:
            part.mesh.delete()
            self.parts.remove(part)
        self.parts.extend(new_parts)
        print(f"[HSR] Pele recortada pelas máscaras de {len(worn)} peça(s): {int(hidden.sum())} pontos da cage cobertos")
        return True

    def _top_over_pants(self, top_obj_path, is_none_bottom):
        """A coat, sweater or dress worn as the top is fitted over the pants' outer cage."""
        from src.clothing.layer_clearance import OUTER_TOP_TYPES, fitted_asset_type
        if is_none_bottom or fitted_asset_type(top_obj_path) not in OUTER_TOP_TYPES:
            return top_obj_path
        gap_mm = int(round(self.outer_top_gap_mm))
        path = self.fitted_path(self.top_id, f"_over_{self.bottom_id}{f'_g{gap_mm}' if gap_mm else ''}")
        if not is_valid_v2_obj(path):
            try:
                from src.clothing.wear_engine import RobloxWearEngine
                engine = RobloxWearEngine(body_type=self.body)
                engine.layer_under_asset = [self.bottom_id]
                engine.layer_gap = gap_mm / 1000.0
                engine.wear(self.top_id, output_obj=path)
            except Exception as e:
                print(f"[CharacterModel] Aviso: top sobre a calça {self.top_id}/{self.bottom_id}: {e}")
                return top_obj_path
        return path if is_valid_v2_obj(path) else top_obj_path

    def _add_shoes(self, vertex_transform):
        """Wear the layered shoes (each foot fitted with its own cages); returns their fitted OBJ paths."""
        self._hide_feet = False
        if self.shoes_id is None:
            return []
        from src.clothing.wear_engine import RobloxWearEngine
        from src.rendering.mesh import TexturedMesh
        engine = RobloxWearEngine(body_type=self.body)
        paths = []
        for asset_id in engine.resolve_shoe_pair(self.shoes_id):
            path = self.fitted_path(asset_id)
            if not is_valid_v2_obj(path):
                try:
                    engine.wear(asset_id, output_obj=path)
                except Exception as e:
                    print(f"[CharacterModel] Aviso: calçado {asset_id}: {e}")
                    continue
            data = parse_obj_as_mesh(path, vertex_transform=vertex_transform)
            if not data:
                continue
            texture_path = find_clothing_texture(asset_id)
            texture_id = upload_texture_rgba(Image.open(texture_path)) if texture_path else self.white_tex_id
            if texture_id != self.white_tex_id:
                self.textures.append(texture_id)
            self.parts.append(CharacterPart(f"shoe_{asset_id}", TexturedMesh(data[0], data[1]), texture_id, source_obj=path))
            paths.append(path)
        if paths:
            # The shoes replace the feet: our block feet are wider than a heel or a slim
            # sneaker and would poke through them (without HSR they are a separate part).
            for part in [p for p in self.parts if p.name == "feet_skin"]:
                part.mesh.delete()
                self.parts.remove(part)
        self._hide_feet = bool(paths)
        return paths

    def _add_outer_top(self, vertex_transform):
        """Wear ``outer_top_id`` over the other garments; returns its fitted OBJ path or None."""
        if self.outer_top_id is None:
            return None
        from src.clothing.layer_clearance import body_cage_from_sidecars, covered_vertices, pull_inner_layer
        from src.rendering.mesh import TexturedMesh
        # Fitted over the outer cages of the top and the pants, as Roblox layers clothing:
        # one cache per combination.
        under = [i for i in (self.top_id, self.bottom_id) if i is not None and str(i).lower() not in ("none", "0")]
        gap_mm = int(round(self.outer_top_gap_mm))
        suffix = "".join(f"_over_{i}" for i in under) + (f"_g{gap_mm}" if gap_mm else "")
        path = self.fitted_path(self.outer_top_id, suffix)
        if not is_valid_v2_obj(path):
            try:
                from src.clothing.wear_engine import RobloxWearEngine
                engine = RobloxWearEngine(body_type=self.body)
                engine.layer_under_asset = under
                engine.layer_gap = gap_mm / 1000.0
                engine.wear(self.outer_top_id, output_obj=path)
            except Exception as e:
                print(f"[CharacterModel] Aviso: gerando peça de cima {self.outer_top_id}: {e}")
                return None
        data = parse_obj_as_mesh(path, vertex_transform=vertex_transform)
        if not data:
            return None
        outer = data[0].reshape(-1, 11)[:, :3]
        body = body_cage_from_sidecars(path)
        for part in [p for p in self.parts if p.name in self._garment_buffers]:
            vertices, indices = self._garment_buffers[part.name]
            rows = np.asarray(vertices, dtype=np.float32).reshape(-1, 11).copy()
            pulled = _memo("pull", (rows[:, :3], outer, data[1], self.outer_top_pull_mm, body),
                           lambda: pull_inner_layer(rows[:, :3], outer, data[1],
                                                    clearance=self.outer_top_pull_mm / 1000.0, body=body))
            faces = np.asarray(indices).reshape(-1, 3)
            # Triangles covered by the outer top at all three corners are hidden, like HSR
            # does for skin: where a ray misses the outer cloth a pull alone can leave a leak.
            hidden = _memo("covered", (pulled, outer, data[1], body),
                           lambda: covered_vertices(pulled, outer, data[1], body=body))[faces].all(1)                 if CULL_COVERED else None
            if not np.allclose(pulled, rows[:, :3]) or (hidden is not None and hidden.any()):
                rows[:, :3] = pulled
                kept = faces if hidden is None else faces[~hidden]
                part.mesh.delete()
                part.mesh = TexturedMesh(rows.ravel(), kept.ravel().astype(np.uint32))
        texture_path = find_clothing_texture(self.outer_top_id)
        texture_id = upload_texture_rgba(Image.open(texture_path)) if texture_path else self.white_tex_id
        if texture_id != self.white_tex_id:
            self.textures.append(texture_id)
        self.parts.append(CharacterPart("outer_top", TexturedMesh(data[0], data[1]), texture_id, source_obj=path))
        return path

    def _build(self) -> None:
        """Carrega e monta todas as malhas e texturas do personagem."""
        from src.rendering.mesh import TexturedMesh

        self._garment_buffers = {}  # CPU copies of the top/pants buffers, for the outer top's layering

        # 1. Textura neutra branca (1x1) para membros com vertex color
        white_img = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
        self.white_tex_id = upload_texture_rgba(white_img)
        self.textures.append(self.white_tex_id)

        is_fem = self.customization.is_female
        clean_obj = self.clean_obj
        skin_color = list(self.customization.skin_color_rgb)

        # 1.1 Resolução de Cabelo Customizado por ID Roblox
        self._resolve_hair()

        # 2. Textura Atlas dinâmica da cabeça (Rosto, olhos, boca e franja 2D)
        atlas_builder = HeadAtlasBuilder()
        head_img = atlas_builder.build_atlas(self.customization)
        head_tex_id = upload_texture_rgba(head_img)
        self.textures.append(head_tex_id)

        # Transformação completa de cabelo: escala nos eixos X, Y, Z ao redor do centro da cabeça (0, 1.70, 0),
        # soma dos offsets manuais do usuário (X, Y, Z) e alinhamento postural da cabeça
        def hair_custom_tf(verts):
            pivot_x = 0.0
            pivot_y = 1.70
            pivot_z = 0.0
            head_dy = 0.0
            head_dz = self.head_forward

            sx = self.hair_scale_x
            sy = self.hair_scale_y
            sz = self.hair_scale_z
            ox = self.hair_offset_x
            oy = self.hair_offset_y
            oz = self.hair_offset_z

            if sx == 1.0 and sy == 1.0 and sz == 1.0 and ox == 0.0 and oy == 0.0 and oz == 0.0 and head_dz == 0.0:
                return verts

            out = []
            for v in verts:
                vx = pivot_x + (v[0] - pivot_x) * sx + ox
                vy = pivot_y + (v[1] - pivot_y) * sy + oy + head_dy
                vz = pivot_z + (v[2] - pivot_z) * sz + oz + head_dz
                out.append([vx, vy, vz])
            return out

        # 3. Cabeça 3D (no modelo limpo de cada corpo, com alinhamento postural no eixo Z)
        head_data = parse_clean_obj_groups(clean_obj, ["Export_cabeca"])
        if head_data:
            v_h = head_data[0].reshape(-1, 11).copy()
            if abs(self.head_forward) > 1e-5:
                v_h[:, 2] += self.head_forward
            mesh = TexturedMesh(v_h.flatten().astype(np.float32), head_data[1])
            self.parts.append(CharacterPart("head", mesh, head_tex_id))

        current = self.customization.custom_hair_obj
        if current and os.path.basename(current).startswith(f"Hair_fitted_{DEFAULT_HAIR_ID}"):
            self.customization.custom_hair_obj = None  # the default hair of the body shown before
        if self.customization.should_render_3d_hair and not self.customization.custom_hair_obj and self.hair_id is None:
            # Default hair, fitted to this body's head; it keeps the customization's hair colour.
            self.customization.custom_hair_obj = self._fitted_hair(DEFAULT_HAIR_ID)

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
            if abs(self.head_forward) > 1e-5:
                v_n[:, 2] += self.head_forward
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
            bottom_obj_path = self.fitted_path(self.bottom_id)
            if not is_valid_v2_obj(bottom_obj_path):
                try:
                    from src.clothing.wear_engine import RobloxWearEngine
                    engine = RobloxWearEngine(body_type=self.body)
                    engine.wear(self.bottom_id, output_obj=bottom_obj_path)
                except Exception as e:
                    print(f"[CharacterModel] Aviso: gerando bottom com cage: {e}")

            if bottom_obj_path and os.path.exists(bottom_obj_path):
                waist_geo = detect_bottom_waistband_geometry(bottom_obj_path)

        if waist_geo is not None:
            eff_waist = waist_geo["c_waist"]
            waist_tilt = waist_geo["tilt"]
        else:
            eff_waist = 1.00
            waist_tilt = 0.18

        # Resolução antecipada do Top com geração automática v2
        top_obj_path = None
        if not is_none_top:
            top_obj_path = self.fitted_path(self.top_id)
            if not is_valid_v2_obj(top_obj_path):
                try:
                    from src.clothing.wear_engine import RobloxWearEngine
                    engine = RobloxWearEngine(body_type=self.body)
                    engine.wear(self.top_id, output_obj=top_obj_path)
                except Exception as e:
                    print(f"[CharacterModel] Aviso: gerando top com cage: {e}")
            top_obj_path = self._top_over_pants(top_obj_path, is_none_bottom)

        eff_hem = 0.985
        is_open_top = False
        top_layer = None

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
                    eff_hem = _front_min
                else:
                    eff_hem = _det_min

        if not is_none_top and top_obj_path and os.path.exists(top_obj_path):
                top_data = parse_obj_as_mesh(top_obj_path)
                top_layer = top_data
                top_tex_path = find_clothing_texture(self.top_id)
                top_tex_id = upload_texture_rgba(Image.open(top_tex_path)) if top_tex_path else self.white_tex_id
                if top_tex_id != self.white_tex_id:
                    self.textures.append(top_tex_id)
                if top_data:
                    mesh = TexturedMesh(top_data[0], top_data[1])
                    self.parts.append(CharacterPart("top", mesh, top_tex_id, source_obj=top_obj_path))
                    self._garment_buffers["top"] = top_data

        # 8. Pele exposta do tronco (Torso e Pelve) com tampas herméticas e auto-detecção
        trunk_part = self._load_trunk_skin(
            clean_obj, skin_color, is_fem, is_none_top, is_none_bottom, eff_waist, eff_hem,
            waist_tilt=waist_tilt, waist_geo=waist_geo, is_open_top=is_open_top
        )
        if trunk_part is not None:
            self.parts.append(trunk_part)

        # 9. Bottom (Calça jeans + botas) ou Pernas se sem calça
        if not is_none_bottom and bottom_obj_path and os.path.exists(bottom_obj_path):
            bottom_data = parse_obj_as_mesh(bottom_obj_path)
            if bottom_data and top_layer:
                # Top and pants are fitted to the body separately; wrap the outer one over the other.
                from src.clothing.layer_clearance import (body_cage_from_sidecars, fitted_asset_type,
                                                          layer_top_and_bottom)
                top_rows = top_layer[0].reshape(-1, 11).copy()
                rows = bottom_data[0].reshape(-1, 11).copy()
                layer_body = body_cage_from_sidecars(top_obj_path, bottom_obj_path)
                top_type = fitted_asset_type(top_obj_path)
                new_top, new_bottom = _memo(
                    "layers", (top_rows[:, :3], top_layer[1], rows[:, :3], bottom_data[1], top_type, layer_body),
                    lambda: layer_top_and_bottom(top_rows[:, :3], top_layer[1], rows[:, :3], bottom_data[1],
                                                 top_type, body=layer_body))
                rows[:, :3] = new_bottom
                bottom_data = (rows.ravel().astype(np.float32), bottom_data[1])
                if not np.array_equal(new_top, top_rows[:, :3]):
                    top_rows[:, :3] = new_top
                    for part in self.parts:
                        if part.name == "top":
                            part.mesh.delete()
                            part.mesh = TexturedMesh(top_rows.ravel().astype(np.float32), top_layer[1])
                            self._garment_buffers["top"] = (top_rows.ravel().astype(np.float32), top_layer[1])
            bottom_tex_path = find_clothing_texture(self.bottom_id)
            bottom_tex_id = upload_texture_rgba(Image.open(bottom_tex_path)) if bottom_tex_path else self.white_tex_id
            if bottom_tex_id != self.white_tex_id:
                self.textures.append(bottom_tex_id)
            if bottom_data:
                mesh = TexturedMesh(bottom_data[0], bottom_data[1])
                self.parts.append(CharacterPart("bottom", mesh, bottom_tex_id, source_obj=bottom_obj_path))
                self._garment_buffers["bottom"] = bottom_data
            # Pants that end at the ankle leave the feet bare. Pants reaching the floor
            # cover them (boots, tights, long hems), where the blocky feet would poke out.
            reaches_floor = bool(bottom_data) and float(bottom_data[0].reshape(-1, 11)[:, 1].min()) < 0.05
            feet_data = None if reaches_floor else parse_clean_obj_groups(
                clean_obj, ["Export_pe_esquerdo", "Export_pe_direito"], default_color=skin_color)
            if feet_data:
                self.parts.append(CharacterPart("feet_skin", TexturedMesh(feet_data[0], feet_data[1]), self.white_tex_id))

        else:
            leg_groups = [
                "Export_coxa_esquerda", "Export_coxa_direita",
                "Export_canela_esquerda", "Export_canela_direita",
                "Export_pe_esquerdo", "Export_pe_direito"
            ]
            legs_data = parse_clean_obj_groups(clean_obj, leg_groups, default_color=skin_color)
            if legs_data:
                mesh = TexturedMesh(legs_data[0], legs_data[1])
                self.parts.append(CharacterPart("legs_skin", mesh, self.white_tex_id))

        # 9.0 Peça por cima do top (jaqueta sobre camisa): fica por fora de tudo, e o
        # que as peças de baixo tiverem furando é puxado para baixo dela.
        outer_obj_path = self._add_outer_top(None)
        shoe_paths = self._add_shoes(None)

        # 9.1 HSR do Roblox: com a máscara de todas as peças vestidas, a pele inteira
        # é desenhada e só os triângulos cobertos pelas roupas são removidos.
        self._apply_hsr_skin(clean_obj, skin_color, top_obj_path, bottom_obj_path,
                             is_none_top, is_none_bottom, extra_obj_paths=(outer_obj_path, *shoe_paths))

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
            from src.clothing.wear_engine import BODY_CAGES
            cage_path = os.path.join(MODELS_DIR, BODY_CAGES[self.body])
            self.cage_debug_mesh = None
            if os.path.exists(cage_path):
                v_arr = []
                i_arr = []
                cage_color = [0.0, 1.0, 0.85]  # Ciano para as cages R15
                with open(cage_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("v "):
                            parts_coord = [float(x) for x in line.split()[1:4]]
                            # As cages já estão em coordenadas OpenGL (X, Y_altura, Z_profundidade)
                            v_arr.extend([parts_coord[0], parts_coord[1], parts_coord[2], 0.0, 1.0, 0.0, 0.0, 0.0, cage_color[0], cage_color[1], cage_color[2]])
                        elif line.startswith("f "):
                            tokens = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                            for i in range(1, len(tokens) - 1):
                                i_arr.extend([tokens[0], tokens[i], tokens[i + 1]])
                self.cage_debug_mesh = TexturedMesh(np.array(v_arr, dtype=np.float32), np.array(i_arr, dtype=np.uint32))
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
        if self.create_mesh and self.async_loading:
            self._dirty = True  # built in the background, swapped in by poll()
            self.loading_status = self.loading_status or "Atualizando personagem..."
            return
        self.delete()
        if self.create_mesh:
            self._build()

    @property
    def is_loading(self) -> bool:
        return self._dirty or self._worker is not None

    def _needs_fitting(self) -> bool:
        """Whether the top or the pants still have no fitted cache for this body (the slow case)."""
        ids = [i for i in (self.top_id, self.bottom_id) if i is not None and str(i).lower() not in
               ("none", "0", "false", "sem", "naked")]
        return any(not is_valid_v2_obj(self.fitted_path(i)) for i in ids)

    def poll(self) -> None:
        """Main thread, every frame: start pending background builds and swap in finished ones."""
        if self._worker is not None:
            if self._worker.is_alive():
                return
            self._worker = None
            builder, images, error = self._worker_result
            self._worker_result = None
            if error is not None:
                print(f"[CharacterModel] Erro montando o personagem: {error}")
            else:
                ids = {key: upload_texture_rgba(image) for key, image in images.items()}
                self.delete()
                for part in builder.parts:
                    part.texture_id = ids.get(part.texture_id, part.texture_id)
                self.parts = builder.parts
                self.textures = [ids.get(t, t) for t in builder.textures]
                self.white_tex_id = ids.get(builder.white_tex_id, builder.white_tex_id)
                self.cage_debug_mesh = builder.cage_debug_mesh
                self._garment_buffers = builder._garment_buffers
                self._hide_feet = getattr(builder, "_hide_feet", False)
        if not self._dirty:
            self.loading_status = ""
            return
        self._dirty = False
        self.loading_status = ("Ajustando roupas ao corpo..." if self._needs_fitting() else "Atualizando personagem...")
        import copy
        builder = copy.copy(self)  # a snapshot of the ids and adjustments, with its own parts
        builder.async_loading = False
        builder.parts, builder.textures = [], []
        builder.white_tex_id, builder.cage_debug_mesh = None, None

        def run():
            from src.rendering.mesh import DEFERRED
            DEFERRED.on = True
            _DEFERRED_TEXTURES.images = {}
            try:
                builder._build()
                self._worker_result = (builder, _DEFERRED_TEXTURES.images, None)
            except Exception as exc:  # the old model stays on screen
                self._worker_result = (None, {}, exc)

        self._worker = threading.Thread(target=run, daemon=True, name="CharacterBuild")
        self._worker.start()

    def update_customization(
        self,
        customization: Optional[AvatarCustomization] = None,
        top_id: Optional[Union[int, str]] = None,
        bottom_id: Optional[Union[int, str]] = None,
        tool_id: Optional[Union[int, str]] = None,
        hair_id: Optional[Union[int, str]] = None,
        outer_top_id: Optional[Union[int, str]] = None,
        shoes_id: Optional[Union[int, str, tuple]] = None,
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
        if outer_top_id is not None:
            self.outer_top_id = None if str(outer_top_id).lower() in ("none", "0", "false", "sem") else outer_top_id
        if shoes_id is not None:
            self.shoes_id = None if str(shoes_id).lower() in ("none", "0", "false", "sem") else shoes_id
        if tool_id is not None:
            self.tool_id = tool_id if tool_id not in ("none", 0, "0", False) else None
        if hair_id is not None:
            self.hair_id = hair_id
            if not self.async_loading:
                self._resolve_hair()  # may fit the hair; a background build does it itself
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
                from src.clothing.wear_engine import RobloxWearEngine, hair_fitted_path
                body = "female" if body_type == BodyType.FEMALE else "male"
                fitted_path = hair_fitted_path(val, body)
                if not os.path.exists(fitted_path):
                    try:
                        RobloxWearEngine(body_type=body).equip_hair(val)
                    except Exception:
                        pass
                if not os.path.exists(fitted_path):
                    fitted_path = os.path.join(CLOTHING_DIR, f"Hair_fitted_{val}.obj")
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
