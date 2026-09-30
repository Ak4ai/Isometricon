"""Compare our Blocky fit of a garment against the mesh exported from Roblox Studio.

Usage: python scripts/compare_roblox_ground_truth.py <studio_export.obj> [asset_id]

The Studio export ("Export Selection" on the dressed Blocky rig) contains the
body parts left after Roblox's HSR plus the deformed garment as ``Handle1``.
Its garment has the same vertex order as the catalog mesh, so every vertex of
our fit is compared with the very same vertex placed by Roblox.
"""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

STUD_CM = 28.0  # Roblox avatar scale: 1 stud = 28 cm.


def load_obj_groups(path):
    vertices, groups, current = [], {}, None
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith(("g ", "o ")):
            current = line.split()[1]
        elif line.startswith("v "):
            vertices.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            face = [int(token.split("/")[0]) - 1 for token in line.split()[1:]]
            groups.setdefault(current, []).extend(
                [face[0], face[i], face[i + 1]] for i in range(1, len(face) - 1))
    vertices = np.asarray(vertices)
    return {name: _compact(vertices, np.asarray(faces)) for name, faces in groups.items()}


def _compact(vertices, faces):
    used, inverse = np.unique(faces, return_inverse=True)
    return vertices[used], inverse.reshape(faces.shape), used


def nearest_distance(points, cloud, chunk=512):
    out = np.empty(len(points))
    for start in range(0, len(points), chunk):
        block = points[start:start + chunk]
        out[start:start + chunk] = np.sqrt(((block[:, None] - cloud[None]) ** 2).sum(-1).min(1))
    return out


def align_studio_to_engine(studio_body, engine_body):
    """Find the axis signs and translation mapping Studio (Y up) to the engine (Z up)."""
    best = None
    for sx in (1, -1):
        for sy in (1, -1):
            matrix = np.array([[sx, 0, 0], [0, 0, sy], [0, 1, 0]], dtype=float)
            mapped = studio_body @ matrix.T
            # Seed with the head: HSR deletes covered body triangles, so the
            # centroid of the exported body moves, but the head is never hidden.
            head_studio = mapped[mapped[:, 2] > mapped[:, 2].max() - 1.0]
            head_engine = engine_body[engine_body[:, 2] > engine_body[:, 2].max() - 1.0]
            shift = head_engine.mean(0) - head_studio.mean(0)
            for _ in range(8):
                moved = mapped + shift
                sample = moved[:: max(1, len(moved) // 1500)]
                d = nearest_distance(sample, engine_body)
                nearest = engine_body[np.argmin(((sample[:, None] - engine_body[None]) ** 2).sum(-1), 1)]
                shift += np.median(nearest - sample, axis=0)
            error = float(np.median(nearest_distance(sample, engine_body)))
            if best is None or error < best[0]:
                best = (error, matrix, shift.copy())
    return best


def winding_inside(points, vertices, faces, chunk=256):
    """Generalized winding number against the union of closed body parts."""
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    total = np.zeros(len(points))
    for start in range(0, len(points), chunk):
        p = points[start:start + chunk, None]
        ra, rb, rc = a[None] - p, b[None] - p, c[None] - p
        la, lb, lc = (np.linalg.norm(r, axis=-1) for r in (ra, rb, rc))
        numerator = np.einsum("pfi,pfi->pf", ra, np.cross(rb, rc))
        denominator = (la * lb * lc + np.einsum("pfi,pfi->pf", ra, rb) * lc
                       + np.einsum("pfi,pfi->pf", rb, rc) * la + np.einsum("pfi,pfi->pf", rc, ra) * lb)
        total[start:start + chunk] = np.abs(2 * np.arctan2(numerator, denominator).sum(1) / (4 * np.pi))
    return total > 0.5


def edge_ratio(reference, fitted, faces):
    edges = np.unique(np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), 1), axis=0)
    before = np.linalg.norm(reference[edges[:, 0]] - reference[edges[:, 1]], axis=1)
    after = np.linalg.norm(fitted[edges[:, 0]] - fitted[edges[:, 1]], axis=1)
    usable = before > 1e-4
    return after[usable] / before[usable]


