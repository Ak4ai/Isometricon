"""Locate left/right differences in source garment, target cage, and saved fits."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_jeans_foot_binding import chart_labels
from src.clothing.wear_engine import RobloxWearEngine

BASE = ROOT / "artifacts/clothing_audit/radial_frames/female_109837605892174"
OUT = ROOT / "artifacts/clothing_audit/female_jeans_runtime"


def mirror_nearest(vertices, mask=None):
    points = np.asarray(vertices, dtype=np.float64)
    if mask is not None:
        points = points[mask]
    opposite = points.copy()
    opposite[:, 0] *= -1
    nearest = np.full(len(points), np.inf)
    for chunk in np.array_split(opposite, max(1, (len(points) + 63) // 64)):
        d2 = ((chunk[:, None] - points[None, :]) ** 2).sum(axis=2)
        start = len(points) - len(opposite)
        nearest[start:start + len(chunk)] = np.sqrt(d2.min(axis=1))
        opposite = opposite[len(chunk):]
    return dict(count=len(points), median=float(np.median(nearest)),
                p95=float(np.quantile(nearest, .95)),
                p99=float(np.quantile(nearest, .99)),
                max=float(nearest.max()))


def part_summaries(source, target, mask):
    out = {}
    for label, side in (("negative_x", -1), ("positive_x", 1)):
        selected = mask & (source[:, 0] * side > 0)
        s = source[selected]
        t = target[selected]
        out[label] = dict(vertices=len(s), source_abs_x_range=[float(np.abs(s[:, 0]).min()),
                           float(np.abs(s[:, 0]).max())],
                          target_x_range=[float(t[:, 0].min()), float(t[:, 0].max())],
                          target_z_range=[float(t[:, 2].min()), float(t[:, 2].max())])
    return out


def main():
    d = dict(np.load(BASE.with_suffix(".npz")))
    b = dict(np.load(BASE.with_name(BASE.name + "_binding.npz")))
    o = dict(np.load(BASE.with_name(BASE.name + "_outputs.npz")))
    source = d["source_vertices"]
    scale = json.loads(BASE.with_suffix(".json").read_text(encoding="utf-8"))["common_metric_scale"]
    _, unique_uv = np.unique(d["uv_index"], return_index=True)
    body = d["target_body"][unique_uv]
    report = dict(scale=scale, source_garment_mirror=mirror_nearest(source),
                  target_body_cage_mirror=mirror_nearest(body),
                  source_garment_lower_mirror=mirror_nearest(source, source[:, 1] < -0.8),
                  target_body_lower_mirror=mirror_nearest(body, body[:, 2] < .85),
                  fits={}, bands={})
    report["authored_reference_lower_mirror"] = mirror_nearest(
        d["reference_parent"][unique_uv], d["reference_parent"][unique_uv, 1] < -.8)
    report["authored_outer_lower_mirror"] = mirror_nearest(
        d["outer_parent"][unique_uv], d["outer_parent"][unique_uv, 1] < -.8)
    report["radial_outer_lower_mirror"] = mirror_nearest(
        o["radial_previous_shell"][unique_uv], o["radial_previous_shell"][unique_uv, 2] < .85)
    faces = d["garment_faces"]
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                                              faces[:, [2, 0]]]), axis=1), axis=0)
    source_length = np.linalg.norm(source[edges[:, 0]] - source[edges[:, 1]], axis=1)
    source_area = np.linalg.norm(np.cross(source[faces[:, 1]] - source[faces[:, 0]],
                                         source[faces[:, 2]] - source[faces[:, 0]]), axis=1)
    for name, target in (("production", d["baseline"]),
                         ("radial_prism", o["radial_previous"])):
        report["fits"][name] = dict(all_mirror=mirror_nearest(target),
                                    lower_mirror=mirror_nearest(target, source[:, 1] < -.8))
        target_length = np.linalg.norm(target[edges[:, 0]] - target[edges[:, 1]], axis=1)
        edge_ratio = target_length / np.maximum(source_length * scale, 1e-30)
        target_area = np.linalg.norm(np.cross(target[faces[:, 1]] - target[faces[:, 0]],
                                             target[faces[:, 2]] - target[faces[:, 0]]), axis=1)
        area_ratio = target_area / np.maximum(source_area * scale**2, 1e-30)
        report["fits"][name]["lower_by_source_side"] = {}
        for label, side in (("negative_x", -1), ("positive_x", 1)):
            edge_mask = np.all((source[edges, 0] * side > 0) &
                               (source[edges, 1] < -.8), axis=1) & (source_length >= .01)
            face_mask = np.all((source[faces, 0] * side > 0) &
                               (source[faces, 1] < -.8), axis=1) & (source_area > 1e-9)
            report["fits"][name]["lower_by_source_side"][label] = dict(
                edges=int(edge_mask.sum()), edges_over_3x=int(np.count_nonzero(edge_mask & (edge_ratio > 3))),
                edge_ratio_p99=float(np.quantile(edge_ratio[edge_mask], .99)),
                faces=int(face_mask.sum()), faces_under_tenth=int(np.count_nonzero(face_mask & (area_ratio < .1))))
    for low, high in ((-2.75, -2.30), (-2.30, -1.80), (-1.80, -1.30),
                      (-1.30, -.80), (-.80, -.30), (-.30, .50)):
        mask = (source[:, 1] >= low) & (source[:, 1] < high)
        key = f"{low:.2f}_to_{high:.2f}"
        report["bands"][key] = {
            "source": part_summaries(source, source, mask),
            "production": part_summaries(source, d["baseline"], mask),
            "radial_prism": part_summaries(source, o["radial_previous"], mask),
        }
    engine = RobloxWearEngine(body_type="female")
    charts, labels = chart_labels(engine, d)
    report["binding_regions"] = {}
    for name, face_id in (("production", d["face_indices"]),
                          ("radial_prism", b["face_ids"])):
        row = {}
        for label, side in (("negative_x", -1), ("positive_x", 1)):
            selected = (source[:, 0] * side > 0) & (source[:, 1] < -.8)
            names = [labels[int(charts[int(i)])] for i in face_id[selected]]
            row[label] = {part: names.count(part) for part in sorted(set(names))}
        report["binding_regions"][name] = row
    (OUT / "LEG_ASYMMETRY.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("source_garment_lower_mirror", "authored_outer_lower_mirror", "target_body_lower_mirror", "radial_outer_lower_mirror", "fits", "binding_regions")}, indent=2))


if __name__ == "__main__":
    main()
