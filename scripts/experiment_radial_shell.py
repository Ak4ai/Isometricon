"""Offline test of thickness-based radial garment outer-cage influences."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_binding_charts import ASSETS
from scripts.benchmark_wrap_frames import edges_report
from scripts.experiment_chart_blend import face_change_report, load_body_for_preview
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.experiment_shell_global_affine import remap_visible
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _cage_edge_stretch, retarget_garment_with_wrap_layer


def area_report(source, fitted, faces, bulk_scale):
    tri = np.asarray(faces, dtype=np.int32)
    first = np.asarray(source)[tri]
    second = np.asarray(fitted)[tri]
    source_area = np.linalg.norm(np.cross(first[:, 1] - first[:, 0],
                                          first[:, 2] - first[:, 0]), axis=1)
    target_area = np.linalg.norm(np.cross(second[:, 1] - second[:, 0],
                                          second[:, 2] - second[:, 0]), axis=1)
    valid = source_area > 1e-9
    ratio = target_area[valid] / (source_area[valid] * bulk_scale**2)
    return {"normalized_area_p01": float(np.quantile(ratio, .01)),
            "normalized_area_median": float(np.median(ratio)),
            "faces_under_tenth_expected_area": int(np.count_nonzero(ratio < .1)),
            "source_nondegenerate_faces": int(valid.sum())}


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    out = ROOT / "artifacts/clothing_audit"
    preview = "--preview" in sys.argv
    radius_args = [arg for arg in sys.argv[1:] if arg.startswith("--radius=")]
    radius_factor = float(radius_args[-1].split("=", 1)[1]) if radius_args else 2.0
    radius_label = f"{radius_factor:g}".replace(".", "p")
    selected = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or ASSETS
    if preview:
        body, body_faces = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report = {}
    for asset in selected:
        vertices, mesh_faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        baseline, _ = retarget_garment_with_wrap_layer(
            engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        shell, influence = transfer_outer_cage_radial(
            trace["reference_parent"], trace["outer_parent"], trace["target_body"],
            trace["projection_faces"], parity=trace["cage_normal_sign"],
            radius_factor=radius_factor, return_audit=True)
        projected = remap_visible(trace, shell)
        prism, prism_audit = bind_dual_cage(vertices, trace, shell)
        outputs = {"baseline": baseline, "projected": projected, "prism": prism}
        report[asset] = {
            "influences": influence,
            "shell_stretch": _cage_edge_stretch(trace["outer_parent"], shell,
                                                 trace["projection_faces"]),
            "shell_change_p99": float(np.quantile(np.linalg.norm(
                shell - trace["reference_order_target_outer"], axis=1), .99)),
            "source_prism_distance_p99": prism_audit["source_prism_distance_p99"],
        }
        for label, fitted in outputs.items():
            report[asset][label] = {
                "edges": edges_report(vertices, fitted, mesh_faces),
                "face_changes_vs_baseline": face_change_report(mesh_faces, baseline, fitted),
                "area_vs_source": area_report(vertices, fitted, mesh_faces, influence["bulk_scale"]),
            }
        if preview:
            shared = np.vstack(list(outputs.values()))
            for label, fitted in outputs.items():
                path = out / f"radial_shell_{radius_label}_{asset}_{label}.png"
                report[asset][label]["visibility"] = depth_preview(
                    body, body_faces, fitted, mesh_faces, path,
                    shared_garment_vertices=shared)
                report[asset][label]["image"] = str(path.relative_to(ROOT))
    path = out / f"WRAP_RADIAL_SHELL_{radius_label}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({asset: {
        "baseline": row["baseline"]["edges"]["over_3x"],
        "projected": row["projected"]["edges"]["over_3x"],
        "prism": row["prism"]["edges"]["over_3x"],
        "multiple_influence_vertices": row["influences"]["outer_vertices_with_multiple_influences"],
        "prism_face_changes": row["prism"]["face_changes_vs_baseline"]["normal_reversed"],
        "prism_faces_under_tenth_area": row["prism"]["area_vs_source"]["faces_under_tenth_expected_area"],
    } for asset, row in report.items()}, indent=2))


if __name__ == "__main__":
    main()
