"""Offline radial shell on logical UV vertices. NOT used by production.

Published basis: US20250265799A1, Figs. 21-24 (radial outer influences,
adjacent-face normals, SVD rotations). Our choices: one sample per UV identity,
RMS bulk scale, unit normals, tiny edge regularizer for undetermined twist,
radius=thickness, source-normalized inverse-distance weights. These choices
are not a claim about Roblox's private implementation.
"""
from __future__ import annotations
import numpy as np


def canonical_cages(reference, outer, target, faces, uv_ids):
    arrays = [np.asarray(x, dtype=float) for x in (reference, outer, target)]
    if any(x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(x).all() for x in arrays):
        raise ValueError('Cages must be finite Nx3 arrays')
    if any(x.shape != arrays[0].shape for x in arrays):
        raise ValueError('Cage shapes must agree')
    ids = np.asarray(uv_ids)
    if ids.shape != (len(arrays[0]),):
        raise ValueError('One UV identity required per input vertex')
    _, first, inverse = np.unique(ids, return_index=True, return_inverse=True)
    for x in arrays:
        tolerance = 1e-6 * max(float(np.linalg.norm(np.ptp(x,axis=0))), 1e-8)
        if np.linalg.norm(x-x[first][inverse],axis=1).max() > tolerance:
            raise ValueError('Conflicting positions for the same UV identity')
    faces = np.asarray(faces, dtype=int)
    mapped = inverse[faces]
    _, unique = np.unique(np.sort(mapped,axis=1), axis=0, return_index=True)
    return (*[x[first] for x in arrays], mapped[np.sort(unique)], inverse)


def similarity_scale(source, target):
    """RMS radius ratio, invariant to units, translation, rotation and parity."""
    denominator = np.linalg.norm(source-source.mean(0))
    if denominator < 1e-15:
        raise ValueError('Collapsed reference cage')
    scale = float(np.linalg.norm(target-target.mean(0))/denominator)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Collapsed target cage')
    return scale


def normal_frames(reference, target, faces, parity):
    """Row-vector orthogonal frames from corresponding incident face normals.

    Geometric normals are pseudovectors: target normals must be multiplied
    by parity before fitting the coordinate map. A small normalized-edge
    term resolves planar neighborhoods' free twist without a world-axis rule.
    """
    normals = []
    valid = np.ones(len(faces), dtype=bool)
    for x in (reference, target):
        tri = x[faces]
        n = np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        length = np.linalg.norm(n,axis=1)
        valid &= length > 1e-12 * max(float(np.linalg.norm(np.ptp(x,axis=0)))**2, 1e-12)
        normals.append(n / np.maximum(length[:,None],1e-30))
    incident = [[] for _ in reference]
    for f in np.flatnonzero(valid):
        for v in faces[f]:
            incident[v].append(f)
    rotations = np.empty((len(reference),3,3))
    ranks = []
    used = np.zeros(len(reference),dtype=bool)
    used[np.unique(faces)] = True
    for i, entries in enumerate(incident):
        if not entries:
            if not used[i]:
                # Storage-only vertex, not part of the cage surface. Its frame
                # will not be used for radial influences or visible binding.
                rotations[i] = np.eye(3)
                ranks.append(0)
                continue
            raise ValueError('Logical cage vertex has no nondegenerate adjacent face')
        a, b = normals[0][entries], parity * normals[1][entries]
        covariance = a.T @ b / len(entries)
        ranks.append(int(np.linalg.matrix_rank(covariance,tol=1e-8)))
        neighbors = np.unique(faces[entries])
        p, q = reference[neighbors]-reference[i], target[neighbors]-target[i]
        lp, lq = np.linalg.norm(p,axis=1), np.linalg.norm(q,axis=1)
        good = (lp>1e-12)&(lq>1e-12)
        p, q = p[good]/lp[good,None], q[good]/lq[good,None]
        covariance += 1e-6 * (p.T @ q) / max(len(p),1)
        u, _, vt = np.linalg.svd(covariance)
        correction = np.eye(3)
        correction[-1,-1] = parity * np.linalg.det(u@vt)
        rotations[i] = u @ correction @ vt
    return rotations, ranks


def transfer_canonical_radial(reference, outer, target, faces, uv_ids, *,
                              parity=1, bulk_scale=None, return_audit=False):
    if parity not in (-1,1):
        raise ValueError('Parity must be -1 or +1')
    r, o, t, f, inverse = canonical_cages(reference,outer,target,faces,uv_ids)
    active = np.zeros(len(r),dtype=bool)
    active[np.unique(f)] = True
    scale = similarity_scale(r[active],t[active]) if bulk_scale is None else float(bulk_scale)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid bulk scale')
    rotations, ranks = normal_frames(r,t,f,parity)
    thickness = np.linalg.norm(o-r,axis=1)
    epsilon = max(float(np.linalg.norm(np.ptp(r,axis=0))) * 1e-12,1e-15)
    total, weights = np.zeros_like(o), np.zeros(len(o))
    counts = np.zeros(len(o),dtype=int)
    for j, center in enumerate(r):
        if not active[j]:
            continue
        distance = np.linalg.norm(o-center,axis=1)
        selected = np.flatnonzero((distance <= thickness[j]+epsilon)&active)
        # Includes the paired point by construction, even for zero thickness.
        proximity = 1 / np.maximum(distance[selected],epsilon)
        w = proximity/proximity.sum()
        predictions = t[j]+scale*(o[selected]-center)@rotations[j]
        total[selected] += w[:,None]*predictions
        weights[selected] += w
        counts[selected] += 1
    logical_result = t.copy()  # Explicit placeholder for unused storage vertices.
    logical_result[active] = total[active] / weights[active,None]
    result = logical_result[inverse]
    audit = dict(raw_vertices=len(reference),logical_vertices=len(r),bulk_scale=scale,
                 normal_covariance_rank_counts={str(k):ranks.count(k) for k in range(4)},
                 unused_logical_vertices=int(sum(~active)),
                 influence_count_p95=float(np.quantile(counts,.95)),radius_factor=1,
                 approximation='UV canonicalization + unit-normal SVD + RMS scale + 1e-6 edge regularizer')
    return (result,audit) if return_audit else result
