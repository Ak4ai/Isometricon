"""Prepare a matched, closed cage pair for volumetric garment binding.

This is preprocessing only. It does not edit the authored Roblox cage meshes.
Both cages receive exactly the same weld and temporary cap connectivity.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np


def _stitch_uv_boundary_edges(source: np.ndarray, target: np.ndarray,
                              faces: np.ndarray, uv: np.ndarray, decimals: int,
                              target_tolerance: float) -> np.ndarray:
    """Merge matching seam edges, never unrelated vertices touching in space."""
    if len(uv) != len(source):
        raise ValueError("Cada vértice da cage precisa de uma UV")
    _, vertex_ids = np.unique(np.round(uv, decimals), axis=0, return_inverse=True)
    n = int(vertex_ids.max()) + 1
    count = np.bincount(vertex_ids)
    positions = np.stack([np.bincount(vertex_ids, weights=source[:, axis]) / count
                          for axis in range(3)], axis=1)
    target_positions = np.stack([np.bincount(vertex_ids, weights=target[:, axis]) / count
                                 for axis in range(3)], axis=1)
    if np.linalg.norm(source - positions[vertex_ids], axis=1).max(initial=0) > 2e-4:
        raise ValueError("UV de cage possui posições geométricas ambíguas")
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def merge(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
            return True
        return False

    # Face-vertex duplicates from mesh decoding are already collapsed by UV.
    # Only paired boundary *edges* may stitch separate UV islands. A mere
    # coordinate collision is not enough to establish topological identity.
    for _ in range(4):
        ids = np.asarray([find(int(i)) for i in vertex_ids], dtype=np.int32)
        current_faces = ids[faces]
        directed = [(int(a), int(b)) for face in current_faces for a, b in
                    ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))]
        counts = Counter(tuple(sorted(edge)) for edge in directed)
        groups = defaultdict(list)
        for a, b in directed:
            if counts[tuple(sorted((a, b)))] != 1:
                continue
            pa, pb = tuple(np.round(positions[a], decimals)), tuple(np.round(positions[b], decimals))
            groups[tuple(sorted((pa, pb)))].append((a, b, pa, pb))
        changed = False
        for edges in groups.values():
            if len(edges) != 2:
                continue
            a, b, pa, pb = edges[0]
            c, d, pc, pd = edges[1]
            if (pa == pd and pb == pc and
                    np.linalg.norm(target_positions[a] - target_positions[d]) <= target_tolerance and
                    np.linalg.norm(target_positions[b] - target_positions[c]) <= target_tolerance):
                changed |= merge(a, d)
                changed |= merge(b, c)
        if not changed:
            break
    roots = np.asarray([find(int(i)) for i in vertex_ids], dtype=np.int32)
    _, inverse = np.unique(roots, return_inverse=True)
    return inverse


def _oriented_boundary_loops(faces: np.ndarray) -> list[list[int]]:
    directed = [(int(a), int(b)) for face in faces for a, b in
                ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))]
    counts = Counter(tuple(sorted(edge)) for edge in directed)
    if any(count > 2 for count in counts.values()):
        raise ValueError("Cage possui arestas não-manifold")
    boundary = [edge for edge in directed if counts[tuple(sorted(edge))] == 1]
    successor = {}
    incoming = Counter()
    for a, b in boundary:
        if a in successor:
            raise ValueError("Contorno de cage ramificado")
        successor[a] = b
        incoming[b] += 1
    if set(successor) != set(incoming) or any(count != 1 for count in incoming.values()):
        raise ValueError("Contorno de cage aberto ou mal orientado")
    remaining = set(successor)
    loops = []
    while remaining:
        start = next(iter(remaining))
        loop = []
        current = start
        while current in remaining:
            remaining.remove(current)
            loop.append(current)
            current = successor[current]
        if current != start or len(loop) < 3:
            raise ValueError("Contorno de cage não fecha em um loop simples")
        loops.append(loop)
    return loops


def _cross2(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _triangulate_min_area_3d(vertices: np.ndarray, loop: list[int]) -> list[tuple[int, int, int]]:
    """Bridge a narrow 3D slit whose projection doubles back on itself."""
    points = vertices[loop]
    n = len(loop)
    cost = np.full((n, n), np.inf)
    split = np.full((n, n), -1, dtype=np.int32)
    for i in range(n - 1):
        cost[i, i + 1] = 0
    for span in range(2, n):
        for i in range(n - span):
            j = i + span
            for k in range(i + 1, j):
                area = float(np.linalg.norm(np.cross(points[k] - points[i],
                                                     points[j] - points[i])) / 2)
                if area <= 1e-12:
                    continue
                candidate = cost[i, k] + cost[k, j] + area
                if candidate < cost[i, j]:
                    cost[i, j] = candidate
                    split[i, j] = k
    if not np.isfinite(cost[0, n - 1]):
        raise ValueError("Contorno de cage sem fechamento 3D não degenerado")
    triangles = []

    def build(i, j):
        if j <= i + 1:
            return
        k = int(split[i, j])
        triangles.append((loop[j], loop[k], loop[i]))
        build(i, k)
        build(k, j)

    build(0, n - 1)
    return triangles


def _triangulate_loop(vertices: np.ndarray, loop: list[int]) -> tuple[list[tuple[int, int, int]], float]:
    points = vertices[loop]
    centered = points - points.mean(axis=0)
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    flat = centered @ axes[:2].T
    plane_error = float(np.max(np.abs(centered @ axes[2])))
    signed_area = sum(_cross2(flat[i], flat[(i + 1) % len(loop)])
                      for i in range(len(loop)))
    if abs(signed_area) < 1e-10:
        raise ValueError("Contorno de cage com área projetada nula")
    orientation = 1 if signed_area > 0 else -1
    remaining = list(range(len(loop)))
    triangles = []
    while len(remaining) > 3:
        found = False
        for offset in range(len(remaining)):
            i = remaining[offset - 1]
            j = remaining[offset]
            k = remaining[(offset + 1) % len(remaining)]
            a, b, c = flat[[i, j, k]]
            area = orientation * _cross2(b - a, c - a)
            if area <= 1e-10:
                continue
            other = [index for index in remaining if index not in (i, j, k)]
            if any(all(orientation * value >= -1e-10 for value in
                       (_cross2(b - a, flat[h] - a),
                        _cross2(c - b, flat[h] - b),
                        _cross2(a - c, flat[h] - c))) for h in other):
                continue
            triangles.append((loop[k], loop[j], loop[i]))
            remaining.pop(offset)
            found = True
            break
        if not found:
            return _triangulate_min_area_3d(vertices, loop), plane_error
    i, j, k = remaining
    triangles.append((loop[k], loop[j], loop[i]))
    return triangles, plane_error


def close_cage_pair(source_vertices: np.ndarray, target_vertices: np.ndarray,
                    faces: np.ndarray, decimals=5,
                    source_uv: np.ndarray | None = None,
                    target_stitch_tolerance: float = 0.005) -> dict:
    """Weld source seams and add identical temporary caps to source/target."""
    source = np.asarray(source_vertices, dtype=np.float64)
    target = np.asarray(target_vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("Cages origem/alvo devem ter os mesmos vértices XYZ")
    if len(faces) == 0 or np.any(faces < 0) or np.any(faces >= len(source)):
        raise ValueError("Faces da cage inválidas")
    if source_uv is None:
        _, inverse = np.unique(np.round(source, decimals), axis=0, return_inverse=True)
    else:
        inverse = _stitch_uv_boundary_edges(source, target, faces, np.asarray(source_uv),
                                            decimals, target_stitch_tolerance)
    count = np.bincount(inverse)
    welded_source = np.stack([np.bincount(inverse, weights=source[:, axis]) / count
                              for axis in range(3)], axis=1)
    welded_target = np.stack([np.bincount(inverse, weights=target[:, axis]) / count
                              for axis in range(3)], axis=1)
    source_spread = np.linalg.norm(source - welded_source[inverse], axis=1)
    target_spread = np.linalg.norm(target - welded_target[inverse], axis=1)
    target_group_spread = np.zeros(len(welded_source))
    np.maximum.at(target_group_spread, inverse, target_spread)
    if source_spread.max(initial=0) > 2e-5:
        raise ValueError("Solda por coordenada uniu posições de origem distintas")
    welded_faces = inverse[faces]
    if np.any(np.diff(np.sort(welded_faces, axis=1), axis=1) == 0):
        raise ValueError("Solda criou faces degeneradas")
    loops = _oriented_boundary_loops(welded_faces)
    caps = []
    planarity = []
    for loop in loops:
        triangles, error = _triangulate_loop(welded_source, loop)
        caps.extend(triangles)
        planarity.append(error)
    closed_faces = np.vstack((welded_faces, np.asarray(caps, dtype=np.int32))) if caps else welded_faces
    if _oriented_boundary_loops(closed_faces):
        raise ValueError("Cage ainda possui bordas após fechamento")
    edges = Counter(tuple(sorted((int(a), int(b)))) for face in closed_faces
                    for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])))
    if any(count != 2 for count in edges.values()):
        raise ValueError("Cage fechada não é manifold")
    source_tri = welded_source[closed_faces]
    target_tri = welded_target[closed_faces]
    source_volume = float(np.einsum("ij,ij->i", source_tri[:, 0],
                                   np.cross(source_tri[:, 1], source_tri[:, 2])).sum() / 6)
    target_volume = float(np.einsum("ij,ij->i", target_tri[:, 0],
                                   np.cross(target_tri[:, 1], target_tri[:, 2])).sum() / 6)
    if abs(source_volume) < 1e-8 or abs(target_volume) < 1e-8:
        raise ValueError("Cage fechada com volume nulo")
    return {
        "source_vertices": welded_source,
        "target_vertices": welded_target,
        "faces": closed_faces,
        "source_vertex_to_welded": inverse,
        "loop_lengths": [len(loop) for loop in loops],
        "cap_face_count": len(caps),
        "cap_plane_error_max": max(planarity, default=0.0),
        "source_seam_spread_max": float(source_spread.max(initial=0)),
        "target_seam_spread_max": float(target_spread.max(initial=0)),
        "target_seam_groups_over_2cm": int(np.count_nonzero(target_group_spread > .02)),
        "largest_target_seams": [
            {"source_center": welded_source[index].round(4).tolist(),
             "spread": round(float(target_group_spread[index]), 5)}
            for index in np.argsort(target_group_spread)[-5:][::-1]
        ],
        "source_signed_volume": source_volume,
        "target_signed_volume": target_volume,
    }
