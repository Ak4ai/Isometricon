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

def extract_attachment_cframe_from_rbxm(data_or_path):
    """Extrai R_att (matriz 3x3) e p_att (vetor 3D) do Attachment de um arquivo ou payload RBXM do Roblox."""
    import struct
    try:
        import lz4.block
    except ImportError:
        lz4 = None

    if isinstance(data_or_path, (int, str)):
        data_or_path = str(data_or_path)
        if os.path.exists(data_or_path):
            with open(data_or_path, "rb") as fp:
                data = fp.read()
        else:
            data = fetch_roblox_asset(data_or_path)
    elif isinstance(data_or_path, (bytes, bytearray)):
        data = bytes(data_or_path)
    else:
        return np.eye(3, dtype=np.float64), np.zeros(3, dtype=np.float64)

    if not data:
        return np.eye(3, dtype=np.float64), np.zeros(3, dtype=np.float64)

    if data.startswith(b"\x1f\x8b"):
        try:
            data = gzip.decompress(data)
        except Exception:
            pass

    if not data.startswith(b"<roblox!"):
        return np.eye(3, dtype=np.float64), np.zeros(3, dtype=np.float64)

    idx = 32
    classes = {}
    R_att = np.eye(3, dtype=np.float64)
    p_att = np.zeros(3, dtype=np.float64)

    while idx + 16 <= len(data):
        fourcc, comp_len, decomp_len, res = struct.unpack("<4sIII", data[idx:idx+16])
        chunk_bytes = data[idx+16:idx+16+comp_len]
        idx += 16 + comp_len

        if comp_len > 0 and lz4 is not None:
            try:
                dec = lz4.block.decompress(chunk_bytes, uncompressed_size=decomp_len)
            except Exception:
                dec = chunk_bytes
        else:
            dec = chunk_bytes

        if fourcc == b"INST":
            c_id, name_len = struct.unpack("<II", dec[:8])
            classes[c_id] = dec[8:8+name_len].decode("ascii", errors="ignore")
        elif fourcc == b"PROP":
            c_id, name_len = struct.unpack("<II", dec[:8])
            p_name = dec[8:8+name_len].decode("ascii", errors="ignore")
            type_id = dec[8+name_len]
            val_bytes = dec[8+name_len+1:]
            c_name = classes.get(c_id, f"Class_{c_id}")
            if p_name == "CFrame" and c_name == "Attachment":
                rot_type = val_bytes[0]
                if rot_type == 0 and len(val_bytes) >= 49:
                    rot_floats = struct.unpack("<9f", val_bytes[1:37])
                    R_att = np.array(rot_floats, dtype=np.float64).reshape(3, 3)
                    p0 = decode_roblox_float_be(val_bytes[37:41])
                    p1 = decode_roblox_float_be(val_bytes[41:45])
                    p2 = decode_roblox_float_be(val_bytes[45:49])
                    p_att = np.array([p0, p1, p2], dtype=np.float64)
                    break
                elif rot_type in ROBLOX_ROTATION_TABLE and len(val_bytes) >= 13:
                    y_deg, x_deg, z_deg = ROBLOX_ROTATION_TABLE[rot_type]
                    R_att = euler_yxz_to_matrix(y_deg, x_deg, z_deg)
                    p0 = decode_roblox_float_be(val_bytes[1:5])
                    p1 = decode_roblox_float_be(val_bytes[5:9])
                    p2 = decode_roblox_float_be(val_bytes[9:13])
                    p_att = np.array([p0, p1, p2], dtype=np.float64)
                    break
        elif fourcc == b"END ":
            break

    return R_att, p_att

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


def load_r15_female_cages(obj_path):
    """Carrega as 15 cages R15 femininas diretamente do OBJ, convertendo para coordenadas do motor.

    Retorna dict: {part_name: {"verts": np.ndarray(N,3), "faces": np.ndarray(M,3),
                                "grid": SpatialGrid3D, "bbox_min": np.ndarray(3), "bbox_max": np.ndarray(3)}}
    Coordenadas OBJ (X, Y_height, Z_depth) → Motor (X, Z_depth, Y_height) — swap Y↔Z.
    """
    parts = {}
    current_name = None
    current_verts = []
    current_faces = []
    global_vert_offset = 0  # OBJ indices are 1-based and global

    all_verts = []  # all verts in OBJ order for face index resolution

    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("o "):
                if current_name is not None:
                    _finalize_r15_part(parts, current_name, current_verts, current_faces, global_vert_offset)
                    global_vert_offset += len(current_verts)
                current_name = line[2:].replace("_OuterCage", "")
                current_verts = []
                current_faces = []
            elif line.startswith("v "):
                coords = [float(x) for x in line.split()[1:4]]
                current_verts.append(coords)
                all_verts.append(coords)
            elif line.startswith("f "):
                indices = []
                for tok in line.split()[1:]:
                    idx = int(tok.split("/")[0]) - 1  # 0-based global
                    indices.append(idx)
                current_faces.append(indices)

    if current_name is not None:
        _finalize_r15_part(parts, current_name, current_verts, current_faces, global_vert_offset)

    return parts


