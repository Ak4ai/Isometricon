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


# A connected piece of a garment with at least this share of its vertices on one limb is all on it.
LIMB_PIECE = 0.6
LIMB_PARTS = {"left arm": ("LeftUpperArm", "LeftLowerArm", "LeftHand"), "right arm": ("RightUpperArm", "RightLowerArm", "RightHand"),
              "left leg": ("LeftUpperLeg", "LeftLowerLeg", "LeftFoot"), "right leg": ("RightUpperLeg", "RightLowerLeg", "RightFoot")}


def _keep_limb_pieces_on_their_limb(points, faces, bindings, inner, outer, prisms, lower, upper, point_parts):
    """Rebind (in place) the strays of the garment pieces that belong to one limb; returns how many.

    A vertex binds to the nearest cage prism, whatever body part that is. The inner side of
    a sleeve sewn apart from the body of a coat can be nearest to the torso or to the thigh
    the hand hangs beside: bound there, it stays behind when the arm is fitted elsewhere and
    the sleeve is drawn into long triangles. A connected piece with most of its vertices on
    one limb is that limb's: its other vertices bind to the nearest prism of that limb.
    """
    if point_parts is None or not len(faces):
        return 0
    point_parts = np.asarray(point_parts).astype(str)
    prism_parts = point_parts[prisms]
    prism_part = np.where(prism_parts[:, 1] == prism_parts[:, 2], prism_parts[:, 1], prism_parts[:, 0])
    bound_part = prism_part[[found[0] for found in bindings]]
    keys = {}
    weld = np.array([keys.setdefault(tuple(p), len(keys)) for p in np.round(points, 5).tolist()])
    parent = list(range(len(keys)))

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for a, b, c in weld[faces].tolist():
        parent[find(a)] = find(b)
        parent[find(b)] = find(c)
    piece = np.array([find(v) for v in weld])
    count = 0

    def rebind(indices, allowed):
        nonlocal count
        allowed = np.flatnonzero(allowed)
        for index in indices:
            _, found = closest_prism_binding(points[index], inner, outer, prisms[allowed], lower[allowed], upper[allowed])
            if found is not None:
                bindings[index] = (int(allowed[found[0]]),) + found[1:]
                bound_part[index] = prism_part[allowed[found[0]]]
                count += 1

    on_a_limb = np.zeros(len(points), dtype=bool)
    for root in np.unique(piece):
        inside = piece == root
        for parts in LIMB_PARTS.values():
            own = np.isin(bound_part, parts)
            if (inside & own).sum() >= LIMB_PIECE * inside.sum():
                rebind(np.flatnonzero(inside & ~own), np.isin(prism_part, parts))
                on_a_limb |= inside

    # In the rest of the garment, cloth bound to an arm must reach the torso up that arm
    # through cloth bound to it (hand, forearm, upper arm, torso: a sleeve). The side of a
    # coat that was merely nearest to the forearm of the reference pose is not a sleeve: it
    # would follow the arm to where our body holds it and stick out as a fin.
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    arm_parts = [part for name, parts in LIMB_PARTS.items() if "arm" in name for part in parts]
    above = {part: parts[k - 1] if k else "UpperTorso" for name, parts in LIMB_PARTS.items() if "arm" in name
             for k, part in enumerate(parts)}
    for _ in range(3):  # hand, forearm, upper arm
        same = bound_part[edges[:, 0]] == bound_part[edges[:, 1]]
        region_parent = list(range(len(points)))

        def region_of(v):
            while region_parent[v] != v:
                region_parent[v] = region_parent[region_parent[v]]
                v = region_parent[v]
            return v

        for a, b in np.concatenate((edges[same], np.column_stack((np.arange(len(points)), np.arange(len(points)))))).tolist():
            region_parent[region_of(a)] = region_of(b)
        # Vertices repeated at the same place (texture seams) are one vertex of the garment.
        first = {}
        for index, key in enumerate(weld.tolist()):
            if key in first and bound_part[first[key]] == bound_part[index]:
                region_parent[region_of(index)] = region_of(first[key])
            first.setdefault(key, index)
        region = np.array([region_of(v) for v in range(len(points))])
        borders = {}
        welded_part = {}
        for index, key in enumerate(weld.tolist()):
            welded_part.setdefault(key, set()).add(bound_part[index])
        for a, b in edges[~same].tolist():
            borders.setdefault(region[a], set()).add(bound_part[b])
            borders.setdefault(region[b], set()).add(bound_part[a])
        for index, key in enumerate(weld.tolist()):
            borders.setdefault(region[index], set()).update(welded_part[key] - {bound_part[index]})
        stray = np.array([bound_part[v] in above and not on_a_limb[v] and above[bound_part[v]] not in borders.get(region[v], ())
                          for v in range(len(points))])
        if not stray.any():
            break
        rebind(np.flatnonzero(stray), ~np.isin(prism_part, arm_parts))
    return count


