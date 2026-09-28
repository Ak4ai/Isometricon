"""Asset-specific Roblox WrapLayer cage transfer for the female static pose.

The clothing texture UVs are unrelated to these cage UVs. Cage UVs identify
corresponding points on a garment's reference, outer, and avatar outer cages.
"""
from __future__ import annotations

import gzip
import math
import os
from pathlib import Path
import struct

import numpy as np

from scripts.import_roblox_clothing import decode_roblox_mesh_to_obj, fetch_roblox_asset


def _roblox_float(data: bytes) -> float:
    raw = struct.unpack(">I", data)[0]
    return struct.unpack(">f", struct.pack(">I", ((raw & 1) << 31) | (raw >> 1)))[0]


def _rbxm_properties(data: bytes) -> dict[str, tuple[int, bytes]]:
    import lz4.block
    if not data.startswith(b"<roblox!"):
        raise ValueError("RBXM binário esperado")
    classes = {}
    properties = {}
    offset = 32
    while offset + 16 <= len(data):
        fourcc, compressed_size, decoded_size, _ = struct.unpack_from("<4sIII", data, offset)
        start = offset + 16
        end = start + compressed_size
        if end > len(data):
            raise ValueError("RBXM truncado")
        chunk = data[start:end]
        offset = end
        if compressed_size:
            chunk = lz4.block.decompress(chunk, uncompressed_size=decoded_size)
        if fourcc == b"INST":
            class_id, name_size = struct.unpack_from("<II", chunk)
            classes[class_id] = chunk[8:8 + name_size].decode("utf-8")
        elif fourcc == b"PROP":
            class_id, name_size = struct.unpack_from("<II", chunk)
            if classes.get(class_id) != "WrapLayer":
                continue
            name = chunk[8:8 + name_size].decode("utf-8")
            properties[name] = (chunk[8 + name_size], chunk[9 + name_size:])
        elif fourcc == b"END ":
            break
    return properties


def _property_payload(properties: dict, name: str, expected_type: int) -> bytes:
    if name not in properties:
        raise ValueError(f"WrapLayer sem propriedade {name}")
    type_id, payload = properties[name]
    if type_id != expected_type:
        raise ValueError(f"Tipo de {name} inesperado: {type_id}")
    return payload


def _property_id(properties: dict, name: str) -> str:
    payload = _property_payload(properties, name, 1)
    size = struct.unpack_from("<I", payload)[0]
    if size > 256 or len(payload) < 4 + size:
        raise ValueError(f"ID inválido em {name}")
    value = payload[4:4 + size].decode("ascii", errors="strict")
    if value.startswith("rbxassetid://"):
        asset_id = value[13:]
    elif "?id=" in value and value.startswith("https://assetdelivery.roblox.com/"):
        asset_id = value.rsplit("?id=", 1)[-1]
    else:
        raise ValueError(f"ID inválido em {name}: {value}")
    if not asset_id.isdigit():
        raise ValueError(f"ID inválido em {name}: {value}")
    return asset_id


def _property_cframe(properties: dict, name: str) -> tuple[np.ndarray, np.ndarray]:
    payload = _property_payload(properties, name, 0x10)
    rotation_type = payload[0]
    if rotation_type == 0:
        if len(payload) < 49:
            raise ValueError(f"CFrame incompleto em {name}")
        rotation = np.asarray(struct.unpack_from("<9f", payload, 1), dtype=np.float64).reshape(3, 3)
        origin = 37
    else:
        from .wear_engine import ROBLOX_ROTATION_TABLE, euler_yxz_to_matrix
        if rotation_type not in ROBLOX_ROTATION_TABLE or len(payload) < 13:
            raise ValueError(f"Rotação CFrame desconhecida em {name}: {rotation_type}")
        rotation = euler_yxz_to_matrix(*ROBLOX_ROTATION_TABLE[rotation_type])
        origin = 1
    position = np.asarray([_roblox_float(payload[origin + 4 * i:origin + 4 * i + 4])
                           for i in range(3)], dtype=np.float64)
    return rotation, position


