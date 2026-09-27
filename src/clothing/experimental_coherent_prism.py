"""Offline graph-coherent reassignment of existing radial dual-cage prism bindings.

Only source prism faces already selected by a garment vertex or one of its
garment-edge neighbours are considered. UV-split copies with aligned source
normals are optimized as one vertex group; opposing panels remain separate.
No clothing labels, body-part rules, or production code paths are involved.
"""
from collections import defaultdict

import numpy as np

from scripts.audit_binding_charts import face_charts
from scripts.experiment_dual_cage_prism import closest_prism_binding
from src.clothing.experimental_canonical_radial import canonical_cages, normal_frames
from src.clothing.wrap_layer_fit import _local_map


def _groups(vertices, faces):
    n = len(vertices)
    tri = np.asarray(vertices, float)[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-15)
    vertex_normals = np.zeros((n, 3))
    np.add.at(vertex_normals, faces.ravel(), np.repeat(normals, 3, axis=0))
    vertex_normals /= np.maximum(np.linalg.norm(vertex_normals, axis=1)[:, None], 1e-15)
    parent = np.arange(n)

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    buckets = defaultdict(list)
    for index, point in enumerate(vertices):
        buckets[tuple(np.round(point, 5))].append(index)
    for ids in buckets.values():
        for offset, a in enumerate(ids):
            for b in ids[offset + 1:]:
                if np.dot(vertex_normals[a], vertex_normals[b]) > .7:
                    parent[root(b)] = root(a)
    _, inverse = np.unique([root(i) for i in range(n)], return_inverse=True)
    members = [np.flatnonzero(inverse == group) for group in range(inverse.max() + 1)]
    return inverse, members


def _evaluate_face(point, face_id, inner, outer, target_inner, target_outer, faces, parity):
    face = faces[face_id]
    six = np.vstack((inner[face], outer[face]))
    _, found = closest_prism_binding(point, inner, outer, faces[face_id:face_id + 1],
                                    six.min(axis=0)[None], six.max(axis=0)[None])
    if found is None:
        return None
    _, depth, bary, residual = found
    source_section = (1 - depth) * inner[face] + depth * outer[face]
    target_section = (1 - depth) * target_inner[face] + depth * target_outer[face]
    transform = _local_map(*source_section, *target_section, normal_sign=parity)
    if transform is None:
        transform = _local_map(*inner[face], *target_inner[face], normal_sign=parity)
    if transform is None:
        transform = _local_map(*outer[face], *target_outer[face], normal_sign=parity)
    if transform is None:
        return None
    return np.asarray(bary) @ target_section + transform @ residual, float(np.linalg.norm(residual))


