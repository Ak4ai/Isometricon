"""Keep an inner garment (pants) from piercing the outer one (a top) where they overlap.

Each garment is fitted to the body on its own, so a thick waistband can end up a
millimetre outside the hem of a hoodie and show through it. Roblox wraps the outer
layer over the inner one; here the few inner vertices that pierce the outer
surface, or sit closer than the clearance, are pulled inward instead.
Positions are in the render buffer layout (x, up, depth).
"""
import numpy as np

UP = 1


def tuck_inner_layer(inner: np.ndarray, outer: np.ndarray, outer_faces: np.ndarray,
                     clearance: float = 0.004, max_pierce: float = 0.01,
                     max_piercing_fraction: float = 0.25) -> np.ndarray:
    """Return a copy of `inner` with the vertices under `outer` moved at least `clearance` inside it.

    Only the band where the outer garment covers the inner one is touched, and only
    vertices within `max_pierce` of the outer surface. When more than
    `max_piercing_fraction` of that band is outside, the inner garment is the outer
    layer on purpose (a top tucked into pants) and nothing changes.
    """
    inner = np.array(inner, dtype=np.float64)
    outer = np.asarray(outer, dtype=np.float64)
    faces = np.asarray(outer_faces).reshape(-1, 3)
    top, bottom = outer[:, UP].max(), outer[:, UP].min()
    band = np.flatnonzero((inner[:, UP] >= bottom) & (inner[:, UP] <= top))
    if not len(band):
        return inner
    tri = outer[faces]
    tri_low, tri_high = tri[:, :, UP].min(1), tri[:, :, UP].max(1)
    lo, hi = inner[band, UP].min(), inner[band, UP].max()
    tri = tri[(tri_high >= lo) & (tri_low <= hi)]
    if not len(tri):
        return inner
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    centre = inner[band].mean(0)

    radius = np.full(len(band), np.nan)  # distance from the axis to the vertex
    surface = np.full(len(band), np.nan)  # distance from the axis to the nearest outer surface
    directions = np.zeros((len(band), 3))
    for start in range(0, len(band), 64):
        points = inner[band[start:start + 64]]
        origin = points.copy()
        origin[:, [0, 2]] = centre[[0, 2]]
        direction = points - origin
        length = np.linalg.norm(direction, axis=1)
        valid = length > 1e-6
        direction[valid] /= length[valid, None]
        p = np.cross(direction[:, None], e2[None])
        det = np.einsum("tk,rtk->rt", e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = origin[:, None] - v0[None]
        u = np.einsum("rtk,rtk->rt", s, p) * inv
        q = np.cross(s, e1[None])
        v = np.einsum("rk,rtk->rt", direction, q) * inv
        t = np.einsum("tk,rtk->rt", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & valid[:, None]
        gap = np.where(hit, np.abs(t - length[:, None]), np.inf)
        nearest = gap.argmin(1)
        found = np.isfinite(gap.min(1))
        rows = np.arange(len(points))
        radius[start:start + 64] = np.where(found, length, np.nan)
        surface[start:start + 64] = np.where(found, t[rows, nearest], np.nan)
        directions[start:start + 64] = direction

    covered = np.isfinite(surface)
    if not covered.any():
        return inner
    piercing = covered & (radius > surface)
    if piercing.sum() > max_piercing_fraction * covered.sum():
        return inner
    move = covered & (radius > surface - clearance) & (radius - surface <= max_pierce)
    target = surface[move] - clearance
    inner[band[move]] -= directions[move] * (radius[move] - target)[:, None]
    return inner