def read_wrap_layer(rbxm_path: str | os.PathLike) -> dict:
    data = Path(rbxm_path).read_bytes()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    properties = _rbxm_properties(data)
    return {
        "reference_id": _property_id(properties, "ReferenceMeshId"),
        "cage_id": _property_id(properties, "CageMeshId"),
        "reference_origin": _property_cframe(properties, "ReferenceOrigin"),
        "cage_origin": _property_cframe(properties, "CageOrigin"),
        "bind_offset": _property_cframe(properties, "BindOffset") if "BindOffset" in properties else
                       (np.eye(3), np.zeros(3)),
    }


def cached_cage_obj(asset_id: str, cache_dir: str | os.PathLike) -> Path:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    obj = cache / f"{asset_id}.obj"
    if obj.exists() and obj.stat().st_size:
        return obj
    payload = cache / f"{asset_id}.mesh"
    if not payload.exists():
        data = fetch_roblox_asset(asset_id)
        if not data:
            raise FileNotFoundError(f"Não foi possível obter cage Roblox {asset_id}")
        payload.write_bytes(data)
    decode_roblox_mesh_to_obj(payload.read_bytes(), str(obj))
    return obj


def _nearest_uv_indices(queries: np.ndarray, keys: np.ndarray, tolerance=2e-4) -> np.ndarray:
    indices = []
    for chunk in np.array_split(np.asarray(queries, dtype=np.float64),
                                max(1, math.ceil(len(queries) / 128))):
        d2 = np.sum((chunk[:, None, :] - keys[None, :, :]) ** 2, axis=2)
        indices.append(d2.argmin(axis=1))
    indices = np.concatenate(indices)
    error = np.linalg.norm(queries - keys[indices], axis=1)
    if not np.isfinite(error).all() or error.max(initial=0) > tolerance:
        raise ValueError(f"UV de cage sem correspondência (erro máximo {error.max():.6f})")
    return indices


# Distinct body-cage UVs are at least 0.003 apart; catalog cages store the same UV
# with up to ~4e-4 of precision noise, so UVs closer than this are one point.
UV_TOLERANCE = 1e-3


def _root(parent, i):
    while parent[i] != i:
        i = parent[i]
    return i


def _cluster_uv(uvs: np.ndarray, tolerance: float = UV_TOLERANCE):
    """Merge UVs closer than `tolerance`: (key UVs, key index of each input UV)."""
    unique, inverse = np.unique(np.round(np.asarray(uvs, dtype=np.float64), 5), axis=0, return_inverse=True)
    parent = np.arange(len(unique))
    for start in range(0, len(unique), 256):
        chunk = unique[start:start + 256]
        close = np.sqrt(((chunk[:, None] - unique[None]) ** 2).sum(-1)) < tolerance
        for i, j in zip(*np.nonzero(close)):
            a, b = _root(parent, int(start + i)), _root(parent, int(j))
            if a != b:
                parent[max(a, b)] = min(a, b)
    roots = np.array([_root(parent, i) for i in range(len(unique))])
    _, cluster = np.unique(roots, return_inverse=True)
    cluster = cluster.ravel()
    keys = np.zeros((cluster.max() + 1, unique.shape[1]))
    np.add.at(keys, cluster, unique)
    keys /= np.bincount(cluster)[:, None]
    return keys, cluster[inverse.ravel()]


def _pair_by_connectivity(key_map, source_adjacency, target_adjacency, distance, free_target):
    """Pair each unpaired source key to the free target key adjacent to the images of its neighbours."""
    free_source = set(np.flatnonzero(key_map < 0).tolist())
    while free_source and free_target:
        best = None
        for r in free_source:
            images = {key_map[n] for n in source_adjacency[r] if key_map[n] >= 0}
            for o in free_target:
                score = len(images & target_adjacency[o])
                candidate = (score, -distance[r, o], r, o)
                if score and (best is None or candidate > best):
                    best = candidate
        if best is None:
            break
        _, _, r, o = best
        key_map[r] = o
        free_source.discard(r)
        free_target.discard(o)
    return key_map


