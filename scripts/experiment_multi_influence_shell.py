"""Compare a topology-local multi-influence shell with the current fitter."""
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
from src.clothing.multi_influence_shell import transfer_outer_cage
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _cage_edge_stretch, retarget_garment_with_wrap_layer


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    out_dir = ROOT / "artifacts/clothing_audit"
    preview = "--preview" in sys.argv
    selected = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or ASSETS
    if preview:
        body, body_faces = load_body_for_preview(
            ROOT / "assets/models/character_female_clean_apose_stage2.obj")
    report = {}
    for asset in selected:
        garment, faces, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
        trace = {}
        baseline, _ = retarget_garment_with_wrap_layer(
            engine, garment, str(next(directory.glob(f"*_{asset}.rbxm"))),
            directory / "wrap_cages", binding_audit=trace)
        source = trace["reference_parent"]
        target = trace["target_body"]
        shell = transfer_outer_cage(source, trace["outer_parent"], target,
                                    trace["projection_faces"],
                                    parity=trace["cage_normal_sign"])
        fitted = remap_visible(trace, shell)
        prism, prism_audit = bind_dual_cage(garment, trace, shell)
        original_outer = trace["reference_order_target_outer"]
        report[asset] = {
            "baseline_edges": edges_report(garment, baseline, faces),
            "candidate_edges": edges_report(garment, fitted, faces),
            "face_changes_vs_baseline": face_change_report(faces, baseline, fitted),
            "baseline_shell_stretch": _cage_edge_stretch(trace["outer_parent"], original_outer,
                                                         trace["projection_faces"]),
            "candidate_shell_stretch": _cage_edge_stretch(trace["outer_parent"], shell,
                                                          trace["projection_faces"]),
            "shell_position_change_p99": float(np.quantile(np.linalg.norm(shell - original_outer, axis=1), .99)),
            "prism_edges": edges_report(garment, prism, faces),
            "prism_face_changes_vs_baseline": face_change_report(faces, baseline, prism),
            "prism_source_distance_p99": prism_audit["source_prism_distance_p99"],
        }
        if preview:
            shared = np.vstack((baseline, fitted, prism))
            for label, output in (("baseline", baseline), ("candidate", fitted),
                                  ("prism", prism)):
                path = out_dir / f"multi_influence_{asset}_{label}.png"
                depth_preview(body, body_faces, output, faces, path,
                              shared_garment_vertices=shared)
                report[asset][label + "_image"] = str(path.relative_to(ROOT))
    output = out_dir / "WRAP_MULTI_INFLUENCE_SHELL.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: {
        "baseline_edges_over_3x": value["baseline_edges"]["over_3x"],
        "candidate_edges_over_3x": value["candidate_edges"]["over_3x"],
        "changed_face_normals": value["face_changes_vs_baseline"]["normal_reversed"],
        "candidate_shell_stretch": value["candidate_shell_stretch"],
        "prism_edges_over_3x": value["prism_edges"]["over_3x"],
        "prism_changed_face_normals": value["prism_face_changes_vs_baseline"]["normal_reversed"],
    } for key, value in report.items()}, indent=2))


if __name__ == "__main__":
    main()
