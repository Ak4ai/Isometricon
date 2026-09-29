"""Build a male R15 body cage from the female one: same topology and UVs, moved onto the male body.

Every garment pairs with the body cage by UV, so a male cage with the female cage's
topology lets the whole female pipeline (WrapLayer fit, HSR, layers, shoes) dress
the male body. Parts are transferred one at a time.

Skin-anchored transfer: each cage point is anchored at its closest point on each
female body group the part covers (e.g. chest and neck) with its offset from there,
and the rebuilt positions are blended by closeness to each group. The anchor moves to the male skin by rings: in its own body
group, at the same height fraction and the same place relative to the skin
cross-section (convex hull: centre, half width and depth), then snapped onto the
male skin. The offset is rotated from the female skin normal to the male one, so
the cage keeps its distance and covers what it covered (the chest cage's collar
goes up the male neck, not flat on the shoulders).

Checks, both ways: male skin poking out through the cage (a skin sample beyond the
cage triangle right above it) and cage points left inside the male skin. The male
body is boxier, so cage triangles can cut its corners: those are pushed out until
neither collision is left.

Usage: python scripts/build_male_cage.py
Output: artifacts/male_cage/<part>_male.npy, <part>_colisoes.npz, relatorio.json
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.clothing.character_model as CM
from src.clothing.hsr import _closest_on_triangles, engine_to_body_mesh
from src.clothing.wear_engine import RobloxWearEngine

FEMALE_BODY = ROOT / "assets/models/character_female_clean_apose_stage2.obj"
MALE_BODY = ROOT / "assets/models/character_clean.obj"
OUT = ROOT / "artifacts/male_cage"
# Cage part -> body mesh groups it covers (render space: x, up, depth).
# The pelvis (LowerTorso) is made by hand in Blender: the male pelvis is too thin a slab
# for the rings to follow automatically.
PARTS = {"UpperTorso": ["Export_torso", "Export_pecoco"],
         "LeftUpperLeg": ["Export_coxa_esquerda"], "RightUpperLeg": ["Export_coxa_direita"],
         "LeftLowerLeg": ["Export_canela_esquerda"], "RightLowerLeg": ["Export_canela_direita"],
         "LeftFoot": ["Export_pe_esquerdo"], "RightFoot": ["Export_pe_direito"]}
# Parts built from the original R15 cage (same points, order and UVs as the female one):
# the male legs are plain boxes like the R15 legs, while the female legs are curved.
FROM_R15 = {"LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg"}
# Parts whose body mesh is identical on both bodies: the female cage is used as it is.
SAME_AS_FEMALE = {"LeftFoot", "RightFoot"}
# Cage part -> (collar group, the group it stands on): points closer to the collar group
# move rigidly with it, standing on the other group's top.
COLLARS = {"UpperTorso": ("Export_pecoco", "Export_torso")}
# Cage part -> (body group, number of edge loops): the cage's rings follow those loops.
EDGE_LOOPS = {"UpperTorso": ("Export_torso", 4)}
# Cage part -> body group transferred by its corners (landmarks), for parts whose corners
# are not rings of four (the pelvis: a ring of 6, the hips, the crotch).
LANDMARKS = {}
# Cage part -> (body group, corners per height level, bottom to top, female and male): the
# levels are split into rings of four (quadrant_rings) for the box transfer.
LEVEL_RINGS = {"LowerTorso": ("Export_pelve", (7, 4, 6), (6, 4, 6))}
# Cage part -> parts built before it whose cage points it shares (same position on the
# female cage, different UVs): those points are copied so the seam stays closed.
SEAMS = {"LowerTorso": ["UpperTorso"], "LeftLowerLeg": ["LeftUpperLeg"], "RightLowerLeg": ["RightUpperLeg"]}
SEAM_FADE = 0.05  # the seam correction fades over 5 cm below the seam
UP = 1


def body_part(path, groups):
    data = CM.parse_clean_obj_groups(str(path), groups)
    return data[0].reshape(-1, 11)[:, :3].astype(np.float64), data[1].reshape(-1, 3)


def face_normals(vertices, faces):
    normal = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    return normal / np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]


def closest_on_mesh(points, vertices, faces, chunk=128):
    """Closest face, barycentric coordinates and point on the mesh for each point."""
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    face = np.empty(len(points), dtype=np.int64)
    bary = np.empty((len(points), 3))
    closest = np.empty_like(points)
    for start in range(0, len(points), chunk):
        p = points[start:start + chunk]
        weights = _closest_on_triangles(p, a, b, c)
        candidates = weights[..., 0, None] * a[None] + weights[..., 1, None] * b[None] + weights[..., 2, None] * c[None]
        best = ((candidates - p[:, None]) ** 2).sum(-1).argmin(1)
        rows = np.arange(len(p))
        face[start:start + chunk] = best
        bary[start:start + chunk] = weights[rows, best]
        closest[start:start + chunk] = candidates[rows, best]
    return face, bary, closest


def section_hull(vertices, faces, height):
    """Convex hull (x, depth) of the mesh cross-section at ``height``, counter-clockwise."""
    tri = vertices[faces]
    crossings = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = tri[:, i], tri[:, j]
        span = b[:, UP] - a[:, UP]
        t = (height - a[:, UP]) / np.where(np.abs(span) < 1e-12, np.nan, span)
        ok = (t >= 0) & (t <= 1)
        crossings.append(a[ok] + t[ok, None] * (b[ok] - a[ok]))
    points = np.unique(np.round(np.concatenate(crossings)[:, [0, 2]], 6), axis=0)
    if len(points) < 3:
        return None
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for point in points:  # Andrew's monotone chain
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in points[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return np.array(lower[:-1] + upper[:-1])


def ring_map(point, female, male, margin=0.02):
    """A point on (or near) the female group's skin, moved to the male group's skin by rings."""
    (fv, ff), (mv, mf) = female, male
    f_low, f_high = fv[:, UP].min(), fv[:, UP].max()
    m_low, m_high = mv[:, UP].min(), mv[:, UP].max()
    fraction = float(np.clip((point[UP] - f_low) / (f_high - f_low), 0.0, 1.0))
    ring = float(np.clip(fraction, margin, 1 - margin))
    f_hull = section_hull(fv, ff, f_low + ring * (f_high - f_low))
    m_hull = section_hull(mv, mf, m_low + ring * (m_high - m_low))
    f_centre, m_centre = (f_hull.min(0) + f_hull.max(0)) / 2, (m_hull.min(0) + m_hull.max(0)) / 2
    scale = (np.ptp(m_hull, axis=0) / 2) / np.maximum(np.ptp(f_hull, axis=0) / 2, 1e-6)
    planar = m_centre + (np.array([point[0], point[2]]) - f_centre) * scale
    return np.array([planar[0], m_low + fraction * (m_high - m_low), planar[1]])


def move_collar(cage_points, male_cage, female_collar, male_collar, female_base, male_base, base_rows,
                standing=0.015, base_reach=0.065):
    """The collar moved with the neck, in two consistent parts.

    - Standing collar (above the base group's top face by more than ``standing``):
      rigid, following the neck's centre across and the top face's height at the
      neck (the male neck sits further back, the male shoulders higher and tilted).
    - Base ring (on the top face, within ``base_reach`` of the neck's centre, square
      distance): across it follows the neck, its height follows the tilted top face.
    Classifying by "closer to the neck than to the chest" split the base ring in two
    halves that went different ways, which notched the neck hole.
    Returns the moved points and the mask of the collar points (both parts).
    """
    (fcv, fcf), (mcv, mcf), (fbv, fbf), (mbv, mbf) = female_collar, male_collar, female_base, male_base
    f_top, m_top = edge_loop_planes(fbv, base_rows)[-1], edge_loop_planes(mbv, base_rows)[-1]
    plane = lambda coefficients, x, z: coefficients[0] + coefficients[1] * x + coefficients[2] * z
    centre_f, centre_m = (fcv.min(0) + fcv.max(0)) / 2, (mcv.min(0) + mcv.max(0)) / 2
    across = (centre_m - centre_f)[[0, 2]]
    f_height = plane(f_top, cage_points[:, 0], cage_points[:, 2])
    square = np.maximum(np.abs(cage_points[:, 0] - centre_f[0]), np.abs(cage_points[:, 2] - centre_f[2]))
    standing_mask = cage_points[:, UP] > f_height + standing
    base_mask = ~standing_mask & (square < base_reach) & (cage_points[:, UP] > f_height - standing)
    moved = male_cage.copy()
    new_x = cage_points[:, 0] + across[0]
    new_z = cage_points[:, 2] + across[1]
    lift = plane(m_top, centre_m[0], centre_m[2]) - plane(f_top, centre_f[0], centre_f[2])
    moved[standing_mask] = np.column_stack((new_x, cage_points[:, UP] + lift, new_z))[standing_mask]
    base_height = plane(m_top, new_x, new_z) + (cage_points[:, UP] - f_height)
    moved[base_mask] = np.column_stack((new_x, base_height, new_z))[base_mask]
    return moved, standing_mask | base_mask


def buried(points, other_groups, depth=0.003):
    """Points lying inside another body group (the neck's base inside the chest)."""
    hidden = np.zeros(len(points), dtype=bool)
    for vertices, faces in other_groups:
        face, _, closest = closest_on_mesh(points, vertices, faces)
        hidden |= ((points - closest) * face_normals(vertices, faces)[face]).sum(1) < -depth
    return hidden


def visible_skin(groups, per_edge=6):
    """Skin samples and normals of every group, without the parts buried in other groups."""
    samples, normals = [], []
    for index, (vertices, faces) in enumerate(groups):
        points, point_normals = skin_samples(vertices, faces, per_edge)
        keep = ~buried(points, [g for k, g in enumerate(groups) if k != index])
        samples.append(points[keep])
        normals.append(point_normals[keep])
    return np.concatenate(samples), np.concatenate(normals)


def warp_transfer(cage_points, female_groups, male_groups, per_edge=3, smoothing=1e-4):
    """Cage moved by one smooth space warp fitted from the female skin to the male skin.

    Skin samples of every group are paired by rings (female sample -> male skin) and a
    biharmonic RBF (phi(r) = r, plus an affine part) interpolates the displacement
    through space. Applied to the whole cage at once, neighbouring points move
    together, so the collar stays a clean ring around the neck.
    """
    sources, targets = [], []
    for (fv, ff), (mv, mf) in zip(female_groups, male_groups):
        steps = [(i / per_edge, j / per_edge) for i in range(per_edge + 1) for j in range(per_edge + 1 - i)]
        weights = np.array([(1 - u - v, u, v) for u, v in steps])
        samples = np.unique(np.round(np.einsum("sk,fkd->fsd", weights, fv[ff]).reshape(-1, 3), 5), axis=0)
        samples = samples[~buried(samples, [g for g in female_groups if g[0] is not fv])]
        # Pair by rings (the width follows each height), then snap onto the male skin. The
        # rings are measured between 10% and 90% of the part: nearer its ends a section is
        # only a sliver (the top of the chest) and threw the shoulder edge back.
        mapped = np.array([ring_map(point, (fv, ff), (mv, mf), margin=0.1) for point in samples])
        _, _, snapped = closest_on_mesh(mapped, mv, mf)
        sources.append(samples)
        targets.append(snapped)
    source, target = np.concatenate(sources), np.concatenate(targets)
    n = len(source)
    kernel = np.linalg.norm(source[:, None] - source[None], axis=-1)
    affine = np.column_stack((np.ones(n), source))
    system = np.zeros((n + 4, n + 4))
    system[:n, :n] = kernel + smoothing * np.eye(n)
    system[:n, n:] = affine
    system[n:, :n] = affine.T
    rhs = np.zeros((n + 4, 3))
    rhs[:n] = target - source
    coefficients = np.linalg.solve(system, rhs)
    warp = np.linalg.norm(cage_points[:, None] - source[None], axis=-1) @ coefficients[:n]
    warp += np.column_stack((np.ones(len(cage_points)), cage_points)) @ coefficients[n:]
    return cage_points + warp


def skin_samples(vertices, faces, per_edge=6):
    """Points spread over every skin triangle, with that triangle's normal."""
    steps = [(i / per_edge, j / per_edge) for i in range(per_edge + 1) for j in range(per_edge + 1 - i)]
    weights = np.array([(1 - u - v, u, v) for u, v in steps])
    points = np.einsum("sk,fkd->fsd", weights, vertices[faces]).reshape(-1, 3)
    normals = np.repeat(face_normals(vertices, faces), len(steps), axis=0)
    return points, normals


def under_cage(samples, sample_normals, cage_points, cage_faces, reach=0.06):
    """Skin samples lying under a cage triangle (foot inside it, surfaces roughly parallel).

    A skin surface crossing a cage triangle edge-on (the neck through the shoulder
    lid) is not covered by it.
    """
    face, bary, closest = closest_on_mesh(samples, cage_points, cage_faces)
    cage_normals = face_normals(cage_points, cage_faces)[face]
    parallel = np.abs((cage_normals * sample_normals).sum(1)) > 0.5
    covered = (bary.min(1) > 1e-3) & (np.linalg.norm(samples - closest, axis=1) < reach) & parallel
    return face, bary, closest, covered


def collisions(cage_points, cage_faces, skin_vertices, skin_faces, visible, reach=0.06):
    """Skin samples poking out through the cage, and cage points inside the skin."""
    samples, sample_normals = visible
    face, bary, closest, covered = under_cage(samples, sample_normals, cage_points, cage_faces, reach)
    # Measured along the skin normal: some cage triangles are wound the other way.
    poking = covered & (((closest - samples) * sample_normals).sum(1) < 0)
    s_face, _, s_closest = closest_on_mesh(cage_points, skin_vertices, skin_faces)
    inside = ((cage_points - s_closest) * face_normals(skin_vertices, skin_faces)[s_face]).sum(1) < 0
    return samples[poking], cage_points[inside], samples[covered]


def resolve_collisions(cage_points, cage_faces, skin_vertices, skin_faces, visible, clearance=0.005,
                       iterations=150, reach=0.06, total_limit=0.06, spread=0.5, fixed=None):
    """Inflate the cage smoothly until no skin pokes through it and no cage point is inside.

    Each iteration, every poking skin sample asks the corners of the cage triangle
    above it to move out along the skin normal (depth + ``clearance``, weighted by the
    barycentric position), and cage points inside the skin ask to move out too. The
    requested moves are spread to neighbouring cage points (the displacement is
    smoothed over the cage graph), so the cage bulges evenly instead of growing
    spikes. Points duplicated at UV seams move together.
    """
    _, weld = np.unique(np.round(cage_points, 6), axis=0, return_inverse=True)
    weld = weld.ravel()
    count = weld.max() + 1
    welded_faces = weld[cage_faces]
    edges = np.unique(np.sort(np.concatenate([welded_faces[:, [0, 1]], welded_faces[:, [1, 2]],
                                              welded_faces[:, [2, 0]]]), axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    degree = np.bincount(edges.ravel(), minlength=count).astype(float)
    base = np.zeros((count, 3))
    base[weld] = cage_points
    displacement = np.zeros_like(base)
    still = np.zeros(count, dtype=bool)
    if fixed is not None:
        still[weld[fixed]] = True  # seam points shared with a finished part stay put
    samples, sample_normals = visible
    skin_face_normals = face_normals(skin_vertices, skin_faces)
    for _ in range(iterations):
        points = base + displacement
        face, bary, closest, covered = under_cage(samples, sample_normals, points, welded_faces, reach)
        height = ((closest - samples) * sample_normals).sum(1)
        poking = np.flatnonzero(covered & (height < clearance / 2))
        s_face, _, s_closest = closest_on_mesh(points, skin_vertices, skin_faces)
        gap = ((points - s_closest) * skin_face_normals[s_face]).sum(1)
        inside = gap < clearance / 2
        if not len(poking) and not inside.any():
            break
        push = np.zeros_like(base)
        for sample in poking:
            amount = (clearance - height[sample]) * bary[sample] / max(bary[sample].max(), 1e-6)
            for corner, value in zip(welded_faces[face[sample]], amount):
                if value > np.linalg.norm(push[corner]):
                    push[corner] = sample_normals[sample] * value
        push[inside] += skin_face_normals[s_face][inside] * (clearance - gap[inside])[:, None]
        displacement += push
        # Spread locally: a point takes at least ``spread`` of its neighbours' mean push, so
        # a bulge fades over a few rings instead of inflating the whole cage.
        total = np.zeros_like(displacement)
        np.add.at(total, edges[:, 0], displacement[edges[:, 1]])
        np.add.at(total, edges[:, 1], displacement[edges[:, 0]])
        mean = spread * total / np.maximum(degree, 1)[:, None]
        raise_it = np.linalg.norm(mean, axis=1) > np.linalg.norm(displacement, axis=1)
        displacement[raise_it] = mean[raise_it]
        length = np.linalg.norm(displacement, axis=1, keepdims=True)
        displacement *= np.minimum(1.0, total_limit / np.maximum(length, 1e-12))
        displacement[still] = 0.0
    return (base + displacement)[weld]


def edge_loop_planes(vertices, rows):
    """The body group's horizontal edge loops, each fitted as a plane y = a + b*x + c*z.

    A box-like part is ``rows`` rings of corners; on the male chest they tilt (the pec
    line runs from 1.15 at one face to 1.25 at the other), so a ring is a tilted plane.
    """
    corners = np.unique(np.round(vertices, 4), axis=0)
    corners = corners[np.argsort(corners[:, UP])]
    planes = []
    for ring in np.array_split(corners, rows):
        design = np.column_stack((np.ones(len(ring)), ring[:, 0], ring[:, 2]))
        planes.append(np.linalg.lstsq(design, ring[:, UP], rcond=None)[0])
    return np.array(planes)


def follow_edge_loops(female_points, male_points, female_vertices, male_vertices, rows=4):
    """Heights of the male cage points set by the edge loops of both bodies.

    A point between two female loops (at its own x, z) keeps its fraction of the way
    between the matching male loops (at its male x, z), so the cage's rings run along
    the male body's edge loops, tilt included. Beyond the first and last loops it
    keeps its distance to them.
    """
    f_planes, m_planes = edge_loop_planes(female_vertices, rows), edge_loop_planes(male_vertices, rows)
    heights = lambda planes, points: planes[:, 0][None] + points[:, [0]] * planes[:, 1][None] + points[:, [2]] * planes[:, 2][None]
    f_loops, m_loops = heights(f_planes, female_points), heights(m_planes, male_points)
    result = male_points.copy()
    for index, y in enumerate(female_points[:, UP]):
        f, m = f_loops[index], m_loops[index]
        if y <= f[0]:
            result[index, UP] = m[0] + (y - f[0])
        elif y >= f[-1]:
            result[index, UP] = m[-1] + (y - f[-1])
        else:
            k = int(np.searchsorted(f, y) - 1)
            t = (y - f[k]) / max(f[k + 1] - f[k], 1e-9)
            result[index, UP] = m[k] + t * (m[k + 1] - m[k])
    return result


def box_rings(vertices, rows):
    """The corners of a box-like body group: ``rows`` rings of 4, ordered (-x-z, +x-z, +x+z, -x+z)."""
    corners = np.unique(np.round(vertices, 4), axis=0)
    corners = corners[np.argsort(corners[:, UP])]
    rings = []
    for ring in np.array_split(corners, rows):
        centre = ring.mean(0)
        key = {(np.sign(c[0] - centre[0]), np.sign(c[2] - centre[2])): c for c in ring}
        rings.append([key[(-1, -1)], key[(1, -1)], key[(1, 1)], key[(-1, 1)]])
    return np.array(rings)  # (rows, 4, 3)


def _trilinear(cell, u, v, w):
    """Point of a hexahedral cell (bottom ring, top ring) at parameters u (x), v (up), w (z)."""
    bottom, top = cell
    ring = lambda r: ((1 - u) * (1 - w) * r[0] + u * (1 - w) * r[1] + u * w * r[2] + (1 - u) * w * r[3])
    return (1 - v) * ring(bottom) + v * ring(top)


def quadrant_rings(vertices, levels):
    """Rings of 4 corners picked per height level: in each (x, z) quadrant, the corner farthest out.

    For parts whose corners are not plain rings of four (the pelvis has 6 at the
    top and centre points at the crotch), this keeps the box outline of each level.
    """
    corners = np.unique(np.round(vertices, 4), axis=0)
    order = np.argsort(corners[:, UP])
    groups = np.array_split(corners[order], np.cumsum(levels)[:-1])
    rings = []
    for group in groups:
        centre = (group.min(0) + group.max(0)) / 2
        ring = []
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            score = sx * (group[:, 0] - centre[0]) + sz * (group[:, 2] - centre[2])
            ring.append(group[score.argmax()])
        rings.append(ring)
    return np.array(rings)


def _map_axis(values, f_low, f_high, m_low, m_high):
    """Inside [f_low, f_high] scale onto [m_low, m_high]; outside keep the distance to the edge."""
    scaled = m_low + (values - f_low) * (m_high - m_low) / (f_high - f_low)
    return np.where(values < f_low, m_low + (values - f_low), np.where(values > f_high, m_high + (values - f_high), scaled))


def axis_transfer(points, f_rings, m_rings, female_skin, male_skin):
    """Points mapped axis by axis: the body's extent is scaled, the cage's offset outside it kept.

    Width and depth come from the whole skin at the part's height (the male thighs
    stick out wider than the male pelvis); height is piecewise linear through the
    rings' heights. Each axis is mapped on its own, so flat cage faces stay flat and
    horizontal bands stay horizontal (the trilinear box map twisted the hip sides),
    and the cage keeps the female cage's distance outside the body.
    """
    f_h, m_h = f_rings[:, :, UP].mean(1), m_rings[:, :, UP].mean(1)
    def extent(skin, low, high):
        v = skin[(skin[:, UP] >= low) & (skin[:, UP] <= high)]
        return v.min(0), v.max(0)
    f_min, f_max = extent(female_skin, f_h[0], f_h[-1])
    m_min, m_max = extent(male_skin, m_h[0], m_h[-1])
    result = np.empty_like(points)
    for axis in (0, 2):
        result[:, axis] = _map_axis(points[:, axis], f_min[axis], f_max[axis], m_min[axis], m_max[axis])
    result[:, UP] = _map_axis(points[:, UP], f_h[0], f_h[-1], m_h[0], m_h[-1])
    inside = (points[:, UP] >= f_h[0]) & (points[:, UP] <= f_h[-1])
    result[inside, UP] = np.interp(points[inside, UP], f_h, m_h)
    return result


# Pelvis rings, set by hand: female cage/body height -> male height. The female pelvis
# cage is a box of rings (top 0.91-0.93, band 0.893, low waist 0.872, hip 0.85, crotch
# 0.76-0.82); the male pelvis is a thin slab whose width changes with height (the pelvis
# is 0.128 wide at the top, the thighs 0.166 at the hip), so each ring gets its own width.
PELVIS_LEVELS = ((0.777, 0.786), (0.801, 0.812), (0.855, 0.836), (0.872, 0.852), (0.893, 0.870), (0.905, 0.884))


def _extents(skin, height):
    """Half width, front and back of the skin's cross-section at ``height`` (x centred on 0).

    ``skin`` is (vertices, faces); the section is the crossing points of its triangles.
    """
    vertices, faces = skin
    tri = vertices[faces]
    crossings = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = tri[:, i], tri[:, j]
        span = b[:, UP] - a[:, UP]
        t = (height - a[:, UP]) / np.where(np.abs(span) < 1e-12, np.nan, span)
        ok = (t >= 0) & (t <= 1)
        crossings.append(a[ok] + t[ok, None] * (b[ok] - a[ok]))
    section = np.concatenate(crossings)
    if len(section) < 3:
        return None
    return np.array([np.abs(section[:, 0]).max(), section[:, 2].max(), section[:, 2].min()])


def pelvis_rings_transfer(points, female_skin, male_skin, levels=PELVIS_LEVELS):
    """Each pelvis cage ring moved to its hand-picked male height, fitted to the body there.

    Between two levels a point interpolates. Across the ring, the body's half width and
    its front and back at that height are scaled from female to male; the part of a
    point beyond the body (the cage's offset) is kept as it was on the female cage.
    """
    f_levels = np.array([f for f, _ in levels])
    m_levels = np.array([m for _, m in levels])
    def level_extents(skin, heights):
        values = [_extents(skin, h) for h in heights]
        known = [k for k, v in enumerate(values) if v is not None]
        # A level past the body's end (the crotch tip) takes the nearest measured level.
        return np.array([values[k] if values[k] is not None else values[min(known, key=lambda j: abs(j - k))]
                         for k in range(len(values))])
    f_ext = level_extents(female_skin, f_levels)
    m_ext = level_extents(male_skin, m_levels)
    result = np.empty_like(points)
    for index, (x, y, z) in enumerate(points):
        t = np.interp(y, f_levels, np.arange(len(levels)))
        k = int(min(np.floor(t), len(levels) - 2))
        w = t - k
        fe = (1 - w) * f_ext[k] + w * f_ext[k + 1]
        me = (1 - w) * m_ext[k] + w * m_ext[k + 1]
        if y < f_levels[0]:
            new_y = m_levels[0] + (y - f_levels[0])
        elif y > f_levels[-1]:
            new_y = m_levels[-1] + (y - f_levels[-1])
        else:
            new_y = np.interp(y, f_levels, m_levels)
        ax = abs(x)
        new_x = ax * me[0] / fe[0] if ax <= fe[0] else me[0] + (ax - fe[0])
        if z >= 0:
            new_z = z * me[1] / fe[1] if z <= fe[1] else me[1] + (z - fe[1])
        else:
            new_z = z * me[2] / fe[2] if z >= fe[2] else me[2] + (z - fe[2])
        result[index] = (np.sign(x) * new_x, new_y, new_z)
    # Below the crotch ring the horizontal ray passes between the thighs: those points keep
    # the axis map.
    above = points[:, UP] >= levels[1][0]
    result[above] = ring_offsets(points[above], result[above], female_skin, male_skin)
    return result


def ring_clearance(points, skin, fixed, clearance=0.006):
    """Points closer than ``clearance`` to the skin along their ring's radius move out along it."""
    from src.clothing.layer_clearance import _farthest_hits
    tri = skin[0][skin[1]]
    centres = []
    for y in points[:, UP]:
        e = _extents(skin, y)
        centres.append(0.0 if e is None else (e[1] + e[2]) / 2)
    origins = np.column_stack((np.zeros(len(points)), points[:, UP], centres))
    flat = points - origins
    flat[:, UP] = 0.0
    radius = np.linalg.norm(flat, axis=1)
    directions = flat / np.maximum(radius, 1e-9)[:, None]
    skin_radius = _farthest_hits(origins, directions, radius, tri, reach=1.0)
    close = np.isfinite(skin_radius) & (radius < skin_radius + clearance) & ~fixed
    result = points.copy()
    result[close] = origins[close] + directions[close] * (skin_radius[close] + clearance)[:, None]
    return result


def ring_offsets(female_points, male_points, female_skin, male_skin):
    """Give each point its female distance to the skin again, along its own ring's radius.

    The ray starts at the centre of the body's cross-section at the point's height and
    runs horizontally through the point; on the female body the cage's distance past
    the skin along it is measured, and the male point is put that far past the male
    skin along its ray. Staying on the ring's radius keeps the rings flat and even.
    """
    from src.clothing.layer_clearance import _farthest_hits
    result = male_points.copy()
    for points, skin, store in ((female_points, female_skin, "f"), (male_points, male_skin, "m")):
        tri = skin[0][skin[1]]
        centres = []
        for y in points[:, UP]:
            e = _extents(skin, y)
            centres.append(0.0 if e is None else (e[1] + e[2]) / 2)
        origins = np.column_stack((np.zeros(len(points)), points[:, UP], centres))
        flat = points - origins
        flat[:, UP] = 0.0
        radius = np.linalg.norm(flat, axis=1)
        directions = flat / np.maximum(radius, 1e-9)[:, None]
        skin_radius = _farthest_hits(origins, directions, radius, tri, reach=1.0)
        if store == "f":
            offset = radius - skin_radius
        else:
            ok = np.isfinite(skin_radius) & np.isfinite(offset) & (offset > 0)
            result[ok] = origins[ok] + directions[ok] * (skin_radius[ok] + offset[ok])[:, None]
    return result


def _source_rings(source):
    """Bottom and top rings of four corners of an R15 cage part (box-like, top may slant).

    Each corner takes the box's x/z corner; its height is the lowest (bottom) or highest
    (top) cage point near that corner, so the thigh's slanted top (low at the crotch,
    high at the hip) is kept.
    """
    low, high = source.min(0), source.max(0)
    size = high - low
    rings = []
    for pick in (np.min, np.max):
        ring = []
        for x, z in ((low[0], low[2]), (high[0], low[2]), (high[0], high[2]), (low[0], high[2])):
            near = (np.abs(source[:, 0] - x) < 0.25 * size[0]) & (np.abs(source[:, 2] - z) < 0.35 * size[2])
            ring.append((x, pick(source[near, UP]), z))
        rings.append(ring)
    return np.array(rings, dtype=np.float64)


def _inverse_trilinear(point, cell):
    """Parameters (u, v, w) of ``point`` in a hexahedral cell (Newton)."""
    uvw = np.array([0.5, 0.5, 0.5])
    for _ in range(25):
        current = _trilinear(cell, *uvw)
        jacobian = np.empty((3, 3))
        for axis in range(3):
            step = np.zeros(3)
            step[axis] = 1e-5
            jacobian[:, axis] = (_trilinear(cell, *(uvw + step)) - current) / 1e-5
        uvw = np.clip(uvw + np.linalg.lstsq(jacobian, point - current, rcond=None)[0], -1.0, 2.0)
    return uvw


def open_edge_planes(points, faces):
    """Planes y = a + b*x + c*z through a cage part's two open edges (bottom, top).

    The edges used by a single triangle form the part's open loops (where it meets the
    next part); split by height into the bottom and the top loop.
    """
    _, weld = np.unique(np.round(points, 5), axis=0, return_inverse=True)
    weld = weld.ravel()
    welded = weld[np.asarray(faces)]
    edges = np.sort(np.concatenate([welded[:, [0, 1]], welded[:, [1, 2]], welded[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    border = np.unique(unique[counts == 1])
    position = np.zeros((weld.max() + 1, 3))
    position[weld] = points
    border_points = position[border]
    middle = (points[:, UP].min() + points[:, UP].max()) / 2
    planes = []
    for loop in (border_points[border_points[:, UP] < middle], border_points[border_points[:, UP] >= middle]):
        design = np.column_stack((np.ones(len(loop)), loop[:, 0], loop[:, 2]))
        planes.append(np.linalg.lstsq(design, loop[:, UP], rcond=None)[0])
    return planes


def r15_box_transfer(source_points, male_body, source_rings=None, margin=0.012, female_points=None,
                     female_rings=None):
    """The R15 cage part fitted into the male body part's slanted box.

    The R15 cage faces the other way in depth (z is mirrored). Its own rings of four
    corners (bottom and top, see ``_source_rings``) are mapped trilinearly onto the male
    part's two rings (each widened by ``margin``), so the cage follows the leg's slant
    and the thigh's slanted top. ``source_rings`` lets two parts share a ring (the knee).
    """
    source = source_points * np.array([1.0, 1.0, -1.0])
    rings = box_rings(male_body, 2)
    for ring in rings:
        centre = ring.mean(0)
        ring[:, 0] += np.sign(ring[:, 0] - centre[0]) * margin
        ring[:, 2] += np.sign(ring[:, 2] - centre[2]) * margin
    f_rings = _source_rings(source) if source_rings is None else source_rings
    if female_points is None:
        return box_transfer(source, None, None, None, f_rings, rings), f_rings
    # Cross-section from the R15 cage (boxy like the male legs), rows from the female
    # cage: the R15 thigh packs its rows low and leaves the hip rows sparse, the female
    # cage spreads them evenly over the thigh. A row's height is its fraction between the
    # female cage's two open edges (knee and slanted top), each fitted as a plane.
    bottom_plane, top_plane = female_rings
    at = lambda plane, pts: plane[0] + plane[1] * pts[:, 0] + plane[2] * pts[:, 2]
    v_all = (female_points[:, UP] - at(bottom_plane, female_points)) / (
        at(top_plane, female_points) - at(bottom_plane, female_points))
    result = np.empty_like(source)
    for index, (point, v) in enumerate(zip(source, v_all)):
        u, _, w = _inverse_trilinear(point, (f_rings[0], f_rings[1]))
        result[index] = _trilinear((rings[0], rings[1]), u, float(np.clip(v, 0, 1)), w)
    return result, f_rings


def box_transfer(points, female_vertices, male_vertices, rows, f_rings=None, m_rings=None):
    """Points moved cell by cell between the stacked boxes of the two body groups.

    Each point is located in the female box cell it belongs to (inverse trilinear
    map, Newton) and rebuilt at the same parameters in the matching male cell, so
    the box's faces map onto the box's faces: the cage keeps its grid on the front
    and on the top face, and its rings follow the tilted edge loops. Points past a
    cell (the cage's offset, the collar above the top) extrapolate the same map.
    """
    if f_rings is None:
        f_rings, m_rings = box_rings(female_vertices, rows), box_rings(male_vertices, rows)
    rows = len(f_rings)
    result = np.empty_like(points)
    for index, point in enumerate(points):
        best = None
        for k in range(rows - 1):
            cell = (f_rings[k], f_rings[k + 1])
            uvw = np.array([0.5, 0.5, 0.5])
            for _ in range(20):
                current = _trilinear(cell, *uvw)
                jacobian = np.empty((3, 3))
                for axis in range(3):
                    step = np.zeros(3)
                    step[axis] = 1e-4
                    jacobian[:, axis] = (_trilinear(cell, *(uvw + step)) - current) / 1e-4
                uvw = uvw + np.linalg.lstsq(jacobian, point - current, rcond=None)[0]
            outside = np.abs(np.clip(uvw, 0, 1) - uvw).sum()
            if best is None or outside < best[0] or (outside == best[0] and abs(uvw[1] - 0.5) < abs(best[2][1] - 0.5)):
                best = (outside, k, uvw)
        _, k, uvw = best
        result[index] = _trilinear((m_rings[k], m_rings[k + 1]), *uvw)
    return result


def match_corners(female_corners, male_corners):
    """Female corner -> male corner, by position in each part's box (greedy, closest first).

    A female corner with no male partner (the female crotch point; the male pelvis is
    flat there) gets the centre of the male corners around it at the same box height.
    """
    f_low, f_size = female_corners.min(0), np.maximum(np.ptp(female_corners, axis=0), 1e-6)
    m_low, m_size = male_corners.min(0), np.maximum(np.ptp(male_corners, axis=0), 1e-6)
    fn, mn = (female_corners - f_low) / f_size, (male_corners - m_low) / m_size
    distance = np.linalg.norm(fn[:, None] - mn[None], axis=-1)
    pairs, used_f, used_m = {}, set(), set()
    for i, j in zip(*np.unravel_index(np.argsort(distance, axis=None), distance.shape)):
        if i in used_f or j in used_m:
            continue
        pairs[int(i)] = male_corners[j]
        used_f.add(i)
        used_m.add(j)
    for i in range(len(female_corners)):
        if i not in pairs:
            near = np.argsort(np.linalg.norm(fn[:, [0, 2]] - fn[i, [0, 2]], axis=1))[1:5]
            target = np.mean([pairs[int(k)] for k in near if int(k) in pairs], axis=0)
            target[UP] = m_low[UP] + fn[i, UP] * m_size[UP]
            pairs[i] = target
    return np.array([pairs[i] for i in range(len(female_corners))])


def landmark_transfer(points, female_vertices, male_vertices):
    """Points moved by the smooth space map that takes every female corner onto its male corner."""
    source = np.unique(np.round(female_vertices, 4), axis=0)
    target = match_corners(source, np.unique(np.round(male_vertices, 4), axis=0))
    n = len(source)
    system = np.zeros((n + 4, n + 4))
    system[:n, :n] = np.linalg.norm(source[:, None] - source[None], axis=-1)
    system[:n, n:] = np.column_stack((np.ones(n), source))
    system[n:, :n] = system[:n, n:].T
    rhs = np.zeros((n + 4, 3))
    rhs[:n] = target - source
    coefficients = np.linalg.solve(system, rhs)
    warp = np.linalg.norm(points[:, None] - source[None], axis=-1) @ coefficients[:n]
    warp += np.column_stack((np.ones(len(points)), points)) @ coefficients[n:]
    return points + warp


def cage_edges(cage_points, cage_faces):
    """Welded vertex index of each cage point and the welded edge list (UV seams joined)."""
    _, weld = np.unique(np.round(cage_points, 6), axis=0, return_inverse=True)
    weld = weld.ravel()
    faces = weld[cage_faces]
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    return weld, edges[edges[:, 0] != edges[:, 1]]


def shrink_wrap(points, female_distance, skin_vertices, skin_faces, cage_faces, fixed, iterations=1, relax=0.0):
    """Put each cage point at its female skin distance from the male skin, following its edges.

    A point projected onto the offset surface of the skin lands over the nearest skin
    feature, so the cage's rings follow the body's corners (chest edges, the waist
    line) like on the female cage, instead of cutting across them as the smooth warp
    did. A light Laplacian relaxation between projections keeps the triangles even;
    ``fixed`` points (the collar) are left where they are.
    """
    weld, edges = cage_edges(points, cage_faces)
    count = weld.max() + 1
    welded = np.zeros((count, 3))
    welded[weld] = points
    distance = np.zeros(count)
    distance[weld] = female_distance
    still = np.zeros(count, dtype=bool)
    still[weld[fixed]] = True
    degree = np.bincount(edges.ravel(), minlength=count).astype(float)
    for _ in range(iterations):
        total = np.zeros_like(welded)
        np.add.at(total, edges[:, 0], welded[edges[:, 1]])
        np.add.at(total, edges[:, 1], welded[edges[:, 0]])
        relaxed = welded + relax * (total / np.maximum(degree, 1)[:, None] - welded)
        face, _, closest = closest_on_mesh(relaxed, skin_vertices, skin_faces)
        offset = relaxed - closest
        length = np.linalg.norm(offset, axis=1)
        # Always to the outside of the skin: points left inside go out along the skin normal.
        normal = face_normals(skin_vertices, skin_faces)[face]
        inward = (offset * normal).sum(1) < 0
        offset[inward] = normal[inward]
        length[inward] = 1.0
        projected = closest + offset / np.maximum(length, 1e-9)[:, None] * distance[:, None]
        welded = np.where(still[:, None], welded, projected)
    return welded[weld]


def merged(groups):
    vertices, faces, offset = [], [], 0
    for v, f in groups:
        vertices.append(v)
        faces.append(f + offset)
        offset += len(v)
    return np.concatenate(vertices), np.concatenate(faces)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    engine = RobloxWearEngine(body_type="female")
    report = {}
    knee_rings, knee_rows = {}, {}
    for part, groups in PARTS.items():
        cage = engine_to_body_mesh(np.asarray(engine.r15_female_cages[part]["verts"], dtype=np.float64))
        cage_faces = np.asarray(engine.r15_female_cages[part]["faces"])
        female_groups = [body_part(FEMALE_BODY, [g]) for g in groups]
        male_groups = [body_part(MALE_BODY, [g]) for g in groups]
        if part in FROM_R15:
            source = engine_to_body_mesh(np.asarray(engine.r15_source_cages[part]["verts"], dtype=np.float64))
            shared, female_shared = None, None
            if part.endswith("LowerLeg"):
                # The knee ring is the thigh's bottom ring, so the knee points land where
                # the thigh's did.
                side = part.replace("LowerLeg", "")
                shared = _source_rings(engine_to_body_mesh(np.asarray(
                    engine.r15_source_cages[part]["verts"], dtype=np.float64)) * np.array([1.0, 1.0, -1.0]))
                shared[1] = knee_rings[side][0]
            thigh = part.endswith("UpperLeg")
            male_cage, rings = r15_box_transfer(source, male_groups[0][0], shared,
                                                female_points=cage if thigh else None,
                                                female_rings=open_edge_planes(cage, cage_faces) if thigh else None)
            if part.endswith("UpperLeg"):
                knee_rings[part.replace("UpperLeg", "")] = (rings[0], _source_rings(cage)[0])
                knee_rows[part.replace("UpperLeg", "")] = male_cage[cage[:, UP] < cage[:, UP].min() + 0.003]

        elif part in SAME_AS_FEMALE:
            male_cage = cage.copy()
        elif part in EDGE_LOOPS:
            group, rows = EDGE_LOOPS[part]
            k = groups.index(group)
            male_cage = box_transfer(cage, female_groups[k][0], male_groups[k][0], rows)
        elif part in LEVEL_RINGS:
            group, f_levels, m_levels = LEVEL_RINGS[part]
            k = groups.index(group)
            f_rings, m_rings = quadrant_rings(female_groups[k][0], f_levels), quadrant_rings(male_groups[k][0], m_levels)
            male_cage = pelvis_rings_transfer(cage, merged(female_groups), merged(male_groups))
        elif part in LANDMARKS:
            k = groups.index(LANDMARKS[part])
            male_cage = landmark_transfer(cage, female_groups[k][0], male_groups[k][0])
        else:
            male_cage = warp_transfer(cage, female_groups, male_groups)
        fixed = np.zeros(len(cage), dtype=bool)
        seam_points = {}
        for other in SEAMS.get(part, []):
            other_female = engine_to_body_mesh(np.asarray(engine.r15_female_cages[other]["verts"], dtype=np.float64))
            other_male = np.load(OUT / f"{other}_male.npy")
            distance = np.linalg.norm(cage[:, None] - other_female[None], axis=-1)
            shared = distance.min(1) < 1e-4
            seam_points.update({int(i): other_male[distance[i].argmin()] for i in np.flatnonzero(shared)})
        if seam_points:
            # Spread the seam's correction (finished part's position - this transfer's) over
            # the band under it, fading out downwards, so the whole top edge moves together
            # instead of 9 points zigzagging off it.
            ids = np.array(list(seam_points))
            delta = np.array([seam_points[i] for i in ids]) - male_cage[ids]
            weights = 1.0 / (np.linalg.norm(male_cage[:, None] - male_cage[ids][None], axis=-1) ** 2 + 1e-6)
            spread = (weights @ delta) / weights.sum(1)[:, None]
            below = np.clip((male_cage[ids, UP].mean() - male_cage[:, UP]) / SEAM_FADE, 0.0, 1.0)
            male_cage += spread * (1 - below * below * (3 - 2 * below))[:, None]
            for i, position in seam_points.items():
                male_cage[i] = position
                fixed[i] = True
        if part.endswith("LowerLeg"):
            # Knee ring points of the calf with no twin on the thigh (a front corner) are
            # clamped to the thigh's knee row outline, after the seam correction, so the
            # ring stays one clean loop.
            row = knee_rows[part.replace("LowerLeg", "")]
            on_knee = cage[:, UP] > cage[:, UP].max() - 0.003
            on_knee[list(seam_points)] = False  # the shared knee points keep the thigh's position
            for axis in (0, 2):
                male_cage[on_knee, axis] = np.clip(male_cage[on_knee, axis], row[:, axis].min(), row[:, axis].max())
            fixed |= on_knee
        if part in COLLARS:
            collar, base = (groups.index(g) for g in COLLARS[part])
            male_cage, fixed = move_collar(cage, male_cage, female_groups[collar], male_groups[collar],
                                           female_groups[base], male_groups[base], EDGE_LOOPS[part][1])
        female_skin, male_skin = merged(female_groups), merged(male_groups)
        visible = {"feminino": visible_skin(female_groups), "masculino": visible_skin(male_groups)}
        _, _, female_closest = closest_on_mesh(cage, *female_skin)
        female_distance = np.linalg.norm(cage - female_closest, axis=1)
        import os
        stage = os.environ.get("CAGE_STAGE", "all")  # debugging: stop after "transfer" or "projection"
        if stage != "transfer" and part not in LEVEL_RINGS and part not in FROM_R15 and part not in SAME_AS_FEMALE:  # the box transfer already fits flat faces
            male_cage = shrink_wrap(male_cage, female_distance, *male_skin, cage_faces, fixed)
        if stage == "all":
            if part in LEVEL_RINGS:
                male_cage = ring_clearance(male_cage, male_skin, fixed)
            else:
                male_cage = resolve_collisions(male_cage, cage_faces, *male_skin, visible["masculino"], fixed=fixed)
        entry_seam = len(seam_points)
        entry = {"pontos": int(len(cage)), "pontos_de_costura_com_partes_anteriores": entry_seam}
        for name, points, skin in (("feminino", cage, female_skin), ("masculino", male_cage, male_skin)):
            poking, inside, covered = collisions(points, cage_faces, *skin, visible[name])
            _, _, closest = closest_on_mesh(points, *skin)
            distance = np.linalg.norm(points - closest, axis=1)
            entry[name] = {
                "distancia_da_pele_cm": {"mediana": round(float(np.median(distance)) * 100, 2),
                                         "max": round(float(distance.max()) * 100, 2)},
                "pele_furando_a_cage": f"{len(poking)} de {len(covered)} amostras cobertas",
                "pontos_da_cage_dentro_da_pele": int(len(inside)),
            }
            np.savez(OUT / f"{part}_{name}_colisoes.npz", poking=poking, inside=inside)
        report[part] = entry
        np.save(OUT / f"{part}_male.npy", male_cage)
    (OUT / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
