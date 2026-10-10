"""Motor Nativo de Vestuário Roblox (100% Python / NumPy, Independente do Blender).

Executa todo o pipeline geométrico em tempo de execução para qualquer PC:
1. Download e decodificação Draco / FileMesh v4 + texturas PNG via HTTP.
2. Identificação topológica robusta (Midline Crossing) e classificação de mangas.
3. Ajuste proporcional anatômico (bainha, cintura, gola e ombros) via Hermite/Smoothstep.
4. Deformação de superfície baricêntrica (Barycentric Cage Wrap) na Roblox_Inner_Cage_Universal.
5. HSR analítico com corte geométrico de planos (Sutherland-Hodgman) para os braços.
6. Ajuste de calças e calçados (cintura até sola do sapato).
7. Geração direta de malhas para OpenGL (ModularCharacter) e exportação OBJ.
"""

import os
import sys
import re
import math
import time
import json
import gzip
import urllib.request
import numpy as np

# Importa decodificadores do projeto
from scripts.import_roblox_clothing import fetch_roblox_asset, decode_roblox_mesh_to_obj

TOP_ASSET_TYPES = {64, 65, 67, 68}        # T-Shirt, Shirt, Jacket, Sweater
BOTTOM_ASSET_TYPES = {66, 69, 70, 71, 72} # Pants, Shorts, LeftShoe, RightShoe, Dress/Skirt
# Shoes: rigid up to the ankle (engine height), cage-fitted above it over this blend height.
SHOE_RIGID_TOP = 0.10
SHOE_BLEND_HEIGHT = 0.08
# R15 outer cages of each body, in assets/models. Both bodies share the A-pose and the
# cage topology and UVs (the male cage was built from the female one), so a garment is
# fitted to either the same way.
BODY_CAGES = {"female": "female_cages_apose_stage2.obj", "male": "male_cages_apose.obj"}


def body_parts_path(fitted_obj) -> str:
    """Sidecar with the body cage part each vertex of a fitted garment is bound to."""
    return os.path.splitext(fitted_obj)[0] + "_parts.npy"


TOGETHER_AT, TOGETHER_APART = 1e-5, 0.001  # how close two vertices are in the garment to be one point, and metres apart after the fit to be put back
FAN_COPIES = 8  # copies of one point, at least, for it to be the middle of a fan (a seam of the UVs has two to four)


def keep_together(source: np.ndarray, fitted: np.ndarray) -> np.ndarray:
    """The fitted vertices, with those that are one point in the garment as it was made brought back to one point.

    A garment closes its armholes and its neck from inside with a fan of triangles, each with its own copy of the
    vertex in the middle. The fit moves a vertex by more than where it is (its normal, its triangle), and sent
    those copies apart: the fan came out as a burst of spikes inside the sleeve, across the arm. They go to the
    middle of where the fit sent them.

    Only the middles of fans (FAN_COPIES copies or more). The fit also parts, by centimetres, the two to four
    copies of many vertices along the UV seams; putting those together too was tried and measured (the robustness
    battery, female body): 12 garments worse, 8 better. The copies follow different bones, and joined at the fit
    they pull the cloth further when the body moves (Realistic White Pigeon: 604 -> 16830 cm2 stretched).
    """
    source = np.asarray(source, dtype=np.float64)
    fitted = np.array(fitted, dtype=np.float64, copy=True)
    if len(source) != len(fitted) or not len(source):
        return fitted
    _, group, counts = np.unique(np.round(source / TOGETHER_AT).astype(np.int64), axis=0, return_inverse=True, return_counts=True)
    group = group.ravel()
    total = np.zeros((len(counts), 3))
    np.add.at(total, group, fitted)
    middle = total / counts[:, None]
    apart = np.zeros(len(counts))
    np.maximum.at(apart, group, np.linalg.norm(fitted - middle[group], axis=1))
    moved = (counts[group] >= FAN_COPIES) & (apart[group] > TOGETHER_APART)
    fitted[moved] = middle[group[moved]]
    return fitted