def _finalize_r15_part(parts, name, verts_list, faces_list, vert_offset):
    """Finaliza uma parte R15: converte coordenadas, cria grid espacial e bounding box."""
    if not verts_list or not faces_list:
        return

    # Converte OBJ (X, Y_height, Z_depth) → Motor (X, -Z_depth, Y_height)
    raw = np.array(verts_list, dtype=np.float64)
    engine_verts = np.zeros_like(raw)
    engine_verts[:, 0] = raw[:, 0]    # X = X_obj
    engine_verts[:, 1] = -raw[:, 2]   # Y_engine = -Z_obj (profundidade: alinhado com cage_verts_rest)
    engine_verts[:, 2] = raw[:, 1]    # Z_engine = Y_obj (altura)

    # Converte índices globais do OBJ para locais da parte
    # Como o eixo Y foi negado (reflexão), inverte a ordem dos vértices para manter as normais apontando para fora
    local_faces = []
    for f in faces_list:
        local_f = [idx - vert_offset for idx in f]
        # Triangula se necessário (fan triangulation com winding invertido)
        if len(local_f) == 3:
            local_faces.append([local_f[0], local_f[2], local_f[1]])
        elif len(local_f) > 3:
            for i in range(1, len(local_f) - 1):
                local_faces.append([local_f[0], local_f[i + 1], local_f[i]])

    faces_arr = np.array(local_faces, dtype=np.int32)

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
        "grid": grid,
        "bbox_min": engine_verts.min(axis=0),
        "bbox_max": engine_verts.max(axis=0),
    }


