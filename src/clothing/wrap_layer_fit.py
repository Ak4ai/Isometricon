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


def _uv_keys_and_adjacency(uvs: np.ndarray, faces: np.ndarray):
    keys, key_of_vertex = np.unique(np.round(uvs, 5), axis=0, return_inverse=True)
    key_of_vertex = key_of_vertex.ravel()
    adjacency = [set() for _ in keys]
    for face in np.asarray(faces):
        a, b, c = key_of_vertex[face]
        adjacency[a].update((b, c))
        adjacency[b].update((a, c))
        adjacency[c].update((a, b))
    return keys, key_of_vertex, adjacency


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
    exact = distance[np.arange(len(ref_keys)), nearest] <= 2e-4
    key_map = np.full(len(ref_keys), -1)
    key_map[exact] = nearest[exact]
    if len(np.unique(key_map[exact])) != int(exact.sum()):
        raise ValueError("UV de cage ambígua entre referência e cage externa")
    free_ref = set(np.flatnonzero(~exact).tolist())
    free_out = set(range(len(out_keys))) - set(key_map[exact].tolist())
    if len(free_ref) > 0.02 * len(ref_keys):
        raise ValueError(f"UV de cage sem correspondência ({len(free_ref)} pontos divergentes)")
    # Some outer cages also drop a few points; those reference points stay unpaired (-1).
    while free_ref and free_out:
        best = None
        for r in free_ref:
            images = {key_map[n] for n in ref_adj[r] if key_map[n] >= 0}
            for o in free_out:
                score = len(images & out_adj[o])
                candidate = (score, -distance[r, o], r, o)
                if score and (best is None or candidate > best):
                    best = candidate
        if best is None:
            break  # the rest stay unpaired and take their neighbours' thickness
        _, _, r, o = best
        key_map[r] = o
        free_ref.discard(r)
        free_out.discard(o)
    first_vertex_of_key = np.full(len(out_keys), -1)
    for vertex, key in enumerate(out_key_of):
        if first_vertex_of_key[key] < 0:
            first_vertex_of_key[key] = vertex
    paired = key_map[ref_key_of]
    return np.where(paired >= 0, first_vertex_of_key[np.maximum(paired, 0)], -1)


def _match_reference_to_body_uv(reference_uv: np.ndarray, body_uv: np.ndarray) -> np.ndarray:
    """Allow a few independently identifiable UV edits in a catalog cage.

    Most assets match within 2e-4. A small number of shifted UVs is safe to
    match by nearest UV only when every unique source UV retains a distinct
    target and the total deviation remains bounded.
    """
    unique, inverse = np.unique(np.round(reference_uv, 5), axis=0, return_inverse=True)
    mapped = _nearest_uv_indices(unique, body_uv, tolerance=.01)
    if len(np.unique(mapped)) != len(unique):
        raise ValueError("UV de cage ambígua: múltiplos pontos mapeiam ao mesmo UV corporal")
    error = np.linalg.norm(unique - body_uv[mapped], axis=1)
    if np.count_nonzero(error > 2e-4) > 8:
        raise ValueError("UV de cage incompatível com a referência corporal")
    return mapped[inverse]


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
    uv_index = _match_reference_to_body_uv(reference_uv, target_uv)
    outer_index = _match_outer_to_reference(reference_uv, faces, outer_uv, outer_faces)
    if len(np.unique(uv_index)) != len(np.unique(np.round(reference_uv, 5), axis=0)):
        raise ValueError("Cage de referência possui UVs corporais ambíguos")
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
                raise ValueError("UV de cage sem correspondência")
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
    if len(orphans) > 0.05 * len(used):
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