def hair_fitted_path(asset_id, body_type) -> str:
    """Hair (or hat) ``asset_id`` fitted to the head of ``body_type``."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "assets", "models", "clothing", f"Hair_fitted_{asset_id}_{body_name(body_type)}.obj")


def body_name(body_type) -> str:
    """'female' or 'male' for any of the spellings the console and the CLI accept."""
    return "female" if str(body_type).lower() in ("female", "feminino", "fem", "f", "mulher", "woman") else "male"

# Tabela canônica de 24 rotações ortogonais do formato binário da Roblox (CFrame special cases)
# Os ângulos estão em graus e são aplicados na ordem Y -> X -> Z
ROBLOX_ROTATION_TABLE = {
    0x02: (0, 0, 0),
    0x03: (90, 0, 0),
    0x05: (0, 180, 180),
    0x06: (-90, 0, 0),
    0x07: (0, 180, 90),
    0x09: (0, 90, 90),
    0x0a: (0, 0, 90),
    0x0c: (0, -90, 90),
    0x0d: (-90, -90, 0),
    0x0e: (0, -90, 0),
    0x10: (90, -90, 0),
    0x11: (0, 90, 180),
    0x14: (0, 180, 0),
    0x15: (-90, -180, 0),
    0x17: (0, 0, 180),
    0x18: (90, 180, 0),
    0x19: (0, 0, -90),
    0x1b: (0, -90, -90),
    0x1c: (0, -180, -90),
    0x1e: (0, 90, -90),
    0x1f: (90, 90, 0),
    0x20: (0, 90, 0),
    0x22: (-90, 90, 0),
    0x23: (0, -90, 180),
}

def decode_roblox_float_be(b: bytes) -> float:
    """Decodifica um float 32-bit no formato proprietário da Roblox (big-endian com rotação de bits)."""
    import struct
    u32 = struct.unpack(">I", b)[0]
    sign = (u32 & 1) << 31
    rest = (u32 >> 1) & 0x7FFFFFFF
    ieee = sign | rest
    return struct.unpack(">f", struct.pack(">I", ieee))[0]

def euler_yxz_to_matrix(y_deg: float, x_deg: float, z_deg: float) -> np.ndarray:
    """Converte ângulos de Euler Roblox (ordem Y -> X -> Z) em matriz de rotação ortogonal 3x3."""
    cy, sy = math.cos(math.radians(y_deg)), math.sin(math.radians(y_deg))
    cx, sx = math.cos(math.radians(x_deg)), math.sin(math.radians(x_deg))
    cz, sz = math.cos(math.radians(z_deg)), math.sin(math.radians(z_deg))

    Ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float64)
    Rz = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)

    return Ry @ Rx @ Rz

class SpatialGrid3D:
    """Estrutura de aceleração espacial 3D uniforme em NumPy puro."""
    def __init__(self, cell_size=0.10):
        self.cell_size = cell_size
        self.grid = {}

    def _cell_coord(self, pt):
        return tuple(np.floor(pt / self.cell_size).astype(int))

    def build(self, centroids):
        self.centroids = np.asarray(centroids, dtype=np.float64)
        self.grid.clear()
        for idx, c in enumerate(centroids):
            cell = self._cell_coord(c)
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append(idx)

    def query_nearest_candidates(self, pt, k_neighbors=1, fallback_top_k=8):
        cx, cy, cz = self._cell_coord(pt)
        candidates = []
        for dx in range(-k_neighbors, k_neighbors + 1):
            for dy in range(-k_neighbors, k_neighbors + 1):
                for dz in range(-k_neighbors, k_neighbors + 1):
                    cell = (cx + dx, cy + dy, cz + dz)
                    if cell in self.grid:
                        candidates.extend(self.grid[cell])
        if candidates:
            return candidates

        # Expansão progressiva para células adjacentes (k + 1, k + 2)
        for extra in (1, 2):
            k = k_neighbors + extra
            for dx in range(-k, k + 1):
                for dy in range(-k, k + 1):
                    for dz in range(-k, k + 1):
                        if max(abs(dx), abs(dy), abs(dz)) == k:
                            cell = (cx + dx, cy + dy, cz + dz)
                            if cell in self.grid:
                                candidates.extend(self.grid[cell])
            if candidates:
                return candidates

        # Fallback instantâneo em C via NumPy para vértices fora do grid (ex: babados, saias largas):
        # Seleciona os fallback_top_k triângulos com centróides mais próximos em ~10 microsegundos
        # em vez de forçar um loop quadrático de milhares de iterações em Python puro!
        if self.centroids is not None and len(self.centroids) > 0:
            diff = self.centroids - pt
            dists_sq = np.sum(diff * diff, axis=1)
            k = min(fallback_top_k, len(self.centroids))
            top_k_indices = np.argpartition(dists_sq, k - 1)[:k]
            return top_k_indices.tolist()

        return candidates

def closest_point_on_triangle(p, a, b, c):
    """Calcula o ponto mais próximo q no triângulo (a, b, c) ao ponto p e as coordenadas baricêntricas."""
    ab = b - a
    ac = c - a
    ap = p - a

    d1 = np.dot(ab, ap)
    d2 = np.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a, 1.0, 0.0, 0.0

    bp = p - b
    d3 = np.dot(ab, bp)
    d4 = np.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b, 0.0, 1.0, 0.0

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return a + v * ab, 1.0 - v, v, 0.0

    cp = p - c
    d5 = np.dot(ab, cp)
    d6 = np.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c, 0.0, 0.0, 1.0

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return a + w * ac, 1.0 - w, 0.0, w

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return b + w * (c - b), 0.0, 1.0 - w, w

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    u = 1.0 - v - w
    return a + ab * v + ac * w, u, v, w

def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)

def slice_mesh_below_z(vertices, faces, plane_z):
    """Secciona uma malha triangular no plano z = plane_z, preservando a porção onde z <= plane_z."""
    new_verts = list(vertices.copy())
    new_faces = []
    cut_segments = []
    edge_split_cache = {}

    def get_intersection(i0, i1):
        key = tuple(sorted([i0, i1]))
        if key in edge_split_cache:
            return edge_split_cache[key]
        p0 = new_verts[i0]
        p1 = new_verts[i1]
        t = (plane_z - p0[2]) / (p1[2] - p0[2] + 1e-12)
        p_int = p0 + t * (p1 - p0)
        p_int[2] = plane_z
        new_idx = len(new_verts)
        new_verts.append(p_int)
        edge_split_cache[key] = new_idx
        return new_idx

    for f in faces:
        v = [vertices[idx] for idx in f]
        below = [v[i][2] <= plane_z for i in range(3)]
        num_below = sum(below)

        if num_below == 3:
            new_faces.append(list(f))
        elif num_below == 0:
            continue
        elif num_below == 1:
            i_below = below.index(True)
            v_b = f[i_below]
            v_a1 = f[(i_below + 1) % 3]
            v_a2 = f[(i_below + 2) % 3]
            int1 = get_intersection(v_b, v_a1)
            int2 = get_intersection(v_b, v_a2)
            new_faces.append([v_b, int1, int2])
            cut_segments.append((int1, int2))
        elif num_below == 2:
            i_above = below.index(False)
            v_a = f[i_above]
            v_b1 = f[(i_above + 1) % 3]
            v_b2 = f[(i_above + 2) % 3]
            int1 = get_intersection(v_b1, v_a)
            int2 = get_intersection(v_b2, v_a)
            new_faces.append([v_b1, v_b2, int1])
            new_faces.append([v_b2, int2, int1])
            cut_segments.append((int2, int1))

    if cut_segments:
        adj = {s: e for s, e in cut_segments}
        start = cut_segments[0][0]
        loop = [start]
        curr = adj.get(start)
        while curr is not None and curr != start and len(loop) < len(cut_segments):
            loop.append(curr)
            curr = adj.get(curr)

        if len(loop) >= 3:
            center = np.mean([new_verts[i] for i in loop], axis=0)
            center_idx = len(new_verts)
            new_verts.append(center)
            for i in range(len(loop)):
                v0 = loop[i]
                v1 = loop[(i + 1) % len(loop)]
                new_faces.append([center_idx, v0, v1])

    used_indices = sorted(list(set(idx for f in new_faces for idx in f)))
    old_to_new = {old: new for new, old in enumerate(used_indices)}
    compact_verts = np.array([new_verts[i] for i in used_indices], dtype=np.float32)
    compact_faces = np.array([[old_to_new[idx] for idx in f] for f in new_faces], dtype=np.int32)

    return compact_verts, compact_faces


def load_r15_cages(obj_path, is_source_cage: bool = False):
    """Carrega as 15 cages R15 de um corpo diretamente do OBJ, convertendo para coordenadas do motor.

    Retorna dict: {part_name: {"verts": np.ndarray(N,3), "faces": np.ndarray(M,3),
                                "grid": SpatialGrid3D, "bbox_min": np.ndarray(3), "bbox_max": np.ndarray(3)}}
    Coordenadas OBJ (X, Y_height, Z_depth) → Motor (X, Z_depth, Y_height) — swap Y↔Z.
    """
    parts = {}
    current_name = None
    current_verts = []
    current_uvs = []
    current_faces = []
    current_face_uv_indices = []
    global_vert_offset = 0  # OBJ indices are 1-based and global
    global_uv_offset = 0
    global_uv_count = 0

    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("o "):
                if current_name is not None:
                    _finalize_r15_part(parts, current_name, current_verts, current_faces, global_vert_offset,
                                       is_source_cage=is_source_cage, uvs_list=current_uvs,
                                       face_uv_indices=current_face_uv_indices, uv_offset=global_uv_offset)
                    global_vert_offset += len(current_verts)
                    global_uv_offset += len(current_uvs)
                current_name = line[2:].replace("_OuterCage", "")
                current_verts = []
                current_uvs = []
                current_faces = []
                current_face_uv_indices = []
            elif line.startswith("v "):
                coords = [float(x) for x in line.split()[1:4]]
                current_verts.append(coords)
            elif line.startswith("vt "):
                current_uvs.append([float(x) for x in line.split()[1:3]])
                global_uv_count += 1
            elif line.startswith("f "):
                indices, uv_indices = [], []
                for tok in line.split()[1:]:
                    fields = tok.split("/")
                    vertex_index = int(fields[0])
                    indices.append(vertex_index - 1 if vertex_index > 0 else global_vert_offset + len(current_verts) + vertex_index)
                    if len(fields) > 1 and fields[1]:
                        uv_index = int(fields[1])
                        uv_indices.append(uv_index - 1 if uv_index > 0 else global_uv_count + uv_index)
                    else:
                        uv_indices.append(None)
                current_faces.append(indices)
                current_face_uv_indices.append(uv_indices)

    if current_name is not None:
        _finalize_r15_part(parts, current_name, current_verts, current_faces, global_vert_offset,
                           is_source_cage=is_source_cage, uvs_list=current_uvs,
                           face_uv_indices=current_face_uv_indices, uv_offset=global_uv_offset)

    # Unifica antebraço e mão em uma única cage contínua por lado (cobre perfeitamente o antebraço feminino)
    if "LeftLowerArm" in parts and "LeftHand" in parts:
        parts["LeftForearm"] = _combine_r15_parts(parts["LeftLowerArm"], parts["LeftHand"])
    if "RightLowerArm" in parts and "RightHand" in parts:
        parts["RightForearm"] = _combine_r15_parts(parts["RightLowerArm"], parts["RightHand"])

    return parts


def _combine_r15_parts(part1, part2):
    """Combina duas partes R15 em uma única cage contínua (ex: antebraço + mão)."""
    v1, f1 = part1["verts"], part1["faces"]
    v2, f2 = part2["verts"], part2["faces"]
    v_comb = np.vstack([v1, v2])
    f_comb = np.vstack([f1, f2 + len(v1)])
    uv1, uv2 = part1.get("face_uvs"), part2.get("face_uvs")
    face_uvs = np.concatenate([uv1, uv2], axis=0) if uv1 is not None and uv2 is not None else None
    grid = SpatialGrid3D(cell_size=0.04)
    grid.build(v_comb)
    return {
        "verts": v_comb,
        "faces": f_comb,
        "face_uvs": face_uvs,
        "grid": grid,
        "bbox_min": v_comb.min(axis=0),
        "bbox_max": v_comb.max(axis=0),
    }


def _finalize_r15_part(
    parts, name, verts_list, faces_list, vert_offset,
    is_source_cage: bool = False, uvs_list=None, face_uv_indices=None, uv_offset=0,
):
    """Finaliza uma parte R15: converte coordenadas, cria grid espacial e bounding box."""
    if not verts_list or not faces_list:
        return

    # Converte OBJ (X, Y_height, Z_depth) → Motor (X, -Z_depth, Y_height)
    # Para cages nativas Roblox (source), Frente é -Z_obj, então Y_engine = +Z_obj.
    # Para cages femininas Blender/OpenGL (target), Frente é +Z_obj, então Y_engine = -Z_obj.
    raw = np.array(verts_list, dtype=np.float64)
    engine_verts = np.zeros_like(raw)
    engine_verts[:, 0] = raw[:, 0]    # X = X_obj
    engine_verts[:, 1] = raw[:, 2] if is_source_cage else -raw[:, 2]   # Profundidade alinhada (Frente = -Y em ambas)
    engine_verts[:, 2] = raw[:, 1]    # Z_engine = Y_obj (altura)

    # Converte índices globais do OBJ para locais da parte mantendo a orientação externa das normais
    local_faces = []
    for f in faces_list:
        local_f = [idx - vert_offset for idx in f]
        # Triangula se necessário (fan triangulation com winding CCW correto para normais externas)
        if len(local_f) == 3:
            local_faces.append([local_f[0], local_f[1], local_f[2]])
        elif len(local_f) > 3:
            for i in range(1, len(local_f) - 1):
                local_faces.append([local_f[0], local_f[i], local_f[i + 1]])

    faces_arr = np.array(local_faces, dtype=np.int32)
    local_face_uvs = []
    for face_index, f in enumerate(faces_list):
        face_uv = face_uv_indices[face_index] if face_uv_indices and face_index < len(face_uv_indices) else None
        if not face_uv or any(idx is None for idx in face_uv) or not uvs_list:
            break
        local_uv = [uvs_list[idx - uv_offset] for idx in face_uv]
        for i in range(1, len(f) - 1):
            local_face_uvs.append([local_uv[0], local_uv[i], local_uv[i + 1]])
    face_uvs_arr = np.asarray(local_face_uvs, dtype=np.float64) if len(local_face_uvs) == len(local_faces) else None

    # Grid espacial para busca rápida de triângulos
    tri_a = engine_verts[faces_arr[:, 0]]
    tri_b = engine_verts[faces_arr[:, 1]]
    tri_c = engine_verts[faces_arr[:, 2]]
    centroids = (tri_a + tri_b + tri_c) / 3.0

    grid = SpatialGrid3D(cell_size=0.08)
    grid.build(centroids)

    parts[name] = {
        "verts": engine_verts,
        "faces": faces_arr,
        "face_uvs": face_uvs_arr,
        "uvs": np.asarray(uvs_list, dtype=np.float64) if uvs_list else None,
        "grid": grid,
        "bbox_min": engine_verts.min(axis=0),
        "bbox_max": engine_verts.max(axis=0),
    }


# Mapeamento de regiões anatômicas para cages R15 (parte superior)
def _uv_key(uv):
    """Stable key for an OBJ UV coordinate at the precision of the cage exports."""
    return tuple(np.round(np.asarray(uv, dtype=np.float64), 6).tolist())


def _align_target_faces_by_uv(source_part, target_part, part_name):
    """Return target triangles in source-triangle order, pairing corners by UV."""
    source_faces = source_part["faces"]
    target_faces = target_part["faces"]
    source_uv = source_part.get("face_uvs")
    target_uv = target_part.get("face_uvs")
    if source_uv is None or target_uv is None:
        raise ValueError(f"{part_name}: UV coordinates are required on both reference and target cages")
    if len(source_faces) != len(source_uv) or len(target_faces) != len(target_uv):
        raise ValueError(f"{part_name}: triangle/UV corner counts do not agree")

    target_by_uv = {}
    for tri_index, uv_triangle in enumerate(target_uv):
        key = tuple(sorted(_uv_key(uv) for uv in uv_triangle))
        if key in target_by_uv:
            raise ValueError(f"{part_name}: target cage has ambiguous UV triangle {key}")
        target_by_uv[key] = tri_index

    aligned_target_faces = np.empty_like(source_faces)
    seen = set()
    for source_index, uv_triangle in enumerate(source_uv):
        key = tuple(sorted(_uv_key(uv) for uv in uv_triangle))
        if key in seen:
            raise ValueError(f"{part_name}: reference cage has ambiguous UV triangle {key}")
        seen.add(key)
        target_index = target_by_uv.get(key)
        if target_index is None:
            raise ValueError(f"{part_name}: target cage is missing reference UV triangle {key}")

        target_uv_triangle = target_uv[target_index]
        target_face = target_faces[target_index]
        uv_to_vertex = {_uv_key(uv): int(vertex) for uv, vertex in zip(target_uv_triangle, target_face)}
        source_corner_keys = [_uv_key(uv) for uv in uv_triangle]
        if len(uv_to_vertex) != 3 or any(uv not in uv_to_vertex for uv in source_corner_keys):
            raise ValueError(f"{part_name}: UV corners cannot be mapped uniquely for triangle {source_index}")
        aligned_target_faces[source_index] = [uv_to_vertex[uv] for uv in source_corner_keys]

    if len(seen) != len(target_by_uv):
        raise ValueError(f"{part_name}: target has UV triangles absent from its reference cage")
    return aligned_target_faces


_TOP_CAGE_REGIONS = [
    # (nome_cage, Z_min, Z_max, X_min, X_max)  — Z=altura, X=horizontal no motor
    ("UpperTorso",    0.90, 1.50, -0.22, 0.22),
    ("LowerTorso",    0.74, 0.93, -0.22, 0.22),
    ("LeftUpperArm",  1.10, 1.50,  0.08, 0.35),
    ("LeftLowerArm",  0.78, 1.18,  0.18, 0.42),
    ("LeftHand",      0.65, 0.87,  0.27, 0.46),
    ("RightUpperArm", 1.10, 1.50, -0.35, -0.08),
    ("RightLowerArm", 0.78, 1.18, -0.42, -0.18),
    ("RightHand",     0.65, 0.87, -0.46, -0.27),
]

# Mapeamento de regiões anatômicas para cages R15 (parte inferior)
_BOTTOM_CAGE_REGIONS = [
    ("LowerTorso",     0.74, 0.95, -0.22, 0.22),
    ("LeftUpperLeg",   0.40, 0.87, -0.02, 0.28),
    ("LeftLowerLeg",  -0.01, 0.44,  0.03, 0.27),
    ("LeftFoot",      -0.05, 0.07,  0.07, 0.26),
    ("RightUpperLeg",  0.40, 0.87, -0.28, 0.02),
    ("RightLowerLeg", -0.01, 0.44, -0.27, -0.03),
    ("RightFoot",     -0.05, 0.07, -0.26, -0.07),
]


def _assign_cage_region(point, regions, cage_parts):
    """Determina qual cage R15 é a mais adequada para um ponto 3D.

    Usa bounding-box expandida + distância ao centróide como critério.
    Retorna o nome da cage ou None se nenhuma região corresponder.
    """
    x, y, z = float(point[0]), float(point[1]), float(point[2])
    best_name = None
    best_score = float("inf")

    for name, z_min, z_max, x_min, x_max in regions:
        if name not in cage_parts:
            continue
        # Expande os limites em 15% para pegar vértices na borda
        dz = (z_max - z_min) * 0.15
        dx = (x_max - x_min) * 0.15
        if z_min - dz <= z <= z_max + dz and x_min - dx <= x <= x_max + dx:
            # Score: distância normalizada ao centro da região
            cz = (z_min + z_max) / 2.0
            cx = (x_min + x_max) / 2.0
            score = ((z - cz) / (z_max - z_min + 1e-8)) ** 2 + ((x - cx) / (x_max - x_min + 1e-8)) ** 2
            if score < best_score:
                best_score = score
                best_name = name

    # Fallback: se nenhuma região bateu, usa a cage mais próxima por distância ao centróide do bbox
    if best_name is None:
        for name, data in cage_parts.items():
            # Só considera partes que existem nas regiões pedidas
            region_names = {r[0] for r in regions}
            if name not in region_names:
                continue
            center = (data["bbox_min"] + data["bbox_max"]) / 2.0
            dist = float(np.linalg.norm(point - center))
            if dist < best_score:
                best_score = dist
                best_name = name

    return best_name


class RobloxWearEngine:
    """Motor completo de deformação, ajuste e vestuário Roblox em Python puro."""

    def __init__(self, cage_data_path=None, body_type="male"):
        self.body_type = body_name(body_type)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        std_cage_path = os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz")
        self.std_cage_data = np.load(std_cage_path)

        # Last-resort fit (garments without usable cages): the standard Roblox mannequin
        # onto the female A-pose cage, which the male body shares the pose of.
        self.cage_data = np.load(os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz"))
        self.src_verts_apose = self.std_cage_data["cage_verts_apose"]
        self.src_verts_tpose_85 = self.std_cage_data["cage_verts_tpose_85"]
        self.src_verts_rest = self.std_cage_data["cage_verts_rest"]
        self.dst_verts_rest = self.cage_data["cage_verts_rest"]
        self.dst_verts_apose = self.cage_data["cage_verts_apose"]
        self.dst_verts_tpose_85 = self.cage_data["cage_verts_tpose_85"]

        self.cage_verts_apose = self.src_verts_apose
        self.cage_verts_rest = self.dst_verts_rest
        self.cage_verts_tpose_85 = self.src_verts_tpose_85
        self.cage_faces = self.std_cage_data["cage_faces"]

        # Carrega segmentação de grupos de faces da cage (0=Torso, 1=Braço Esquerdo, 2=Braço Direito)
        if "cage_face_groups" in self.cage_data and len(self.cage_data["cage_face_groups"]) == len(self.cage_faces):
            self.cage_face_groups = self.cage_data["cage_face_groups"]
        else:
            v_a = self.cage_verts_apose[self.cage_faces]
            c_x = np.mean(v_a[:, :, 0], axis=1)
            self.cage_face_groups = np.zeros(len(self.cage_faces), dtype=np.int32)
            self.cage_face_groups[c_x > 0.25] = 1
            self.cage_face_groups[c_x < -0.25] = 2


        # Acelerador A-Pose Global (Parte Superior)
        tri_a = self.cage_verts_apose[self.cage_faces[:, 0]]
        tri_b = self.cage_verts_apose[self.cage_faces[:, 1]]
        tri_c = self.cage_verts_apose[self.cage_faces[:, 2]]
        centroids_apose = (tri_a + tri_b + tri_c) / 3.0
        self.grid_apose = SpatialGrid3D(cell_size=0.10)
        self.grid_apose.build(centroids_apose)

        # Aceleradores Particionados por Membros (Torso, Braço Esquerdo, Braço Direito)
        self.g0_tris = np.where(self.cage_face_groups == 0)[0]
        self.g1_tris = np.where(self.cage_face_groups == 1)[0]
        self.g2_tris = np.where(self.cage_face_groups == 2)[0]

        self.grid_apose_g0 = SpatialGrid3D(cell_size=0.10)
        self.grid_apose_g0.build(centroids_apose[self.g0_tris])

        self.grid_apose_g1 = SpatialGrid3D(cell_size=0.10)
        self.grid_apose_g1.build(centroids_apose[self.g1_tris])

        self.grid_apose_g2 = SpatialGrid3D(cell_size=0.10)
        self.grid_apose_g2.build(centroids_apose[self.g2_tris])

        # Acelerador T-Pose (Calças)
        tri_ta = self.cage_verts_tpose_85[self.cage_faces[:, 0]]
        tri_tb = self.cage_verts_tpose_85[self.cage_faces[:, 1]]
        tri_tc = self.cage_verts_tpose_85[self.cage_faces[:, 2]]
        centroids_tpose = (tri_ta + tri_tb + tri_tc) / 3.0
        self.grid_tpose = SpatialGrid3D(cell_size=0.10)
        self.grid_tpose.build(centroids_tpose)

        # Acelerador Rest Pose Global (para cálculo de offset e espessura da roupa)
        self.tri_ra = self.cage_verts_rest[self.cage_faces[:, 0]]
        self.tri_rb = self.cage_verts_rest[self.cage_faces[:, 1]]
        self.tri_rc = self.cage_verts_rest[self.cage_faces[:, 2]]
        centroids_rest = (self.tri_ra + self.tri_rb + self.tri_rc) / 3.0
        self.grid_rest = SpatialGrid3D(cell_size=0.10)
        self.grid_rest.build(centroids_rest)

        # Referências esqueléticas
        self.elbow_l = self.cage_data["elbow_l"]
        self.wrist_l = self.cage_data["wrist_l"]
        self.elbow_z = float(self.elbow_l[2])
        self.wrist_z = float(self.wrist_l[2])

        # R15 cages of this body and the Roblox reference cages the garments were made on
        self.body_cages = None
        self.r15_source_cages = None
        self.dual_cage_ready = False
        body_obj = os.path.join(base_dir, "assets", "models", BODY_CAGES[self.body_type])
        r15_src_obj = os.path.join(base_dir, "assets", "models", "roblox_reference_cages.obj")
        if os.path.exists(body_obj) and os.path.exists(r15_src_obj):
            self.body_cages = load_r15_cages(body_obj, is_source_cage=False)
            self.r15_source_cages = load_r15_cages(r15_src_obj, is_source_cage=True)
            print(f"[R15] Carregadas cages de {os.path.basename(body_obj)} "
                  f"e referência UV de {os.path.basename(r15_src_obj)}.")
            self._init_dual_cage()

    def _under_outer_cage(self, asset_id, body_positions):
        """Fitted outer cage of ``asset_id`` per body-cage UV point (the body where it has none)."""
        from .radial_prism_fit import fit_radial_prism
        from .wrap_layer_fit import retarget_garment_with_wrap_layer
        under = self.fetch_asset(asset_id)
        verts, faces, _, _ = self.load_obj(under["obj_path"])
        trace = {}
        retarget_garment_with_wrap_layer(self, verts, under["rbxm_path"],
                                         os.path.join(os.path.dirname(under["obj_path"]), "wrap_cages"),
                                         binding_audit=trace)
        fit_radial_prism(verts, faces, trace)
        total = np.zeros_like(body_positions)
        count = np.zeros(len(body_positions))
        np.add.at(total, trace["uv_index"], trace["target_outer"])
        np.add.at(count, trace["uv_index"], 1)
        shell = body_positions.copy()
        known = count > 0
        shell[known] = total[known] / count[known, None]
        return shell

    def _layered_body_cage(self):
        """Body cage positions with the fitted outer cages of ``layer_under_asset`` on top.

        Roblox fits each layered garment over the outer cages of the ones under it,
        so a jacket wraps the shirt and a coat the pants instead of meeting them on
        the bare body. ``layer_under_asset`` is one asset id or a list of them; at
        each cage point the outermost shell wins. Returns None (plain body) when no
        garment under it has usable cages.
        """
        from .wrap_layer_fit import _unique_uv_positions
        under = self.layer_under_asset
        under = [under] if isinstance(under, (int, str)) else [a for a in under if a is not None]
        _, body = _unique_uv_positions(self.body_cages)
        positions, lift = body.copy(), np.zeros(len(body))
        used = []
        for asset_id in under:
            try:
                shell = self._under_outer_cage(asset_id, body)
            except Exception as exc:
                print(f"[WrapLayer] Camada de baixo {asset_id} indisponível: {exc}")
                continue
            shell_lift = np.linalg.norm(shell - body, axis=1)
            outer = shell_lift > lift
            positions[outer], lift[outer] = shell[outer], shell_lift[outer]
            used.append(asset_id)
        if not used:
            return None
        gap = float(getattr(self, "layer_gap", 0.0) or 0.0)
        if gap:
            # Manual extra room between the layers, along the layered shell's normals.
            from .hsr import _cage_vertex_normals, body_cage_faces
            positions += _cage_vertex_normals(positions, body_cage_faces(self.body_cages)) * gap
        print(f"[WrapLayer] Encaixando sobre a cage externa de {used} (folga {gap * 1000:.0f} mm)")
        return positions

    @staticmethod
    def _fit_shoe_affine(verts, trace, margin=0.15, ankle_height=0.08):
        """Shoe vertices moved by the similarity (rotation, one scale, offset) of the foot cage around them.

        A shoe is rigid, so it keeps its own proportions: only the foot (target
        height below ``ankle_height``) sets the map. A free affine map squashed
        boots flat on our flat box foot, and fitting the shin too widened them on
        our thick calves.
        """
        reference = np.asarray(trace["reference_parent"], dtype=np.float64)
        target = np.asarray(trace["target_body"], dtype=np.float64)
        points = np.asarray(verts, dtype=np.float64)
        low, high = points.min(0), points.max(0)
        pad = margin * np.ptp(points, axis=0).max()
        near = np.all((reference >= low - pad) & (reference <= high + pad), axis=1) & (target[:, 2] < ankle_height)
        if near.sum() < 8:
            return None
        # The rotation (the reference cage is Y-up, ours Z-up) comes from the whole body
        # cage, where it is well defined; the flat foot alone flipped some shoes over.
        # The foot sets only the uniform scale and the position.
        whole_a = reference - reference.mean(0)
        whole_b = target - target.mean(0)
        u, _, vt = np.linalg.svd(whole_b.T @ whole_a)
        d = np.eye(3)
        if np.linalg.det(u) * np.linalg.det(vt) < 0:
            d[2, 2] = -1
        rotation = u @ d @ vt
        source, dest = reference[near] @ rotation.T, target[near]
        source_mean, dest_mean = source.mean(0), dest.mean(0)
        scale = float(np.sqrt(((dest - dest_mean) ** 2).sum(1).mean() / ((source - source_mean) ** 2).sum(1).mean()))
        return ((points @ rotation.T - source_mean) * scale + dest_mean).astype(np.float32)

    def _rigid_footwear(self, verts, faces, fitted, trace):
        """Boots that come with a garment (pants with boots) keep their shape below the ankle.

        Like layered shoes: the cage fit crushes a boot onto our flat box foot, so on each
        side the part below SHOE_RIGID_TOP follows the foot's similarity map, blending into
        the cage fit over SHOE_BLEND_HEIGHT. Garments that end above the feet are untouched.
        """
        fitted = np.asarray(fitted, dtype=np.float64)
        if fitted[:, 2].min() > SHOE_RIGID_TOP / 2:
            return fitted
        faces = np.asarray([f[:3] for f in faces], dtype=np.int64)
        top = SHOE_RIGID_TOP + SHOE_BLEND_HEIGHT
        low_faces = faces[(fitted[faces, 2] < top).all(1)]
        # Connected pieces of cloth below the blend top: a piece reaching out to both feet
        # is a long skirt's hem (no boots); the others go to the foot on their side (wide
        # trouser hems can cross the middle a little).
        parent = np.arange(len(fitted))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for a, b, c in low_faces:
            for u, v in ((a, b), (b, c)):
                ru, rv = root(u), root(v)
                if ru != rv:
                    parent[ru] = rv
        low = np.unique(low_faces)
        roots = np.array([root(i) for i in low])
        points = np.asarray(verts, dtype=np.float64)
        out = fitted.copy()
        feet = {1: [], -1: []}
        for piece in np.unique(roots):
            members = low[roots == piece]
            xs = fitted[members, 0]
            if min(-xs.min(), xs.max()) > 0.12:  # reaches both feet (they sit about 0.16 out)
                return fitted
            feet[1 if xs.mean() > 0 else -1].append(members)
        for members in feet.values():
            if not members:
                continue
            foot = np.concatenate(members)
            if len(foot) < 8:
                continue
            rigid = self._fit_shoe_affine(points[foot], trace)
            if rigid is None:
                continue
            t = np.clip((fitted[foot, 2] - SHOE_RIGID_TOP) / SHOE_BLEND_HEIGHT, 0.0, 1.0)
            weight = (t * t * (3 - 2 * t))[:, None]
            out[foot] = (1 - weight) * rigid + weight * fitted[foot]
        return out.astype(np.float32)

    def _fit_asset_wrap_layer(self, verts, meta, faces=None):
        """Use an asset's own cages when UVs and garment-to-cage distance validate."""
        if not self.body_cages or not meta.get("rbxm_path"):
            return None
        try:
            from .wrap_layer_fit import retarget_garment_with_wrap_layer
            cache = os.path.join(os.path.dirname(meta["obj_path"]), "wrap_cages")
            trace = {}
            layered = self._layered_body_cage() if getattr(self, "layer_under_asset", None) else None
            result = retarget_garment_with_wrap_layer(self, verts, meta["rbxm_path"], cache, binding_audit=trace,
                                                      target_positions=layered)
            info = result[1]
            from .wrap_layer_fit import body_uv_parts, garment_body_parts
            info["body_parts"] = garment_body_parts(self.body_cages, trace)  # bone of each vertex when animated
            trace["cage_point_parts"] = np.array(body_uv_parts(self.body_cages))[trace["uv_index"]]
            # The per-triangle fit extrapolates badly far from the outer cage, so it is
            # only trusted with the garment close to a sane cage. The radial + prism fit
            # handles far points (prism residual, hanging parts) and is used whenever the
            # cages pair: on costumes and oversized pieces these limits rejected (outer
            # cage stretched up to 26x, garment 0.1-0.2 from its cage) it still produced
            # the whole costume, where the older fallback showed a torso fragment.
            per_triangle_ok = (info["outer_edge_stretch_p99"] <= 2.5 and info["median_source_distance"] <= 0.05
                               and info["p99_source_distance"] <= 0.2)
            if faces is None and not per_triangle_ok:
                raise ValueError("roupa distante demais da cage externa para encaixe estável")
        except Exception as exc:  # Asset decoding must never stop the outfit pipeline.
            print(f"[WrapLayer] Usando encaixe anterior: {exc}")
            return None
        try:
            from .hsr import engine_to_body_mesh, hidden_body_cage_mask
            from .wrap_layer_fit import _unique_uv_positions
            _, cage_positions = _unique_uv_positions(self.body_cages)
            hidden = hidden_body_cage_mask(meta["rbxm_path"], trace, len(cage_positions),
                                           os.path.join(os.path.dirname(meta["obj_path"]), "hsr"))
            if hidden is not None:
                from .hsr import body_cage_faces
                result[1]["hsr"] = {"cage_points": engine_to_body_mesh(cage_positions), "hidden": hidden,
                                    "cage_faces": body_cage_faces(self.body_cages)}
                print(f"[HSR] {int(hidden.sum())} de {len(hidden)} pontos da cage cobertos pela roupa")
        except Exception as exc:  # HSR is optional: without it the skin keeps the rule-based cuts.
            print(f"[HSR] Sem dados de HSR: {exc}")
        if meta.get("type_id") in (70, 71):
            # Shoes are rigid: one affine map of the nearby cage (foot and shin) keeps
            # their shape. The per-triangle fit crushed a sneaker built for a tall,
            # arched reference foot onto our flat box foot, and broke heels.
            fitted = self._fit_shoe_affine(verts, trace)
            if fitted is not None:
                if faces is not None:
                    # A boot shaft is cloth around the calf: above the ankle blend into the
                    # cage fit, so the shaft wraps our thicker calves instead of cutting in.
                    try:
                        from .radial_prism_fit import fit_radial_prism
                        wrapped, _ = fit_radial_prism(verts, faces, trace)
                        t = np.clip((fitted[:, 2] - SHOE_RIGID_TOP) / SHOE_BLEND_HEIGHT, 0.0, 1.0)
                        weight = (t * t * (3 - 2 * t))[:, None]
                        fitted = ((1 - weight) * fitted + weight * wrapped).astype(np.float32)
                    except Exception as exc:
                        print(f"[WrapLayer] Cano do calçado sem encaixe por cage: {exc}")
                print(f"[WrapLayer] Calçado encaixado (pé rígido, cano pela cage): {result[1]}")
                return fitted, {**result[1], "method": "shoe_rigid_foot"}
        if faces is not None:
            try:
                from .radial_prism_fit import fit_radial_prism
                fitted, audit = fit_radial_prism(verts, faces, trace)
                fitted = self._rigid_footwear(verts, faces, fitted, trace)
                print(f"[WrapLayer] Cages do asset aplicadas (radial + prisma): {result[1]} {audit}")
                return fitted, {**result[1], **audit, "method": "radial_prism"}
            except Exception as exc:  # Keep the per-triangle fit if the prism fit cannot bind.
                print(f"[WrapLayer] Radial + prisma indisponível: {exc}")
        if not per_triangle_ok:
            print("[WrapLayer] Usando encaixe anterior: roupa distante demais da cage para o encaixe por triângulo")
            return None
        print(f"[WrapLayer] Cages do asset aplicadas: {result[1]}")
        return result

    def _init_dual_cage(self):
        """Inicializa e pré-computa os aceleradores espaciais da Dual Cage R15 feminina bilateral."""
        if not self.body_cages or not self.r15_source_cages:
            return

        c_src = self.r15_source_cages
        c_fem = self.body_cages
        
        # Never reorder or repair these vertices by index: the binding is established by UVs below.

        # Escalonamento da source cage para o espaço métrico do motor
        ut_s = c_src["UpperTorso"]["verts"]
        ut_f = c_fem["UpperTorso"]["verts"]
        scale = (ut_f[:, 2].max() - ut_f[:, 2].min()) / (ut_s[:, 2].max() - ut_s[:, 2].min() + 1e-8)
        z_shift = ut_f[:, 2].max() - ut_s[:, 2].max() * scale
        y_shift = ut_f[:, 1].mean() - ut_s[:, 1].mean() * scale

        def scale_src(v):
            out = v.copy()
            out[:, 0] *= scale
            out[:, 1] = out[:, 1] * scale + y_shift
            out[:, 2] = out[:, 2] * scale + z_shift
            return out

        def combine_parts(part_names):
            source_vertices, target_vertices = [], []
            source_faces, target_faces = [], []
            source_offset = target_offset = 0
            for part_name in part_names:
                source_part = c_src[part_name]
                target_part = c_fem[part_name]
                aligned_target = _align_target_faces_by_uv(source_part, target_part, part_name)
                source_vertices.append(scale_src(source_part["verts"]))
                target_vertices.append(target_part["verts"])
                source_faces.append(source_part["faces"] + source_offset)
                target_faces.append(aligned_target + target_offset)
                source_offset += len(source_part["verts"])
                target_offset += len(target_part["verts"])
            return (
                np.vstack(source_vertices), np.vstack(target_vertices),
                np.vstack(source_faces), np.vstack(target_faces),
            )

        try:
            self.v_torso_s, self.v_torso_f, self.f_torso, self.f_torso_target = combine_parts(
                ["UpperTorso", "LowerTorso"]
            )
            self.v_arm_l_s, self.v_arm_l_f, self.f_arm_l, self.f_arm_l_target = combine_parts(
                ["LeftUpperArm", "LeftLowerArm", "LeftHand"]
            )
            self.v_arm_r_s, self.v_arm_r_f, self.f_arm_r, self.f_arm_r_target = combine_parts(
                ["RightUpperArm", "RightLowerArm", "RightHand"]
            )
        except (KeyError, ValueError) as exc:
            print(f"[R15] Dual cage desativada: mapeamento UV invÃ¡lido ({exc}).")
            return

        def prep_grid(v_arr, f_arr):
            ta = v_arr[f_arr[:, 0]]
            tb = v_arr[f_arr[:, 1]]
            tc = v_arr[f_arr[:, 2]]
            centroids = (ta + tb + tc) / 3.0
            fn = np.cross(tb - ta, tc - ta)
            fn_len = np.linalg.norm(fn, axis=1, keepdims=True)
            fn_len[fn_len < 1e-8] = 1.0
            fn /= fn_len
            grid = SpatialGrid3D(cell_size=0.08)
            grid.build(centroids)
            return ta, tb, tc, fn, grid

        self.ta_ts, self.tb_ts, self.tc_ts, self.fn_ts, self.grid_torso_s = prep_grid(self.v_torso_s, self.f_torso)
        self.ta_tf, self.tb_tf, self.tc_tf, self.fn_tf, _ = prep_grid(self.v_torso_f, self.f_torso_target)

        self.ta_las, self.tb_las, self.tc_las, self.fn_las, self.grid_arm_l_s = prep_grid(self.v_arm_l_s, self.f_arm_l)
        self.ta_laf, self.tb_laf, self.tc_laf, self.fn_laf, _ = prep_grid(self.v_arm_l_f, self.f_arm_l_target)

        self.ta_ras, self.tb_ras, self.tc_ras, self.fn_ras, self.grid_arm_r_s = prep_grid(self.v_arm_r_s, self.f_arm_r)
        self.ta_raf, self.tb_raf, self.tc_raf, self.fn_raf, _ = prep_grid(self.v_arm_r_f, self.f_arm_r_target)

        self.dual_cage_ready = True

    def deform_dual_cage(
        self,
        apose_verts: np.ndarray,
        faces: list,
        sleeve_indices: set,
        torso_indices: set,
        is_jacket: bool = False,
        is_sleeveless: bool = False,
    ) -> np.ndarray:
        """Aplica o algoritmo Roblox Dual-Cage WrapDeformer bilateral para avatares femininos em Python puro.
        - Deformação baricêntrica canônica Source Cage (Roblox) -> Target Cage (Feminina A-Pose 30°).
        - Puffiness normal ajustada para evitar 100% de penetração na pele sem descaracterizar a malha.
        - Seam arch bulge e relaxamento Laplaciano para ombro contínuo e curvatura natural.
        """
        def deform_wrap(p, ta_s, tb_s, tc_s, fn_s, grid_s, ta_t, tb_t, tc_t, fn_t, f_arr, min_puff=0.018, max_puff=0.040):
            cands = grid_s.query_nearest_candidates(p, 2) or range(len(f_arr))
            best_d = float("inf")
            best_t = 0
            best_u, best_v, best_w = 1.0, 0.0, 0.0
            best_q = p
            for t in cands:
                q, u, v, w = closest_point_on_triangle(p, ta_s[t], tb_s[t], tc_s[t])
                d = float(np.linalg.norm(p - q))
                if d < best_d:
                    best_d = d
                    best_t = t
                    best_u, best_v, best_w = u, v, w
                    best_q = q

            norm_s = fn_s[best_t]
            norm_t = fn_t[best_t]
            h = float(np.dot(p - best_q, norm_s))
            tan = (p - best_q) - h * norm_s
            tan_l = float(np.linalg.norm(tan))
            if tan_l > 0.025:
                tan *= (0.025 / tan_l)

            puff = max(min_puff, min(h, max_puff))
            p_tgt = best_u * ta_t[best_t] + best_v * tb_t[best_t] + best_w * tc_t[best_t]
            return p_tgt + puff * norm_t + tan, norm_t

        # Refinamento baricêntrico canônico: assegura que vértices da axila/manga
        # geometricamente vinculados à cage do braço sejam processados como manga (elimina 100% de spikes)
        eff_sleeve_indices = set(sleeve_indices)
        if eff_sleeve_indices and not is_sleeveless:
            for i in torso_indices:
                p = apose_verts[i]
                if abs(p[0]) > 0.18 and p[2] > 1.08:
                    is_left = p[0] > 0
                    grid_a = self.grid_arm_l_s if is_left else self.grid_arm_r_s
                    ta_a = self.ta_las if is_left else self.ta_ras
                    tb_a = self.tb_las if is_left else self.tb_ras
                    tc_a = self.tc_las if is_left else self.tc_ras

                    cands_t = self.grid_torso_s.query_nearest_candidates(p, 2)
                    best_dt = min(float(np.linalg.norm(p - closest_point_on_triangle(p, self.ta_ts[t], self.tb_ts[t], self.tc_ts[t])[0])) for t in cands_t)

                    cands_a = grid_a.query_nearest_candidates(p, 2)
                    best_da = min(float(np.linalg.norm(p - closest_point_on_triangle(p, ta_a[t], tb_a[t], tc_a[t])[0])) for t in cands_a)

                    if best_da < best_dt:
                        eff_sleeve_indices.add(i)

        sh_start = 0.14
        sh_end = 0.22

        deformed = np.zeros_like(apose_verts)
        for i in range(len(apose_verts)):
            p = apose_verts[i]
            ax = abs(p[0])
            is_left = p[0] > 0

            if is_sleeveless:
                arm_puff = 0.015
                torso_puff = 0.012
            elif is_jacket:
                arm_puff = 0.024 if p[2] > 1.35 else 0.020
                torso_puff = 0.020 if p[2] > 1.25 else 0.016
            else:
                arm_puff = 0.016 if p[2] > 1.35 else 0.014
                torso_puff = 0.015 if p[2] > 1.25 else 0.012

            if is_sleeveless or len(eff_sleeve_indices) == 0:
                p_torso, _ = deform_wrap(
                    p, self.ta_ts, self.tb_ts, self.tc_ts, self.fn_ts, self.grid_torso_s,
                    self.ta_tf, self.tb_tf, self.tc_tf, self.fn_tf, self.f_torso, min_puff=torso_puff
                )
                deformed[i] = p_torso
            else:
                if is_left:
                    p_arm, n_arm = deform_wrap(
                        p, self.ta_las, self.tb_las, self.tc_las, self.fn_las, self.grid_arm_l_s,
                        self.ta_laf, self.tb_laf, self.tc_laf, self.fn_laf, self.f_arm_l, min_puff=arm_puff
                    )
                else:
                    p_arm, n_arm = deform_wrap(
                        p, self.ta_ras, self.tb_ras, self.tc_ras, self.fn_ras, self.grid_arm_r_s,
                        self.ta_raf, self.tb_raf, self.tc_raf, self.fn_raf, self.f_arm_r, min_puff=arm_puff
                    )

                p_torso, n_torso = deform_wrap(
                    p, self.ta_ts, self.tb_ts, self.tc_ts, self.fn_ts, self.grid_torso_s,
                    self.ta_tf, self.tb_tf, self.tc_tf, self.fn_tf, self.f_torso, min_puff=torso_puff
                )

                if i in eff_sleeve_indices:
                    if ax > sh_end or p[2] < 1.25:
                        deformed[i] = p_arm
                    else:
                        w = smoothstep(sh_start, sh_end, ax)
                        deformed[i] = (1.0 - w) * p_torso + w * p_arm
                else:
                    # Torso 100% isolado da cage dos braços (fidelidade total à silhueta feminina da cage)
                    deformed[i] = p_torso

        # Relaxamento Laplaciano no anel de costura para acabamento contínuo
        adj = {}
        for face in faces:
            for fi in range(len(face)):
                i0, i1 = face[fi], face[(fi + 1) % len(face)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        seam_ring = {i for i in eff_sleeve_indices if sh_start <= abs(apose_verts[i, 0]) <= sh_end and apose_verts[i, 2] > 1.30}
        disp = deformed - apose_verts
        smoothed_disp = disp.copy()
        for _ in range(6):
            new_disp = smoothed_disp.copy()
            for s_i in seam_ring:
                nbrs = list(adj.get(s_i, []))
                if nbrs:
                    new_disp[s_i] = 0.65 * smoothed_disp[s_i] + 0.35 * np.mean(smoothed_disp[nbrs], axis=0)
            smoothed_disp = new_disp

        res_verts = apose_verts + smoothed_disp

        if is_sleeveless:
            strap_verts = {
                i for i in range(len(apose_verts))
                if abs(apose_verts[i, 0]) >= 0.08 and abs(apose_verts[i, 0]) <= 0.18 and apose_verts[i, 2] > 1.35
            }
            for _ in range(2):
                new_res = res_verts.copy()
                for s_i in strap_verts:
                    nbrs = [n for n in adj.get(s_i, []) if n in strap_verts]
                    if nbrs:
                        new_res[s_i] = 0.60 * res_verts[s_i] + 0.40 * np.mean(res_verts[nbrs], axis=0)
                res_verts = new_res

        return res_verts

    def fetch_asset(self, asset_id, output_dir=None):
        """Baixa malha e textura do Roblox em Python puro."""
        if output_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            output_dir = os.path.join(base_dir, "assets", "models", "clothing")
        # Verifica cache local existente para resiliência offline
        cached_objs = [
            f for f in os.listdir(output_dir)
            if str(asset_id) in f and f.endswith(".obj")
            and not f.startswith("Hair_fitted_")
            and not f.startswith("character_")
        ]
        cached_pngs = [f for f in os.listdir(output_dir) if str(asset_id) in f and f.endswith(".png")]
        cached_rbxms = [f for f in os.listdir(output_dir) if str(asset_id) in f and f.endswith(".rbxm")]
        rbxm_path = os.path.join(output_dir, cached_rbxms[0]) if cached_rbxms else None

        if cached_objs:
            obj_path = os.path.join(output_dir, cached_objs[0])
            tex_path = os.path.join(output_dir, cached_pngs[0]) if cached_pngs else None
            name = cached_objs[0].replace(f"_{asset_id}.obj", "").replace(".obj", "").strip("_")
            is_top_guess = not any(b in name.lower() for b in ["pants", "jeans", "trouser", "skirt", "shorts", "shoe", "boot"])
            type_id = 65 if is_top_guess else 66
            try:
                url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=2) as resp:
                    meta = json.loads(resp.read().decode("utf-8"))
                    name = re.sub(r"[^a-zA-Z0-9_-]", "_", meta.get("Name", name)).strip("_")
                    type_id = meta.get("AssetTypeId", type_id)
            except Exception:
                pass

            # Auto-recuperação de textura e rbxm caso o cache antigo não os tenha baixado
            if (not tex_path or not os.path.exists(tex_path)) or (not rbxm_path or not os.path.exists(rbxm_path)):
                try:
                    raw_data = fetch_roblox_asset(asset_id)
                    if raw_data:
                        target_rbxm = os.path.join(output_dir, f"{name}_{asset_id}.rbxm")
                        with open(target_rbxm, "wb") as f_rbxm:
                            f_rbxm.write(raw_data)
                        rbxm_path = target_rbxm

                    decomp = raw_data
                    if raw_data and raw_data.startswith(b"\x1f\x8b"):
                        try:
                            decomp = gzip.decompress(raw_data)
                        except Exception:
                            pass
                    m_tex = re.search(rb"(?:ColorMap|TextureID|TextureId|TexturePack|Texture).*?(?:rbxassetid://|id=)(\d+)", decomp, re.IGNORECASE)
                    if m_tex and (not tex_path or not os.path.exists(tex_path)):
                        found_tex_id = m_tex.group(1).decode("ascii")
                        tex_bytes = fetch_roblox_asset(found_tex_id)
                        if tex_bytes:
                            if tex_bytes.startswith(b"\x1f\x8b"):
                                try:
                                    tex_bytes = gzip.decompress(tex_bytes)
                                except Exception:
                                    pass
                            target_png = os.path.join(output_dir, f"{name}_{asset_id}.png")
                            with open(target_png, "wb") as fp:
                                fp.write(tex_bytes)
                            tex_path = target_png
                except Exception:
                    pass

            is_hair = type_id == 41 or any(k in name.lower() for k in ["hair", "cabelo", "wig", "popstar", "ponytail", "pigtails", "braids"])
            return {
                "name": name,
                "asset_id": asset_id,
                "type_id": type_id,
                "is_top": (type_id in TOP_ASSET_TYPES or type_id not in BOTTOM_ASSET_TYPES) and not is_hair,
                "is_hair": is_hair,
                "obj_path": obj_path,
                "tex_path": tex_path,
                "rbxm_path": rbxm_path
            }

        url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            meta = json.loads(resp.read().decode("utf-8"))

        asset_name = re.sub(r"[^a-zA-Z0-9_-]", "_", meta.get("Name", f"asset_{asset_id}")).strip("_")
        type_id = meta.get("AssetTypeId", 65)

        raw_data = fetch_roblox_asset(asset_id)
        rbxm_path = os.path.join(output_dir, f"{asset_name}_{asset_id}.rbxm")
        if raw_data:
            try:
                with open(rbxm_path, "wb") as f_rbxm:
                    f_rbxm.write(raw_data)
            except Exception:
                pass

        decomp = raw_data
        if raw_data.startswith(b"\x1f\x8b"):
            try:
                decomp = gzip.decompress(raw_data)
            except:
                pass

        mesh_id = str(asset_id)
        tex_id = None
        if decomp.startswith(b"<roblox") or decomp.startswith(b"<roblox!"):
            m_mesh = re.search(rb"(?:MeshId|MeshID).*?(?:rbxassetid://|id=)(\d+)", decomp, re.IGNORECASE)
            if m_mesh:
                mesh_id = m_mesh.group(1).decode("ascii")
            m_tex = re.search(rb"(?:ColorMap|TextureID|TextureId|TexturePack|Texture).*?(?:rbxassetid://|id=)(\d+)", decomp, re.IGNORECASE)
            if m_tex:
                tex_id = m_tex.group(1).decode("ascii")

        obj_path = os.path.join(output_dir, f"{asset_name}_{asset_id}.obj")
        tex_path = os.path.join(output_dir, f"{asset_name}_{asset_id}.png")

        mesh_bytes = fetch_roblox_asset(mesh_id)
        decode_roblox_mesh_to_obj(mesh_bytes, obj_path)

        if tex_id:
            tex_bytes = fetch_roblox_asset(tex_id)
            if tex_bytes:
                if tex_bytes.startswith(b"\x1f\x8b"):
                    try:
                        tex_bytes = gzip.decompress(tex_bytes)
                    except:
                        pass
                with open(tex_path, "wb") as f:
                    f.write(tex_bytes)
        else:
            tex_path = None

        is_hair = type_id == 41 or any(k in asset_name.lower() for k in ["hair", "cabelo", "wig", "popstar", "ponytail", "pigtails", "braids"])
        return {
            "name": asset_name,
            "asset_id": asset_id,
            "type_id": type_id,
            "is_top": (type_id in TOP_ASSET_TYPES or type_id not in BOTTOM_ASSET_TYPES) and not is_hair,
            "is_hair": is_hair,
            "obj_path": obj_path,
            "tex_path": tex_path,
            "rbxm_path": rbxm_path
        }

    def load_obj(self, obj_path):
        """Lê vértices, uvs e faces de um OBJ em NumPy."""
        verts = []
        uvs = []
        faces = []
        face_uvs = []

        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("v "):
                    verts.append([float(x) for x in line.split()[1:4]])
                elif line.startswith("vt "):
                    uvs.append([float(x) for x in line.split()[1:3]])
                elif line.startswith("f "):
                    parts = line.split()[1:]
                    f_v = [int(p.split("/")[0]) - 1 for p in parts]
                    faces.append(f_v)
                    if "/" in parts[0] and parts[0].split("/")[1]:
                        f_uv = [int(p.split("/")[1]) - 1 for p in parts]
                        face_uvs.append(f_uv)
        if not face_uvs and len(uvs) == len(verts):
            face_uvs = faces

        return (
            np.array(verts, dtype=np.float32),
            np.array(faces, dtype=np.int32),
            np.array(uvs, dtype=np.float32) if uvs else np.zeros((len(verts), 2), dtype=np.float32),
            np.array(face_uvs, dtype=np.int32) if face_uvs else np.zeros((len(faces), 3), dtype=np.int32)
        )

    def analyze_topology(self, verts, faces):
        """Identifica componentes conexos e separa mangas do torso via Midline Crossing."""
        from collections import defaultdict
        adj = defaultdict(set)
        for f in faces:
            for i in range(len(f)):
                v0, v1 = f[i], f[(i + 1) % len(f)]
                adj[v0].add(v1)
                adj[v1].add(v0)

        visited = set()
        components = []
        for v in range(len(verts)):
            if v not in visited:
                comp = []
                stack = [v]
                visited.add(v)
                while stack:
                    curr = stack.pop()
                    comp.append(curr)
                    for nxt in adj[curr]:
                        if nxt not in visited:
                            visited.add(nxt)
                            stack.append(nxt)
                components.append(comp)

        max_abs_x = float(np.max(np.abs(verts[:, 0])))
        y_min_orig = float(np.min(verts[:, 1]))
        y_max_orig = float(np.max(verts[:, 1]))
        span_y = y_max_orig - y_min_orig
        hem_y = y_min_orig + 0.20 * span_y

        norm_scale = 1.80 / span_y if span_y > 2.0 else 1.0
        world_width = max_abs_x * 0.54 * norm_scale

        # Largura da porção superior (ombros/peito)
        top_mask = verts[:, 1] > (y_min_orig + 0.45 * span_y)
        top_max_x = float(np.max(np.abs(verts[top_mask, 0]))) if np.any(top_mask) else max_abs_x
        top_world_w = top_max_x * 0.54 * norm_scale

        # Se a largura nos ombros ou a largura total for menor ou igual à largura dos ombros do tronco (0.38m),
        # a peça é uma REGATA / TANK TOP / COLETE / VESTIDO SEM MANGAS. Todos os vértices pertencem ao torso.
        if top_world_w <= 0.38 or world_width <= 0.38:
            return set(), set(range(len(verts)))

        sleeve_indices = set()
        torso_indices = set()

        sleeve_x_thresh_obj = 0.22 / (0.54 * norm_scale + 1e-8)
        arm_y_min_obj = y_min_orig + 0.25 * span_y

        if len(components) > 1:
            for c in components:
                c_xs = verts[c, 0]
                min_x = float(np.min(c_xs))
                max_x = float(np.max(c_xs))
                max_y = float(np.max(verts[c, 1]))
                comp_max_abs_x = max(abs(min_x), abs(max_x))
                comp_world_x = comp_max_abs_x * 0.54 * norm_scale
                crosses_midline = (min_x < -0.10 and max_x > 0.10)

                if crosses_midline:
                    # Se o componente cruza a linha média mas se estende para os braços (ex: malha monobloco braço-a-braço > 0.42m),
                    # classifica os vértices pontualmente por coordenadas espaciais. Caso contrário, é 100% torso.
                    if comp_world_x > 0.42:
                        for idx in c:
                            vx = verts[idx, 0]
                            vy = verts[idx, 1]
                            if abs(vx) > sleeve_x_thresh_obj and vy > arm_y_min_obj:
                                sleeve_indices.add(idx)
                            else:
                                torso_indices.add(idx)
                    else:
                        torso_indices.update(c)
                else:
                    # Componentes laterais (mangas, punhos, braçadeiras, laços de manga):
                    # Se o componente alcança a região dos braços (> 0.22m) ou é um punho/braçadeira,
                    # classifica integralmente como manga (independente de tamanho do componente).
                    if comp_world_x > 0.22 and max_y > arm_y_min_obj:
                        sleeve_indices.update(c)
                    elif comp_world_x > 0.30:
                        sleeve_indices.update(c)
                    else:
                        torso_indices.update(c)
            return sleeve_indices, torso_indices

        # Fallback para malha monobloco soldada (único componente conexo)
        center_mask = np.abs(verts[:, 0]) < 0.25 * max_abs_x
        torso_y_min = float(np.min(verts[center_mask, 1])) if np.any(center_mask) else y_min_orig
        hem_band = verts[np.abs(verts[:, 1] - torso_y_min) < 0.15 * span_y]
        inner_hem = hem_band[np.abs(hem_band[:, 0]) < 0.70 * max_abs_x]
        torso_hem_w = float(np.max(np.abs(inner_hem[:, 0]))) if len(inner_hem) > 0 else 0.40 * max_abs_x

        sleeve_x_thresh = max(0.40 * max_abs_x, 0.22 / (0.54 * norm_scale + 1e-8))

        for i in range(len(verts)):
            x = verts[i, 0]
            y = verts[i, 1]
            if abs(x) > sleeve_x_thresh and y > (torso_y_min + 0.25 * span_y):
                sleeve_indices.add(i)
            else:
                torso_indices.add(i)

        return sleeve_indices, torso_indices

    def fit_top_clothing(self, verts, faces, sleeve_indices, torso_indices, is_jacket: bool = False, is_dress: bool = False):
        """Executa tapering da cintura, gola Hermite e detecção inteligente de mangas."""
        y_min_orig = float(np.min(verts[:, 1]))
        y_max_orig = float(np.max(verts[:, 1]))
        total_y_span = y_max_orig - y_min_orig
        norm_scale = 1.80 / total_y_span if total_y_span > 2.0 else 1.0
        uniform_scale = 0.54 * norm_scale
        # Ancoragem Anatômica Universal dos Ombros:
        # A peça de roupa repousa sobre a sustentação anatômica dos ombros/clavícula.
        # Topo anatômico do ombro: Z ≈ 1.475m (feminino), Z ≈ 1.485m (masculino), com +0.020m para jaquetas/bombers.
        target_shoulder_z = 1.475
        sh_mask = (np.abs(verts[:, 0]) >= 0.35) & (np.abs(verts[:, 0]) <= 0.75) & (verts[:, 1] > 0)
        shoulder_y = float(np.max(verts[sh_mask, 1])) if np.any(sh_mask) else y_max_orig
        loc_z = target_shoulder_z - shoulder_y * uniform_scale

        if sleeve_indices:
            sleeve_ys = verts[list(sleeve_indices), 1]
            min_sleeve_y = float(np.min(sleeve_ys))
            lowest_sleeve_z = loc_z + min_sleeve_y * uniform_scale
        else:
            min_sleeve_y = 1.0
            lowest_sleeve_z = 2.0

        is_sleeveless = (len(sleeve_indices) == 0 or lowest_sleeve_z > 1.32)
        is_long_sleeves = (lowest_sleeve_z <= self.wrist_z + 0.12) and not is_sleeveless
        is_short_sleeves = not is_sleeveless and not is_long_sleeves

        adj_verts = verts.copy()

        # Alinhamento Suave da Manga em Profundidade (Z local -> Y mundo)
        # Transição suave: zero na costura do ombro até o alinhamento pleno no punho
        # Elimina 100% de cisalhamento, degraus e rasgos na costura entre manga e torso
        if sleeve_indices:
            s_list = list(sleeve_indices)
            raw_sleeve_z_mean = float(np.mean(adj_verts[s_list, 2]))
            s_xs = np.abs(adj_verts[s_list, 0])
            min_sx = float(np.min(s_xs))
            max_sx = float(np.max(s_xs))
            trans_len = max_sx - min_sx + 1e-8
            for idx in s_list:
                t = max(0.0, min(1.0, (abs(adj_verts[idx, 0]) - min_sx) / trans_len))
                w = t * t * (3.0 - 2.0 * t)
                adj_verts[idx, 2] -= raw_sleeve_z_mean * w

        # Transforma para o espaço 3D da A-Pose canônica (sem distorções destrutivas manuais)
        world_apose = np.zeros_like(adj_verts)
        world_apose[:, 0] = -adj_verts[:, 0] * uniform_scale
        world_apose[:, 1] = adj_verts[:, 2] * uniform_scale + -0.051
        world_apose[:, 2] = adj_verts[:, 1] * uniform_scale + loc_z

        return world_apose, lowest_sleeve_z, is_sleeveless, is_short_sleeves, is_long_sleeves

    def fit_bottom_clothing(self, verts, target_waist_z=None):
        """Ajusta calças e sapatos a partir do cós até a sola do chão."""
        y_min_orig = float(np.min(verts[:, 1]))
        y_max_orig = float(np.max(verts[:, 1]))
        total_y_span = y_max_orig - y_min_orig

        if target_waist_z is None:
            # Meio do caminho do declive anatômico (entre 0.928m da pelve e 1.067m da cintura superior)
            target_waist_z = 1.000
        target_sole_z = -0.010
        target_z_span = target_waist_z - target_sole_z

        scale_y = target_z_span / (total_y_span + 1e-8)
        loc_z = target_waist_z - y_max_orig * scale_y
        loc_y = 0.005

        world_tpose = np.zeros_like(verts)
        world_tpose[:, 0] = -verts[:, 0] * scale_y
        world_tpose[:, 1] = verts[:, 2] * scale_y + loc_y
        world_tpose[:, 2] = verts[:, 1] * scale_y + loc_z

        return world_tpose

    def deform_top_mesh(self, input_verts, faces, sleeve_indices, torso_indices, is_jacket: bool = False, is_sleeveless: bool = False):
        """Aplica a deformação baricêntrica contínua particionada por membros (Torso, Braço E, Braço D).
        Elimina 100% de rasgos na dorsal e costuras do ombro via relaxamento Laplaciano no anel da costura.
        """
        if self.dual_cage_ready:
            return self.deform_dual_cage(input_verts, faces, sleeve_indices, torso_indices, is_jacket=is_jacket, is_sleeveless=is_sleeveless)

        tri_a = self.cage_verts_apose[self.cage_faces[:, 0]]
        tri_b = self.cage_verts_apose[self.cage_faces[:, 1]]
        tri_c = self.cage_verts_apose[self.cage_faces[:, 2]]

        dst_a = self.cage_verts_rest[self.cage_faces[:, 0]]
        dst_b = self.cage_verts_rest[self.cage_faces[:, 1]]
        dst_c = self.cage_verts_rest[self.cage_faces[:, 2]]

        def deform_point(p, grid, subset_idx, is_sleeve=False):
            cands_local = grid.query_nearest_candidates(p, 1) or grid.query_nearest_candidates(p, 2) or range(len(subset_idx))
            best_d = float("inf")
            best_u, best_v, best_w = 1.0, 0.0, 0.0
            best_t = subset_idx[0]
            best_offset = np.zeros(3)

            for l_idx in cands_local:
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

            p_t = best_u * ta + best_v * tb + best_w * tc

            R = np.column_stack([dst_u, dst_v, dst_norm]) @ np.column_stack([src_u, src_v, src_norm]).T
            rot_offset = R @ best_offset
            n_dist = float(np.dot(rot_offset, dst_norm))
            tan_vec = rot_offset - n_dist * dst_norm

            # Damping de puffiness normal (impede peças oversized/boxy de inflarem desmedidamente)
            max_n = 0.045 if is_jacket else 0.035
            min_n = 0.010 if is_sleeve else 0.005

            tan_len = float(np.linalg.norm(tan_vec))

            # Clamping normal anatômico:
            # Na região da gola/nuca (dst_norm[2] > 0.35): a normal aponta para cima.
            # Preserva o offset natural da modelagem (n_dist pode ser negativo para decotes baixos/abertos),
            # impedindo que a gola de camisas ou decotes seja forçada para cima até o queixo/cabeça.
            if dst_norm[2] > 0.35:
                d_n = n_dist
                d_tan = tan_vec
            else:
                if n_dist > 0.016:
                    d_n = 0.016 + (n_dist - 0.016) * 0.35
                    d_n = min(d_n, max_n)
                elif n_dist < min_n:
                    d_n = min_n
                else:
                    d_n = n_dist

                # Damping tangencial no tronco (evita que a barra forme pontas excessivamente largas)
                max_tan = 0.045 if is_jacket else (0.038 if is_sleeve else 0.026)
                if tan_len > max_tan:
                    d_tan = tan_vec * ((max_tan + (tan_len - max_tan) * 0.30) / tan_len)
                else:
                    d_tan = tan_vec

            # Regatas, alças finas e biquínis: conformação suave e direta sobre o busto e ombros
            if is_sleeveless and p[2] > 1.22 and not is_jacket:
                d_n = max(0.003, min(d_n, 0.008))
                d_tan = tan_vec * (min(tan_len, 0.008) / (tan_len + 1e-8))

            # Folga de camada externa (+0.005m na normal) para sobrepor a cintura da calça sem z-fighting
            layer_offset = (0.005 * dst_norm) if p[2] < 1.02 else np.zeros(3)
            return p_t + d_n * dst_norm + d_tan + layer_offset

        sh_start = 0.12
        sh_end   = 0.21
        seam_x_min = 0.11

        deformed = input_verts.copy()
        if is_sleeveless or len(sleeve_indices) == 0:
            for i in range(len(input_verts)):
                p = input_verts[i]
                deformed[i] = deform_point(p, self.grid_apose_g0, self.g0_tris, is_sleeve=False)
        else:
            for i in range(len(input_verts)):
                p = input_verts[i]
                ax = abs(p[0])
                if i in sleeve_indices:
                    grid_arm = self.grid_apose_g1 if p[0] > 0 else self.grid_apose_g2
                    tris_arm = self.g1_tris if p[0] > 0 else self.g2_tris
                    if ax > sh_end:
                        deformed[i] = deform_point(p, grid_arm, tris_arm, is_sleeve=True)
                    else:
                        w_arm = smoothstep(sh_start, sh_end, ax)
                        p_t = deform_point(p, self.grid_apose_g0, self.g0_tris, is_sleeve=False)
                        p_a = deform_point(p, grid_arm, tris_arm, is_sleeve=True)
                        deformed[i] = (1.0 - w_arm) * p_t + w_arm * p_a
                else: # torso
                    if ax > sh_start and p[2] > 1.15:
                        w_arm = smoothstep(sh_start, sh_end, ax) * 0.85
                        p_t = deform_point(p, self.grid_apose_g0, self.g0_tris, is_sleeve=False)
                        grid_arm = self.grid_apose_g1 if p[0] > 0 else self.grid_apose_g2
                        tris_arm = self.g1_tris if p[0] > 0 else self.g2_tris
                        p_a = deform_point(p, grid_arm, tris_arm, is_sleeve=True)
                        deformed[i] = (1.0 - w_arm) * p_t + w_arm * p_a
                    else:
                        deformed[i] = deform_point(p, self.grid_apose_g0, self.g0_tris, is_sleeve=False)

        # Adjacência de arestas topológicas
        adj = {}
        for face in faces:
            for fi in range(len(face)):
                i0, i1 = face[fi], face[(fi + 1) % len(face)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        # Conexão geométrica entre componentes da costura ombro/manga
        grid_in = SpatialGrid3D(cell_size=0.05)
        grid_in.build(input_verts)
        seam_verts = set()

        for f_v in faces:
            has_sleeve = any(idx in sleeve_indices for idx in f_v)
            has_torso = any(idx in torso_indices for idx in f_v)
            if has_sleeve and has_torso:
                seam_verts.update(f_v)

        for si in sleeve_indices:
            p = input_verts[si]
            if p[2] > 1.12:
                cands = grid_in.query_nearest_candidates(p, 1) or grid_in.query_nearest_candidates(p, 2)
                for ti in cands:
                    if ti in torso_indices:
                        d = float(np.linalg.norm(p - input_verts[ti]))
                        if d < 0.040:
                            adj.setdefault(si, set()).add(ti)
                            adj.setdefault(ti, set()).add(si)
                            seam_verts.add(si)
                            seam_verts.add(ti)

        # Identifica anel de costura expandido (apenas ombro e braço superior, sem afetar a barra da cintura)
        disp = deformed - input_verts
        smoothed_disp = disp.copy()
        seam_ring = {v_i for v_i in seam_verts if input_verts[v_i, 2] > 1.12 and abs(input_verts[v_i, 0]) > seam_x_min}
        for _ in range(3):
            for v_i in list(seam_ring):
                for nbr in adj.get(v_i, []):
                    if input_verts[nbr, 2] > 1.12 and abs(input_verts[nbr, 0]) > seam_x_min:
                        seam_ring.add(nbr)

        # Relaxamento Laplaciano suave no anel da costura para uniformizar a curvatura da transição
        for _ in range(16):
            new_disp = smoothed_disp.copy()
            for s_i in seam_ring:
                nbrs = list(adj.get(s_i, []))
                if nbrs:
                    new_disp[s_i] = 0.40 * smoothed_disp[s_i] + 0.60 * np.mean(smoothed_disp[nbrs], axis=0)
            smoothed_disp = new_disp
        res_verts = input_verts + smoothed_disp

        # Suavização 1D de curvatura sobre a clavícula para alças finas (regatas, biquínis, vestidos)
        # Elimina micro-ondulações ou facetas angulares resultantes da discretização triangular da cage
        if is_sleeveless:
            strap_verts = {
                i for i in range(len(input_verts))
                if abs(input_verts[i, 0]) >= 0.08 and abs(input_verts[i, 0]) <= 0.18 and input_verts[i, 2] > 1.35
            }
            for _ in range(2):
                new_res = res_verts.copy()
                for s_i in strap_verts:
                    nbrs = [n for n in adj.get(s_i, []) if n in strap_verts]
                    if nbrs:
                        new_res[s_i] = 0.60 * res_verts[s_i] + 0.40 * np.mean(res_verts[nbrs], axis=0)
                res_verts = new_res

        return res_verts

    def deform_mesh(self, input_verts, src_cage, dst_cage, spatial_grid):
        """Aplica a deformação baricêntrica acelerada de uma cage fonte para uma cage destino."""
        tri_a = src_cage[self.cage_faces[:, 0]]
        tri_b = src_cage[self.cage_faces[:, 1]]
        tri_c = src_cage[self.cage_faces[:, 2]]

        dst_a = dst_cage[self.cage_faces[:, 0]]
        dst_b = dst_cage[self.cage_faces[:, 1]]
        dst_c = dst_cage[self.cage_faces[:, 2]]

        deformed = np.zeros_like(input_verts)

        for i in range(len(input_verts)):
            p = input_verts[i]
            cands = spatial_grid.query_nearest_candidates(p, k_neighbors=1)
            if not cands:
                cands = spatial_grid.query_nearest_candidates(p, k_neighbors=2)
            if not cands:
                cands = range(len(self.cage_faces))

            best_dist = float("inf")
            best_u, best_v, best_w = 1.0, 0.0, 0.0
            best_tri = 0
            best_offset = np.zeros(3)

            for tri_idx in cands:
                a, b, c = tri_a[tri_idx], tri_b[tri_idx], tri_c[tri_idx]
                q, u, v, w = closest_point_on_triangle(p, a, b, c)
                d = float(np.linalg.norm(p - q))
                if d < best_dist:
                    best_dist = d
                    best_u, best_v, best_w = u, v, w
                    best_tri = tri_idx
                    best_offset = p - q

            ta = dst_a[best_tri]
            tb = dst_b[best_tri]
            tc = dst_c[best_tri]

            src_u = tri_b[best_tri] - tri_a[best_tri]
            src_u /= (np.linalg.norm(src_u) + 1e-8)
            src_norm = np.cross(src_u, tri_c[best_tri] - tri_a[best_tri])
            src_norm /= (np.linalg.norm(src_norm) + 1e-8)
            src_v = np.cross(src_norm, src_u)

            dst_u = tb - ta
            dst_u /= (np.linalg.norm(dst_u) + 1e-8)
            dst_norm = np.cross(dst_u, tc - ta)
            dst_norm /= (np.linalg.norm(dst_norm) + 1e-8)
            dst_v = np.cross(dst_norm, dst_u)

            R_src = np.column_stack([src_u, src_v, src_norm])
            R_dst = np.column_stack([dst_u, dst_v, dst_norm])
            R = R_dst @ R_src.T

            p_target = best_u * ta + best_v * tb + best_w * tc
            eff_offset = best_offset.copy()
            # Transição suave e contínua de offset, evitando degraus ou vincos artificiais nas coxas
            if p_target[2] < 0.78:
                eff_offset = best_offset * 0.75
            elif p_target[2] < 0.90:
                t = (p_target[2] - 0.78) / 0.12
                eff_offset = best_offset * (0.75 + 0.25 * t)
            off_vec = R @ eff_offset
            norm_comp = float(np.dot(off_vec, dst_norm))
            min_clear = 0.003
            if p_target[2] > 0.86 and dst_norm[1] < -0.3:
                min_clear = 0.006
                # Fivela do cinto frontal (|X| < 0.04 e Z entre 0.90 e 0.96)
                if abs(p_target[0]) < 0.04 and 0.90 < p_target[2] < 0.96:
                    min_clear = 0.012
            if norm_comp < min_clear:
                off_vec += (min_clear - norm_comp) * dst_norm
            deformed[i] = p_target + off_vec

        return deformed

    def deform_bottom_mesh(self, input_verts: np.ndarray, faces: list) -> np.ndarray:
        """Aplica deformação baricêntrica contínua e suave para peças inferiores (calças, saias).
        Utiliza relaxamento Laplaciano no campo de deslocamento para eliminar 100% de rasgos,
        buracos na virilha e vincos nas pernas preservando o caimento da peça de forma global.
        """
        src_cage = self.cage_verts_tpose_85
        dst_cage = self.cage_verts_rest

        tri_a = src_cage[self.cage_faces[:, 0]]
        tri_b = src_cage[self.cage_faces[:, 1]]
        tri_c = src_cage[self.cage_faces[:, 2]]

        dst_a = dst_cage[self.cage_faces[:, 0]]
        dst_b = dst_cage[self.cage_faces[:, 1]]
        dst_c = dst_cage[self.cage_faces[:, 2]]

        raw_deformed = np.zeros_like(input_verts)
        for i in range(len(input_verts)):
            p = input_verts[i]
            cands = self.grid_tpose.query_nearest_candidates(p, k_neighbors=1) or range(len(self.cage_faces))
            best_dist = float("inf")
            best_u, best_v, best_w = 1.0, 0.0, 0.0
            best_tri = 0
            best_offset = np.zeros(3)
            for tri_idx in cands:
                a, b, c = tri_a[tri_idx], tri_b[tri_idx], tri_c[tri_idx]
                q, u, v, w = closest_point_on_triangle(p, a, b, c)
                d = float(np.linalg.norm(p - q))
                if d < best_dist:
                    best_dist = d
                    best_u, best_v, best_w = u, v, w
                    best_tri = tri_idx
                    best_offset = p - q

            ta, tb, tc = dst_a[best_tri], dst_b[best_tri], dst_c[best_tri]
            src_u = tri_b[best_tri] - tri_a[best_tri]
            src_u /= (np.linalg.norm(src_u) + 1e-8)
            src_norm = np.cross(src_u, tri_c[best_tri] - tri_a[best_tri])
            src_norm /= (np.linalg.norm(src_norm) + 1e-8)
            src_v = np.cross(src_norm, src_u)

            dst_u = tb - ta
            dst_u /= (np.linalg.norm(dst_u) + 1e-8)
            dst_norm = np.cross(dst_u, tc - ta)
            dst_norm /= (np.linalg.norm(dst_norm) + 1e-8)
            dst_v = np.cross(dst_norm, dst_u)

            R = np.column_stack([dst_u, dst_v, dst_norm]) @ np.column_stack([src_u, src_v, src_norm]).T
            p_target = best_u * ta + best_v * tb + best_w * tc
            raw_deformed[i] = p_target + R @ best_offset

        # 1. Identifica grupos de vértices coincidentes (costuras de textura UV / arestas duras)
        pos_map = {}
        for idx, v in enumerate(input_verts):
            key = (round(float(v[0]), 4), round(float(v[1]), 4), round(float(v[2]), 4))
            pos_map.setdefault(key, []).append(idx)
        coincident_groups = [idxs for idxs in pos_map.values() if len(idxs) > 1]

        # 2. Constrói grafo de adjacência unindo faces e costuras UV
        adj = {}
        for f in faces:
            for fi in range(len(f)):
                i0, i1 = f[fi], f[(fi + 1) % len(f)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        for group in coincident_groups:
            for i in group:
                for j in group:
                    if i != j:
                        adj.setdefault(i, set()).add(j)

        # 3. Relaxamento Laplaciano com soldagem garantida das costuras
        disp = raw_deformed - input_verts
        for group in coincident_groups:
            mean_d = np.mean([disp[idx] for idx in group], axis=0)
            for idx in group:
                disp[idx] = mean_d

        smoothed_disp = disp.copy()
        for _ in range(25):
            new_disp = smoothed_disp.copy()
            for v_idx in range(len(input_verts)):
                nbrs = list(adj.get(v_idx, []))
                if nbrs:
                    new_disp[v_idx] = 0.50 * smoothed_disp[v_idx] + 0.50 * np.mean(smoothed_disp[nbrs], axis=0)
            for group in coincident_groups:
                mean_d = np.mean([new_disp[idx] for idx in group], axis=0)
                for idx in group:
                    new_disp[idx] = mean_d
            smoothed_disp = new_disp

        return input_verts + smoothed_disp

    def _project_onto_r15_cage(self, point, part_data):
        """Projeta um ponto na superfície de uma cage R15, retornando posição e offset.

        Retorna (projected_pos, offset_along_normal, distance).
        """
        verts = part_data["verts"]
        faces = part_data["faces"]
        grid = part_data["grid"]

        tri_a = verts[faces[:, 0]]
        tri_b = verts[faces[:, 1]]
        tri_c = verts[faces[:, 2]]

        cands = grid.query_nearest_candidates(point, 1)
        if not cands:
            cands = grid.query_nearest_candidates(point, 2)
        if not cands:
            cands = range(len(faces))

        best_dist = float("inf")
        best_q = point.copy()
        best_normal = np.array([0.0, 0.0, 1.0])

        for tri_idx in cands:
            a, b, c = tri_a[tri_idx], tri_b[tri_idx], tri_c[tri_idx]
            q, u, v, w = closest_point_on_triangle(point, a, b, c)
            d = float(np.linalg.norm(point - q))
            if d < best_dist:
                best_dist = d
                best_q = q
                n = np.cross(b - a, c - a)
                n_len = np.linalg.norm(n)
                best_normal = n / n_len if n_len > 1e-10 else np.array([0.0, 0.0, 1.0])

        return best_q, best_normal, best_dist

    def deform_top_mesh_r15(self, apose_verts, faces, sleeve_indices, torso_indices, is_jacket: bool = False, is_sleeveless: bool = False):
        """Deformação anatômica universal R15 para corpo feminino.

        Combina a deformação contínua do torso (UpperTorso / LowerTorso) com rotação
        de Lie óssea de 2 segmentos nos membros superiores, acompanhando a Rest Pose flexionada
        a 15.8° e com envelope radial progressivo.
        """
        # Se for regata ou sem mangas, deforma integralmente pelo torso cage
        if is_sleeveless or len(sleeve_indices) == 0:
            return self.deform_top_mesh(
                apose_verts, faces, set(), set(range(len(apose_verts))),
                is_jacket=is_jacket, is_sleeveless=True
            )

        # Centros ósseos das mangas:
        # Origem (A-Pose canônica Roblox)
        s_top = np.array([0.2400, 0.0100, 1.3500], dtype=np.float32)
        s_el  = np.array([0.4038, 0.0260, 0.9847], dtype=np.float32)
        s_wr  = np.array([0.7323, -0.0382, 0.6128], dtype=np.float32)

        # Destino (Corpo feminino do Isometricon em Rest Pose com braços flexionados)
        # Coordenadas em wear_engine: X lateral, Y profundidade (-Y frente, +Y trás), Z altura
        d_top = np.array([0.1761, -0.0554, 1.4510], dtype=np.float32)
        d_el  = np.array([0.2558,  0.0271, 1.1544], dtype=np.float32)
        d_wr  = np.array([0.3859,  0.0212, 0.6955], dtype=np.float32)

        b_src_ua = s_el - s_top
        b_dst_ua = d_el - d_top
        b_src_fa = s_wr - s_el
        b_dst_fa = d_wr - d_el

        def get_rotation_between(v1, v2):
            v1 = v1 / (np.linalg.norm(v1) + 1e-8)
            v2 = v2 / (np.linalg.norm(v2) + 1e-8)
            axis = np.cross(v1, v2)
            axis_len = np.linalg.norm(axis)
            if axis_len < 1e-6:
                return np.eye(3, dtype=np.float32)
            axis /= axis_len
            angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
            K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]], dtype=np.float32)
            return np.eye(3, dtype=np.float32) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)

        R_ua = get_rotation_between(b_src_ua, b_dst_ua)
        R_fa = get_rotation_between(b_src_fa, b_dst_fa)

        def deform_left_arm_vertex(p):
            if p[2] > s_el[2]:
                t_ua = (s_top[2] - p[2]) / (s_top[2] - s_el[2] + 1e-8)
                t = t_ua * 0.5
            else:
                t_fa = (s_el[2] - p[2]) / (s_el[2] - s_wr[2] + 1e-8)
                t = 0.5 + t_fa * 0.5
                
            t = max(0.0, min(1.0, t))
            
            if t <= 0.5:
                u = t / 0.5
                c_src = (1.0 - u) * s_top + u * s_el
                c_dst = (1.0 - u) * d_top + u * d_el
                R = R_ua
            else:
                u = (t - 0.5) / 0.5
                c_src = (1.0 - u) * s_el + u * s_wr
                c_dst = (1.0 - u) * d_el + u * d_wr
                w_rot = smoothstep(0.40, 0.60, t)
                R = (1.0 - w_rot) * R_ua + w_rot * R_fa
                
            delta = p - c_src
            rot_delta = R @ delta
            
            r = np.sqrt(rot_delta[0]**2 + rot_delta[1]**2)
            r_min = (1.0 - t) * 0.075 + t * 0.088
            r_target = max(r * 1.12, r_min)
            scale_r = r_target / (r + 1e-8)
            rot_delta[0] *= scale_r
            rot_delta[1] *= scale_r
            
            return c_dst + rot_delta

        # Deformação contínua do torso (mantendo puffiness e folga natural)
        torso_deformed = self.deform_top_mesh(
            apose_verts, faces, set(), set(range(len(apose_verts))),
            is_jacket=is_jacket, is_sleeveless=False
        )

        deformed = np.zeros_like(apose_verts)

        for i in range(len(apose_verts)):
            p = apose_verts[i]
            ax = abs(p[0])
            
            if p[0] > 0:
                p_arm = deform_left_arm_vertex(p)
            else:
                p_sym = np.array([-p[0], p[1], p[2]], dtype=np.float32)
                p_arm_sym = deform_left_arm_vertex(p_sym)
                p_arm = np.array([-p_arm_sym[0], p_arm_sym[1], p_arm_sym[2]], dtype=np.float32)
                
            p_torso = torso_deformed[i]
            
            # Seam transition suave: ax in [0.15, 0.25] e Z > 1.20
            if p[2] > 1.20 and 0.15 <= ax <= 0.25:
                w = smoothstep(0.15, 0.25, ax)
                deformed[i] = (1.0 - w) * p_torso + w * p_arm
            elif i in sleeve_indices:
                deformed[i] = p_arm
            else:
                deformed[i] = p_torso

        # Adjacência de arestas para relaxamento Laplaciano no campo de deslocamento
        adj = {}
        for face in faces:
            for fi in range(len(face)):
                i0, i1 = face[fi], face[(fi + 1) % len(face)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        seam_verts = set()
        for f in faces:
            has_s = any(idx in sleeve_indices for idx in f)
            has_t = any(idx in torso_indices for idx in f)
            if has_s and has_t:
                seam_verts.update(f)

        seam_ring = set(seam_verts)
        for _ in range(2):
            for s in list(seam_ring):
                seam_ring.update(adj.get(s, []))

        disp = deformed - apose_verts
        smoothed_disp = disp.copy()
        for _ in range(16):
            new_disp = smoothed_disp.copy()
            for s in seam_ring:
                nbrs = list(adj.get(s, []))
                if nbrs:
                    new_disp[s] = 0.50 * smoothed_disp[s] + 0.50 * np.mean(smoothed_disp[nbrs], axis=0)
            smoothed_disp = new_disp

        return apose_verts + smoothed_disp

    def deform_mesh_r15(self, rest_verts, faces):
        """Deformação R15 nativa para peças inferiores (calças, saias) usando as cages femininas.

        Cada vértice é projetado na cage R15 correspondente (LowerTorso, pernas, pés).
        """
        if not self.body_cages:
            return rest_verts

        deformed = np.zeros_like(rest_verts)
        cage_assignment = {}

        for i in range(len(rest_verts)):
            p = rest_verts[i]

            # 1. Mede o offset original em relação à cage rest masculina
            cands_m = self.grid_rest.query_nearest_candidates(p, 1) or range(len(self.cage_faces))
            best_dm = float('inf')
            best_qm = p
            best_nm = np.array([0.0, 0.0, 1.0])
            for t in cands_m:
                q, u, v, w = closest_point_on_triangle(p, self.tri_ra[t], self.tri_rb[t], self.tri_rc[t])
                d = float(np.linalg.norm(p - q))
                if d < best_dm:
                    best_dm = d
                    best_qm = q
                    n = np.cross(self.tri_rb[t] - self.tri_ra[t], self.tri_rc[t] - self.tri_ra[t])
                    nl = np.linalg.norm(n)
                    best_nm = n / nl if nl > 1e-8 else np.array([0.0, 0.0, 1.0])

            signed_offset = float(np.dot(p - best_qm, best_nm))
            cloth_offset = max(0.002, min(signed_offset, 0.020))

            region_name = _assign_cage_region(p, _BOTTOM_CAGE_REGIONS, self.body_cages)
            if region_name is None:
                region_name = "LowerTorso"

            cage_assignment[i] = region_name
            part_data = self.body_cages[region_name]
            proj_q, normal, dist = self._project_onto_r15_cage(p, part_data)

            deformed[i] = proj_q + cloth_offset * normal

        # Adjacência de arestas para relaxamento Laplaciano
        adj = {}
        for face in faces:
            for fi in range(len(face)):
                i0, i1 = face[fi], face[(fi + 1) % len(face)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        seam_verts = set()
        for f_v in faces:
            cage_names_in_face = set()
            for idx in f_v:
                if idx in cage_assignment:
                    cage_names_in_face.add(cage_assignment[idx])
            if len(cage_names_in_face) > 1:
                seam_verts.update(f_v)

        seam_ring = set(seam_verts)
        for _ in range(2):
            for v_i in list(seam_ring):
                seam_ring.update(adj.get(v_i, []))

        disp = deformed - rest_verts
        smoothed_disp = disp.copy()
        for _ in range(8):
            new_disp = smoothed_disp.copy()
            for s_i in seam_ring:
                nbrs = list(adj.get(s_i, []))
                if nbrs:
                    new_disp[s_i] = 0.5 * smoothed_disp[s_i] + 0.5 * np.mean(smoothed_disp[nbrs], axis=0)
            smoothed_disp = new_disp

        return rest_verts + smoothed_disp

    def taper_female_sleeves(self, verts: np.ndarray, sleeve_idx: set, is_jacket: bool = False) -> np.ndarray:
        """Afina anatomicamente a manga longa ao longo do antebraço feminino (do cotovelo ao punho),
        eliminando o efeito de manga espalhada / boca-de-sino e harmonizando com o corpo estilizado.
        Para jaquetas/bombers, aplica afunilamento suave (12%) para preservar punhos elásticos volumosos e estilo oversized.
        """
        v = verts.copy()
        elbow_z = 1.1543
        wrist_z = 0.6955
        taper_factor = 0.12 if is_jacket else 0.42
        for side_mult in [1, -1]:
            s_side = [i for i in sleeve_idx if (v[i, 0] * side_mult) > 0.18 and v[i, 2] < 1.45]
            if not s_side:
                continue

            z_min = float(np.min(v[s_side, 2]))
            effective_wrist_z = min(wrist_z, z_min)
            for i in s_side:
                z = v[i, 2]
                if z < elbow_z:
                    t = max(0.0, min(1.0, (elbow_z - z) / (elbow_z - effective_wrist_z + 1e-8)))
                    # Eixo central do braço feminino (acompanha a inclinação natural em direção à mão)
                    cx = side_mult * (0.2566 + t * (0.3862 - 0.2566))
                    cy = 0.0324 + t * (0.0214 - 0.0324)

                    # Redução progressiva da largura e profundidade oversized em direção ao punho
                    scale = 1.0 - t * taper_factor
                    v[i, 0] = cx + (v[i, 0] - cx) * scale
                    v[i, 1] = cy + (v[i, 1] - cy) * scale

        return v

    def support_female_waistband(self, verts: np.ndarray) -> np.ndarray:
        """Garante que a cintura e cinto da calça feminina permaneçam apoiados sobre a pelve:
        - Impede que qualquer vértice afunde para dentro da cavidade da pelve (parede da pelve Y ≈ -0.185m).
        """
        v = verts.copy()
        for i in range(len(v)):
            x, y, z = v[i]
            if z > 0.86 and y < -0.04:
                ax = abs(x)
                if ax < 0.12:
                    min_y = -0.190 - 0.005 * (1.0 - (ax / 0.12) ** 2)
                    if y > min_y:
                        v[i, 1] = min_y

        return v

    def smooth_female_pants_legs(self, verts: np.ndarray, faces: list, iterations: int = 3) -> np.ndarray:
        """Suaviza os vincos e facetas das pernas da calça feminina causados por variações
        normais da cage, mantendo a cintura e cinto (Z >= 0.86m) 100% ancorados."""
        v = verts.copy()
        adj_v = {}
        for f in faces:
            for i in range(len(f)):
                i0 = f[i]
                i1 = f[(i + 1) % len(f)]
                adj_v.setdefault(i0, set()).add(i1)
                adj_v.setdefault(i1, set()).add(i0)

        for _ in range(iterations):
            new_v = v.copy()
            for i in range(len(v)):
                if v[i, 2] < 0.86:
                    nbrs = list(adj_v.get(i, []))
                    if nbrs:
                        new_v[i] = 0.60 * v[i] + 0.40 * np.mean(v[nbrs], axis=0)
            v = new_v
        return v

    def wear(self, asset_id, output_obj=None, body_type=None, target_waist_z=None):
        """Executa o pipeline nativo completo de ponta a ponta sem Blender."""
        target_body = str(body_type).lower() if body_type is not None else self.body_type
        if target_body != self.body_type:
            engine = RobloxWearEngine(body_type=target_body)
            return engine.wear(asset_id, output_obj=output_obj, target_waist_z=target_waist_z)

        t0 = time.perf_counter()
        print(f"\n==================================================")
        print(f"  VESTIR ASSET NATIVO PYTHON: {asset_id} ({self.body_type.upper()})")
        print(f"==================================================")

        meta = self.fetch_asset(asset_id)
        type_id = meta.get("type_id", 65)

        # Para AssetType 72 (Dress/Skirt): auto-detecta vestido vs saia pela geometria/nome
        # Vestidos chegam até o peito (cobertura total → tratar como top/full-outfit)
        # Saias/skorts são apenas inferiores
        if type_id == 72 and meta.get("is_top") is False:
            asset_name_lower = meta.get("name", "").lower()
            is_dress = any(k in asset_name_lower for k in ["dress", "vestido", "gown", "sundress", "robe", "kimono"])
            is_skirt_word = any(k in asset_name_lower for k in ["skirt", "saia", "skort", "tutu", "kilt"])
            if is_dress and not is_skirt_word:
                meta = dict(meta, is_top=True)
            elif not is_skirt_word:
                # Fallback geométrico: lê os verts e verifica se tem cobertura de torso
                raw_v = []
                with open(meta["obj_path"], "r", encoding="utf-8", errors="ignore") as _fp:
                    for _l in _fp:
                        if _l.startswith("v "):
                            raw_v.append([float(x) for x in _l.split()[1:4]])
                if raw_v:
                    _v = np.array(raw_v)
                    _y_max = _v[:, 1].max()
                    _top_verts = _v[_v[:, 1] > _y_max - 0.25]
                    if len(_top_verts) > 0 and (_top_verts[:, 0].max() - _top_verts[:, 0].min()) > 1.2:
                        meta = dict(meta, is_top=True)

        print(f"[*] Asset: '{meta['name']}' (Tipo: {type_id} -> {'PARTE SUPERIOR' if meta['is_top'] else 'PARTE INFERIOR'})")
        print(f"[*] Malha baixada: {meta['obj_path']}")

        verts, faces, uvs, face_uvs = self.load_obj(meta["obj_path"])
        used_asset_wrap = False
        print(f"[*] Geometria: {len(verts)} vértices, {len(faces)} faces.")

        if meta["is_top"]:
            is_jacket = (meta.get("type_id") == 67) or any(k in meta.get("name", "").lower() for k in ["jacket", "bomber", "coat", "parka"])
            is_dress = (meta.get("type_id") == 72) or any(k in meta.get("name", "").lower() for k in ["dress", "vestido", "gown", "sundress", "robe"])
            sleeve_idx, torso_idx = self.analyze_topology(verts, faces)
            print(f"[*] Topologia: {len(sleeve_idx)} vértices manga, {len(torso_idx)} vértices torso.")

            wrap_result = self._fit_asset_wrap_layer(verts, meta, faces)

            if wrap_result is not None:
                deformed_verts = wrap_result[0]
                used_asset_wrap = True
                if sleeve_idx:
                    lowest_sleeve_z = float(np.min(deformed_verts[list(sleeve_idx), 2]))
                    is_sleeveless = lowest_sleeve_z > 1.32
                    is_long = lowest_sleeve_z <= 0.95 and not is_sleeveless
                    is_short = not is_sleeveless and not is_long
                else:
                    lowest_sleeve_z = 2.0
                    is_sleeveless, is_short, is_long = True, False, False
                cuff_z = lowest_sleeve_z
            elif self.dual_cage_ready:
                ut_s = self.r15_source_cages["UpperTorso"]["verts"]
                ut_f = self.body_cages["UpperTorso"]["verts"]
                scale = (ut_f[:, 2].max() - ut_f[:, 2].min()) / (ut_s[:, 2].max() - ut_s[:, 2].min() + 1e-8)
                z_shift = ut_f[:, 2].max() - ut_s[:, 2].max() * scale
                y_shift = ut_f[:, 1].mean() - ut_s[:, 1].mean() * scale

                # Espaço canônico nativo Roblox (sem inversão de X e sem adivinhação de ombro)
                v_canon = np.zeros_like(verts)
                v_canon[:, 0] = verts[:, 0] * scale
                v_canon[:, 1] = verts[:, 2] * scale + y_shift
                v_canon[:, 2] = (verts[:, 1] + 1.222) * scale + z_shift

                if len(sleeve_idx) == 0:
                    is_sleeveless = True
                    is_short = False
                    is_long = False
                    lowest_sleeve_z = 2.0
                else:
                    s_zs = v_canon[list(sleeve_idx), 2]
                    lowest_sleeve_z = float(np.min(s_zs))
                    is_sleeveless = lowest_sleeve_z > 1.32 or (len(s_zs) < 40 and lowest_sleeve_z > 1.25)
                    is_long = (lowest_sleeve_z <= 0.95) and not is_sleeveless
                    is_short = not is_sleeveless and not is_long

                cuff_z = lowest_sleeve_z
                sleeve_label = "REGATA" if is_sleeveless else ("MANGA CURTA" if is_short else "MANGA LONGA")
                print(f"[*] Tipo de Manga: {sleeve_label} (Z cuff = {cuff_z:.3f}m, Casaco={is_jacket}, Vestido={is_dress})")

                deformed_verts = self.deform_dual_cage(
                    v_canon, faces, sleeve_idx, torso_idx, is_jacket=is_jacket, is_sleeveless=is_sleeveless
                )
            else:
                apose_verts, cuff_z, is_sleeveless, is_short, is_long = self.fit_top_clothing(
                    verts, faces, sleeve_idx, torso_idx, is_jacket=is_jacket, is_dress=is_dress
                )
                sleeve_label = "REGATA" if is_sleeveless else ("MANGA CURTA" if is_short else "MANGA LONGA")
                print(f"[*] Tipo de Manga: {sleeve_label} (Z cuff = {cuff_z:.3f}m, Casaco={is_jacket}, Vestido={is_dress})")

                deformed_verts = self.deform_top_mesh(apose_verts, faces, sleeve_idx, torso_idx, is_jacket=is_jacket, is_sleeveless=is_sleeveless)

            # Recalcula a altura real da bainha da manga pós-deformação da cage
            cuff_center_map = {}
            if sleeve_idx:
                s_list = list(sleeve_idx)
                s_zs = deformed_verts[s_list, 2]
                real_cuff_z = float(np.min(s_zs))
                cuff_verts_z = s_zs[s_zs < real_cuff_z + 0.055]
                max_cuff_z = float(np.max(cuff_verts_z)) if len(cuff_verts_z) > 0 else real_cuff_z

                # Para manga longa, detecta o anel da barra da manga de cada lado para alinhar a mão
                if is_long:
                    for side_mult, pt_side in [(1, "esquerdo"), (-1, "direito")]:
                        s_side = [i for i in sleeve_idx if (deformed_verts[i, 0] * side_mult) > 0]
                        if s_side:
                            s_v = deformed_verts[s_side]
                            side_min_z = float(np.min(s_v[:, 2]))
                            ring = s_v[s_v[:, 2] < side_min_z + 0.045]
                            if len(ring) > 0:
                                cx = float((ring[:, 0].min() + ring[:, 0].max()) / 2)
                                cy = float((ring[:, 1].min() + ring[:, 1].max()) / 2)
                                cuff_center_map[pt_side] = (cx, cy)
            else:
                real_cuff_z = 2.0
                max_cuff_z = 2.0
            print(f"[*] Altura Real da Manga pós-deformação: Z cuff = [{real_cuff_z:.3f}m, {max_cuff_z:.3f}m]")

            # Detecção de ombros nus / mangas destacadas / tomara-que-caia:
            # Detecção de ombros nus / mangas destacadas / tomara-que-caia:
            # Se a roupa não possui cobertura estruturada de ombro (|X| > 0.22 e Z > 1.35 com teto >= 1.42m),
            # os ombros são anatomicamente expostos e os braços superiores devem ser preservados 100% íntegros
            sh_x_cut = 0.16
            sh_z_ceil = 1.390
            shoulder_pts = deformed_verts[(np.abs(deformed_verts[:, 0]) > sh_x_cut) & (deformed_verts[:, 2] > 1.35)]
            has_bare_shoulders = (
                is_sleeveless
                or (len(shoulder_pts) < 30)
                or (float(shoulder_pts[:, 2].max()) < sh_z_ceil if len(shoulder_pts) > 0 else True)
            )
            if has_bare_shoulders and not is_sleeveless:
                print(f"[*] Detecção Anatômica: Ombros nus / mangas destacadas (pts={len(shoulder_pts)} -> preservando braço superior completo)")

        else:
            wrap_result = self._fit_asset_wrap_layer(verts, meta, faces)
            if wrap_result is not None:
                deformed_verts = wrap_result[0]
                used_asset_wrap = True
            else:
                tpose_verts = self.fit_bottom_clothing(verts, target_waist_z=target_waist_z)
                deformed_verts = self.deform_bottom_mesh(tpose_verts, faces)

            cuff_z = None
            is_short, is_sleeveless, is_long = False, False, False

        if output_obj is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            output_obj = os.path.join(base_dir, "assets", "models", f"character_native_{asset_id}_{self.body_type}.obj")

        if meta.get("is_top", False) and not used_asset_wrap:
            # Inverte X no final para leitura frontal correta de logos/texturas, invertendo winding para preservar normais externas.
            # Só no encaixe antigo: o WrapLayer já sai na orientação do corpo (confere com o Roblox) e espelhá-lo invertia os textos.
            deformed_verts[:, 0] = -deformed_verts[:, 0]
            faces = [list(f)[::-1] for f in faces]
            if face_uvs is not None and len(face_uvs) > 0:
                face_uvs = [list(f_uv)[::-1] for f_uv in face_uvs]

        # What is one point in the garment is one point on the body (the fans that close its armholes and neck).
        deformed_verts = keep_together(np.asarray(verts, dtype=np.float64), deformed_verts)

        # Calcula normais suaves por vértice para Gouraud/Phong shading contínuo
        vert_normals = np.zeros_like(deformed_verts, dtype=np.float32)
        for f_idx in faces:
            if len(f_idx) >= 3:
                p0 = deformed_verts[f_idx[0]]
                p1 = deformed_verts[f_idx[1]]
                p2 = deformed_verts[f_idx[2]]
                fn = np.cross(p1 - p0, p2 - p0)
                norm = np.linalg.norm(fn)
                if norm > 1e-8:
                    fn /= norm
                    for vi in f_idx:
                        vert_normals[vi] += fn
        vn_lens = np.linalg.norm(vert_normals, axis=1, keepdims=True)
        vn_lens[vn_lens < 1e-8] = 1.0
        vert_normals /= vn_lens

        with open(output_obj, "w", encoding="utf-8") as f:
            f.write(f"# Isometricon Universal Fitted Clothing v37: {asset_id}\n")
            f.write(f"# asset_type {int(meta.get('type_id', 0))}\n")  # layering order at runtime
            for v in deformed_verts:
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
            for vn in vert_normals:
                f.write(f"vn {vn[0]:.4f} {vn[1]:.4f} {vn[2]:.4f}\n")
            for uv in uvs:
                f.write(f"vt {uv[0]:.5f} {uv[1]:.5f}\n")
            for i, face in enumerate(faces):
                if len(face_uvs) > i:
                    f.write("f " + " ".join(f"{face[j]+1}/{face_uvs[i][j]+1}/{face[j]+1}" for j in range(len(face))) + "\n")
                else:
                    f.write("f " + " ".join(f"{idx+1}//{idx+1}" for idx in face) + "\n")

        from .hsr import body_cage_faces, engine_to_body_mesh, ray_hidden_mask, sidecar_path
        hsr_path = sidecar_path(output_obj)
        hsr_info = wrap_result[1].get("hsr") if used_asset_wrap and wrap_result is not None else None
        if hsr_info is None and self.body_cages:
            # No usable Roblox HSR data: derive the covered skin from the fitted garment
            # itself (the final vertices, in the same space the renderer receives).
            try:
                from .wrap_layer_fit import _unique_uv_positions
                _, cage_positions = _unique_uv_positions(self.body_cages)
                cage_faces = body_cage_faces(self.body_cages)
                garment_faces = np.asarray([f[:3] for f in faces], dtype=np.int64)
                hidden = ray_hidden_mask(cage_positions, cage_faces, deformed_verts, garment_faces,
                                         reach_fraction=0.12)
                hsr_info = {"cage_points": engine_to_body_mesh(cage_positions), "hidden": hidden,
                            "cage_faces": cage_faces}
                print(f"[HSR] Máscara geométrica: {int(hidden.sum())} de {len(hidden)} pontos da cage cobertos")
            except Exception as exc:
                print(f"[HSR] Máscara geométrica indisponível: {exc}")
        if hsr_info is not None:
            np.savez_compressed(hsr_path, cage_points=hsr_info["cage_points"], hidden=hsr_info["hidden"],
                                cage_faces=hsr_info["cage_faces"])
        elif os.path.exists(hsr_path):
            os.remove(hsr_path)  # a stale mask must not cull skin under a garment fitted without it
        parts_path = body_parts_path(output_obj)
        body_parts = wrap_result[1].get("body_parts") if used_asset_wrap and wrap_result is not None else None
        if body_parts is not None and len(body_parts) == len(deformed_verts):
            np.save(parts_path, np.asarray(body_parts))
        elif os.path.exists(parts_path):
            os.remove(parts_path)

        t1 = time.perf_counter()
        elapsed = (t1 - t0) * 1000
        print(f"[OK] Pipeline concluído com sucesso em {elapsed:.1f}ms (Python puro, ZERO Blender)!")
        print(f"[*] Modelo final exportado em: {output_obj}")

        return {
            "name": meta["name"],
            "asset_id": asset_id,
            "type_id": meta["type_id"],
            "is_top": meta["is_top"],
            "is_short_sleeves": is_short,
            "is_sleeveless": is_sleeveless,
            "is_long_sleeves": is_long,
            "cuff_z": cuff_z,
            "output_obj": output_obj,
            "tex_path": meta["tex_path"],
            "verts": deformed_verts,
            "faces": faces,
            "uvs": uvs,
        }

    def equip_tool(self, asset_id, hand="right", output_obj=None):
        """Equipa uma ferramenta/arma/katana do Roblox diretamente na mão do avatar."""
        t0 = time.perf_counter()
        print(f"\n==================================================")
        print(f"  EQUIPAR TOOL/ARMA NATIVO PYTHON: {asset_id} (Mão: {hand})")
        print(f"==================================================")

        meta = self.fetch_asset(asset_id)
        raw_obj = meta["obj_path"]

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        models_dir = os.path.join(base_dir, "assets", "models")
        if output_obj is None:
            output_obj = os.path.join(models_dir, f"character_native_tool_{asset_id}.obj")

        raw_verts = []
        raw_uvs = []
        raw_faces = []

        with open(raw_obj, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("v "):
                    raw_verts.append([float(x) for x in line.split()[1:4]])
                elif line.startswith("vt "):
                    raw_uvs.append([float(x) for x in line.split()[1:3]])
                elif line.startswith("f "):
                    raw_faces.append(line.split()[1:])

        raw_verts = np.array(raw_verts, dtype=np.float64)

        # Determina a escala proporcional (em torno de 0.22 metros por stud)
        stud_scale = 0.22
        scale_vec = np.array([1.5 * stud_scale, 1.5 * stud_scale, 1.65 * stud_scale])

        # Detecta orientação e grip
        z_min = raw_verts[:, 2].min()
        z_max = raw_verts[:, 2].max()
        z_len = z_max - z_min

        # Se for espada/katana (comprimento dominante no eixo Z)
        is_sword = z_len > 2.0 * max(raw_verts[:, 0].max() - raw_verts[:, 0].min(),
                                     raw_verts[:, 1].max() - raw_verts[:, 1].min())

        if is_sword:
            grip_z = z_min + 0.27 * z_len # posição da mão na empunhadura
            grip_local = np.array([0.0, 0.0, grip_z]) * scale_vec
            v_centered = raw_verts * scale_vec - grip_local

            # Mão direita ou esquerda
            if hand == "right":
                p_hand = np.array([-0.345, -0.025, 0.725])
                angle_rad = math.radians(26.0)
                dir_blade = np.array([0.0, -math.cos(angle_rad), -math.sin(angle_rad)])
                dir_blade /= np.linalg.norm(dir_blade)
                dir_spine = np.array([0.0, math.sin(angle_rad), -math.cos(angle_rad)])
                dir_spine /= np.linalg.norm(dir_spine)
                dir_side = np.cross(dir_spine, dir_blade)
                dir_side /= np.linalg.norm(dir_side)
                R = np.column_stack([dir_spine, dir_side, dir_blade])
            else:
                p_hand = np.array([0.345, -0.025, 0.725])
                angle_rad = math.radians(26.0)
                dir_blade = np.array([0.0, -math.cos(angle_rad), -math.sin(angle_rad)])
                dir_blade /= np.linalg.norm(dir_blade)
                dir_spine = np.array([0.0, math.sin(angle_rad), -math.cos(angle_rad)])
                dir_spine /= np.linalg.norm(dir_spine)
                dir_side = -np.cross(dir_spine, dir_blade)
                dir_side /= np.linalg.norm(dir_side)
                R = np.column_stack([dir_spine, dir_side, dir_blade])
            v_world = (R @ v_centered.T).T + p_hand
        else:
            center = (raw_verts.min(axis=0) + raw_verts.max(axis=0)) / 2.0
            v_centered = (raw_verts - center) * stud_scale
            p_hand = np.array([-0.345 if hand == "right" else 0.345, -0.025, 0.725])
            v_world = v_centered + p_hand

        with open(output_obj, "w", encoding="utf-8") as f:
            f.write(f"# Isometricon Native Fitted Tool: {asset_id} ({meta['name']})\n")
            for v in v_world:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for vt in raw_uvs:
                f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
            for f_idx in raw_faces:
                f.write(f"f {' '.join(f_idx)}\n")

        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[OK] Tool equipada com sucesso em {elapsed:.1f}ms: {output_obj}")
        return {
            "name": meta["name"],
            "asset_id": asset_id,
            "hand": hand,
            "output_obj": output_obj,
            "tex_path": meta["tex_path"]
        }

    def resolve_shoe_pair(self, shoes_id):
        """Asset ids worn for ``shoes_id``: a bundle's shoe assets, or the ids given ("left,right" / one id)."""
        if isinstance(shoes_id, (list, tuple)):
            return [str(i) for i in shoes_id if i is not None]
        text = str(shoes_id).strip()
        if "," in text:
            return [i.strip() for i in text.split(",") if i.strip()]
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_path = os.path.join(base_dir, "assets", "models", "clothing", "shoe_bundles.json")
        try:
            with open(cache_path, encoding="utf-8") as handle:
                cache = json.load(handle)
        except (OSError, ValueError):
            cache = {}
        if text not in cache:
            assets = []
            try:
                url = f"https://catalog.roblox.com/v1/bundles/{text}/details"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    details = json.loads(resp.read().decode("utf-8"))
                assets = [str(item["id"]) for item in details.get("items", []) if item.get("type") == "Asset"]
            except Exception:
                pass  # not a bundle: a single shoe asset
            cache[text] = assets or [text]
            try:
                with open(cache_path, "w", encoding="utf-8") as handle:
                    json.dump(cache, handle, indent=2)
            except OSError:
                pass
        return cache[text]

    def equip_shoes(self, bundle_or_asset_id):
        """Equipa calçados 3D (tênis/sneakers/shoes) do Roblox nos pés esquerdo e direito."""
        t0 = time.perf_counter()
        print(f"\n==================================================")
        print(f"  EQUIPAR CALÇADOS NATIVO PYTHON: {bundle_or_asset_id}")
        print(f"==================================================")

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        models_dir = os.path.join(base_dir, "assets", "models")
        clothing_dir = os.path.join(models_dir, "clothing")
        os.makedirs(clothing_dir, exist_ok=True)

        left_asset_id = None
        right_asset_id = None
        shoe_name = f"shoes_{bundle_or_asset_id}"

        # 1. Verifica se é um Bundle ID (ex: 331325 para Adidas Red Campus 00s)
        try:
            b_url = f"https://catalog.roblox.com/v1/bundles/{bundle_or_asset_id}/details"
            req = urllib.request.Request(b_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                b_data = json.loads(resp.read().decode("utf-8"))
                shoe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", b_data.get("name", shoe_name)).strip("_")
                for it in b_data.get("items", []):
                    it_name = it.get("name", "").lower()
                    if "left" in it_name or it.get("type") == "Asset" and left_asset_id is None:
                        left_asset_id = it.get("id")
                    elif "right" in it_name or it.get("type") == "Asset":
                        right_asset_id = it.get("id")
        except Exception:
            pass

        # Fallback se for ID direto
        if left_asset_id is None:
            left_asset_id = bundle_or_asset_id
        if right_asset_id is None:
            right_asset_id = bundle_or_asset_id

        # 2. Processa cada lado (esquerdo e direito)
        results = {}
        for side, aid, x_center in [("left", left_asset_id, 0.170), ("right", right_asset_id, -0.170)]:
            meta = self.fetch_asset(aid)
            raw_obj = meta["obj_path"]

            raw_verts = []
            raw_uvs = []
            raw_faces = []
            with open(raw_obj, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("v "):
                        raw_verts.append([float(x) for x in line.split()[1:4]])
                    elif line.startswith("vt "):
                        raw_uvs.append([float(x) for x in line.split()[1:3]])
                    elif line.startswith("f "):
                        raw_faces.append(line.split()[1:])

            raw_verts = np.array(raw_verts, dtype=np.float64)

            # Proporções e escala para calçados Roblox Layered Clothing nos pés do avatar:
            scale_x = 0.44
            scale_y = 0.30
            scale_z = 0.31

            y_min = raw_verts[:, 1].min()
            v_world = np.zeros_like(raw_verts)
            v_world[:, 0] = raw_verts[:, 0] * scale_x + x_center
            v_world[:, 1] = raw_verts[:, 2] * scale_z - 0.010
            v_world[:, 2] = (raw_verts[:, 1] - y_min) * scale_y + 0.000

            out_obj = os.path.join(models_dir, f"character_native_shoe_{side}_{bundle_or_asset_id}.obj")
            with open(out_obj, "w", encoding="utf-8") as f:
                f.write(f"# Isometricon Native Fitted Shoe ({side}): {bundle_or_asset_id}\n")
                for v in v_world:
                    f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                for vt in raw_uvs:
                    f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
                for face in raw_faces:
                    f.write(f"f {' '.join(face)}\n")

            results[side] = {
                "obj_path": out_obj,
                "tex_path": meta["tex_path"]
            }

        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[OK] Calçados '{shoe_name}' equipados com sucesso em {elapsed:.1f}ms!")
        return {
            "name": shoe_name,
            "bundle_id": bundle_or_asset_id,
            "left": results["left"],
            "right": results["right"]
        }

    def equip_hair(self, asset_id):
        """Equipa cabelo 3D do Roblox (AssetType 41 ou modelo de cabelo) na cabeça do avatar em tempo real (Python puro)."""
        t0 = time.perf_counter()
        print(f"\n==================================================")
        print(f"  EQUIPAR CABELO NATIVO PYTHON: {asset_id} ({self.body_type.upper()})")
        print(f"==================================================")

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        models_dir = os.path.join(base_dir, "assets", "models")
        clothing_dir = os.path.join(models_dir, "clothing")
        os.makedirs(clothing_dir, exist_ok=True)

        meta = self.fetch_asset(asset_id)
        raw_obj = meta["obj_path"]
        rbxm_path = meta.get("rbxm_path")

        raw_verts = []
        raw_uvs = []
        raw_faces = []
        with open(raw_obj, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("v "):
                    raw_verts.append([float(x) for x in line.split()[1:4]])
                elif line.startswith("vt "):
                    raw_uvs.append([float(x) for x in line.split()[1:3]])
                elif line.startswith("f "):
                    raw_faces.append(line.split()[1:])

        # The accessory's attachment meets the same attachment on the Roblox head, and the
        # head cages carry it from the Roblox head to ours (see hair_fit).
        from .hair_fit import fit_head_accessory
        from .hsr import engine_to_body_mesh
        if not rbxm_path or not os.path.exists(rbxm_path) or not self.body_cages:
            raise ValueError(f"Cabelo {asset_id} sem .rbxm ou sem cages do corpo para encaixar")
        v_world = engine_to_body_mesh(fit_head_accessory(raw_verts, rbxm_path, self.r15_source_cages, self.body_cages))

        out_obj = hair_fitted_path(asset_id, self.body_type)
        with open(out_obj, "w", encoding="utf-8") as f:
            f.write(f"# Isometricon Native Fitted Hair: {asset_id} ({meta['name']})\n")
            for v in v_world:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for vt in raw_uvs:
                f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
            for face in raw_faces:
                f.write(f"f {' '.join(face)}\n")

        elapsed = (time.perf_counter() - t0) * 1000
        print(f"[OK] Cabelo '{meta['name']}' ({asset_id}) equipado com sucesso em {elapsed:.1f}ms: {out_obj}")
        return {
            "name": meta["name"],
            "asset_id": asset_id,
            "output_obj": out_obj,
            "tex_path": meta["tex_path"]
        }

def wear_asset(asset_id, output_obj=None):
    engine = RobloxWearEngine()
    return engine.wear(asset_id, output_obj=output_obj)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        wear_asset(sys.argv[1])
    else:
        print("Uso: python -m src.clothing.wear_engine <asset_id>")
