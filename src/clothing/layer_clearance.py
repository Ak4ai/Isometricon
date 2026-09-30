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
    """Distance along each ray to the farthest triangle hit within ``reach`` of ``lengths`` (nan if none)."""
    v0, e1, e2 = triangles[:, 0], triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    result = np.full(len(origins), np.nan)
    for start in range(0, len(origins), 128):
        o, d, length = origins[start:start + 128], directions[start:start + 128], lengths[start:start + 128]
        p = np.cross(d[:, None], e2[None])
        det = np.einsum("tk,rtk->rt", e1, p)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o[:, None] - v0[None]
        u = np.einsum("rtk,rtk->rt", s, p) * inv
        q = np.cross(s, e1[None])
        v = np.einsum("rk,rtk->rt", d, q) * inv
        t = np.einsum("tk,rtk->rt", e2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0) & (np.abs(t - length[:, None]) < reach)
        farthest = np.where(hit, t, -np.inf).max(1)
        result[start:start + 128] = np.where(np.isfinite(farthest), farthest, np.nan)
    return result


def _closest_body_points(points, body_points, body_faces, chunk=64):
    from .hsr import _closest_on_triangles
    a, b, c = (body_points[body_faces[:, k]] for k in range(3))
    closest = np.empty_like(points)
    for start in range(0, len(points), chunk):
        p = points[start:start + chunk]
        bary = _closest_on_triangles(p, a, b, c)
        candidates = bary[..., 0, None] * a[None] + bary[..., 1, None] * b[None] + bary[..., 2, None] * c[None]
        best = ((candidates - p[:, None]) ** 2).sum(-1).argmin(1)
        closest[start:start + chunk] = candidates[np.arange(len(p)), best]
    return closest


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


# Ray directions for the skin cover test: the 26 neighbours of a cube cell.
_DIRECTIONS = np.array([(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)],
                       dtype=np.float64)
_DIRECTIONS /= np.linalg.norm(_DIRECTIONS, axis=1)[:, None]


# Share of the rays leaving a skin vertex that may miss the cloth with the vertex still
# counted as covered. Under a sweater, at most 10% slip out through the gap Roblox shirts
# (and their cages) leave under the arm; exposed skin loses 60-90% of them.
SKIN_ESCAPE_FRACTION = 0.25


def skin_under_cloth(points: np.ndarray, bones: tuple, cloth: np.ndarray, cloth_faces: np.ndarray,
                     reach: float = 0.6) -> np.ndarray:
    """Skin vertices enclosed by cloth: nearly every ray leaving the body from them hits it.

    "Leaving the body" is judged from the skeleton (``bones`` = (heads, tails)): the rays kept
    point away from the nearest bone, whatever the orientation of the skin's faces. One ray
    is not enough, and neither is requiring all of them: from an armpit corner some slip out
    between the sleeve and the torso. ``reach`` spans a sleeve: from the shoulder, rays run
    down inside it before meeting cloth.
    """
    points = np.asarray(points, dtype=np.float64)
    cloth = np.asarray(cloth, dtype=np.float64)
    triangles = cloth[np.asarray(cloth_faces).reshape(-1, 3)]
    low, high = triangles.min((0, 1)) - reach, triangles.max((0, 1)) + reach
    band = np.flatnonzero(((points >= low) & (points <= high)).all(1))
    covered = np.zeros(len(points), dtype=bool)
    if not len(band):
        return covered
    heads, tails = (np.asarray(b, dtype=np.float64) for b in bones)
    axis = tails - heads
    p = points[band]
    t = np.clip(np.einsum("nbk,bk->nb", p[:, None] - heads[None], axis) / (axis ** 2).sum(1), 0.0, 1.0)
    closest = heads[None] + t[..., None] * axis[None]
    radial = p - closest[np.arange(len(p)), np.linalg.norm(p[:, None] - closest, axis=2).argmin(1)]
    radial /= np.maximum(np.linalg.norm(radial, axis=1), 1e-9)[:, None]
    outward = radial @ _DIRECTIONS.T > 0.2  # (n, 26) rays that leave the body
    escaped = np.zeros(len(p))
    for k, direction in enumerate(_DIRECTIONS):
        rays = np.flatnonzero(outward[:, k])
        if not len(rays):
            continue
        # Rays sharing a direction only meet triangles whose shadow along it covers their
        # origin: project on the plane across the direction and keep those per small batch.
        u = np.cross(direction, [0.0, 0.0, 1.0] if abs(direction[2]) < 0.9 else [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        plane = np.stack([u, np.cross(direction, u)], axis=1)
        flat = triangles @ plane
        tri_low, tri_high = flat.min(1), flat.max(1)
        origins = p[rays] - direction * 1e-3
        flat_origins = origins @ plane
        order = np.lexsort(flat_origins.T)
        for start in range(0, len(order), 32):
            batch = order[start:start + 32]
            low, high = flat_origins[batch].min(0), flat_origins[batch].max(0)
            near = np.all((tri_low <= high) & (tri_high >= low), axis=1)
            if not near.any():
                escaped[rays[batch]] += 1
                continue
            hits = _farthest_hits(origins[batch], np.repeat(direction[None], len(batch), 0),
                                  np.full(len(batch), reach / 2), triangles[near], reach / 2)
            escaped[rays[batch]] += ~np.isfinite(hits)
    covered[band] = escaped <= SKIN_ESCAPE_FRACTION * np.maximum(outward.sum(1), 1)
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
