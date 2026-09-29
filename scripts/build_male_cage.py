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
PARTS = {"UpperTorso": ["Export_torso", "Export_pecoco"]}
# Cage part -> (collar group, the group it stands on): points closer to the collar group
# move rigidly with it, standing on the other group's top.
COLLARS = {"UpperTorso": ("Export_pecoco", "Export_torso")}
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


def move_collar(cage_points, male_cage, female_collar, male_collar, female_base, male_base):
    """Points closer to the collar group (the neck) than to its base group, moved rigidly.

    The collar ring follows the neck's centre across and the base group's top up and
    down: the male neck sits further back and the male shoulders higher, and a smooth
    warp averaged those two moves, laying the collar flat on the shoulders.
    """
    (fcv, fcf), (mcv, mcf), (fbv, fbf), (mbv, mbf) = female_collar, male_collar, female_base, male_base
    near_collar = (np.linalg.norm(cage_points - closest_on_mesh(cage_points, fcv, fcf)[2], axis=1)
                   < np.linalg.norm(cage_points - closest_on_mesh(cage_points, fbv, fbf)[2], axis=1))
    shift = np.array([0.0, mbv[:, UP].max() - fbv[:, UP].max(), 0.0])
    centre_f, centre_m = (fcv.min(0) + fcv.max(0)) / 2, (mcv.min(0) + mcv.max(0)) / 2
    shift[[0, 2]] = (centre_m - centre_f)[[0, 2]]
    male_cage = male_cage.copy()
    male_cage[near_collar] = cage_points[near_collar] + shift
    return male_cage


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
                       iterations=150, reach=0.06, total_limit=0.06):
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
        # Spread: blend each point's displacement with its neighbours' mean, never below
        # what it was asked for.
        total = np.zeros_like(displacement)
        np.add.at(total, edges[:, 0], displacement[edges[:, 1]])
        np.add.at(total, edges[:, 1], displacement[edges[:, 0]])
        mean = total / np.maximum(degree, 1)[:, None]
        smoothed = 0.5 * displacement + 0.5 * mean
        keep = np.linalg.norm(smoothed, axis=1) < np.linalg.norm(displacement, axis=1)
        smoothed[keep & (np.linalg.norm(push, axis=1) > 0)] = displacement[keep & (np.linalg.norm(push, axis=1) > 0)]
        displacement = smoothed
        length = np.linalg.norm(displacement, axis=1, keepdims=True)
        displacement *= np.minimum(1.0, total_limit / np.maximum(length, 1e-12))
    return (base + displacement)[weld]


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
        _, _, closest = closest_on_mesh(relaxed, skin_vertices, skin_faces)
        offset = relaxed - closest
        length = np.linalg.norm(offset, axis=1)
        # Points that relaxed inside the skin keep their previous side.
        _, _, previous = closest_on_mesh(welded, skin_vertices, skin_faces)
        flip = (offset * (welded - previous)).sum(1) < 0
        offset[flip] *= -1
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
    for part, groups in PARTS.items():
        cage = engine_to_body_mesh(np.asarray(engine.r15_female_cages[part]["verts"], dtype=np.float64))
        cage_faces = np.asarray(engine.r15_female_cages[part]["faces"])
        female_groups = [body_part(FEMALE_BODY, [g]) for g in groups]
        male_groups = [body_part(MALE_BODY, [g]) for g in groups]
        male_cage = warp_transfer(cage, female_groups, male_groups)
        if part in COLLARS:
            collar, base = (groups.index(g) for g in COLLARS[part])
            male_cage = move_collar(cage, male_cage, female_groups[collar], male_groups[collar],
                                    female_groups[base], male_groups[base])
        female_skin, male_skin = merged(female_groups), merged(male_groups)
        visible = {"feminino": visible_skin(female_groups), "masculino": visible_skin(male_groups)}
        _, _, female_closest = closest_on_mesh(cage, *female_skin)
        female_distance = np.linalg.norm(cage - female_closest, axis=1)
        fixed = np.zeros(len(cage), dtype=bool)
        if part in COLLARS:
            (fcv, fcf), (fbv, fbf) = (female_groups[groups.index(g)] for g in COLLARS[part])
            fixed = (np.linalg.norm(cage - closest_on_mesh(cage, fcv, fcf)[2], axis=1)
                     < np.linalg.norm(cage - closest_on_mesh(cage, fbv, fbf)[2], axis=1))
        male_cage = shrink_wrap(male_cage, female_distance, *male_skin, cage_faces, fixed)
        male_cage = resolve_collisions(male_cage, cage_faces, *male_skin, visible["masculino"])
        entry = {"pontos": int(len(cage))}
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
