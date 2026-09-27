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


def hidden_reference_vertices(hsr_data: bytes, reference_vertex_count: int) -> np.ndarray:
    """Boolean per reference-cage vertex: True where the body is hidden."""
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


def engine_to_body_mesh(points: np.ndarray) -> np.ndarray:
    """Engine (x, depth, up) -> body mesh / OpenGL space (x, up, -depth)."""
    points = np.asarray(points, dtype=np.float64)
    return np.column_stack((points[:, 0], points[:, 2], -points[:, 1]))


def sidecar_path(fitted_obj_path) -> str:
    return os.path.splitext(str(fitted_obj_path))[0] + "_hsr.npz"


def cull_hidden_triangles(positions: np.ndarray, faces: np.ndarray, cage_points: np.ndarray,
                          hidden_cage: np.ndarray) -> np.ndarray:
    """Faces kept after HSR. A triangle is hidden when at least two of its vertices'
    nearest body-cage points are hidden (the rule closest to Studio's culling)."""
    if len(faces) == 0 or not hidden_cage.any():
        return faces
    nearest = np.concatenate([((positions[i:i + 512, None] - cage_points[None]) ** 2).sum(-1).argmin(1)
                              for i in range(0, len(positions), 512)])
    vertex_hidden = hidden_cage[nearest]
    return faces[vertex_hidden[faces].sum(1) < 2]