def heat_color(values, limit):
    t = np.clip(values / limit, 0, 1)[:, None]
    stops = np.array([[40, 90, 200], [60, 200, 90], [245, 215, 50], [225, 40, 35]], float)
    position = t * (len(stops) - 1)
    low = np.floor(position).astype(int).clip(0, len(stops) - 2)
    frac = position - low
    return (stops[low[:, 0]] * (1 - frac) + stops[low[:, 0] + 1] * frac).astype(np.uint8)


def render_row(layers, bounds, width=300, height=420):
    """Z-buffered orthographic views. ``layers`` = [(vertices, faces, per-face RGB)]."""
    labels = ((0, "frente"), (np.pi / 2, "lado"), (np.pi, "costas"), (np.pi / 4, "3/4"))
    lo, hi = bounds
    radius = np.abs(np.vstack((lo[:2], hi[:2]))).max() * 1.1
    scale = min((width - 1) / (2 * radius), (height - 1) / (hi[2] - lo[2] + .2))
    zc = (hi[2] + lo[2]) / 2
    row = Image.new("RGB", (width * 4, height + 22), "white")
    for column, (angle, label) in enumerate(labels):
        right, toward = np.array([np.cos(angle), np.sin(angle)]), np.array([np.sin(angle), -np.cos(angle)])
        zbuffer = np.full((height, width), -np.inf)
        pixels = np.full((height, width, 3), 255, np.uint8)
        for vertices, faces, colors in layers:
            depth = vertices[:, :2] @ toward
            screen = np.column_stack(((width - 1) / 2 + (vertices[:, :2] @ right) * scale,
                                      (height - 1) / 2 + (zc - vertices[:, 2]) * scale))
            for face, color in zip(faces, colors):
                pa, pb, pc = screen[face]
                x0, x1 = max(0, int(min(pa[0], pb[0], pc[0]))), min(width - 1, int(max(pa[0], pb[0], pc[0])) + 1)
                y0, y1 = max(0, int(min(pa[1], pb[1], pc[1]))), min(height - 1, int(max(pa[1], pb[1], pc[1])) + 1)
                den = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
                if x1 < x0 or y1 < y0 or abs(den) < 1e-10:
                    continue
                ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
                u = ((pb[1] - pc[1]) * (xs - pc[0]) + (pc[0] - pb[0]) * (ys - pc[1])) / den
                v = ((pc[1] - pa[1]) * (xs - pc[0]) + (pa[0] - pc[0]) * (ys - pc[1])) / den
                w = 1 - u - v
                z = u * depth[face[0]] + v * depth[face[1]] + w * depth[face[2]]
                patch = zbuffer[y0:y1 + 1, x0:x1 + 1]
                hit = (u >= 0) & (v >= 0) & (w >= 0) & (z > patch)
                patch[hit] = z[hit]
                pixels[y0:y1 + 1, x0:x1 + 1][hit] = color
        row.paste(Image.fromarray(pixels), (column * width, 22))
        ImageDraw.Draw(row).text((column * width + 6, 5), label, fill="black")
    return row