def _uv_keys_and_adjacency(uvs: np.ndarray, faces: np.ndarray):
    keys, key_of_vertex = _cluster_uv(uvs)
    adjacency = [set() for _ in keys]
    for face in np.asarray(faces):
        a, b, c = key_of_vertex[face]
        adjacency[a].update((b, c))
        adjacency[b].update((a, c))
        adjacency[c].update((a, b))
    return keys, key_of_vertex, adjacency


MAX_UNPAIRED_OUTER = 0.35
# Cage points that touch only collapsed triangles (a costume reference cage can
# flatten whole parts) take their neighbours' displacement.
MAX_ORPHAN_UVS = 0.35


def _match_outer_to_reference(reference_uv: np.ndarray, reference_faces: np.ndarray,
                              outer_uv: np.ndarray, outer_faces: np.ndarray) -> np.ndarray:
    """Outer-cage vertex for each reference-cage vertex.

    Cages are paired by UV. Some catalog outer cages carry a few edited UVs
    (e.g. 16 of 1709), which makes nearest-UV pairing ambiguous. Those points
    are paired by connectivity instead: a reference point goes to the outer
    point whose neighbours are the images of its own already-paired neighbours.
    """
    try:
        return _nearest_uv_indices(reference_uv, outer_uv)
    except ValueError:
        pass
    ref_keys, ref_key_of, ref_adj = _uv_keys_and_adjacency(reference_uv, reference_faces)
    out_keys, out_key_of, out_adj = _uv_keys_and_adjacency(outer_uv, outer_faces)
    distance = np.sqrt(((ref_keys[:, None] - out_keys[None]) ** 2).sum(-1))
    nearest = distance.argmin(1)
    exact = distance[np.arange(len(ref_keys)), nearest] <= UV_TOLERANCE
    key_map = np.full(len(ref_keys), -1)
    key_map[exact] = nearest[exact]
    if len(np.unique(key_map[exact])) != int(exact.sum()):
        raise ValueError("UV de cage ambígua entre referência e cage externa")
    if (~exact).sum() > MAX_UNPAIRED_OUTER * len(ref_keys):
        raise ValueError(f"UV de cage sem correspondência ({int((~exact).sum())} pontos divergentes)")
    # Some outer cages drop points (a puffer without hands, a hood edge); those
    # reference points stay unpaired (-1) and take their neighbours' thickness.
    free_out = set(range(len(out_keys))) - set(key_map[exact].tolist())
    key_map = _pair_by_connectivity(key_map, ref_adj, out_adj, distance, free_out)
    first_vertex_of_key = np.full(len(out_keys), -1)
    for vertex, key in enumerate(out_key_of):
        if first_vertex_of_key[key] < 0:
            first_vertex_of_key[key] = vertex
    paired = key_map[ref_key_of]
    return np.where(paired >= 0, first_vertex_of_key[np.maximum(paired, 0)], -1)


def _match_reference_to_body_uv(reference_uv: np.ndarray, body_uv: np.ndarray,
                                reference_faces: np.ndarray | None = None,
                                body_adjacency: list | None = None) -> np.ndarray:
    """Body-cage UV index of each reference-cage vertex.

    UVs within UV_TOLERANCE are the same point; a UV edited by less than 0.01
    takes the nearest body UV unless another point claims it. UVs moved further
    by the asset author are paired by connectivity: the free body point adjacent
    to the images of the reference point's already-paired neighbours.
    """
    keys, key_of_vertex = _cluster_uv(reference_uv)
    distance = np.sqrt(((keys[:, None] - body_uv[None]) ** 2).sum(-1))
    nearest = distance.argmin(1)
    close = distance[np.arange(len(keys)), nearest] <= UV_TOLERANCE
    key_map = np.where(close, nearest, -1)
    # Small edits (under 0.01) take the nearest body UV when no other point claims it.
    edited = ~close & (distance[np.arange(len(keys)), nearest] <= 0.01)
    key_map[edited] = nearest[edited]
    close |= edited
    if len(np.unique(key_map[close])) != int(close.sum()):
        raise ValueError("UV de cage ambígua: múltiplos pontos mapeiam ao mesmo UV corporal")
    if not close.all():
        if reference_faces is None or body_adjacency is None or (~close).sum() > 0.02 * len(keys):
            raise ValueError(f"UV de cage incompatível com a referência corporal ({int((~close).sum())} pontos)")
        adjacency = [set() for _ in keys]
        for face in np.asarray(reference_faces):
            a, b, c = key_of_vertex[face]
            adjacency[a].update((b, c))
            adjacency[b].update((a, c))
            adjacency[c].update((a, b))
        free_body = set(range(len(body_uv))) - set(key_map[close].tolist())
        key_map = _pair_by_connectivity(key_map, adjacency, body_adjacency, distance, free_body)
        if (key_map < 0).any():
            raise ValueError(f"UV de cage sem correspondência no corpo ({int((key_map < 0).sum())} pontos)")
    return key_map[key_of_vertex]


