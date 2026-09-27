"""Radial outer cage + dual-cage prism binding for WrapLayer garments.

Validated against Roblox Studio exports of the same garments on the official
Blocky body (scripts/batch_compare_roblox.py): it matches Roblox within ~1-2 cm
median on tight and loose garments and is closer than the per-triangle runtime
fit on every tested garment except one jacket.

Pipeline, starting from the trace of ``retarget_garment_with_wrap_layer``:
1. The garment's authored outer cage is carried to the target body with
   thickness-radius influences (``transfer_outer_cage_radial``).
2. Each visible vertex is located inside the prism between a garment inner-cage
   triangle and its outer-cage twin (barycentric position + layer depth t), and
   re-evaluated in the target prism. A residual outside the prism follows the
   prism's local frame.
3. Parts hanging well outside every prism (bows, strings) keep the position of
   the point where they attach but their authored direction (one global map),
   instead of being swung by the local frame of the hem they hang from.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .multi_influence_shell import transfer_outer_cage_radial
from .wear_engine import closest_point_on_triangle
from .wrap_layer_fit import _local_map

# Residual (garment point to its prism) beyond which a vertex counts as hanging.
# Asset units are studs; 1 stud = 28 cm at Roblox avatar scale, so this is 3 cm.
HANGING_RESIDUAL = 3.0 / 28.0


def closest_prism_binding(point, inner, outer, faces, lower, upper):
    """Closest point of ``point`` in the paired inner/outer triangle prisms."""
    lower_bound = np.linalg.norm(np.maximum(np.maximum(lower - point, point - upper), 0), axis=1)
    best_distance = float("inf")
    best = None
    for face_id in np.argsort(lower_bound):
        if lower_bound[face_id] > best_distance + 1e-10:
            break
        inner_face = inner[faces[face_id]]
        outer_face = outer[faces[face_id]]
        # Alternate exact triangle projection and closed-form layer depth;
        # several starts avoid freezing on a degenerate inner triangle.
        for start in (0.0, 0.5, 1.0):
            t = start
            for _ in range(4):
                section = (1 - t) * inner_face + t * outer_face
                _, u, v, w = closest_point_on_triangle(point, *section)
                bary = np.asarray((u, v, w))
                direction = bary @ (outer_face - inner_face)
                denom = float(np.dot(direction, direction))
                if denom > 1e-16:
                    t = float(np.clip(np.dot(point - bary @ inner_face, direction) / denom, 0, 1))
            section = (1 - t) * inner_face + t * outer_face
            q, u, v, w = closest_point_on_triangle(point, *section)
            distance = float(np.linalg.norm(point - q))
            if distance < best_distance:
                best_distance = distance
                best = (int(face_id), t, np.asarray((u, v, w)), point - q)
    return best_distance, best


def _global_map(reference, target):
    """Least-squares linear map (row vectors) from the reference cage to the body cage."""
    matrix, *_ = np.linalg.lstsq(reference - reference.mean(0), target - target.mean(0), rcond=None)
    return matrix


def _anchors(bound, faces):
    """For every vertex, the nearest (along garment edges) vertex that is bound; -1 if none."""
    neighbors = [[] for _ in bound]
    for a, b, c in faces:
        for i, j in ((a, b), (b, c), (c, a)):
            neighbors[i].append(j)
            neighbors[j].append(i)
    anchor = np.where(bound, np.arange(len(bound)), -1)
    queue = deque(np.flatnonzero(bound))
    while queue:
        i = queue.popleft()
        for j in neighbors[i]:
            if anchor[j] < 0:
                anchor[j] = anchor[i]
                queue.append(j)
    return anchor


def fit_radial_prism(garment: np.ndarray, faces: np.ndarray, trace: dict) -> tuple[np.ndarray, dict]:
    """Garment vertices on the target body. ``trace`` is a WrapLayer binding audit."""
    inner = np.asarray(trace["reference_parent"], dtype=np.float64)
    outer = np.asarray(trace["outer_parent"], dtype=np.float64)
    target_inner = np.asarray(trace["target_body"], dtype=np.float64)
    cage_faces = np.asarray(trace["projection_faces"], dtype=np.int32)
    parity = int(trace["cage_normal_sign"])
    target_outer = transfer_outer_cage_radial(inner, outer, target_inner, cage_faces,
                                              parity=parity, radius_factor=1.0)

    area = lambda v: np.linalg.norm(np.cross(v[cage_faces[:, 1]] - v[cage_faces[:, 0]],
                                             v[cage_faces[:, 2]] - v[cage_faces[:, 0]]), axis=1)
    prisms = cage_faces[(area(inner) > 1e-8) & (area(outer) > 1e-8)]
    six = np.concatenate((inner[prisms], outer[prisms]), axis=1)
    lower, upper = six.min(axis=1), six.max(axis=1)

    points = np.asarray(garment, dtype=np.float64)
    result = np.empty_like(points)
    residual_length = np.empty(len(points))
    for index, point in enumerate(points):
        _, found = closest_prism_binding(point, inner, outer, prisms, lower, upper)
        if found is None:
            raise ValueError("Nenhum prisma de cage para um vértice da roupa")
        face_id, t, bary, residual = found
        face = prisms[face_id]
        source_section = (1 - t) * inner[face] + t * outer[face]
        target_section = (1 - t) * target_inner[face] + t * target_outer[face]
        transform = None
        for source, target in ((source_section, target_section), (inner[face], target_inner[face]),
                               (outer[face], target_outer[face])):
            transform = _local_map(*source, *target, normal_sign=parity)
            if transform is not None:
                break
        if transform is None:
            raise ValueError("Prisma de cage sem referencial utilizável")
        result[index] = bary @ target_section + transform @ residual
        residual_length[index] = np.linalg.norm(residual)

    hanging = residual_length > HANGING_RESIDUAL
    if hanging.any():
        anchor = _anchors(~hanging, np.asarray(faces))
        global_map = _global_map(inner, target_inner)
        for i in np.flatnonzero(hanging & (anchor >= 0)):
            a = anchor[i]
            result[i] = result[a] + (points[i] - points[a]) @ global_map
    return result, {"hanging_vertices": int(hanging.sum()),
                    "residual_p99": float(np.quantile(residual_length, .99))}
