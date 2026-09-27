"""Analytic determinant bounds for linear paired-triangle wedges, offline only.

The determinant is affine in barycentric coordinates and quadratic in depth.
Its extrema over the closed wedge parameter domain therefore occur at a
barycentric corner and a depth endpoint or quadratic stationary point.
This checks local volume validity, NOT global overlap or garment collision.
"""
import numpy as np


def determinant_bounds(low, high):
    """Return per-cell min/max and minimizing (corner, depth), up to roundoff."""
    low, high = np.asarray(low, float), np.asarray(high, float)
    if low.shape != high.shape or low.ndim != 3 or low.shape[1:] != (3, 3):
        raise ValueError('Expected paired arrays of shape (cells, 3, 3)')
    gap = high - low
    a, b = low[:, 1] - low[:, 0], low[:, 2] - low[:, 0]
    da, db = gap[:, 1] - gap[:, 0], gap[:, 2] - gap[:, 0]
    n0 = np.cross(a, b)
    n1 = np.cross(da, b) + np.cross(a, db)
    n2 = np.cross(da, db)
    c0, c1, c2 = [np.einsum('ni,nji->nj', n, gap) for n in (n0, n1, n2)]
    stationary = np.zeros_like(c2)
    np.divide(-c1, 2 * c2, out=stationary, where=c2 != 0)
    depths = np.stack((np.zeros_like(c2), np.ones_like(c2),
                       np.clip(stationary, 0, 1)), axis=-1)
    values = (c2[..., None] * depths + c1[..., None]) * depths + c0[..., None]
    flat = values.reshape(len(low), 9)
    ids = flat.argmin(axis=1)
    return (flat.min(axis=1), flat.max(axis=1), ids // 3,
            depths.reshape(len(low), 9)[np.arange(len(low)), ids])