def main():
    studio_path = Path(sys.argv[1])
    asset = sys.argv[2] if len(sys.argv) > 2 else "109837605892174"
    out_dir = ROOT / "artifacts/roblox_ground_truth" / f"compare_{asset}"
    out_dir.mkdir(parents=True, exist_ok=True)

    body, body_faces, _ = load_classic_body(FBX)
    groups = load_obj_groups(studio_path)
    studio_garment, garment_faces_studio, _ = groups.pop("Handle1")
    studio_body = np.vstack([g[0] for g in groups.values()])
    error, matrix, shift = align_studio_to_engine(studio_body, body)
    to_engine = lambda p: p @ matrix.T + shift
    roblox = to_engine(studio_garment)
    offset = 0
    culled_parts = []
    for name, (vertices, faces, _) in groups.items():
        culled_parts.append((to_engine(vertices), faces))

    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
    source, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{asset}.obj"))))
    same_topology = len(source) == len(roblox) and np.array_equal(np.sort(faces, 1), np.sort(garment_faces_studio, 1))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))), DIRECTORY / "wrap_cages", binding_audit=trace)
    shell = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                       trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
    radial_prism, _ = bind_dual_cage(source, trace, shell)

    inside_roblox = winding_inside(roblox, body, body_faces)
    report = {"studio_export": str(studio_path), "asset": asset,
              "alignment_median_error_studs": error, "axis_matrix": matrix.tolist(), "shift": shift.tolist(),
              "same_vertex_order_and_faces": bool(same_topology),
              "roblox": {"inside_body_fraction": float(inside_roblox.mean()),
                         "edges_over_3x_vs_roblox": 0},
              "studio_body_parts_exported": len(groups), "fbx_body_parts": 15}
    limit = 0.25  # studs (7 cm) = full red in the heat map
    rows = [("Roblox Studio (corpo com HSR do Roblox)", render_row(
        [(v, f, np.tile([218, 187, 164], (len(f), 1))) for v, f in culled_parts]
        + [(roblox, faces, np.tile([90, 90, 90], (len(faces), 1)))], (body.min(0), body.max(0))))]
    for label, fitted in (("runtime atual", baseline), ("radial + prisma", radial_prism)):
        distance = np.linalg.norm(fitted - roblox, axis=1)
        inside = winding_inside(fitted, body, body_faces)
        ratio = edge_ratio(roblox, fitted, faces)
        heights = roblox[:, 2]
        bands = {}
        for name, lo, hi in (("pe/bota", -9, -1.2), ("canela", -1.2, -0.4), ("coxa", -0.4, 0.2), ("quadril/cintura", 0.2, 9)):
            mask = (heights >= lo) & (heights < hi)
            if mask.any():
                bands[name] = {"vertices": int(mask.sum()), "median_cm": float(np.median(distance[mask]) * STUD_CM),
                               "p95_cm": float(np.quantile(distance[mask], .95) * STUD_CM)}
        report[label] = {
            "distance_to_roblox_cm": {"median": float(np.median(distance) * STUD_CM),
                                      "p90": float(np.quantile(distance, .9) * STUD_CM),
                                      "p99": float(np.quantile(distance, .99) * STUD_CM),
                                      "max": float(distance.max() * STUD_CM),
                                      "under_1cm": float((distance * STUD_CM < 1).mean()),
                                      "over_5cm": float((distance * STUD_CM > 5).mean())},
            "by_height": bands,
            "inside_body_fraction": float(inside.mean()),
            "edges_over_3x_vs_roblox": int((ratio > 3).sum()),
            "edges_under_third_vs_roblox": int((ratio < 1 / 3).sum()),
        }
        np.save(out_dir / f"{label.replace(' ', '_').replace('+', 'plus')}_distance.npy", distance)
        face_colors = heat_color(distance[faces].mean(1), limit)
        rows.append((f"{label}: distancia ao Roblox (azul 0 -> vermelho >= {limit * STUD_CM:.0f} cm)",
                     render_row([(body, body_faces, np.tile([218, 187, 164], (len(body_faces), 1))),
                                 (fitted, faces, face_colors)], (body.min(0), body.max(0)))))
        rows.append((f"{label}: mesma malha sem o corpo",
                     render_row([(fitted, faces, face_colors)], (body.min(0), body.max(0)))))
    canvas = Image.new("RGB", (rows[0][1].width, sum(r.height + 24 for _, r in rows)), "white")
    y = 0
    for title, row in rows:
        ImageDraw.Draw(canvas).text((8, y + 6), title, fill="black")
        canvas.paste(row, (0, y + 24))
        y += row.height + 24
    canvas.save(out_dir / "heatmap.png")
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