def _body_uv_adjacency(cages: dict, body_uv: np.ndarray) -> list:
    """Neighbouring body-cage UV points, indexed like the `_unique_uv_positions` keys."""
    index = {}  # same keys and order as _unique_uv_positions
    for name, part in cages.items():
        if not name.endswith("Forearm"):
            for uv_face in part["face_uvs"]:
                for uv in uv_face:
                    index.setdefault(tuple(np.round(uv, 5)), len(index))
    adjacency = [set() for _ in body_uv]
    for name, part in cages.items():
        if name.endswith("Forearm"):
            continue
        for uv_face in part["face_uvs"]:
            ids = [index[tuple(np.round(uv, 5))] for uv in uv_face]
            for i in ids:
                adjacency[i].update(j for j in ids if j != i)
    return adjacency


def _unique_uv_positions(cages: dict) -> tuple[np.ndarray, np.ndarray]:
    positions = {}
    for name, part in cages.items():
        if name.endswith("Forearm"):
            continue  # Runtime helper that duplicates arm/hand cages.
        for face, uv_face in zip(part["faces"], part["face_uvs"]):
            for vertex_index, uv in zip(face, uv_face):
                key = tuple(np.round(uv, 5))
                position = np.asarray(part["verts"][vertex_index], dtype=np.float64)
                if key in positions and np.linalg.norm(position - positions[key]) > 2e-4:
                    raise ValueError(f"UV corporal ambígua em {name}: {key}")
                positions[key] = position
    return np.asarray(list(positions), dtype=np.float64), np.asarray(list(positions.values()))


def _basis(a: np.ndarray, b: np.ndarray, c: np.ndarray):
    e1 = b - a
    l1 = np.linalg.norm(e1)
    normal = np.cross(e1, c - a)
    area2 = np.linalg.norm(normal)
    if l1 < 1e-8 or area2 < 1e-9:
        return None
    e1 /= l1
    normal /= area2
    e2 = np.cross(normal, e1)
    l2 = np.dot(c - a, e2)
    if abs(l2) < 1e-8:
        return None
    return np.column_stack((e1, e2, normal)), np.array([l1, abs(l2)])


