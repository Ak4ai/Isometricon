"""Build a male R15 body cage from the female one: same topology and UVs, moved onto the male body.

Every garment pairs with the body cage by UV, so a male cage with the female cage's
topology lets the whole female pipeline (WrapLayer fit, HSR, layers, shoes) dress
the male body. Parts are transferred one at a time.

Rings transfer (the two bodies do not share vertex order, and their parts differ in
shape: the female chest is widest at the waist, the male one at the shoulders):
each cage point is described on the female part by its height fraction in the part
and its position relative to the skin cross-section at that height (the convex hull
of the section, centre and half width/depth); it is rebuilt at the same height
fraction and relative position on the male part. Points above or below the part
(neck and waist caps) keep their vertical gap, and points that end up much farther
from the male skin than they were from the female skin are brought back.

Usage: python scripts/build_male_cage.py
Output: artifacts/male_cage/ (report and plots)
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
# Cage part -> body mesh groups (render space: x, up, depth).
PARTS = {"UpperTorso": ["Export_torso"]}
UP = 1


def body_part(path, groups):
    data = CM.parse_clean_obj_groups(str(path), groups)
    return data[0].reshape(-1, 11)[:, :3].astype(np.float64), data[1].reshape(-1, 3)


def triangle_frames(vertices, faces):
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    e1 = b - a
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    normal = np.cross(b - a, c - a)
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    e2 = np.cross(normal, e1)
    return np.stack((e1, e2, normal), axis=1)  # (F, 3 axes, 3)


def closest_on_mesh(points, vertices, faces):
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    bary = _closest_on_triangles(points, a, b, c)
    candidates = bary[..., 0, None] * a[None] + bary[..., 1, None] * b[None] + bary[..., 2, None] * c[None]
    best = ((candidates - points[:, None]) ** 2).sum(-1).argmin(1)
    rows = np.arange(len(points))
    return best, bary[rows, best], candidates[rows, best]


def section_hull(vertices, faces, height):
    """Convex hull (x, depth) of the skin cross-section at ``height``, counter-clockwise."""
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
    # Andrew's monotone chain.
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in points[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return np.array(lower[:-1] + upper[:-1])


def hull_centre(hull):
    return (hull.min(0) + hull.max(0)) / 2


def transfer_rings(cage_points, female_vertices, female_faces, male_vertices, male_faces, margin=0.02):
    """Cage points moved from the female part to the male part, ring by ring.

    Each ring is the convex hull of the skin cross-section at that height, so a part
    left open where a limb attaches (the chest at the shoulders) still has a boundary;
    a point keeps its place relative to that ring's width and depth.
    """
    f_low, f_high = female_vertices[:, UP].min(), female_vertices[:, UP].max()
    m_low, m_high = male_vertices[:, UP].min(), male_vertices[:, UP].max()
    result = np.empty_like(cage_points)
    for index, point in enumerate(cage_points):
        fraction = (point[UP] - f_low) / (f_high - f_low)
        inside = float(np.clip(fraction, margin, 1 - margin))  # caps: measure on the ring just inside
        f_hull = section_hull(female_vertices, female_faces, f_low + inside * (f_high - f_low))
        m_hull = section_hull(male_vertices, male_faces, m_low + inside * (m_high - m_low))
        f_centre, m_centre = hull_centre(f_hull), hull_centre(m_hull)
        # The sections are box-like: width follows the width and depth the depth
        # (a fixed direction would not follow the male chest's wider shoulders).
        f_half = np.ptp(f_hull, axis=0) / 2
        m_half = np.ptp(m_hull, axis=0) / 2
        planar = m_centre + (np.array([point[0], point[2]]) - f_centre) * (m_half / np.maximum(f_half, 1e-6))
        # Height: inside the part by fraction; beyond it (caps) keep the vertical gap.
        if fraction > 1 - margin:
            height = m_high + (point[UP] - f_high)
        elif fraction < margin:
            height = m_low + (point[UP] - f_low)
        else:
            height = m_low + fraction * (m_high - m_low)
        result[index] = (planar[0], height, planar[1])
    return result


def keep_skin_distance(points, female_distance, vertices, faces, slack=0.01):
    """Bring points that ended far from the male skin back to their female skin distance.

    Where the two parts differ most (the male chest narrows sharply at the waist), a
    ring's diagonal rays can leave cage corners several cm off the skin.
    """
    face, _, closest = closest_on_mesh(points, vertices, faces)
    offset = points - closest
    distance = np.linalg.norm(offset, axis=1)
    far = distance > female_distance + slack
    points = points.copy()
    points[far] = closest[far] + offset[far] / distance[far, None] * female_distance[far, None]
    return points


def skin_offsets(points, vertices, faces):
    """Distance to the skin and whether each point is outside it."""
    face, _, closest = closest_on_mesh(points, vertices, faces)
    normal = triangle_frames(vertices, faces)[face][:, 2]
    return np.linalg.norm(points - closest, axis=1), ((points - closest) * normal).sum(1) > 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    engine = RobloxWearEngine(body_type="female")
    report, plots = {}, []
    for part, groups in PARTS.items():
        cage = engine_to_body_mesh(np.asarray(engine.r15_female_cages[part]["verts"], dtype=np.float64))
        female_vertices, faces = body_part(FEMALE_BODY, groups)
        male_vertices, male_faces = body_part(MALE_BODY, groups)
        male_cage = transfer_rings(cage, female_vertices, faces, male_vertices, male_faces)
        f_dist, f_out = skin_offsets(cage, female_vertices, faces)
        male_cage = keep_skin_distance(male_cage, f_dist, male_vertices, male_faces)
        m_dist, m_out = skin_offsets(male_cage, male_vertices, male_faces)
        report[part] = {
            "pontos": int(len(cage)),
            "feminino_distancia_cm": {"mediana": round(float(np.median(f_dist)) * 100, 2),
                                      "max": round(float(f_dist.max()) * 100, 2), "por_fora": int(f_out.sum())},
            "masculino_distancia_cm": {"mediana": round(float(np.median(m_dist)) * 100, 2),
                                       "max": round(float(m_dist.max()) * 100, 2), "por_fora": int(m_out.sum())},
            "corpo_feminino_bbox": [female_vertices.min(0).round(3).tolist(), female_vertices.max(0).round(3).tolist()],
            "corpo_masculino_bbox": [male_vertices.min(0).round(3).tolist(), male_vertices.max(0).round(3).tolist()],
            "cage_masculina_bbox": [male_cage.min(0).round(3).tolist(), male_cage.max(0).round(3).tolist()],
        }
        plots.append((part, cage, female_vertices, male_cage, male_vertices))
        np.save(OUT / f"{part}_male.npy", male_cage)
    (OUT / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as MPath
    fractions = (0.1, 0.3, 0.5, 0.7, 0.9)
    fig, axes = plt.subplots(2 * len(plots), len(fractions), figsize=(4.4 * len(fractions), 9 * len(plots)),
                             squeeze=False)
    for index, (part, cage, fv, male_cage, mv) in enumerate(plots):
        cage_faces = np.asarray(engine.r15_female_cages[part]["faces"])
        female_faces = body_part(FEMALE_BODY, PARTS[part])[1]
        male_faces = body_part(MALE_BODY, PARTS[part])[1]
        for row, (points, body, faces, name) in enumerate(((cage, fv, female_faces, "feminino"),
                                                            (male_cage, mv, male_faces, "masculino"))):
            low, high = body[:, UP].min(), body[:, UP].max()
            inside_total = 0
            for column, fraction in enumerate(fractions):
                height = low + fraction * (high - low)
                skin, ring = section_hull(body, faces, height), section_hull(points, cage_faces, height)
                inside = int(MPath(skin).contains_points(ring).sum())
                inside_total += inside
                ax = axes[2 * index + row, column]
                ax.fill(skin[:, 0], skin[:, 1], color="tan", alpha=0.7, label="pele")
                ax.plot(np.r_[ring[:, 0], ring[:1, 0]], np.r_[ring[:, 1], ring[:1, 1]], c="blue", label="cage")
                ax.set_aspect("equal")
                ax.set_title(f"{part} {name} {fraction:.0%} (cantos dentro: {inside})", fontsize=9)
                ax.legend(fontsize=7)
            report[part][f"{name}_cantos_do_anel_dentro_da_pele"] = inside_total
    plt.tight_layout()
    plt.savefig(OUT / "fatias.png", dpi=55)
    (OUT / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print({part: {k: v for k, v in r.items() if "cantos" in k or k == "masculino_distancia_cm"} for part, r in report.items()})
    print("[OK]", OUT / "fatias.png")

if __name__ == "__main__":
    main()