# Mapeamento de regiões anatômicas para cages R15 (parte superior)
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
        self.body_type = str(body_type).lower()
        self.is_female = self.body_type in ("female", "feminino", "fem")

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        std_cage_path = os.path.join(base_dir, "assets", "models", "roblox_cage_data.npz")
        self.std_cage_data = np.load(std_cage_path)

        if self.is_female:
            fem_cage_path = os.path.join(base_dir, "assets", "models", "roblox_female_cage_data.npz")
            if not os.path.exists(fem_cage_path):
                raise FileNotFoundError(f"Arquivo de dados da cage feminina não encontrado: {fem_cage_path}")
            self.cage_data = np.load(fem_cage_path)
            # Source cages are the standard Roblox mannequin (where clothing was authored)
            self.src_verts_apose = self.std_cage_data["cage_verts_apose"]
            self.src_verts_tpose_85 = self.std_cage_data["cage_verts_tpose_85"]
            self.src_verts_rest = self.std_cage_data["cage_verts_rest"]
            # Target destination cages are the sculpted female cages
            self.dst_verts_rest = self.cage_data["cage_verts_rest"]
            self.dst_verts_apose = self.cage_data["cage_verts_apose"]
            self.dst_verts_tpose_85 = self.cage_data["cage_verts_tpose_85"]
        else:
            self.cage_data = self.std_cage_data
            self.src_verts_apose = self.std_cage_data["cage_verts_apose"]
            self.src_verts_tpose_85 = self.std_cage_data["cage_verts_tpose_85"]
            self.src_verts_rest = self.std_cage_data["cage_verts_rest"]
            self.dst_verts_rest = self.std_cage_data["cage_verts_rest"]
            self.dst_verts_apose = self.std_cage_data["cage_verts_apose"]
            self.dst_verts_tpose_85 = self.std_cage_data["cage_verts_tpose_85"]

        self.cage_verts_apose = self.src_verts_apose
        self.cage_verts_rest = self.dst_verts_rest
        self.cage_verts_tpose_85 = self.src_verts_tpose_85
        self.cage_faces = self.std_cage_data["cage_faces"]

        # Carrega segmentação de grupos de faces da cage (0=Torso, 1=Braço Esquerdo, 2=Braço Direito)
        if "cage_face_groups" in self.cage_data and len(self.cage_data["cage_face_groups"]) == len(self.cage_faces):
            self.cage_face_groups = self.cage_data["cage_face_groups"]
        else:
            groups_path = os.path.join(os.path.dirname(std_cage_path), "cage_face_groups.npy")
            if os.path.exists(groups_path) and not self.is_female:
                self.cage_face_groups = np.load(groups_path)
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

        # Cages R15 femininas (carregadas apenas para body_type feminino se existirem)
        self.r15_female_cages = None
        if self.is_female:
            cage_dir = os.path.join(base_dir, "assets", "models")
            r15_obj = os.path.join(cage_dir, "clothing", "female_cages.obj")
            if os.path.exists(r15_obj):
                self.r15_female_cages = load_r15_female_cages(r15_obj)
                print(f"[R15] Carregadas {len(self.r15_female_cages)} cages femininas R15: {list(self.r15_female_cages.keys())}")

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
                    # Se o componente cruza a linha média mas se estende para os braços (ex: suéter contínuo),
                    # classifica os vértices pontualmente por coordenadas espaciais
                    if comp_world_x > 0.28:
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
        loc_z = 1.185

        # Detecção de peças curtas / biquínis (total_y_span < 1.35)
        is_cropped = (total_y_span < 1.35) and not is_dress

        # Ancoragem Vertical Inteligente para tops curtos e biquínis:
        # Garante que o topo alcance a clavícula (Z ≈ 1.465m), impedindo que caiam 12cm sobre o umbigo
        top_raw_z = loc_z + y_max_orig * uniform_scale
        if is_cropped and top_raw_z < 1.450:
            loc_z += (1.465 - top_raw_z)

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

        # Tapering da Cintura e Controle de Largura para Peças Boxy/Oversized
        # Para VESTIDOS e CROPPED TOPS:
        # - Vestidos mantêm a saia aberta e longa até os joelhos (sem esmagar verticalmente em Z=0.985m)
        # - Cropped tops mantêm a barra natural acima do umbigo, expondo o abdômen sem esticar até a calça
        if not is_dress and not is_cropped:
            torso_list = list(torso_indices)
            torso_ys = verts[torso_list, 1] if torso_list else np.array([y_min_orig])
            t_ymin = float(np.min(torso_ys))
            t_ymax = float(np.max(torso_ys))
            hem_thresh = t_ymin + 0.15 * (t_ymax - t_ymin)
            hem_mask = [idx for idx in torso_list if verts[idx, 1] < hem_thresh]

            if hem_mask:
                hem_xs = verts[hem_mask, 0]
                hem_zs = verts[hem_mask, 2]
                raw_w = float(np.max(hem_xs) - np.min(hem_xs))
                raw_d = float(np.max(hem_zs) - np.min(hem_zs))
            else:
                raw_w, raw_d = 0.50, 0.40

            target_waist_w = 0.300
            target_waist_d = 0.240 if self.is_female else 0.245
            if self.is_female:
                sc_waist_x = min(1.0, (target_waist_w / uniform_scale) / raw_w) if raw_w > 0 else 0.58
                sc_waist_z = min(1.0, (target_waist_d / uniform_scale) / raw_d) if raw_d > 0 else 0.62
                y_target_min = (0.985 - loc_z) / uniform_scale
            else:
                sc_waist_x = min(1.0, (target_waist_w / uniform_scale) / raw_w) if raw_w > 0 else 0.57
                sc_waist_z = min(1.0, (target_waist_d / uniform_scale) / raw_d) if raw_d > 0 else 0.64
                y_target_min = (0.890 - loc_z) / uniform_scale

            y_anchor_bot = 0.15 * norm_scale
            compression = (y_anchor_bot - y_target_min) / (y_anchor_bot - t_ymin + 1e-8)

            for idx in torso_list:
                y = adj_verts[idx, 1]
                if y < y_anchor_bot:
                    blend = min(max((y_anchor_bot - y) / (y_anchor_bot - t_ymin + 1e-8), 0.0), 1.0)
                    curve = blend ** 1.2
                    sx = 1.0 - (1.0 - sc_waist_x) * curve
                    sz = 1.0 - (1.0 - sc_waist_z) * curve
                    adj_verts[idx, 1] = y_anchor_bot + (y - y_anchor_bot) * compression
                    adj_verts[idx, 0] *= sx
                    adj_verts[idx, 2] *= sz

        # Suavização Contínua de Gola e Ombros
        # Jaquetas e casacos preservam gola alta estruturada (teto ~1.515m).
        # Vestidos, regatas e camisas têm teto suave na clavícula/base do pescoço (1.485m female, 1.492m male),
        # impedindo que decotes e alças escalem desmedidamente até o queixo/boca.
        y_anchor_top = 0.35 * norm_scale
        max_abs_x = float(np.max(np.abs(verts[:, 0])))
        num_bins = 30
        envelope = {}
        for idx in range(len(verts)):
            y = adj_verts[idx, 1]
            if y > y_anchor_top:
                b_idx = int(min(abs(adj_verts[idx, 0]) / (max_abs_x + 1e-8), 0.999) * num_bins)
                envelope[b_idx] = max(envelope.get(b_idx, y_anchor_top), y)

        for idx in range(len(adj_verts)):
            y = adj_verts[idx, 1]
            x = adj_verts[idx, 0]
            if y > y_anchor_top:
                b_idx = int(min(abs(x) / (max_abs_x + 1e-8), 0.999) * num_bins)
                orig_top = envelope.get(b_idx, y)
                if orig_top > y_anchor_top:
                    wx = abs(x) * uniform_scale
                    base_collar_z = 1.515 if is_jacket else (1.485 if self.is_female else 1.492)
                    if wx < 0.20:
                        wz = base_collar_z
                    elif wx < 0.28:
                        s = smoothstep(0.20, 0.28, wx)
                        wz = base_collar_z - s * (base_collar_z - 1.480)
                    else:
                        # Deltoide robusto: preserva altura anatômica sem estrangular o topo do ombro
                        s = smoothstep(0.28, 0.38, wx)
                        wz = 1.480 - s * 0.025
                    target_top_y = (wz - loc_z) / uniform_scale
                    if orig_top > target_top_y:
                        ratio = (target_top_y - y_anchor_top) / (orig_top - y_anchor_top + 1e-8)
                        adj_verts[idx, 1] = y_anchor_top + (y - y_anchor_top) * ratio

        # Transforma para o espaço 3D da A-Pose
        world_apose = np.zeros_like(adj_verts)
        world_apose[:, 0] = -adj_verts[:, 0] * uniform_scale
        world_apose[:, 1] = adj_verts[:, 2] * uniform_scale + 0.007
        world_apose[:, 2] = adj_verts[:, 1] * uniform_scale + loc_z

        return world_apose, lowest_sleeve_z, is_sleeveless, is_short_sleeves, is_long_sleeves

    def fit_bottom_clothing(self, verts, target_waist_z=None):
        """Ajusta calças e sapatos a partir do cós até a sola do chão."""
        y_min_orig = float(np.min(verts[:, 1]))
        y_max_orig = float(np.max(verts[:, 1]))
        total_y_span = y_max_orig - y_min_orig

        if target_waist_z is None:
            # Meio do caminho do declive anatômico (entre 0.928m da pelve e 1.067m da cintura superior)
            target_waist_z = 1.000 if self.is_female else 0.935
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
            max_n = 0.045 if is_jacket else (0.035 if self.is_female else 0.030)
            min_n = 0.005

            # Amortecimento anatômico do ombro masculino (impede ombros de armadura de futebol americano)
            if not self.is_female and not is_jacket and abs(p[0]) > 0.20 and p[2] > 1.35:
                max_n = 0.020

            if n_dist > 0.016:
                d_n = 0.016 + (n_dist - 0.016) * 0.35
                d_n = min(d_n, max_n)
            elif n_dist < min_n:
                d_n = min_n
            else:
                d_n = n_dist

            # Damping tangencial (evita que as laterais e a barra formem pontas excessivamente largas)
            max_tan = 0.045 if is_jacket else (0.026 if self.is_female else 0.032)
            tan_len = float(np.linalg.norm(tan_vec))
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
                    if ax > 0.28:
                        deformed[i] = deform_point(p, grid_arm, tris_arm, is_sleeve=True)
                    else:
                        w_arm = smoothstep(0.18, 0.28, ax)
                        p_t = deform_point(p, self.grid_apose_g0, self.g0_tris, is_sleeve=False)
                        p_a = deform_point(p, grid_arm, tris_arm, is_sleeve=True)
                        deformed[i] = (1.0 - w_arm) * p_t + w_arm * p_a
                else: # torso
                    if ax > 0.18 and p[2] > 1.15:
                        w_arm = smoothstep(0.18, 0.28, ax) * 0.85
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
        seam_ring = {v_i for v_i in seam_verts if input_verts[v_i, 2] > 1.12 and abs(input_verts[v_i, 0]) > 0.16}
        for _ in range(3):
            for v_i in list(seam_ring):
                for nbr in adj.get(v_i, []):
                    if input_verts[nbr, 2] > 1.12 and abs(input_verts[nbr, 0]) > 0.16:
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
            if self.is_female:
                # Transição suave e contínua de offset, evitando degraus ou vincos artificiais nas coxas
                if p_target[2] < 0.78:
                    eff_offset = best_offset * 0.75
                elif p_target[2] < 0.90:
                    t = (p_target[2] - 0.78) / 0.12
                    eff_offset = best_offset * (0.75 + 0.25 * t)
            off_vec = R @ eff_offset
            if self.is_female:
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

        if not self.is_female:
            return raw_deformed

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

    def deform_top_mesh_r15(self, rest_verts, faces, sleeve_indices, torso_indices):
        """Deformação R15 nativa para peças superiores usando as 15 cages femininas diretamente.

        Conforma a roupa (já colocada em rest pose) diretamente na superfície das cages femininas,
        preservando a espessura e caimento de cada peça com relaxamento Laplaciano nas costuras.
        """
        if not self.r15_female_cages:
            return rest_verts

        deformed = np.zeros_like(rest_verts)
        cage_assignment = {}  # vertex_idx -> cage_name (para detecção de costuras)

        for i in range(len(rest_verts)):
            p = rest_verts[i]

            # 1. Mede o offset/espessura original em relação à cage rest masculina
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
            cloth_offset = max(0.002, min(signed_offset, 0.025))

            # 2. Determina a cage feminina R15 correspondente
            region_name = _assign_cage_region(p, _TOP_CAGE_REGIONS, self.r15_female_cages)
            if region_name is None:
                region_name = "UpperTorso"

            cage_assignment[i] = region_name
            part_data = self.r15_female_cages[region_name]
            proj_q, normal, dist = self._project_onto_r15_cage(p, part_data)

            deformed[i] = proj_q + cloth_offset * normal

        # Adjacência de arestas para relaxamento Laplaciano
        adj = {}
        for face in faces:
            for fi in range(len(face)):
                i0, i1 = face[fi], face[(fi + 1) % len(face)]
                adj.setdefault(i0, set()).add(i1)
                adj.setdefault(i1, set()).add(i0)

        # Identifica vértices nas costuras entre cages R15 diferentes
        seam_verts = set()
        for f_v in faces:
            cage_names_in_face = set()
            for idx in f_v:
                if idx in cage_assignment:
                    cage_names_in_face.add(cage_assignment[idx])
            if len(cage_names_in_face) > 1:
                seam_verts.update(f_v)

        # Expande o anel de costura em 2 anéis para suavização
        seam_ring = set(seam_verts)
        for _ in range(2):
            for v_i in list(seam_ring):
                seam_ring.update(adj.get(v_i, []))

        # Relaxamento Laplaciano nas costuras entre cages
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

    def deform_mesh_r15(self, rest_verts, faces):
        """Deformação R15 nativa para peças inferiores (calças, saias) usando as cages femininas.

        Cada vértice é projetado na cage R15 correspondente (LowerTorso, pernas, pés).
        """
        if not self.r15_female_cages:
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

            region_name = _assign_cage_region(p, _BOTTOM_CAGE_REGIONS, self.r15_female_cages)
            if region_name is None:
                region_name = "LowerTorso"

            cage_assignment[i] = region_name
            part_data = self.r15_female_cages[region_name]
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

    def _slim_arm(self, world_verts: np.ndarray, y_scale: float = 0.78, x_scale: float = 0.88) -> np.ndarray:
        """Aplica afiamento anatômico XY suave ao braço para harmonizar com o estilo estilizado anime.
        - y_scale: 0.78 (profundidade suave)
        - x_scale: 0.88 (largura lateral suave)
        Ambas as escalas são em torno do centro anatômico, preservando a curvatura e as alturas Z."""
        verts = world_verts.copy()
        _wrist_z    = self.wrist_z       # 0.684
        _elbow_z    = 1.093
        _shoulder_z = 1.482
        # Centro Y anatômico por zona (profundidade)
        _yc = {'wrist': -0.030, 'elbow': +0.054, 'shoulder': +0.025}
        # Centro X anatômico: eixo do braço (X médio da cage)
        x_center = float((world_verts[:, 0].min() + world_verts[:, 0].max()) / 2)

        for i in range(len(verts)):
            z = verts[i, 2]
            if z <= _wrist_z:
                yc = _yc['wrist']
            elif z <= _elbow_z:
                t  = (z - _wrist_z) / (_elbow_z - _wrist_z)
                yc = _yc['wrist'] + t * (_yc['elbow'] - _yc['wrist'])
            elif z <= _shoulder_z:
                t  = (z - _elbow_z) / (_shoulder_z - _elbow_z)
                yc = _yc['elbow'] + t * (_yc['shoulder'] - _yc['elbow'])
            else:
                yc = _yc['shoulder']
            # Comprimir Y (profundidade) em torno do centro anatômico
            verts[i, 1] = yc + (verts[i, 1] - yc) * y_scale
            # Comprimir X (largura) em torno do centro do braço
            verts[i, 0] = x_center + (verts[i, 0] - x_center) * x_scale

        return verts

    def square_sleeve_cuffs(
        self,
        deformed_verts: np.ndarray,
        sleeve_idx: set,
        is_long: bool,
        is_short: bool,
    ) -> np.ndarray:
        """Aplica quadratura anatômica estilizada nas pontas das mangas:
        - Na barra extrema (cuff), projeta a seção transversal elíptica em um quadrado/squircle (~85%).
        - Suaviza gradualmente (via smoothstep Hermite) conforme sobe pelo braço, retornando ao formato
          natural e orgânico da roupa em direção ao cotovelo/ombro.
        """
        verts = deformed_verts.copy()
        if not sleeve_idx:
            return verts

        for side_mult in [1, -1]:
            s_side = [i for i in sleeve_idx if (verts[i, 0] * side_mult) > 0]
            if not s_side:
                continue

            s_v = verts[s_side]
            min_z = float(np.min(s_v[:, 2]))
            transition_len = 0.14 if is_long else 0.09
            max_trans_z = min_z + transition_len

            cuff_verts = s_v[s_v[:, 2] < min_z + 0.040]
            if len(cuff_verts) == 0:
                continue

            cx = float((cuff_verts[:, 0].min() + cuff_verts[:, 0].max()) / 2)
            cy = float((cuff_verts[:, 1].min() + cuff_verts[:, 1].max()) / 2)
            rx = float((cuff_verts[:, 0].max() - cuff_verts[:, 0].min()) / 2)
            ry = float((cuff_verts[:, 1].max() - cuff_verts[:, 1].min()) / 2)

            if rx < 1e-4 or ry < 1e-4:
                continue

            for i in s_side:
                z = verts[i, 2]
                if z < max_trans_z:
                    t = (z - min_z) / transition_len
                    t = min(max(t, 0.0), 1.0)
                    # Curva suave: 85% quadrado na ponta extrema, decaindo para 0% no topo da transição
                    factor = (1.0 - (t * t * (3.0 - 2.0 * t))) * 0.85

                    if factor > 0.001:
                        dx = verts[i, 0] - cx
                        dy = verts[i, 1] - cy
                        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                            continue

                        theta = np.arctan2(dy, dx)
                        cos_t = np.cos(theta)
                        sin_t = np.sin(theta)

                        denom_box = max(abs(cos_t) / min(rx, 0.046 if self.is_female else 0.080), abs(sin_t) / min(ry, 0.046 if self.is_female else 0.075))
                        r_box_unit = 1.0 / denom_box

                        denom_ellipse = np.sqrt((cos_t / rx)**2 + (sin_t / ry)**2)
                        r_ellipse_unit = 1.0 / denom_ellipse

                        box_ratio = r_box_unit / r_ellipse_unit
                        box_dx = dx * box_ratio
                        box_dy = dy * box_ratio

                        verts[i, 0] = cx + (1.0 - factor) * dx + factor * box_dx
                        verts[i, 1] = cy + (1.0 - factor) * dy + factor * box_dy

        return verts

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

    def apply_arm_hsr(self, lowest_sleeve_z, is_sleeveless, is_short_sleeves, max_cuff_z=None, cuff_center_map=None, has_bare_shoulders=False):
        """Retorna as malhas dos braços do personagem ajustadas para a roupa atual.
        Para manga longa com cuff_center_map, translada a mão fatiada para o centro exato da manga.
        Se os ombros estiverem nus (has_bare_shoulders ou is_sleeveless), preserva o braço superior 100% íntegro."""
        res = {}
        for side in ["esquerdo", "direito"]:
            name = f"braco superior {side}"
            v_raw = self.cage_data[f"{name}_verts"]
            f_raw = self.cage_data[f"{name}_faces"]
            mw = self.cage_data[f"{name}_matrix_world"]
            world_verts = (mw[:3, :3] @ v_raw.T).T + mw[:3, 3]
            # Slim arm moderado (apenas a pele)
            world_verts = self._slim_arm(world_verts, y_scale=0.74, x_scale=0.86)

            if is_sleeveless or has_bare_shoulders:
                res[name] = {"visible": True, "verts": world_verts, "faces": f_raw}
            elif is_short_sleeves:
                # O braço superior fica preservado dentro da manga curta,
                # preenchendo o interior sem penetrar o peito ou a costura do ombro
                cut_z = 1.200 if self.is_female else 1.280
                s_verts, s_faces = slice_mesh_below_z(world_verts, f_raw, cut_z)
                res[name] = {"visible": True, "verts": s_verts, "faces": s_faces}
            else:
                res[name] = {"visible": False, "verts": world_verts, "faces": f_raw}

            ab_name = f"antebraco {side}"
            ab_v = self.cage_data[f"{ab_name}_verts"]
            ab_f = self.cage_data[f"{ab_name}_faces"]
            ab_mw = self.cage_data[f"{ab_name}_matrix_world"]
            ab_world = (ab_mw[:3, :3] @ ab_v.T).T + ab_mw[:3, 3]
            # Slim forearm moderado (apenas a pele)
            ab_world = self._slim_arm(ab_world, y_scale=0.78, x_scale=0.88)

            if is_sleeveless or is_short_sleeves:
                res[ab_name] = {"visible": True, "verts": ab_world, "faces": ab_f}
            else:
                # Manga Longa / 3/4: fatia o antebraço logo acima da barra da manga,
                # mantendo a mão visível e embutida com folga estanque dentro da manga (>= 0.760m),
                # sem que o cotovelo ou antebraço superior furem o tecido.
                effective_cuff = max_cuff_z if max_cuff_z is not None else lowest_sleeve_z
                cut_ab_z = min(max(effective_cuff + 0.020, self.wrist_z + 0.020), 1.050)
                s_ab_v, s_ab_f = slice_mesh_below_z(ab_world, ab_f, cut_ab_z)

                # Alinhamento concêntrico: se o centro do punho da manga for conhecido,
                # translada a mão para emergir perfeitamente do meio da manga
                if cuff_center_map and side in cuff_center_map and len(s_ab_v) > 0:
                    target_cx, target_cy = cuff_center_map[side]
                    cur_hx = float((s_ab_v[:, 0].min() + s_ab_v[:, 0].max()) / 2)
                    cur_hy = float((s_ab_v[:, 1].min() + s_ab_v[:, 1].max()) / 2)
                    s_ab_v = s_ab_v.copy()
                    s_ab_v[:, 0] += (target_cx - cur_hx)
                    s_ab_v[:, 1] += (target_cy - cur_hy)

                res[ab_name] = {"visible": True, "verts": s_ab_v, "faces": s_ab_f}

        return res


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
        print(f"[*] Geometria: {len(verts)} vértices, {len(faces)} faces.")

        if meta["is_top"]:
            is_jacket = (meta.get("type_id") == 67) or any(k in meta.get("name", "").lower() for k in ["jacket", "bomber", "coat", "parka"])
            is_dress = (meta.get("type_id") == 72) or any(k in meta.get("name", "").lower() for k in ["dress", "vestido", "gown", "sundress", "robe"])
            sleeve_idx, torso_idx = self.analyze_topology(verts, faces)
            print(f"[*] Topologia: {len(sleeve_idx)} vértices manga, {len(torso_idx)} vértices torso.")

            apose_verts, cuff_z, is_sleeveless, is_short, is_long = self.fit_top_clothing(
                verts, faces, sleeve_idx, torso_idx, is_jacket=is_jacket, is_dress=is_dress
            )
            sleeve_label = "REGATA" if is_sleeveless else ("MANGA CURTA" if is_short else "MANGA LONGA")
            print(f"[*] Tipo de Manga: {sleeve_label} (Z cuff = {cuff_z:.3f}m, Casaco={is_jacket}, Vestido={is_dress})")

            rest_verts = self.deform_top_mesh(apose_verts, faces, sleeve_idx, torso_idx, is_jacket=is_jacket, is_sleeveless=is_sleeveless)
            deformed_verts = rest_verts

            # Calibração da ponta da manga longa (Z):
            # Garante que a barra da manga termine na altura anatômica do punho (Z ≈ 0.740m),
            # deixando a mão (~5.6cm) exposta e visível de forma natural, sem alterar a largura ou espessura da roupa.
            if is_long and sleeve_idx:
                target_cuff_z = self.wrist_z + 0.056  # 0.740m
                elbow_z = 1.080
                for side_mult in [1, -1]:
                    s_side = [i for i in sleeve_idx if (deformed_verts[i, 0] * side_mult) > 0]
                    if s_side:
                        min_s_z = float(np.min(deformed_verts[s_side, 2]))
                        if min_s_z < target_cuff_z:
                            for i in s_side:
                                z = deformed_verts[i, 2]
                                if z < elbow_z:
                                    t = (elbow_z - z) / (elbow_z - min_s_z + 1e-8)
                                    deformed_verts[i, 2] = elbow_z - t * (elbow_z - target_cuff_z)

            # Tapering anatômico feminino de mangas compridas
            if self.is_female and is_long and sleeve_idx:
                deformed_verts = self.taper_female_sleeves(deformed_verts, sleeve_idx, is_jacket=is_jacket)

            # Estilização Blocky: Aplica quadratura nas pontas das mangas com transição suave
            if sleeve_idx and not is_sleeveless:
                deformed_verts = self.square_sleeve_cuffs(deformed_verts, sleeve_idx, is_long, is_short)

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
            shoulder_pts = deformed_verts[(np.abs(deformed_verts[:, 0]) > 0.22) & (deformed_verts[:, 2] > 1.35)]
            has_bare_shoulders = (
                is_sleeveless
                or (len(shoulder_pts) < 30)
                or (float(shoulder_pts[:, 2].max()) < 1.420 if len(shoulder_pts) > 0 else True)
            )
            if has_bare_shoulders and not is_sleeveless:
                print(f"[*] Detecção Anatômica: Ombros nus / mangas destacadas (pts={len(shoulder_pts)} -> preservando braço superior completo)")

            arm_hsr = self.apply_arm_hsr(
                real_cuff_z, is_sleeveless, is_short,
                max_cuff_z=max_cuff_z, cuff_center_map=cuff_center_map,
                has_bare_shoulders=has_bare_shoulders
            )
        else:
            tpose_verts = self.fit_bottom_clothing(verts, target_waist_z=target_waist_z)
            deformed_verts = self.deform_bottom_mesh(tpose_verts, faces)

            arm_hsr = None
            cuff_z = None
            is_short, is_sleeveless, is_long = False, False, False

        if output_obj is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            suffix = "_female.obj" if self.body_type in ("female", "feminino", "fem") else ".obj"
            output_obj = os.path.join(base_dir, "assets", "models", f"character_native_{asset_id}{suffix}")

        models_dir = os.path.dirname(output_obj)
        # Exporta as malhas dos braços fatiados pelo HSR para OBJ (específicas por asset e padrão)
        if arm_hsr:
            arm_suffix = "_female.obj" if self.is_female else ".obj"
            for side, eng_name in [("left", "braco superior esquerdo"), ("right", "braco superior direito")]:
                arm_data = arm_hsr.get(eng_name)
                # Exporta tanto arquivo específico quanto padrão se for manga longa
                paths = [
                    os.path.join(models_dir, f"character_native_arm_{side}_{asset_id}.obj"),
                    os.path.join(models_dir, f"character_native_arm_{side}_{asset_id}{arm_suffix}"),
                ]
                if is_long:
                    paths.append(os.path.join(models_dir, f"character_native_arm_{side}.obj"))
                    paths.append(os.path.join(models_dir, f"character_native_arm_{side}{arm_suffix}"))
                for arm_obj_path in set(paths):
                    if arm_data and arm_data.get("visible", False):
                        with open(arm_obj_path, "w", encoding="utf-8") as f:
                            f.write(f"# Isometricon Native Sliced Arm: {side}\n")
                            for v in arm_data["verts"]:
                                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                            for face in arm_data["faces"]:
                                f.write("f " + " ".join(str(idx + 1) for idx in face) + "\n")
                    else:
                        with open(arm_obj_path, "w", encoding="utf-8") as f:
                            f.write("# Arm hidden\n")

            for side, eng_name in [("left", "antebraco esquerdo"), ("right", "antebraco direito")]:
                ab_data = arm_hsr.get(eng_name)
                paths = [
                    os.path.join(models_dir, f"character_native_forearm_{side}_{asset_id}.obj"),
                    os.path.join(models_dir, f"character_native_forearm_{side}_{asset_id}{arm_suffix}"),
                ]
                if is_long:
                    paths.append(os.path.join(models_dir, f"character_native_forearm_{side}.obj"))
                    paths.append(os.path.join(models_dir, f"character_native_forearm_{side}{arm_suffix}"))
                for ab_obj_path in set(paths):
                    if ab_data and ab_data.get("visible", False):
                        with open(ab_obj_path, "w", encoding="utf-8") as f:
                            f.write(f"# Isometricon Native Forearm: {side}\n")
                            for v in ab_data["verts"]:
                                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                            for face in ab_data["faces"]:
                                f.write("f " + " ".join(str(idx + 1) for idx in face) + "\n")
                    else:
                        with open(ab_obj_path, "w", encoding="utf-8") as f:
                            f.write("# Forearm hidden\n")

        with open(output_obj, "w", encoding="utf-8") as f:
            f.write(f"# Isometricon Native Fitted Clothing: {asset_id}\n")
            for v in deformed_verts:
                f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
            for uv in uvs:
                f.write(f"vt {uv[0]:.5f} {uv[1]:.5f}\n")
            for i, face in enumerate(faces):
                if len(face_uvs) > i:
                    f.write("f " + " ".join(f"{face[j]+1}/{face_uvs[i][j]+1}" for j in range(len(face))) + "\n")
                else:
                    f.write("f " + " ".join(f"{idx+1}" for idx in face) + "\n")

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
            "arm_hsr": arm_hsr
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

        # Alinhamento CFrame preciso do HairAttachment / HatAttachment do modelo Roblox
        R_att, p_att = extract_attachment_cframe_from_rbxm(rbxm_path if (rbxm_path and os.path.exists(rbxm_path)) else asset_id)

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

        # 1. Alinha com Attachment do Roblox:
        # v_rel = (v_mesh - p_att) @ R_att
        # Remove o offset de ancoragem do criador e orienta no padrão Roblox
        v_rel = (raw_verts - p_att) @ R_att

        # 2. Converte para coordenadas do Isometricon:
        # Calibrado milimetricamente usando como base o cabelo masculino padrão do jogo (Hair_fitted_116773763268018):
        # - Rotação de 180° no plano horizontal (inversão de X e Z) para converter do referencial Roblox (-Z frontal)
        #   para o referencial Isometricon (+Z frontal)
        # - Escalas anatômicas: X=0.2078m/stud, Y=0.2000m/stud, Z=0.2220m/stud
        # - Ancoragem canônica no topo da cabeça: Y_anchor = 1.815m, X_center = 0.005m, Z_center = -0.003m
        v_world = np.zeros_like(v_rel)
        v_world[:, 0] = -v_rel[:, 0] * 0.2078 + 0.0050
        v_world[:, 1] =  v_rel[:, 1] * 0.2000 + 1.8150
        v_world[:, 2] = -v_rel[:, 2] * 0.2220 - 0.0028

        out_obj = os.path.join(clothing_dir, f"Hair_fitted_{asset_id}.obj")
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
