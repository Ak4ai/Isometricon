"""Experimental radial outer-cage transfer with source and target centers.

The published US20250265799A1 description constructs proximity influences for
points on both the source inner cage and destination cage. Existing local
radial trials only use source-cage centers. This isolated variant adds target
centers while retaining the same shell, local rotations, radius rule and
weights as ``transfer_outer_cage_radial``. It is an approximation, not Roblox
engine code, and is not used by production.
"""
from __future__ import annotations

import numpy as np

from .multi_influence_shell import _neighborhoods, _rotation


def transfer_outer_cage_bidirectional_radial(
    reference: np.ndarray,
    outer: np.ndarray,
    target: np.ndarray,
    faces: np.ndarray,
    *,
    radius_factor: float = 1.0,
    parity: int = 1,
    bulk_scale: float | None = None,
    return_audit: bool = False,
):
    """Transfer an outer cage using nearby source *and* destination centers.

    For each logical vertex, the source and target positions each query the
    authored outer cage within a radius set by the corresponding garment
    thickness. Each query predicts target positions for selected outer points
    using the same local rotation and bulk scale as the source-only control.
    Predictions are averaged at each outer point.

    The corresponding outer vertex is retained as a fallback when a query has
    no points in range. This makes the transfer defined under large body-shape
    changes and preserves exact identity when ``target == reference``.
    """
    reference = np.asarray(reference, dtype=np.float64)
    outer = np.asarray(outer, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    if (reference.shape != outer.shape or reference.shape != target.shape
            or reference.ndim != 2 or reference.shape[1] != 3):
        raise ValueError("Corresponding cage positions must have shape (N, 3)")
    if parity not in (-1, 1) or radius_factor <= 0 or not np.isfinite(radius_factor):
        raise ValueError("Invalid parity or radius factor")
    if not (np.isfinite(reference).all() and np.isfinite(outer).all()
            and np.isfinite(target).all()):
        raise ValueError("Cage positions must be finite")
    if faces.ndim != 2 or faces.shape[1] != 3 or np.any(faces < 0) or np.any(faces >= len(reference)):
        raise ValueError("Faces must be valid triangles over cage vertices")

    if bulk_scale is None:
        source_extent = np.ptp(reference, axis=0)
        target_extent = np.ptp(target, axis=0)
        valid = source_extent > 1e-8
        bulk_scale = float(np.median(target_extent[valid] / source_extent[valid])) if np.any(valid) else 1.0
    if not np.isfinite(bulk_scale) or bulk_scale <= 0:
        raise ValueError("Invalid bulk scale")

    neighborhoods = _neighborhoods(faces, len(reference), 1)
    rotations = np.empty((len(reference), 3, 3), dtype=np.float64)
    for index, adjacent in enumerate(neighborhoods):
        rotations[index] = _rotation(reference[adjacent] - reference[index],
                                     target[adjacent] - target[index], parity)

    thickness = np.linalg.norm(outer - reference, axis=1)
    epsilon = max(float(np.linalg.norm(np.ptp(reference, axis=0))) * 1e-12, 1e-15)
    total = np.zeros_like(outer)
    weight_total = np.zeros(len(outer), dtype=np.float64)
    source_counts = np.zeros(len(outer), dtype=np.int32)
    target_counts = np.zeros(len(outer), dtype=np.int32)
    query_counts = {"source": [], "target": []}

    # Each source or destination vertex is a query center. Per-center weights
    # are normalized over nearby authored outer-cage samples, matching the
    # orientation of the existing radial accumulator.
    for center_kind, centers in (("source", reference), ("target", target)):
        counts = source_counts if center_kind == "source" else target_counts
        for source_id, center in enumerate(centers):
            distance = np.linalg.norm(outer - center, axis=1)
            radius = max(radius_factor * thickness[source_id], epsilon)
            selected = np.flatnonzero(distance <= radius)
            if source_id not in selected:
                selected = np.append(selected, source_id)
            query_counts[center_kind].append(len(selected))

            proximity = 1.0 / np.maximum(distance[selected], epsilon)
            weights = proximity / proximity.sum()
            offsets = outer[selected] - reference[source_id]
            predicted = target[source_id] + bulk_scale * (offsets @ rotations[source_id])
            np.add.at(total, selected, weights[:, None] * predicted)
            np.add.at(weight_total, selected, weights)
            np.add.at(counts, selected, 1)

    if np.any(weight_total <= 0):
        raise ValueError("Some outer-cage vertices received no radial prediction")
    result = total / weight_total[:, None]
    if not return_audit:
        return result
    audit = {
        "source_center_queries": len(reference),
        "target_center_queries": len(target),
        "source_influence_count_p95": float(np.quantile(source_counts, .95)),
        "target_influence_count_p95": float(np.quantile(target_counts, .95)),
        "source_influence_count_max": int(source_counts.max(initial=0)),
        "target_influence_count_max": int(target_counts.max(initial=0)),
        "outer_vertices_receiving_target_influence": int(np.count_nonzero(target_counts)),
        "mean_outer_samples_per_source_query": float(np.mean(query_counts["source"])),
        "mean_outer_samples_per_target_query": float(np.mean(query_counts["target"])),
        "source_thickness_p95": float(np.quantile(thickness, .95)),
        "bulk_scale": float(bulk_scale),
        "radius_factor": float(radius_factor),
        "approximation": "source+target centers; source thickness; inverse-distance weights; one-ring SVD rotations",
    }
    return result, audit