def coherent_prism_binding(data, binding, target_outer, baseline, scale, *, rounds=4):
    """Change prism support, leaving cage geometry and source garment fixed."""
    garment = np.asarray(data["garment"], float)
    garment_faces = np.asarray(data["garment_faces"], int)
    cage_faces = np.asarray(binding["faces"], int)
    selected = np.asarray(binding["face_ids"], int)
    source = np.asarray(baseline, float)
    inner = np.asarray(data["reference_parent"], float)
    outer = np.asarray(data["outer_parent"], float)
    target_inner = np.asarray(data["target_body"], float)
    target_outer = np.asarray(target_outer, float)
    parity = int(data["cage_normal_sign"])
    if source.shape != garment.shape or len(selected) != len(garment):
        raise ValueError("Garment, binding and baseline vertex counts differ")
    if not np.array_equal(cage_faces, data["projection_faces"]):
        raise ValueError("Prism face list differs from cage trace")

    vertex_group, members = _groups(garment, garment_faces)
    group_source = np.asarray([garment[ids].mean(axis=0) for ids in members])
    current = np.asarray([source[ids].mean(axis=0) for ids in members])
    original_current = current.copy()
    charts = face_charts(cage_faces, data["uv_index"])
    edges = np.unique(np.sort(np.concatenate([
        garment_faces[:, [0, 1]], garment_faces[:, [1, 2]], garment_faces[:, [2, 0]]
    ]), axis=1), axis=0)
    group_edges = np.unique(np.sort(vertex_group[edges], axis=1), axis=0)
    group_edges = group_edges[group_edges[:, 0] != group_edges[:, 1]]
    face_groups = vertex_group[garment_faces]
    baseline_triangles = source[garment_faces]
    baseline_normals = np.cross(baseline_triangles[:, 1] - baseline_triangles[:, 0],
                                baseline_triangles[:, 2] - baseline_triangles[:, 0])
    valid_baseline_faces = np.linalg.norm(baseline_normals, axis=1) > 1e-10
    reference_canon, _, target_canon, canonical_faces, inverse = canonical_cages(
        inner, outer, target_inner, data["projection_faces"], data["uv_index"])
    frames, _ = normal_frames(reference_canon, target_canon, canonical_faces, parity)
    vertex_frames = frames[inverse][cage_faces[selected]].mean(axis=1)
    source_triangles = garment[garment_faces]
    source_normals = np.cross(source_triangles[:, 1] - source_triangles[:, 0],
                              source_triangles[:, 2] - source_triangles[:, 0])
    expected_normals = parity * np.einsum(
        "ni,nij->nj", source_normals, vertex_frames[garment_faces].mean(axis=1))
    incident = [[] for _ in members]
    for face_id, ids in enumerate(face_groups):
        for group in set(ids):
            incident[int(group)].append(face_id)
    source_lengths = np.linalg.norm(group_source[group_edges[:, 0]] - group_source[group_edges[:, 1]], axis=1)
    positive = source_lengths[source_lengths > 1e-7]
    if not len(positive):
        raise ValueError("Garment has no nonzero edges")
    length_floor = .1 * float(np.median(positive)) * scale
    neighbours = [dict() for _ in members]
    for (a, b), length in zip(group_edges, source_lengths):
        if length < 1e-7:
            continue
        neighbours[int(a)][int(b)] = float(length)
        neighbours[int(b)][int(a)] = float(length)

    thickness = np.linalg.norm(outer - inner, axis=1)
    face_thickness = thickness[cage_faces].mean(axis=1)
    positive_thickness = face_thickness[face_thickness > 1e-8]
    thickness_floor = .1 * float(np.median(positive_thickness))
    options = []
    chart_boundary_groups = 0
    for g, ids in enumerate(members):
        own_faces = {int(selected[v]) for v in ids}
        candidate_faces = set(own_faces)
        for neighbour in neighbours[g]:
            for v in members[neighbour]:
                face_id = int(selected[v])
                if all(charts[face_id] != charts[own] for own in own_faces):
                    candidate_faces.add(face_id)
        base_face = int(selected[ids[0]])
        base_distance = float(np.min(np.linalg.norm(binding["residual"][ids], axis=1)))
        group_options = [(None, original_current[g], base_distance /
                          max(face_thickness[base_face], thickness_floor))]
        if len(candidate_faces) > len(own_faces):
            chart_boundary_groups += 1
        for face_id in sorted(candidate_faces):
            evaluated = _evaluate_face(group_source[g], face_id, inner, outer,
                                       target_inner, target_outer, cage_faces, parity)
            if evaluated is None:
                continue
            point, distance = evaluated
            normalized = distance / max(face_thickness[face_id], thickness_floor)
            group_options.append((face_id, point, normalized))
        options.append(group_options)

    def local_energy(group, position, normalized_distance):
        energy = normalized_distance ** 2
        for other, rest_length in neighbours[group].items():
            expected = scale * rest_length
            actual = float(np.linalg.norm(position - current[other]))
            ratio = max(actual, length_floor * .05) / max(expected, length_floor)
            energy += float(np.log(ratio) ** 2)
        return energy

    def would_reverse(group, position):
        """Reject new wrong-way faces; allow correction of existing wrong-way faces."""
        ids = np.asarray(incident[group], dtype=int)
        ids = ids[valid_baseline_faces[ids]]
        if not len(ids):
            return False
        tri = current[face_groups[ids]].copy()
        tri[face_groups[ids] == group] = position
        normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        before = np.einsum("ij,ij->i", baseline_normals[ids], expected_normals[ids])
        after = np.einsum("ij,ij->i", normals, expected_normals[ids])
        newly_wrong = (before > 0) & (after <= 0)
        flipped_without_correction = (
            np.einsum("ij,ij->i", normals, baseline_normals[ids]) <= 0
        ) & ~((before < 0) & (after > 0))
        return bool(np.any(newly_wrong | flipped_without_correction))

    choice = np.zeros(len(members), dtype=int)
    changes_by_round = []
    inversion_rejections = 0
    order = sorted(range(len(members)), key=lambda g: -len(options[g]))
    for _ in range(rounds):
        changed = 0
        for group in order:
            if len(options[group]) == 1:
                continue
            scores = []
            for _, point, distance in options[group]:
                if would_reverse(group, point):
                    scores.append(np.inf)
                    inversion_rejections += 1
                else:
                    scores.append(local_energy(group, point, distance))
            best = int(np.argmin(scores))
            if best != choice[group] and scores[best] < scores[choice[group]] - 1e-10:
                choice[group] = best
                current[group] = options[group][best][1]
                changed += 1
        changes_by_round.append(changed)
        if not changed:
            break

    result = source.copy()
    selected_faces = selected.copy()
    for group, ids in enumerate(members):
        chosen_face, position, _ = options[group][choice[group]]
        if chosen_face is not None:
            result[ids] = position
            selected_faces[ids] = chosen_face
    audit = dict(groups=len(members), chart_boundary_groups=chart_boundary_groups,
                 groups_changed=int(np.count_nonzero(choice)),
                 vertices_changed=int(sum(len(members[g]) for g in np.flatnonzero(choice))),
                 changes_by_round=changes_by_round,
                 inversion_rejections=inversion_rejections,
                 max_displacement=float(np.linalg.norm(result - source, axis=1).max()),
                 selected_faces=selected_faces)
    return result, audit
