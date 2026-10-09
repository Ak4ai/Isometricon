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


def _cage_vertex_normals(cage_points, cage_faces):
    normals = np.zeros_like(cage_points)
    corners = cage_points[cage_faces]
    face_normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    for k in range(3):
        np.add.at(normals, cage_faces[:, k], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    if np.einsum("ij,ij->i", cage_points - cage_points.mean(0), normals).mean() < 0:
        normals = -normals  # outward
    return normals


def ray_hidden_mask(cage_points: np.ndarray, cage_faces: np.ndarray, garment_vertices: np.ndarray,
                    garment_faces: np.ndarray, reach_fraction: float = 0.08,
                    inside_fraction: float = 0.02) -> np.ndarray:
    """Body-cage points with garment cloth in front of them along the outward normal.

    Unlike a proximity test, a ray passes through an open zip or slit between two
    garment pieces, so the skin behind it stays visible instead of leaving a hole.
    Against Roblox Studio on the Blocky (9 garments, reach 12%): agreement 88%
    (proximity: 82%; asset HSR 0x12: ~89%), gaps 1.2% of the body area (2.2%).
    """
    cage_points = np.asarray(cage_points, dtype=np.float64)
    garment = np.asarray(garment_vertices, dtype=np.float64)
    tri = garment[np.asarray(garment_faces)]
    normals = _cage_vertex_normals(cage_points, cage_faces)
    height = float(np.ptp(cage_points, axis=0).max())
    reach, inside = reach_fraction * height, inside_fraction * height
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    hidden = np.zeros(len(cage_points), dtype=bool)
    for start in range(0, len(cage_points), 64):
        origin = cage_points[start:start + 64] - normals[start:start + 64] * inside
        direction = normals[start:start + 64]
        # Moller-Trumbore, all rays of the chunk against all garment triangles.
        p = np.cross(direction[:, None], e2[None])
        det = np.einsum("tk,rtk->rt", e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = origin[:, None] - v0[None]
        u = np.einsum("rtk,rtk->rt", s, p) * inv
        q = np.cross(s, e1[None])
        v = np.einsum("rk,rtk->rt", direction, q) * inv
        t = np.einsum("tk,rtk->rt", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= reach + inside)
        hidden[start:start + 64] = hit.any(1)
    return _hide_isolated_visible(hidden, cage_points, cage_faces)


def _hide_isolated_visible(hidden: np.ndarray, cage_points: np.ndarray, cage_faces: np.ndarray,
                           min_visible_neighbours: int = 1) -> np.ndarray:
    """Hide visible points that have no visible neighbour on the cage.

    A ray can escape through a tiny gap in the cloth (drawstring eyelet, cuff seam)
    and leave one lone point visible, which shows as a diamond of skin through the
    garment. A real opening such as a zip slit is a line of points and survives,
    ends included.
    Points duplicated at UV seams are welded by position first.
    """
    _, weld = np.unique(np.round(cage_points, 5), axis=0, return_inverse=True)
    weld = weld.ravel()
    faces = weld[np.asarray(cage_faces)]
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = edges[edges[:, 0] != edges[:, 1]]
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    welded_hidden = np.zeros(weld.max() + 1, dtype=bool)
    np.logical_or.at(welded_hidden, weld, hidden)
    visible = ~welded_hidden
    count = np.zeros(len(visible), dtype=int)
    np.add.at(count, edges[:, 0], visible[edges[:, 1]])
    np.add.at(count, edges[:, 1], visible[edges[:, 0]])
    welded_hidden |= visible & (count < min_visible_neighbours)
    return welded_hidden[weld]


# Limb cage parts and the bone whose axis measures their height.
LIMB_CAGE_BONES = {"LeftUpperArm": "UpperArm_L", "RightUpperArm": "UpperArm_R",
                   "LeftLowerArm": "LowerArm_L", "RightLowerArm": "LowerArm_R",
                   "LeftUpperLeg": "UpperLeg_L", "RightUpperLeg": "UpperLeg_R",
                   "LeftLowerLeg": "LowerLeg_L", "RightLowerLeg": "LowerLeg_R"}
# Rays cast around a limb's bone to test whether a garment wraps it, how far they reach (m)
# and how many must meet the garment. Toward the torso a sleeve has no wall of its own: those
# rays cross the body to the far side of the shirt, so the reach spans a torso. At the
# shoulder one or two rays slip out through the neck opening. A sleeveless top leaves the
# whole outer half of the turn empty (4-6 hits out of 16).
WRAP_RAYS = 16
WRAP_REACH = 0.6
WRAP_MIN_HITS = 14


def _garment_triangles(fitted_obj_path) -> np.ndarray:
    """(T, 3, 3) triangles of a fitted garment OBJ, in body-mesh coordinates."""
    vertices, faces = [], []
    with open(fitted_obj_path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("v "):
                vertices.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                ids = [int(token.split("/")[0]) - 1 for token in line.split()[1:]]
                faces += [[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)]
    return engine_to_body_mesh(np.asarray(vertices, dtype=np.float64))[np.asarray(faces)]


def _wrapped(triangles, centre, axis) -> bool:
    """Whether the rays leaving ``centre`` across ``axis`` meet the garment all around (WRAP_MIN_HITS)."""
    from .layer_clearance import _farthest_hits
    side = np.cross(axis, [0.0, 0.0, 1.0])
    side /= np.linalg.norm(side)
    front = np.cross(side, axis)
    turns = np.linspace(0.0, 2 * np.pi, WRAP_RAYS, endpoint=False)
    directions = np.cos(turns)[:, None] * side + np.sin(turns)[:, None] * front
    hits = _farthest_hits(np.repeat(centre[None], WRAP_RAYS, 0), directions,
                          np.full(WRAP_RAYS, WRAP_REACH / 2), triangles, WRAP_REACH / 2)
    return int(np.isfinite(hits).sum()) >= WRAP_MIN_HITS


def close_wrapped_limbs(hidden: np.ndarray, body: str, fitted_obj_path) -> np.ndarray:
    """The garment's HSR mask, also covering the limb cage where the garment wraps the limb.

    Roblox's limb cages are open along the side facing the torso (the armpit, between the
    legs), and their masks leave the points around that opening visible even under a sleeve
    that goes all around the arm; once the arm moves, the skin there comes out through the
    sleeve. Here, at the height of each such point along its limb, rays are cast all around
    the bone in the fitting pose: only when they meet the garment all around (a sleeve or a
    trouser leg, WRAP_MIN_HITS) is the point covered. A sleeveless top, a short sleeve below its hem or a
    skirt never wraps the limb, so their masks are left as they were.
    """
    from .skeleton import Skeleton
    from .wear_engine import BODY_CAGES, load_r15_cages
    from .wrap_layer_fit import _unique_uv_positions, body_uv_parts
    models = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "assets", "models")
    cages = load_r15_cages(os.path.join(models, BODY_CAGES[body]))
    body_uv, positions = _unique_uv_positions(cages)
    if len(body_uv) != len(hidden) or not os.path.exists(fitted_obj_path):
        return hidden
    positions = engine_to_body_mesh(positions)
    parts = np.array(body_uv_parts(cages))
    triangles = _garment_triangles(fitted_obj_path)
    skeleton = Skeleton.load(body)
    result = hidden.copy()
    for part, bone_name in LIMB_CAGE_BONES.items():
        todo = np.flatnonzero((parts == part) & ~hidden)
        if not len(todo):
            continue
        bone = skeleton.index(bone_name)
        head = skeleton.heads[bone]
        axis = skeleton.tails[bone] - head
        length = np.linalg.norm(axis)
        axis /= length
        reach = length + WRAP_REACH
        near = triangles[np.all((triangles.min(1) <= head + reach) & (triangles.max(1) >= head - reach), axis=1)]
        wrapped = {}
        for point in todo:
            height = float(np.clip((positions[point] - head) @ axis, 0.0, length))
            key = round(height, 2)
            if key not in wrapped:
                wrapped[key] = _wrapped(near, head + axis * height, axis)
            result[point] = wrapped[key]
    return result


# The skin while its mask is edited, painted by what each point of it is (as vertex colours):
# showing, hidden by the clothes, hidden by hand, shown by hand.
EDIT_SHOWN, EDIT_HIDDEN = (0.78, 0.80, 0.86), (1.00, 0.55, 0.20)
EDIT_PAINTED_HIDDEN, EDIT_PAINTED_SHOWN = (1.00, 0.22, 0.22), (0.25, 0.90, 0.42)


def edit_colours(nearest, cage_faces: np.ndarray, hidden: np.ndarray, painted_hidden=(), painted_shown=()) -> np.ndarray:
    """Colour (N, 3) of each skin vertex in the edit mode, blended over the body-cage surface.

    ``nearest``: what ``closest_on_surface`` gives for the vertices (triangle, barycentric
    coordinates). The whole skin is drawn, hidden or not, so that all of it can be painted.
    """
    best, bary = nearest
    corners = np.asarray(cage_faces)[best]

    def blended(flags) -> np.ndarray:
        return (bary * np.asarray(flags, dtype=np.float64)[corners]).sum(-1)[:, None]

    def marked(indices) -> np.ndarray:
        flags = np.zeros(len(hidden))
        flags[[int(i) for i in (indices or ()) if 0 <= int(i) < len(hidden)]] = 1.0
        return flags

    colour = np.array(EDIT_SHOWN) + (np.array(EDIT_HIDDEN) - np.array(EDIT_SHOWN)) * blended(hidden)
    for indices, tone in ((painted_hidden, EDIT_PAINTED_HIDDEN), (painted_shown, EDIT_PAINTED_SHOWN)):
        colour = colour + (np.array(tone) - colour) * blended(marked(indices))
    return colour


EDGE_SHOWN = 0.010   # metres past a garment's moved edge, under the cloth, where the skin is still drawn
EDGE_HIDDEN = 0.015  # and metres short of it where the skin is not hidden yet: no gap at the edge, no hole


def cage_point_parts(body: str, count: int):
    """Name of the body part of each body-cage point (in the order of the masks), or None when
    the cage of this body is not the one the mask was made with."""
    from .wear_engine import BODY_CAGES, load_r15_cages
    from .wrap_layer_fit import _unique_uv_positions, body_uv_parts
    models = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "assets", "models")
    cages = load_r15_cages(os.path.join(models, BODY_CAGES[body]))
    body_uv, _ = _unique_uv_positions(cages)
    return np.array(body_uv_parts(cages)) if len(body_uv) == count else None


def move_mask_edge(hidden: np.ndarray, cage_points: np.ndarray, parts, edge: float, shift: float,
                   lower: bool = True) -> np.ndarray:
    """A garment's mask after one of its edges, at the height ``edge``, was moved ``shift`` metres up.

    ``lower``: its lower edge (a hem); otherwise its upper one (a waist). The skin the edge
    uncovers is shown again, and the skin it now covers is hidden; the arms are left alone (a
    top's sleeves do not move with its hem).
    """
    hidden = np.array(hidden, dtype=bool, copy=True)
    if not shift:
        return hidden
    y = np.asarray(cage_points, dtype=np.float64)[:, 1]
    body = np.ones(len(hidden), dtype=bool) if parts is None else \
        np.array(["Arm" not in str(name) and "Hand" not in str(name) for name in parts])
    moved = edge + shift
    if lower:
        if shift > 0:
            hidden[body & (y < moved + EDGE_SHOWN)] = False
        else:
            hidden[body & (y >= moved + EDGE_HIDDEN) & (y < edge)] = True
    elif shift < 0:
        hidden[body & (y > moved - EDGE_SHOWN)] = False
    else:
        hidden[body & (y <= moved - EDGE_HIDDEN) & (y > edge)] = True
    return hidden




def garment_mesh(fitted_obj_path):
    """(vertices in body-mesh coordinates, triangles) of a fitted garment OBJ."""
    vertices, faces = [], []
    with open(fitted_obj_path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("v "):
                vertices.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                ids = [int(token.split("/")[0]) - 1 for token in line.split()[1:]]
                faces += [[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)]
    return engine_to_body_mesh(np.asarray(vertices, dtype=np.float64).reshape(-1, 3)), np.asarray(faces, dtype=np.int64).reshape(-1, 3)


def recut_mask_edges(hidden: np.ndarray, cage_points: np.ndarray, cage_faces: np.ndarray, parts, vertices: np.ndarray,
                     faces: np.ndarray, moves, keep=None) -> np.ndarray:
    """A garment's mask after its edges were moved, computed again from the garment as it is now.

    ``moves``: (height of the edge, metres it was moved up, whether it is the lower edge) of each
    edge moved. The garment is moved as the character shows it (``body_shape.move_edge``; ``keep``:
    its vertices that move, a top's sleeves staying on the arms) and rays are cast from the body
    cage through it (``ray_hidden_mask``): from each moved edge outwards, and into the garment as
    far as its cloth moved with the edge (``EDGE_FALLOFF``), the mask is what the rays find (skin
    newly hidden only where it is covered all around); the rest of it, and the arms, stay as they were.
    """
    from .body_shape import EDGE_FALLOFF, move_edge
    hidden = np.array(hidden, dtype=bool, copy=True)
    moves = [(float(edge), float(shift), bool(lower)) for edge, shift, lower in moves if shift]
    if not moves or cage_faces is None or not len(faces):
        for edge, shift, lower in moves:
            hidden = move_mask_edge(hidden, cage_points, parts, edge, shift, lower)
        return hidden
    moved = np.asarray(vertices, dtype=np.float64)
    for edge, shift, lower in moves:
        moved = move_edge(moved, edge, shift, lower, keep)
    covered = ray_hidden_mask(cage_points, cage_faces, moved, faces)
    # Skin that was showing is hidden only where the cloth covers it and all around it: a string or
    # a strap passing over the skin is met by a ray too, and hiding the skin under it leaves a hole.
    beside_bare = np.zeros(len(covered), dtype=bool)
    cage = np.asarray(cage_faces)
    for a, b in ((0, 1), (1, 2), (2, 0)):
        np.logical_or.at(beside_bare, cage[:, a], ~covered[cage[:, b]])
        np.logical_or.at(beside_bare, cage[:, b], ~covered[cage[:, a]])
    covered = np.where(hidden, covered, covered & ~beside_bare)
    y = np.asarray(cage_points, dtype=np.float64)[:, 1]
    body = np.ones(len(hidden), dtype=bool) if parts is None else \
        np.array(["Arm" not in str(name) and "Hand" not in str(name) for name in parts])
    for edge, shift, lower in moves:
        zone = body & ((y < max(edge, edge + shift) + EDGE_FALLOFF) if lower else (y > min(edge, edge + shift) - EDGE_FALLOFF))
        hidden[zone] = covered[zone]
    return hidden


MIRROR_REACH = 0.005  # metres within which a cage point is the mirror of another, across the middle of the body


def mirror_index(cage_points: np.ndarray, reach: float = MIRROR_REACH) -> np.ndarray:
    """For each body-cage point, the point that mirrors it on the other side of the body (-1 without one)."""
    points = np.asarray(cage_points, dtype=np.float64)
    mirrored = points * np.array([-1.0, 1.0, 1.0])
    found = np.full(len(points), -1, dtype=np.int64)
    for start in range(0, len(points), 256):
        distance = ((mirrored[start:start + 256, None] - points[None]) ** 2).sum(-1)
        nearest = distance.argmin(1)
        found[start:start + 256] = np.where(distance[np.arange(len(nearest)), nearest] < reach * reach, nearest, -1)
    return found


def adjusted_hidden(hidden: np.ndarray, cage_points: np.ndarray, mirror: bool = False, hide=(), show=()) -> np.ndarray:
    """The mask of hidden skin with the character's own corrections over what the garments give.

    ``mirror``: a point hidden on one side of the body hides the one that mirrors it (the mask of
    a garment whose mesh is not symmetric covers one arm and narrowly misses the other, and the
    skin then comes through the cloth on that side only). ``hide`` and ``show``: points painted
    by hand, which win over everything else.
    """
    hidden = np.array(hidden, dtype=bool, copy=True)
    if mirror:
        other = mirror_index(cage_points)
        paired = other >= 0
        hidden[paired] |= hidden[other[paired]].copy()
    for indices, value in ((hide, True), (show, False)):
        ids = [int(i) for i in (indices or ()) if 0 <= int(i) < len(hidden)]
        hidden[ids] = value
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


def closest_on_surface(points, a, b, c, chunk=256):
    """(triangle index, barycentric coordinates) of each point's closest point on the triangles.

    Exact, but not brute force: equal points (render buffers repeat every vertex per face
    corner) are solved once, and each batch of neighbouring points only looks at the
    triangles whose box lies within the distance to their nearest triangle corner.
    """
    points = np.asarray(points, dtype=np.float64)
    if not len(points):
        return np.zeros(0, dtype=np.int64), np.zeros((0, 3))
    unique, inverse = np.unique(points, axis=0, return_inverse=True)
    tri_low = np.minimum(np.minimum(a, b), c)
    tri_high = np.maximum(np.maximum(a, b), c)
    order = np.lexsort(np.floor(unique / 0.1).T)  # neighbours in the same batch
    best = np.empty(len(unique), dtype=np.int64)
    bary = np.empty((len(unique), 3))
    squares = (a ** 2).sum(1)
    for start in range(0, len(order), chunk):
        rows = order[start:start + chunk]
        p = unique[rows]
        # No closest point is farther than the nearest triangle corner.
        corner = (p ** 2).sum(1)[:, None] - 2.0 * p @ a.T + squares[None]
        bound = float(np.sqrt(max(corner.min(1).max(), 0.0))) + 1e-6
        candidates = np.flatnonzero(np.all((tri_low <= p.max(0) + bound) & (tri_high >= p.min(0) - bound), axis=1))
        ca, cb, cc = a[candidates], b[candidates], c[candidates]
        weights = _closest_on_triangles(p, ca, cb, cc)
        closest = weights[..., 0, None] * ca[None] + weights[..., 1, None] * cb[None] + weights[..., 2, None] * cc[None]
        nearest = ((closest - p[:, None]) ** 2).sum(-1).argmin(1)
        best[rows] = candidates[nearest]
        bary[rows] = weights[np.arange(len(p)), nearest]
    inverse = inverse.ravel()
    return best[inverse], bary[inverse]


def vertex_hidden_on_cage_surface(positions, cage_points, cage_faces, hidden_cage):
    """Hidden fraction at each point's closest point on the body-cage surface (0..1)."""
    a, b, c = (np.asarray(cage_points, dtype=np.float64)[cage_faces[:, k]] for k in range(3))
    flags = hidden_cage[cage_faces].astype(np.float64)
    best, bary = closest_on_surface(positions, a, b, c)
    return (bary * flags[best]).sum(-1)


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


# The skin against the cloth that is worn, vertex by vertex: metres behind the skin a ray starts looking for cloth
# and how far in front of it it looks, the gap left between skin that is kept and the cloth right over it, and the
# most a vertex is moved in to leave that gap.
CLOTH_INSIDE, CLOTH_REACH, CLOTH_CLEAR, CLOTH_PUSH = 0.02, 0.15, 0.004, 0.025
CLOTH_SUNK = 0.06   # metres into the body a garment may be sunk (a tight one on a wider body): there the mask stands


def _first_hit(origins: np.ndarray, directions: np.ndarray, triangles: np.ndarray, reach: float) -> np.ndarray:
    """Distance along each ray to the first triangle it meets within ``reach`` (inf when none). Moller-Trumbore.

    The rays are taken a few at a time, neighbours together, and each lot only against the triangles its rays can
    reach: a whole outfit is tens of thousands of triangles, and most are a limb away from any given ray."""
    out = np.full(len(origins), np.inf)
    if not len(triangles) or not len(origins):
        return out
    low, high = triangles.min(1), triangles.max(1)
    ends = origins + directions * reach
    cells = np.floor(origins / max(reach, 0.05)).astype(np.int64)
    order = np.lexsort((cells[:, 0], cells[:, 2], cells[:, 1]))          # neighbours in space, one after the other
    for start in range(0, len(order), 64):
        rows = order[start:start + 64]
        origin, direction = origins[rows], directions[rows]
        box_low = np.minimum(origin, ends[rows]).min(0)
        box_high = np.maximum(origin, ends[rows]).max(0)
        some = triangles[np.all((high >= box_low) & (low <= box_high), axis=1)]
        if not len(some):
            continue
        v0, e1, e2 = some[:, 0], some[:, 1] - some[:, 0], some[:, 2] - some[:, 0]
        p = np.cross(direction[:, None], e2[None])
        det = np.einsum("tk,rtk->rt", e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = origin[:, None] - v0[None]
        u = np.einsum("rtk,rtk->rt", s, p) * inv
        q = np.cross(s, e1[None])
        v = np.einsum("rk,rtk->rt", direction, q) * inv
        t = np.einsum("tk,rtk->rt", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= reach)
        out[rows] = np.where(hit, t, np.inf).min(axis=1)
    return out


def cloth_behind(points: np.ndarray, normals: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Which points have cloth behind them, inside the body (within CLOTH_SUNK along the normal, inwards): a
    garment sunk into a body wider than its own. Skin left there stands out of the cloth, so a mask that hides it
    is right, though nothing is in front of the skin."""
    points = np.asarray(points, dtype=np.float64)
    behind = np.zeros(len(points), dtype=bool)
    if not len(triangles) or not len(points):
        return behind
    corners = triangles.reshape(-1, 3)
    near = np.flatnonzero(np.all((points >= corners.min(0) - CLOTH_SUNK) & (points <= corners.max(0) + CLOTH_SUNK), axis=1))
    behind[near] = np.isfinite(_first_hit(points[near], -np.asarray(normals, dtype=np.float64)[near], triangles, CLOTH_SUNK))
    return behind


def cloth_distance(points: np.ndarray, normals: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """How far in front of each skin vertex the cloth is, along the vertex's normal: negative when the cloth is
    behind the skin's surface there (down to -CLOTH_INSIDE), inf when there is none within CLOTH_REACH."""
    points = np.asarray(points, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    out = np.full(len(points), np.inf)
    if not len(triangles) or not len(points):
        return out
    low, high = triangles.reshape(-1, 3).min(0) - CLOTH_REACH, triangles.reshape(-1, 3).max(0) + CLOTH_REACH
    near = np.flatnonzero(np.all((points >= low) & (points <= high), axis=1))   # only the skin about the clothes
    out[near] = _first_hit(points[near] - normals[near] * CLOTH_INSIDE, normals[near], triangles, CLOTH_REACH + CLOTH_INSIDE) - CLOTH_INSIDE
    return out


def clip_hidden(rows: np.ndarray, faces: np.ndarray, share: np.ndarray, threshold: float, covered: np.ndarray = None):
    """The skin cut along the mask's own line: (rows, faces) of what is kept.

    ``share``: how hidden each vertex is (0 to 1). A triangle wholly past ``threshold`` goes, one wholly short of it
    stays, and one the line crosses is cut along it (new vertices on its edges, every attribute interpolated).
    Dropping only the whole triangles left the ones the line crosses standing: a saw's teeth along every cut,
    which come through the cloth when the body moves.

    ``covered``: the vertices with cloth over them. A triangle the line crosses is only cut when the corners it
    loses are covered; otherwise it stays whole, as it always did: what is cut away is never what was showing.
    """
    rows = np.asarray(rows)
    faces = np.asarray(faces, dtype=np.int64)
    over = share > threshold
    count = over[faces].sum(1)
    mixed = (count == 1) | (count == 2)
    whole = np.zeros(len(faces), dtype=bool)
    if covered is not None:
        whole = mixed & (over & ~np.asarray(covered, dtype=bool))[faces].any(1)
    kept = [faces[(count == 0) | whole]]
    crossed = faces[mixed & ~whole]
    if not len(crossed):
        return rows, kept[0]
    added, index = [], {}

    def on_edge(a: int, b: int) -> int:
        """The vertex where the line crosses the edge from a (kept) to b (cut)."""
        key = (a, b)
        if key not in index:
            t = float((threshold - share[a]) / max(share[b] - share[a], 1e-9))
            row = rows[a] + (rows[b] - rows[a]) * min(max(t, 0.0), 1.0)
            if rows.shape[1] >= 6:  # the normal stays of unit length
                row[3:6] /= max(float(np.linalg.norm(row[3:6])), 1e-8)
            index[key] = len(rows) + len(added)
            added.append(row)
        return index[key]

    cut = []
    for face in crossed:
        inside = [int(i) for i in face if not over[i]]
        # Turned so that the kept corners come first, in the triangle's own order.
        k = next(k for k in range(3) if not over[face[k]] and (over[face[k - 1]] or len(inside) == 1))
        a, b, c = (int(face[(k + j) % 3]) for j in range(3))
        if len(inside) == 1:                 # a kept, b and c cut: the corner at a
            cut.append((a, on_edge(a, b), on_edge(a, c)))
        else:                                # a and b kept, c cut: the strip along ab
            bc, ac = on_edge(b, c), on_edge(a, c)
            cut += [(a, b, bc), (a, bc, ac)]
    kept.append(np.asarray(cut, dtype=np.int64).reshape(-1, 3))
    rows = np.vstack([rows, np.asarray(added, dtype=rows.dtype)]) if added else rows
    return rows, np.concatenate(kept)


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
