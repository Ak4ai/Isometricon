"""Experimental UV-corresponded, multi-influence outer-cage transfer.

This is an offline candidate, not an implementation of Roblox's private
deformer. Cage connectivity bounds influences so nearby but unrelated body
regions (for example the two legs) cannot contaminate one another.
"""
from __future__ import annotations

import numpy as np


def _neighborhoods(faces: np.ndarray, count: int, rings: int) -> list[np.ndarray]:
    neighbors = [set((i,)) for i in range(count)]
    for a, b, c in np.asarray(faces, dtype=np.int32):
        neighbors[a].update((b, c))
        neighbors[b].update((a, c))
        neighbors[c].update((a, b))
    result = []
    for start in range(count):
        visited = {start}
        frontier = {start}
        for _ in range(rings):
            frontier = set().union(*(neighbors[index] for index in frontier)) - visited
            visited.update(frontier)
        result.append(np.fromiter(sorted(visited), dtype=np.int32))
    return result


def _rotation(source: np.ndarray, target: np.ndarray, parity: int) -> np.ndarray:
    """Best proper/improper orthogonal map between matched local directions."""
    covariance = source.T @ target
    u, _, vt = np.linalg.svd(covariance)
    correction = np.eye(3)
    correction[-1, -1] = parity * np.linalg.det(u @ vt)
    return u @ correction @ vt


def transfer_outer_cage(reference: np.ndarray, outer: np.ndarray,
                        target: np.ndarray, faces: np.ndarray,
                        *, rings: int = 2, parity: int = 1,
                        bulk_scale: float | None = None) -> np.ndarray:
    """Transport an authored shell using nearby UV-corresponded cage vertices.

    Each output vertex averages predictions from connected reference-cage
    vertices. A prediction transports the offset from an influence point to
    the *specific* outer-cage vertex, so an identity target reproduces the
    authored shell exactly even after blending. No clothing-type labels or
    geometric nearest-part classification are involved.
    """
    reference = np.asarray(reference, dtype=np.float64)
    outer = np.asarray(outer, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    if reference.shape != outer.shape or reference.shape != target.shape or reference.ndim != 2 or reference.shape[1] != 3:
        raise ValueError("Corresponding cage positions must have shape (N, 3)")
    if parity not in (-1, 1) or rings < 1:
        raise ValueError("Invalid parity or ring count")
    if not np.isfinite(reference).all() or not np.isfinite(outer).all() or not np.isfinite(target).all():
        raise ValueError("Cage positions must be finite")
    if bulk_scale is None:
        source_extent = np.ptp(reference, axis=0)
        target_extent = np.ptp(target, axis=0)
        valid = source_extent > 1e-8
        bulk_scale = float(np.median(target_extent[valid] / source_extent[valid])) if np.any(valid) else 1.0
    if not np.isfinite(bulk_scale) or bulk_scale <= 0:
        raise ValueError("Invalid bulk scale")

    adjacent = _neighborhoods(faces, len(reference), rings)
    rotations = np.empty((len(reference), 3, 3))
    for index, ids in enumerate(adjacent):
        source_vectors = reference[ids] - reference[index]
        target_vectors = target[ids] - target[index]
        rotations[index] = _rotation(source_vectors, target_vectors, parity)

    result = np.empty_like(outer)
    for index, ids in enumerate(adjacent):
        distances = np.linalg.norm(reference[ids] - reference[index], axis=1)
        positive = distances[distances > 1e-10]
        radius = float(np.median(positive)) if len(positive) else 1.0
        weights = np.exp(-0.5 * (distances / max(radius, 1e-8)) ** 2)
        weights /= weights.sum()
        offsets = outer[index] - reference[ids]
        predictions = target[ids] + bulk_scale * np.einsum("nij,nj->ni", rotations[ids].transpose(0, 2, 1), offsets)
        result[index] = weights @ predictions
    return result


def transfer_outer_cage_radial(reference: np.ndarray, outer: np.ndarray,
                               target: np.ndarray, faces: np.ndarray,
                               *, radius_factor: float = 2.0, parity: int = 1,
                               bulk_scale: float | None = None,
                               return_audit: bool = False):
    """Experimental source-outer radial influence transfer.

    For each inner-cage vertex, search the *authored outer cage* within a
    radius proportional to that vertex's garment thickness. This can couple
    nearby outer-cage seam points even when their inner-cage charts/parts are
    disconnected. Corresponding same-index vertices are always included.
    It is a documented-method approximation, not exact Roblox engine code.
    """
    reference = np.asarray(reference, dtype=np.float64)
    outer = np.asarray(outer, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    if (reference.shape != outer.shape or reference.shape != target.shape or
            reference.ndim != 2 or reference.shape[1] != 3):
        raise ValueError("Corresponding cage positions must have shape (N, 3)")
    if parity not in (-1, 1) or radius_factor <= 0 or not np.isfinite(radius_factor):
        raise ValueError("Invalid parity or radius factor")
    if not (np.isfinite(reference).all() and np.isfinite(outer).all() and
            np.isfinite(target).all()):
        raise ValueError("Cage positions must be finite")
    if bulk_scale is None:
        source_extent = np.ptp(reference, axis=0)
        target_extent = np.ptp(target, axis=0)
        valid = source_extent > 1e-8
        bulk_scale = float(np.median(target_extent[valid] / source_extent[valid])) if np.any(valid) else 1.0
    if not np.isfinite(bulk_scale) or bulk_scale <= 0:
        raise ValueError("Invalid bulk scale")

    neighborhoods = _neighborhoods(faces, len(reference), 1)
    rotations = np.empty((len(reference), 3, 3))
    for index, adjacent in enumerate(neighborhoods):
        rotations[index] = _rotation(reference[adjacent] - reference[index],
                                     target[adjacent] - target[index], parity)

    thickness = np.linalg.norm(outer - reference, axis=1)
    total = np.zeros_like(outer)
    weight_total = np.zeros(len(outer), dtype=np.float64)
    influence_count = np.zeros(len(outer), dtype=np.int32)
    cross_index_influences = 0
    for source_id, center in enumerate(reference):
        distance = np.linalg.norm(outer - center, axis=1)
        radius = max(radius_factor * thickness[source_id], 1e-8)
        selected = np.flatnonzero(distance <= radius)
        if source_id not in selected:
            selected = np.append(selected, source_id)
        # Normalize for each inner-cage source before accumulating at outer
        # vertices, as with a transposed influence list.
        proximity = 1.0 / np.maximum(distance[selected], 1e-6)
        weights = proximity / proximity.sum()
        offsets = outer[selected] - center
        predicted = target[source_id] + bulk_scale * (offsets @ rotations[source_id])
        np.add.at(total, selected, weights[:, None] * predicted)
        np.add.at(weight_total, selected, weights)
        np.add.at(influence_count, selected, 1)
        cross_index_influences += int(np.count_nonzero(selected != source_id))
    result = total / weight_total[:, None]
    if return_audit:
        return result, {
            "outer_vertices_with_multiple_influences": int(np.count_nonzero(influence_count > 1)),
            "outer_vertices_with_only_corresponding_influence": int(np.count_nonzero(influence_count == 1)),
            "cross_index_influences": cross_index_influences,
            "influence_count_p95": float(np.quantile(influence_count, .95)),
            "influence_count_max": int(influence_count.max()),
            "source_thickness_p95": float(np.quantile(thickness, .95)),
            "bulk_scale": bulk_scale,
            "radius_factor": radius_factor,
        }
    return result
