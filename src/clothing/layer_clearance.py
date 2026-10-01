"""Layer a top and pants that were each fitted to the body on their own.

Roblox wraps the outer layer over the inner one. Here the outer garment is left
untouched and the parts of the inner garment that poke through it (a thick
waistband under a hoodie hem, jeans under a lab coat, a shirt under a jacket's
sleeves) are pulled back under it, where they are hidden anyway. Positions are
in the render buffer layout (x, up, depth). Distances are measured along rays
leaving the body, not along garment normals, because a waistband's lining faces
inwards: from the closest point of the body cage when it is known (arms,
shoulders, chest), otherwise horizontally from the body axis.
"""
import numpy as np

UP = 1
# Roblox always draws these over pants: jacket, sweater, dress/skirt.
OUTER_TOP_TYPES = {67, 68, 72}


def fitted_asset_type(obj_path) -> int | None:
    """Asset type written in a fitted OBJ header (``# asset_type N``), if any."""
    try:
        with open(obj_path, encoding="utf-8", errors="ignore") as handle:
            for _ in range(3):
                line = handle.readline()
                if line.startswith("# asset_type "):
                    return int(line.split()[2])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _farthest_hits(origins, directions, lengths, triangles, reach):
    """Distance along each ray to the farthest triangle hit within ``reach`` of ``lengths`` (nan if none).

    Exact, but not brute force: equal rays (render buffers repeat every vertex per face
    corner) are cast once, and each batch of neighbouring rays only meets the triangles whose
    box touches the stretch of the rays where a hit counts.
    """
    origins = np.asarray(origins, dtype=np.float64)
    directions = np.asarray(directions, dtype=np.float64)
    lengths = np.asarray(lengths, dtype=np.float64)
    reach = np.broadcast_to(np.asarray(reach, dtype=np.float64), (len(origins),))
    if not len(origins):
        return np.zeros(0)
    rays = np.column_stack((origins, directions, lengths, reach))
    rays, inverse = np.unique(rays, axis=0, return_inverse=True)
    o_all, d_all, length_all, reach_all = rays[:, :3], rays[:, 3:6], rays[:, 6], rays[:, 7]
    # The part of each ray where a hit counts: t in (max(0, length - reach), length + reach).
    near = o_all + d_all * np.maximum(length_all - reach_all, 0.0)[:, None]
    far = o_all + d_all * (length_all + reach_all)[:, None]
    low, high = np.minimum(near, far), np.maximum(near, far)
    order = np.lexsort(np.floor((low + high) / 0.2).T)  # neighbours in the same batch
    tri_low, tri_high = triangles.min(1), triangles.max(1)
    result = np.full(len(rays), np.nan)
    for start in range(0, len(order), 128):
        rows = order[start:start + 128]
        touched = np.all((tri_low <= high[rows].max(0) + 1e-9) & (tri_high >= low[rows].min(0) - 1e-9), axis=1)
        if not touched.any():
            continue
        tri = triangles[touched]
        v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        o, d, length = o_all[rows], d_all[rows], length_all[rows]
        p = np.cross(d[:, None], e2[None])
        det = np.einsum("tk,rtk->rt", e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o[:, None] - v0[None]
        u = np.einsum("rtk,rtk->rt", s, p) * inv
        q = np.cross(s, e1[None])
        v = np.einsum("rk,rtk->rt", d, q) * inv
        t = np.einsum("tk,rtk->rt", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & (np.abs(t - length[:, None]) < reach_all[rows, None])
        farthest = np.where(hit, t, -np.inf).max(1)
        result[rows] = np.where(np.isfinite(farthest), farthest, np.nan)
    return result[inverse.ravel()]


def _closest_body_points(points, body_points, body_faces):
    from .hsr import closest_on_surface
    a, b, c = (body_points[body_faces[:, k]] for k in range(3))
    best, bary = closest_on_surface(points, a, b, c)
    return bary[:, 0, None] * a[best] + bary[:, 1, None] * b[best] + bary[:, 2, None] * c[best]


def _outer_surface(inner, outer, outer_faces, reach, body=None):
    """For the inner vertices the outer garment may cover: ids, ray directions, radii and outer-surface radii."""
    triangles = outer[np.asarray(outer_faces).reshape(-1, 3)]
    if body is not None:
        low, high = outer.min(0) - reach, outer.max(0) + reach
        band = np.flatnonzero(((inner >= low) & (inner <= high)).all(1))
    else:
        band = np.flatnonzero((inner[:, UP] >= outer[:, UP].min()) & (inner[:, UP] <= outer[:, UP].max()))
    if not len(band):
        return band, np.zeros((0, 3)), np.zeros(0), np.zeros(0)
    if body is not None:
        origins = _closest_body_points(inner[band], np.asarray(body[0], dtype=np.float64), np.asarray(body[1]))
    else:
        tri_low, tri_high = triangles[:, :, UP].min(1), triangles[:, :, UP].max(1)
        triangles = triangles[(tri_high >= inner[band, UP].min()) & (tri_low <= inner[band, UP].max())]
        centre = inner[band].mean(0)
        origins = inner[band].copy()
        origins[:, [0, 2]] = centre[[0, 2]]
    directions = inner[band] - origins
    radii = np.linalg.norm(directions, axis=1)
    directions /= np.maximum(radii, 1e-9)[:, None]
    return band, directions, radii, _farthest_hits(origins, directions, radii, triangles, reach)


def pull_inner_layer(inner: np.ndarray, outer: np.ndarray, outer_faces: np.ndarray,
                     clearance: float = 0.005, reach: float = 0.08, body=None) -> np.ndarray:
    """Pull the inner-garment vertices that poke through the outer garment back under it.

    Along the ray leaving the body (``body`` = (cage points, cage faces), or the body
    axis without it), each such vertex ends ``clearance`` inside the outermost outer
    surface within ``reach``.
    """
    inner = np.array(inner, dtype=np.float64)
    band, directions, radii, surface = _outer_surface(inner, np.asarray(outer, dtype=np.float64), outer_faces,
                                                      reach, body)
    poking = np.isfinite(surface) & (radii > surface - clearance)
    inner[band[poking]] -= directions[poking] * (radii[poking] - surface[poking] + clearance)[:, None]
    return inner


def covered_vertices(inner: np.ndarray, outer: np.ndarray, outer_faces: np.ndarray, reach: float = 0.08,
                     body=None) -> np.ndarray:
    """Inner vertices with outer-garment cloth along their ray within ``reach`` (hidden under it)."""
    inner = np.asarray(inner, dtype=np.float64)
    band, _, _, surface = _outer_surface(inner, np.asarray(outer, dtype=np.float64), outer_faces, reach, body)
    covered = np.zeros(len(inner), dtype=bool)
    covered[band[np.isfinite(surface)]] = True
    return covered


def outside_fraction(inner: np.ndarray, outer: np.ndarray, outer_faces: np.ndarray, reach: float = 0.08,
                     body=None) -> float:
    """Share of the covered inner vertices that sit outside the outer garment."""
    _, _, radii, surface = _outer_surface(np.asarray(inner, dtype=np.float64), np.asarray(outer, dtype=np.float64),
                                          outer_faces, reach, body)
    covered = np.isfinite(surface)
    return float((radii[covered] > surface[covered]).sum() / max(covered.sum(), 1))


def layer_top_and_bottom(top: np.ndarray, top_faces: np.ndarray, bottom: np.ndarray, bottom_faces: np.ndarray,
                         top_type: int | None, body=None):
    """New (top, bottom) positions with the inner garment pulled under the outer one.

    Jackets, sweaters and dresses are outside; any other top is outside unless most
    of the pants already sit outside it (a shirt tucked into the pants).
    """
    top = np.asarray(top, dtype=np.float64)
    bottom = np.asarray(bottom, dtype=np.float64)
    if top_type in OUTER_TOP_TYPES or outside_fraction(bottom, top, top_faces, body=body) <= 0.5:
        return top, pull_inner_layer(bottom, top, top_faces, body=body)
    return pull_inner_layer(top, bottom, bottom_faces, body=body), bottom


def body_cage_from_sidecars(*fitted_obj_paths):
    """(cage points, cage faces) of the body in render space, from any garment's HSR sidecar."""
    import os
    from .hsr import sidecar_path
    for path in fitted_obj_paths:
        sidecar = sidecar_path(path) if path else None
        if sidecar and os.path.exists(sidecar):
            with np.load(sidecar) as data:
                if "cage_faces" in data:
                    return np.asarray(data["cage_points"], dtype=np.float64), np.asarray(data["cage_faces"])
    return None
