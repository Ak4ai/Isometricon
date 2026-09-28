"""Hidden surface removal (HSR) from Roblox's per-garment HiddenSurfaceRemovalAsset.

Each layered garment's WrapLayer points (HSRAssetId) to a HiddenSurfaceRemovalAsset
whose HSRData starts with: 5 header bytes, uint32 garment face count, uint32
(unidentified), uint32 zero, then one bit per vertex of the garment's reference
cage, least-significant bit first. Bit 0 means the body surface under that cage
vertex is covered by the garment. Further tables follow and are not used here.

Because every Roblox cage shares one UV layout, the mask carries over to any
body through the reference-cage -> body-cage UV pairing of the WrapLayer fit.
Checked against Roblox Studio exports of the Blocky: the body area it hides
matches Studio's culling on 85-100% of the body for 9 of 10 garments
(scripts/audit_hsr_mask_roblox.py).
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path
import re
import struct

import numpy as np

HEADER_BYTES = 17


def hsr_asset_id(rbxm_path) -> str | None:
    from .wrap_layer_fit import _rbxm_properties
    data = Path(rbxm_path).read_bytes()
    data = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
    properties = _rbxm_properties(data)
    if "HSRAssetId" not in properties:
        return None
    payload = properties["HSRAssetId"][1]
    url = payload[4:4 + struct.unpack_from("<I", payload)[0]].decode("ascii", errors="ignore")
    match = re.search(r"id=(\d+)", url)
    return match.group(1) if match else None


def load_hsr_data(asset_id: str, cache_dir) -> bytes:
    """HSRData payload of a HiddenSurfaceRemovalAsset (downloaded once into ``cache_dir``)."""
    import lz4.block
    cache = Path(cache_dir)
    path = cache / f"{asset_id}.bin"
    if not path.exists() or not path.stat().st_size:
        from scripts.import_roblox_clothing import fetch_roblox_asset
        data = fetch_roblox_asset(asset_id)
        if not data:
            raise FileNotFoundError(f"HSR {asset_id} indisponível")
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if not data.startswith(b"<roblox!"):
        raise ValueError("HSR não é um RBXM binário")
    index = 32
    while index + 16 <= len(data):
        name, compressed, size, _ = struct.unpack_from("<4sIII", data, index)
        body = data[index + 16:index + 16 + (compressed or size)]
        index += 16 + (compressed or size)
        if compressed:
            body = lz4.block.decompress(body, uncompressed_size=size)
        if name == b"PROP":
            length = struct.unpack_from("<I", body, 4)[0]
            if body[8:8 + length] == b"HSRData":
                payload = body[9 + length:]
                return payload[4:4 + struct.unpack_from("<I", payload)[0]]
        if name == b"END\x00":
            break
    raise ValueError("HSRData ausente")


SUPPORTED_VERSION = 0x12


def hidden_reference_vertices(hsr_data: bytes, reference_vertex_count: int) -> np.ndarray:
    """Boolean per reference-cage vertex: True where the body is hidden.

    Only the 0x12 layout is decoded. Older assets carry 0x10/0x11 data whose mask,
    read the same way, scatters over the body (spatial coherence 0.5-0.8 against
    0.84-1.0 for 0x12 across 56 cached garments) and would punch holes in visible
    skin, so they are treated as having no HSR data.
    """
    if not hsr_data or hsr_data[0] != SUPPORTED_VERSION:
        version = f"0x{hsr_data[0]:02x}" if hsr_data else "vazia"
        raise ValueError(f"versão de HSR {version} não suportada (só 0x{SUPPORTED_VERSION:02x})")
    needed = HEADER_BYTES + (reference_vertex_count + 7) // 8
    if len(hsr_data) < needed:
        raise ValueError("HSRData menor que a máscara da cage de referência")
    raw = np.frombuffer(hsr_data[HEADER_BYTES:needed], np.uint8)
    return np.unpackbits(raw, bitorder="little")[:reference_vertex_count] == 0


def hidden_body_cage_mask(rbxm_path, trace: dict, body_cage_count: int, cache_dir) -> np.ndarray | None:
    """Per body-cage point (UV order of the WrapLayer fit): True under the garment; None without HSR data."""
    asset_id = hsr_asset_id(rbxm_path)
    if asset_id is None:
        return None
    uv_index = np.asarray(trace["uv_index"])
    hidden_reference = hidden_reference_vertices(load_hsr_data(asset_id, cache_dir), len(uv_index))
    hidden = np.zeros(body_cage_count, dtype=bool)
    hidden[uv_index[hidden_reference]] = True
    return hidden


def geometric_hidden_mask(cage_points: np.ndarray, cage_faces: np.ndarray, garment_vertices: np.ndarray,
                          radius_fraction: float = 0.03, inside_fraction: float = 0.02) -> np.ndarray:
    """Body-cage points covered by a fitted garment, for garments without usable HSR data.

    A cage point is covered when some garment vertex lies within ``radius_fraction``
    of the body height and not more than ``inside_fraction`` of it inside the body
    (along the outward cage normal): cloth sunk a little into the skin (e.g. a
    chest larger than the garment's reference body) must still hide it. On the
    Blocky it agrees with Roblox Studio's culling on ~80% of the body area and
    hides ~2% where Studio shows skin; a 4.9% radius agreed on 86% but opened
    5.6% gaps at the hems, which make garments look detached.
    """
    cage_points = np.asarray(cage_points, dtype=np.float64)
    garment = np.asarray(garment_vertices, dtype=np.float64)
    normals = np.zeros_like(cage_points)
    corners = cage_points[cage_faces]
    face_normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    for k in range(3):
        np.add.at(normals, cage_faces[:, k], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    if np.einsum("ij,ij->i", cage_points - cage_points.mean(0), normals).mean() < 0:
        normals = -normals  # outward
    height = float(np.ptp(cage_points, axis=0).max())
    radius, inside = radius_fraction * height, inside_fraction * height
    hidden = np.zeros(len(cage_points), dtype=bool)
    for start in range(0, len(cage_points), 128):
        offset = garment[None] - cage_points[start:start + 128, None]
        near = (offset ** 2).sum(-1) < radius * radius
        outside = np.einsum("pgk,pk->pg", offset, normals[start:start + 128]) > -inside
        hidden[start:start + 128] = (near & outside).any(1)
    return hidden


def engine_to_body_mesh(points: np.ndarray) -> np.ndarray:
    """Engine (x, depth, up) -> body mesh / OpenGL space (x, up, -depth)."""
    points = np.asarray(points, dtype=np.float64)
    return np.column_stack((points[:, 0], points[:, 2], -points[:, 1]))


def sidecar_path(fitted_obj_path) -> str:
    return os.path.splitext(str(fitted_obj_path))[0] + "_hsr.npz"


def body_cage_faces(cages: dict) -> np.ndarray:
    """Body-cage triangles indexed like ``_unique_uv_positions`` (one point per UV)."""
    from .wrap_layer_fit import _unique_uv_positions
    keys, _ = _unique_uv_positions(cages)
    index = {tuple(key): i for i, key in enumerate(keys)}
    faces = []
    for name, part in cages.items():
        if name.endswith("Forearm"):
            continue  # runtime helper that duplicates arm/hand cages
        for uv_face in part["face_uvs"]:
            faces.append([index[tuple(np.round(uv, 5))] for uv in uv_face])
    return np.asarray(faces, dtype=np.int32)


def _closest_on_triangles(points, a, b, c):
    """Barycentric coordinates (n, m, 3) of each point's closest point on each triangle."""
    ab, ac = b - a, c - a
    ap = points[:, None] - a[None]
    d1, d2 = (ap * ab).sum(-1), (ap * ac).sum(-1)
    bp = points[:, None] - b[None]
    d3, d4 = (bp * ab).sum(-1), (bp * ac).sum(-1)
    cp = points[:, None] - c[None]
    d5, d6 = (cp * ab).sum(-1), (cp * ac).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    denom = np.where(np.abs(va + vb + vc) < 1e-20, 1e-20, va + vb + vc)
    v, w = vb / denom, vc / denom
    bary = np.stack((1 - v - w, v, w), -1)
    regions = [  # Ericson's Voronoi regions, most specific last so they win
        (d1 <= 0) & (d2 <= 0), (d3 >= 0) & (d4 <= d3), (d6 >= 0) & (d5 <= d6),
        (vc <= 0) & (d1 >= 0) & (d3 <= 0), (vb <= 0) & (d2 >= 0) & (d6 <= 0),
        (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)]
    t_ab = np.clip(d1 / np.where(np.abs(d1 - d3) < 1e-20, 1e-20, d1 - d3), 0, 1)
    t_ac = np.clip(d2 / np.where(np.abs(d2 - d6) < 1e-20, 1e-20, d2 - d6), 0, 1)
    t_bc = np.clip((d4 - d3) / np.where(np.abs((d4 - d3) + (d5 - d6)) < 1e-20, 1e-20, (d4 - d3) + (d5 - d6)), 0, 1)
    choices = [np.stack((np.ones_like(v), 0 * v, 0 * v), -1), np.stack((0 * v, np.ones_like(v), 0 * v), -1),
               np.stack((0 * v, 0 * v, np.ones_like(v)), -1), np.stack((1 - t_ab, t_ab, 0 * v), -1),
               np.stack((1 - t_ac, 0 * v, t_ac), -1), np.stack((0 * v, 1 - t_bc, t_bc), -1)]
    edge_or_vertex = np.zeros(v.shape, bool)
    for region, choice in zip(reversed(regions), reversed(choices)):
        take = region & ~edge_or_vertex
        bary[take] = choice[take]
        edge_or_vertex |= region
    return bary


def vertex_hidden_on_cage_surface(positions, cage_points, cage_faces, hidden_cage, chunk=64):
    """Hidden fraction at each point's closest point on the body-cage surface (0..1)."""
    a, b, c = (cage_points[cage_faces[:, k]] for k in range(3))
    flags = hidden_cage[cage_faces].astype(np.float64)
    out = np.empty(len(positions))
    for start in range(0, len(positions), chunk):
        p = positions[start:start + chunk]
        bary = _closest_on_triangles(p, a, b, c)
        closest = bary[..., 0, None] * a[None] + bary[..., 1, None] * b[None] + bary[..., 2, None] * c[None]
        best = ((closest - p[:, None]) ** 2).sum(-1).argmin(1)
        rows = np.arange(len(p))
        out[start:start + chunk] = (bary[rows, best] * flags[best]).sum(-1)
    return out


def cull_hidden_triangles(positions: np.ndarray, faces: np.ndarray, cage_points: np.ndarray,
                          hidden_cage: np.ndarray, cage_faces: np.ndarray | None = None,
                          min_hidden: int = 3, threshold: float = 0.9) -> np.ndarray:
    """Faces kept after HSR: a triangle is hidden when ``min_hidden`` of its vertices are.

    With ``cage_faces`` a skin vertex is hidden when the mask, interpolated at its
    closest point on the body-cage surface, is past ``threshold``: 0.9 keeps the skin
    running about one cage triangle under each garment edge, so hems never leave a
    gap (Studio agreement unchanged, uncovered-skin area 1.3% -> 1.0%); otherwise its
    nearest cage point decides. On a subdivided skin all three is the safe rule: a
    garment edge may leave some skin under the cloth but never a hole.
    """
    if len(faces) == 0 or not hidden_cage.any():
        return faces
    positions = np.asarray(positions, dtype=np.float64)
    if cage_faces is not None and len(cage_faces):
        vertex_hidden = vertex_hidden_on_cage_surface(positions, cage_points, cage_faces, hidden_cage) > threshold
    else:
        nearest = np.concatenate([((positions[i:i + 512, None] - cage_points[None]) ** 2).sum(-1).argmin(1)
                                  for i in range(0, len(positions), 512)])
        vertex_hidden = hidden_cage[nearest]
    return faces[vertex_hidden[faces].sum(1) < min_hidden]


def subdivide(vertices: np.ndarray, faces: np.ndarray, levels: int = 2):
    """Midpoint subdivision (1 triangle -> 4 per level), interpolating every vertex attribute.

    Our body parts are coarse boxes whose triangles can span a whole thigh, so
    HSR decided per original triangle would cut holes past a garment's hem.
    """
    vertices = np.asarray(vertices, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int64)
    for _ in range(levels):
        edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
        unique, inverse = np.unique(edges, axis=0, return_inverse=True)
        inverse = inverse.ravel()
        midpoints = (vertices[unique[:, 0]] + vertices[unique[:, 1]]) / 2
        if vertices.shape[1] >= 6:  # keep interpolated normals unit length
            normals = midpoints[:, 3:6]
            midpoints[:, 3:6] = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
        m = len(vertices) + inverse.reshape(3, -1).T  # midpoint ids of edges ab, bc, ca per face
        a, b, c = faces.T
        ab, bc, ca = m.T
        faces = np.concatenate((np.column_stack((a, ab, ca)), np.column_stack((ab, b, bc)),
                                np.column_stack((ca, bc, c)), np.column_stack((ab, bc, ca))))
        vertices = np.vstack((vertices, midpoints.astype(np.float32)))
    return vertices, faces