def _signed_surface_volume(vertices: np.ndarray, faces: np.ndarray) -> float:
    """Orientation score for two UV-corresponding cage surfaces."""
    triangles = np.asarray(vertices)[faces]
    return float(np.einsum("ij,ij->i", triangles[:, 0],
                           np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)


def _local_map(sa, sb, sc, ta, tb, tc, normal_sign=1):
    source = _basis(sa, sb, sc)
    target = _basis(ta, tb, tc)
    if source is None or target is None:
        return None
    s_basis, s_lengths = source
    t_basis, t_lengths = target
    ratios = np.clip(t_lengths / s_lengths, 0.08, 1.5)
    normal_ratio = math.sqrt(float(ratios[0] * ratios[1]))
    return t_basis @ np.diag([ratios[0], ratios[1], normal_sign * normal_ratio]) @ s_basis.T


def _closest_triangle(point, vertices, faces, lo, hi, closest_point):
    # Triangle AABB distance is a lower bound on exact point-to-triangle
    # distance. Expand the shortlist until it proves the chosen face is global.
    lower = np.linalg.norm(np.maximum(np.maximum(lo - point, point - hi), 0), axis=1)
    order = np.argsort(lower)
    best_distance = float("inf")
    best = None
    for t in order:
        if lower[t] > best_distance + 1e-10:
            break
        a, b, c = vertices[faces[t]]
        q, u, v, w = closest_point(point, a, b, c)
        distance = float(np.linalg.norm(point - q))
        if distance < best_distance:
            best_distance = distance
            best = (int(t), q, (u, v, w))
    return best_distance, best


def _cage_edge_stretch(source: np.ndarray, target: np.ndarray,
                       faces: np.ndarray, minimum_length=0.01) -> tuple[float, int]:
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    source_length = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    valid = source_length >= minimum_length
    if not np.any(valid):
        raise ValueError("Cage sem arestas mensuráveis")
    edges = edges[valid]
    source_length = source_length[valid]
    target_length = np.linalg.norm(target[edges[:, 0]] - target[edges[:, 1]], axis=1)
    ratios = target_length / source_length
    return float(np.quantile(ratios, .99)), int(np.count_nonzero(ratios > 3.0))


def retarget_garment_with_wrap_layer(engine, garment_vertices: np.ndarray, rbxm_path: str,
                                    cache_dir: str | os.PathLike,
                                    binding_audit: dict | None = None,
                                    *, _shell_transform=None, _mesh_transform=None,
                                    _shell_area_weighted=False,
                                    _use_authored_outer_faces=False,
                                    _shell_bulk_scale=False) -> tuple[np.ndarray, dict]:
    """Return static-pose garment vertices in engine XYZ using asset cages."""
    from .wear_engine import closest_point_on_triangle

    shell_transform = _shell_transform or _local_map
    mesh_transform = _mesh_transform or _local_map

    wrap = read_wrap_layer(rbxm_path)
    bind_rotation, bind_translation = wrap["bind_offset"]
    if (not np.allclose(bind_rotation, np.eye(3), atol=1e-5) or
            not np.allclose(bind_translation, 0, atol=1e-5)):
        raise ValueError("BindOffset do asset requer transferência de rig não suportada")
    reference_obj = cached_cage_obj(wrap["reference_id"], cache_dir)
    cage_obj = cached_cage_obj(wrap["cage_id"], cache_dir)
    reference, faces, reference_uv, _ = engine.load_obj(str(reference_obj))
    outer, outer_faces, outer_uv, _ = engine.load_obj(str(cage_obj))
    reference = np.asarray(reference, dtype=np.float64)
    outer = np.asarray(outer, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    # Cages are paired with the body by UV below, not by triangle count: some
    # catalog references (e.g. 2684 faces) drop a few triangles of the R15 layout.
    target_uv, target_positions = _unique_uv_positions(engine.r15_female_cages)
    uv_index = _match_reference_to_body_uv(reference_uv, target_uv, faces,
                                           _body_uv_adjacency(engine.r15_female_cages, target_uv))
    outer_index = _match_outer_to_reference(reference_uv, faces, outer_uv, outer_faces)
    outer_original = outer
    missing_outer = outer_index < 0
    outer = outer_original[np.maximum(outer_index, 0)]
    target = target_positions[uv_index]

    r_ref, p_ref = wrap["reference_origin"]
    r_cage, p_cage = wrap["cage_origin"]
    reference_parent = reference @ r_ref.T + p_ref
    outer_parent = outer @ r_cage.T + p_cage
    if missing_outer.any():
        # Reference points whose outer twin the author deleted take the garment
        # thickness of their cage neighbours.
        thickness = outer_parent - reference_parent
        neighbours = [set() for _ in reference_parent]
        for face in faces:
            for i in face:
                neighbours[i].update(int(j) for j in face if j != i)
        known = ~missing_outer
        pending = set(np.flatnonzero(missing_outer).tolist())
        while pending:
            ready = {i for i in pending if any(known[j] for j in neighbours[i])}
            if not ready:
                # A whole cage part is missing from the outer cage (e.g. a puffer's
                # hands): take the thickness of the closest known point.
                source = np.flatnonzero(known)
                for i in pending:
                    nearest = source[np.argmin(np.linalg.norm(reference_parent[source] - reference_parent[i], axis=1))]
                    thickness[i] = thickness[nearest]
                break
            for i in ready:
                thickness[i] = thickness[[j for j in neighbours[i] if known[j]]].mean(axis=0)
            for i in ready:
                known[i] = True
            pending -= ready
        outer_parent = reference_parent + thickness
        outer = (outer_parent - p_cage) @ r_cage
    delta = outer_parent - reference_parent
    if _shell_bulk_scale:
        source_box = np.ptp(reference_parent, axis=0)
        target_box = np.ptp(target, axis=0)
        if min(source_box.min(), target_box.min()) <= 1e-8:
            raise ValueError("Cannot measure bulk cage scale from a flat bounding box")
        shell_bulk_scale = float(np.cbrt(np.prod(target_box / source_box)))
    else:
        shell_bulk_scale = 1.0
    source_orientation = _signed_surface_volume(reference_parent, faces)
    target_orientation = _signed_surface_volume(target, faces)
    if abs(source_orientation) < 1e-8 or abs(target_orientation) < 1e-8:
        raise ValueError("Orientação global da cage ambígua")
    cage_normal_sign = -1 if source_orientation * target_orientation < 0 else 1

    # Each UV's garment shell displacement follows the corresponding local
    # triangle frame of the target cage, including rotations of the arms.
    uv_delta = np.zeros_like(target_positions)
    uv_counts = np.zeros(len(target_positions), dtype=np.float64)
    for face in faces:
        sa, sb, sc = reference_parent[face]
        ta, tb, tc = target[face]
        transform = shell_transform(sa, sb, sc, ta, tb, tc, normal_sign=cage_normal_sign)
        if transform is None:
            continue
        ids = uv_index[face]
        weight = float(np.linalg.norm(np.cross(sb - sa, sc - sa))) if _shell_area_weighted else 1.0
        np.add.at(uv_delta, ids, (delta[face] @ transform.T) * weight * shell_bulk_scale)
        np.add.at(uv_counts, ids, weight)
    used = np.unique(uv_index)
    orphans = used[uv_counts[used] == 0]
    if len(orphans) > MAX_ORPHAN_UVS * len(used):
        raise ValueError("Cage com UVs sem faces válidas")
    uv_delta[used[uv_counts[used] > 0]] /= uv_counts[used[uv_counts[used] > 0], None]
    if len(orphans):
        # A few cage points touch only collapsed (zero-area) triangles, so no local
        # frame exists there: take the displacement of their cage neighbours.
        neighbours = {int(i): set() for i in orphans}
        for face in uv_index[faces]:
            for i in face:
                if int(i) in neighbours:
                    neighbours[int(i)].update(int(j) for j in face if j != i)
        filled = set(used[uv_counts[used] > 0].tolist())
        pending = set(neighbours)
        while pending:
            ready = {i for i in pending if neighbours[i] & filled}
            if not ready:
                # Points in no triangle at all: use the closest filled cage point.
                known = np.fromiter(filled, dtype=np.int64)
                for i in pending:
                    nearest = known[np.argmin(np.linalg.norm(target_positions[known] - target_positions[i], axis=1))]
                    uv_delta[i] = uv_delta[nearest]
                break
            for i in ready:
                known = list(neighbours[i] & filled)
                uv_delta[i] = uv_delta[known].mean(axis=0)
            filled |= ready
            pending -= ready
    target_outer = target_positions[uv_index] + uv_delta[uv_index]
    outer_edge_p99, outer_edges_over_3x = _cage_edge_stretch(outer, target_outer, faces)

    if _use_authored_outer_faces:
        outer_to_reference = _nearest_uv_indices(outer_uv, reference_uv)
        binding_source = outer_original
        binding_target = target_outer[outer_to_reference]
        binding_faces = np.asarray(outer_faces, dtype=np.int32)
    else:
        binding_source = outer
        binding_target = target_outer
        binding_faces = faces

    # The visible MeshPart vertices are in parent-local coordinates. Express
    # them in the authored outer cage's coordinates before finding bindings.
    garment = np.asarray(garment_vertices, dtype=np.float64)
    garment_cage_space = (garment - p_cage) @ r_cage
    source_triangles = binding_source[binding_faces]
    target_triangles = binding_target[binding_faces]
    source_area2 = np.linalg.norm(np.cross(source_triangles[:, 1] - source_triangles[:, 0],
                                            source_triangles[:, 2] - source_triangles[:, 0]), axis=1)
    target_area2 = np.linalg.norm(np.cross(target_triangles[:, 1] - target_triangles[:, 0],
                                            target_triangles[:, 2] - target_triangles[:, 0]), axis=1)
    usable = (source_area2 > 1e-8) & (target_area2 > 1e-10)
    for f in np.flatnonzero(usable):
        # A sliver can pass the area test and still have no local frame.
        if mesh_transform(*source_triangles[f], *target_triangles[f], normal_sign=cage_normal_sign) is None:
            usable[f] = False
    projection_faces = binding_faces[usable]
    if not len(projection_faces):
        raise ValueError("Cage externa sem triângulos válidos")
    tri_lo = np.min(binding_source[projection_faces], axis=1)
    tri_hi = np.max(binding_source[projection_faces], axis=1)
    result = np.empty_like(garment_cage_space)
    distances = np.empty(len(garment_cage_space))
    invalid_faces = int((~usable).sum())
    if binding_audit is not None:
        binding_audit["face_indices"] = np.empty(len(garment_cage_space), dtype=np.int32)
        binding_audit["distances"] = distances
        binding_audit["source_vertices"] = garment_cage_space
        binding_audit["target_vertices"] = result
        binding_audit["projection_faces"] = projection_faces
        binding_audit["reference_uv"] = reference_uv
        binding_audit["uv_index"] = uv_index
        binding_audit["target_uv"] = target_uv
        binding_audit["source_outer"] = binding_source
        binding_audit["target_outer"] = binding_target
        binding_audit["reference_order_outer"] = outer
        binding_audit["reference_order_target_outer"] = target_outer
        binding_audit["reference_parent"] = reference_parent
        binding_audit["outer_parent"] = outer_parent
        binding_audit["target_body"] = target
        binding_audit["cage_normal_sign"] = cage_normal_sign
    for i, point in enumerate(garment_cage_space):
        distance, found = _closest_triangle(point, binding_source, projection_faces, tri_lo, tri_hi,
                                             closest_point_on_triangle)
        if found is None:
            raise ValueError("Cage externa sem triângulo próximo válido")
        face_index, q, weights = found
        if binding_audit is not None:
            binding_audit["face_indices"][i] = face_index
        face = projection_faces[face_index]
        source_triangle = binding_source[face]
        target_triangle = binding_target[face]
        # The same frame parity applies to both transfers. Otherwise a
        # reflected target reverses the mesh's signed distance to its cage,
        # even when the transferred outer cage itself is exact.
        transform = mesh_transform(*source_triangle, *target_triangle,
                                   normal_sign=cage_normal_sign)
        if transform is None:
            raise ValueError("Triângulo degenerado na cage externa")
        result[i] = np.asarray(weights) @ target_triangle + transform @ (point - q)
        distances[i] = distance
    if not np.isfinite(result).all():
        raise ValueError("Deformação produziu coordenadas não finitas")
    return result.astype(np.float32), {
        "cage_normal_sign": cage_normal_sign,
        "reference_id": wrap["reference_id"],
        "cage_id": wrap["cage_id"],
        "median_source_distance": float(np.median(distances)),
        "p99_source_distance": float(np.quantile(distances, .99)),
        "invalid_faces": invalid_faces,
        "outer_edge_stretch_p99": outer_edge_p99,
        "outer_edges_over_3x": outer_edges_over_3x,
    }
