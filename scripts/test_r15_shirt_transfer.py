"""Transfer a catalog shirt from its authored reference cage to local R15 cages."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer
import src.clothing.wrap_layer_fit as wrap_fit
from scripts.inspect_classic_mannequin_fbx import load_classic_body, export_outer_cages_obj

ASSET = "133331049150205"
DIRECTORY = ROOT / "assets/models/clothing"
FBX = ROOT / "artifacts/clothing_audit/BlockyCharacter.fbx"
CAGE_OBJ = ROOT / "artifacts/clothing_audit/BlockyCharacter_OuterCages.obj"
FLIP_CAGE = "--flip-normal" in sys.argv or "--flip-cage" in sys.argv
FLIP_GARMENT = "--flip-normal" in sys.argv or "--flip-garment" in sys.argv
VARIANT = ("flip_both" if FLIP_CAGE and FLIP_GARMENT else
           "flip_cage" if FLIP_CAGE else "flip_garment" if FLIP_GARMENT else "baseline")
PREFIX = "blocky_r15_office_shirt_" + VARIANT
OUT = ROOT / f"artifacts/clothing_audit/{PREFIX}_transfer.png"


def edge_metrics(source, target, faces):
    edges = np.unique(np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]],
                                          faces[:, [2, 0]])), axis=1), axis=0)
    before = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    after = np.linalg.norm(target[edges[:, 0]] - target[edges[:, 1]], axis=1)
    usable = before >= .01
    ratio = after[usable] / before[usable]
    return {"edge_ratio_median": float(np.median(ratio)),
            "edge_ratio_p99": float(np.quantile(ratio, .99)),
            "edges_over_3x": int(np.count_nonzero(ratio > 3)),
            "edges_under_one_third": int(np.count_nonzero(ratio < 1 / 3)),
            "edges_over_3x_with_source_over_3cm": int(np.count_nonzero(
                (after > 3 * before) & (before >= .03))),
            "edge_count": int(len(ratio))}


def worst_cage_edges(source, target, faces, uvs, count=12):
    edges = np.unique(np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]],
                                          faces[:, [2, 0]])), axis=1), axis=0)
    before = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    after = np.linalg.norm(target[edges[:, 0]] - target[edges[:, 1]], axis=1)
    ratio = after / np.maximum(before, 1e-10)
    ranked = np.argsort(np.where(before >= .03, ratio, -1))[-count:][::-1]
    return [{"vertices": edges[i].tolist(), "uvs": uvs[edges[i]].tolist(),
             "source": source[edges[i]].tolist(), "target": target[edges[i]].tolist(),
             "source_length": float(before[i]), "target_length": float(after[i]),
             "ratio": float(ratio[i])} for i in ranked]


def signed_surface_volume(vertices, faces):
    triangles = np.asarray(vertices)[faces]
    return float(np.einsum("ij,ij->i", triangles[:, 0],
                           np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)


def draw(ax, garment, faces, body=None, body_faces=None):
    if body is not None:
        ax.add_collection3d(Poly3DCollection(body[body_faces], facecolor="#c8b1a0",
                                                edgecolor="none", alpha=.28))
    ax.add_collection3d(Poly3DCollection(garment[faces], facecolor="#28577b",
                                            edgecolor="none", alpha=.96))
    # Keep both rows framed around the garment; the full R15 legs would make
    # the transferred shirt too small to inspect.
    center = (garment.min(0) + garment.max(0)) / 2
    radius = max(np.ptp(garment, axis=0)) * .58
    for axis, value in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
        axis(value - radius, value + radius)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()


def depth_preview(body, body_faces, garment, garment_faces, output,
                  shared_garment_vertices=None):
    width, height = 340, 440
    canvas = Image.new("RGB", (width * 4, height + 28), "white")
    labels = ((0, "frente"), (np.pi / 2, "lado"), (np.pi, "costas"),
              (np.pi / 4, "3/4"))
    coverage = {}
    # One isotropic camera scale for every view. Independent horizontal and
    # vertical fitting made the side view look much wider than the actual mesh.
    camera_garment = garment if shared_garment_vertices is None else shared_garment_vertices
    all_vertices = np.vstack((body, camera_garment))
    horizontal_limit = max(np.abs(all_vertices[:, :2] @
                                  np.array([np.cos(a), np.sin(a)])).max()
                           for a, _ in labels) * 1.08
    z_top = max(body[:, 2].max(), camera_garment[:, 2].max()) + .1
    z_bottom = min(-.25, camera_garment[:, 2].min() - .1)
    scale = min((width - 1) / (2 * horizontal_limit),
                (height - 1) / (z_top - z_bottom))
    z_center = (z_top + z_bottom) / 2
    for column, (angle, label) in enumerate(labels):
        right = np.array([np.cos(angle), np.sin(angle)])
        toward = np.array([np.sin(angle), -np.cos(angle)])
        zbuffer = np.full((height, width), -np.inf)
        pixels = np.full((height, width, 3), 255, dtype=np.uint8)
        garment_silhouette = np.zeros((height, width), dtype=bool)
        for vertices, triangles, color in ((body, body_faces, (218, 187, 164)),
                                           (garment, garment_faces, (38, 87, 125))):
            horizontal = vertices[:, :2] @ right
            depths = vertices[:, :2] @ toward
            screen = np.column_stack(((width - 1) / 2 + horizontal * scale,
                                      (height - 1) / 2 + (z_center - vertices[:, 2]) * scale))
            for face in triangles:
                points = screen[face]
                x0 = max(0, int(np.floor(points[:, 0].min())))
                x1 = min(width - 1, int(np.ceil(points[:, 0].max())))
                y0 = max(0, int(np.floor(points[:, 1].min())))
                y1 = min(height - 1, int(np.ceil(points[:, 1].max())))
                if x1 < x0 or y1 < y0:
                    continue
                a, b, c = points
                denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                if abs(denominator) < 1e-10:
                    continue
                ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
                u = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / denominator
                v = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / denominator
                w = 1 - u - v
                depth = u * depths[face[0]] + v * depths[face[1]] + w * depths[face[2]]
                patch = zbuffer[y0:y1 + 1, x0:x1 + 1]
                visible = (u >= 0) & (v >= 0) & (w >= 0) & (depth > patch)
                if vertices is garment:
                    garment_silhouette[y0:y1 + 1, x0:x1 + 1] |= (u >= 0) & (v >= 0) & (w >= 0)
                patch[visible] = depth[visible]
                pixels[y0:y1 + 1, x0:x1 + 1][visible] = color
        visible_shirt = np.all(pixels == np.asarray((38, 87, 125)), axis=2)
        coverage[label] = {"shirt_silhouette_pixels": int(garment_silhouette.sum()),
                           "visible_shirt_pixels": int(visible_shirt.sum()),
                           "visible_fraction": float(visible_shirt.sum() /
                                                     max(1, garment_silhouette.sum()))}
        canvas.paste(Image.fromarray(pixels), (column * width, 28))
        ImageDraw.Draw(canvas).text((column * width + 8, 7), label, fill="black")
    canvas.save(output)
    return coverage


def main():
    if FLIP_CAGE or FLIP_GARMENT:
        original_map = wrap_fit._local_map
        call_count = 0

        def mirrored_normal_map(sa, sb, sc, ta, tb, tc, normal_sign=1):
            nonlocal call_count
            call_count += 1
            transform = original_map(sa, sb, sc, ta, tb, tc, normal_sign=normal_sign)
            is_cage = call_count <= 2690  # Validated face count for this asset.
            if transform is None or not (FLIP_CAGE if is_cage else FLIP_GARMENT):
                return transform
            source_normal = np.cross(sb - sa, sc - sa)
            target_normal = np.cross(tb - ta, tc - ta)
            source_normal /= np.linalg.norm(source_normal)
            target_normal /= np.linalg.norm(target_normal)
            normal_scale = float(target_normal @ transform @ source_normal)
            return transform - 2 * normal_scale * np.outer(target_normal, source_normal)

        wrap_fit._local_map = mirrored_normal_map
    engine = RobloxWearEngine(body_type="female")
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    source, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{ASSET}.obj"))))
    trace = {}
    fitted, fit = retarget_garment_with_wrap_layer(
        engine, source, str(next(DIRECTORY.glob(f"*_{ASSET}.rbxm"))),
        DIRECTORY / "wrap_cages", binding_audit=trace)
    reference_id = fit["reference_id"]
    _, ref_faces, _, _ = engine.load_obj(str(DIRECTORY / "wrap_cages" / (reference_id + ".obj")))
    source_engine = np.asarray(source)[:, [0, 2, 1]] * np.array([1, -1, 1])
    body, body_faces, body_names = load_classic_body(FBX)
    views = [(-90, "frente"), (0, "lado"), (90, "costas"), (-45, "3/4")]
    fig = plt.figure(figsize=(16, 8), dpi=140)
    for row, (label, mesh, overlay) in enumerate((("camisa original", source_engine, False),
                                                   ("camisa no R15", fitted, True))):
        for column, (azimuth, view) in enumerate(views):
            ax = fig.add_subplot(2, 4, row * 4 + column + 1, projection="3d")
            draw(ax, mesh, faces, body if overlay else None,
                 body_faces if overlay else None)
            ax.view_init(elev=8, azim=azimuth)
            ax.set_title(f"{label} · {view}")
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    plt.close(fig)
    depth_path = OUT.with_name(PREFIX + "_depth.png")
    visibility = depth_preview(body, body_faces, fitted, faces, depth_path)
    edges = np.unique(np.sort(np.vstack((faces[:, [0, 1]], faces[:, [1, 2]],
                                          faces[:, [2, 0]])), axis=1), axis=0)
    before = np.linalg.norm(source_engine[edges[:, 0]] - source_engine[edges[:, 1]], axis=1)
    after = np.linalg.norm(fitted[edges[:, 0]] - fitted[edges[:, 1]], axis=1)
    stretched = edges[(before >= .03) & (after > 3 * before)]
    detail = fig = plt.figure(figsize=(12, 5), dpi=150)
    for column, (azimuth, view) in enumerate(((-90, "frente"), (90, "costas"), (-45, "3/4"))):
        ax = fig.add_subplot(1, 3, column + 1, projection="3d")
        draw(ax, fitted, faces)
        ax.add_collection3d(Line3DCollection(fitted[stretched], colors="#ed3b30", linewidths=1.2))
        ax.view_init(elev=8, azim=azimuth)
        ax.set_title(f"arestas >3x · {view}")
    detail.tight_layout()
    detail_path = OUT.with_name(PREFIX + "_stretched_edges.png")
    detail.savefig(detail_path)
    plt.close(detail)
    metrics = {"asset_id": ASSET, "source_reference_id": fit["reference_id"],
               "experimental_normal_flip": VARIANT,
               "target": str(CAGE_OBJ.relative_to(ROOT)),
               "rendered_body": "15 Geo meshes from official BlockyCharacter.fbx",
               "body_parts": body_names,
               "source_bounds": [source_engine.min(0).tolist(), source_engine.max(0).tolist()],
               "target_bounds": [fitted.min(0).tolist(), fitted.max(0).tolist()],
               "fit": fit, "mesh_edges": edge_metrics(source_engine, fitted, faces),
               "cage_stage_edges": {
                   "reference_to_body": edge_metrics(trace["reference_parent"], trace["target_body"], ref_faces),
                   "outer_to_target_outer": edge_metrics(trace["outer_parent"], trace["target_outer"], ref_faces),
               },
               "worst_reference_to_body_edges": worst_cage_edges(
                   trace["reference_parent"], trace["target_body"], ref_faces,
                   trace["reference_uv"]),
               "orientation_volumes": {
                   "reference": signed_surface_volume(trace["reference_parent"], ref_faces),
                   "body": signed_surface_volume(trace["target_body"], ref_faces),
                   "source_outer": signed_surface_volume(trace["source_outer"], ref_faces),
                   "target_outer": signed_surface_volume(trace["target_outer"], ref_faces),
               },
               "depth_visibility": visibility,
               "image": str(OUT.relative_to(ROOT)),
               "depth_image": str(depth_path.relative_to(ROOT)),
               "stretched_edges_image": str(detail_path.relative_to(ROOT))}
    report = OUT.with_suffix(".json")
    report.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