def _global_map(reference, target):
    """Least-squares linear map (row vectors) from the reference cage to the body cage."""
    matrix, *_ = np.linalg.lstsq(reference - reference.mean(0), target - target.mean(0), rcond=None)
    return matrix


def _anchors(bound, faces, points):
    """For every vertex, the bound vertex it hangs from.

    Along garment edges, the nearest bound vertex. A separate mesh piece with no
    bound vertex at all (a loose bow or string) hangs as a whole from the bound
    vertex closest to it in space.
    """
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
    bound_ids = np.flatnonzero(bound)
    if not len(bound_ids):
        return anchor
    for start in np.flatnonzero(anchor < 0):
        if anchor[start] >= 0:
            continue
        piece, stack = [start], [start]
        anchor[start] = -2  # visited marker while collecting the piece
        while stack:
            for j in neighbors[stack.pop()]:
                if anchor[j] == -1:
                    anchor[j] = -2
                    piece.append(j)
                    stack.append(j)
        distance = ((points[piece][:, None] - points[bound_ids][None]) ** 2).sum(-1)
        anchor[piece] = bound_ids[np.unravel_index(distance.argmin(), distance.shape)[1]]
    return anchor


def _harmonic_fill(values, faces, free, bound, iterations=400):
    """Relax ``values`` of the free vertices towards the mean of their garment neighbours.

    Vertices neither free nor bound keep their value. A free piece that touches
    no bound vertex (a loose bow) only averages within itself, so it moves rigidly.
    """
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    touches = free[edges[:, 0]] | free[edges[:, 1]]
    edges = edges[touches & ((free | bound)[edges[:, 0]]) & ((free | bound)[edges[:, 1]])]
    degree = np.zeros(len(values))
    np.add.at(degree, edges[:, 0], 1)
    np.add.at(degree, edges[:, 1], 1)
    update = free & (degree > 0)
    values = values.copy()
    for _ in range(iterations):
        total = np.zeros_like(values)
        np.add.at(total, edges[:, 0], values[edges[:, 1]])
        np.add.at(total, edges[:, 1], values[edges[:, 0]])
        values[update] = total[update] / degree[update, None]
    return values


def fit_radial_prism(garment: np.ndarray, faces: np.ndarray, trace: dict) -> tuple[np.ndarray, dict]:
    """Garment vertices on the target body. ``trace`` is a WrapLayer binding audit."""
    inner = np.asarray(trace["reference_parent"], dtype=np.float64)
    outer = np.asarray(trace["outer_parent"], dtype=np.float64)
    target_inner = np.asarray(trace["target_body"], dtype=np.float64)
    cage_faces = np.asarray(trace["projection_faces"], dtype=np.int32)
    parity = int(trace["cage_normal_sign"])
    target_outer = transfer_outer_cage_radial(inner, outer, target_inner, cage_faces,
                                              parity=parity, radius_factor=1.0)
    trace["target_outer"] = target_outer  # the next layer is fitted over it

    area = lambda v: np.linalg.norm(np.cross(v[cage_faces[:, 1]] - v[cage_faces[:, 0]],
                                             v[cage_faces[:, 2]] - v[cage_faces[:, 0]]), axis=1)
    prisms = cage_faces[(area(inner) > 1e-8) & (area(outer) > 1e-8)]
    six = np.concatenate((inner[prisms], outer[prisms]), axis=1)
    lower, upper = six.min(axis=1), six.max(axis=1)

    points = np.asarray(garment, dtype=np.float64)
    result = np.empty_like(points)
    residual_length = np.empty(len(points))
    bindings = []
    for point in points:
        _, found = closest_prism_binding(point, inner, outer, prisms, lower, upper)
        if found is None:
            raise ValueError("Nenhum prisma de cage para um vértice da roupa")
        bindings.append(found)
    rebound = _keep_limb_pieces_on_their_limb(points, np.asarray(faces), bindings, inner, outer, prisms, lower, upper,
                                              trace.get("cage_point_parts"))
    for index, found in enumerate(bindings):
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
        faces = np.asarray(faces)
        anchor = _anchors(~hanging, faces, points)
        global_map = _global_map(inner, target_inner)
        # A hanging vertex keeps its authored shape (global map) plus an offset.
        # The offset is interpolated harmonically from the bound vertices along the
        # garment, so neighbours hanging from different anchors do not tear apart.
        offset = result - points @ global_map
        movable = np.flatnonzero(hanging & (anchor >= 0))
        offset[movable] = offset[anchor[movable]]
        offset = _harmonic_fill(offset, faces, hanging & (anchor >= 0), ~hanging)
        result[movable] = points[movable] @ global_map + offset[movable]
    return result, {"hanging_vertices": int(hanging.sum()), "rebound_to_limb": rebound,
                    "residual_p99": float(np.quantile(residual_length, .99))}
