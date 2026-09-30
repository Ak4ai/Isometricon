"""Test the radial shell and paired prism on an official Blocky R15 body."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.benchmark_wrap_frames import edges_report
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import (
    ASSET, CAGE_OBJ, DIRECTORY, FBX, depth_preview, export_outer_cages_obj,
    load_classic_body,
)
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def main():
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
    vertices, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{ASSET}.obj"))))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, vertices, str(next(DIRECTORY.glob(f"*_{ASSET}.rbxm"))),
        DIRECTORY / "wrap_cages", binding_audit=trace)
    shell, audit = transfer_outer_cage_radial(
        trace["reference_parent"], trace["outer_parent"], trace["target_body"],
        trace["projection_faces"], parity=trace["cage_normal_sign"],
        radius_factor=1.0, return_audit=True)
    candidate, prism_audit = bind_dual_cage(vertices, trace, shell)
    body, body_faces, _ = load_classic_body(FBX)
    out_dir = ROOT / "artifacts/clothing_audit"
    shared = np.vstack((baseline, candidate))
    report = {"asset": ASSET, "radial_influences": audit,
              "prism_source_distance_p99": prism_audit["source_prism_distance_p99"]}
    for label, fitted in (("baseline", baseline), ("candidate", candidate)):
        path = out_dir / f"radial_blocky_{ASSET}_{label}.png"
        report[label] = {"edges": edges_report(vertices, fitted, faces),
                         "visibility": depth_preview(body, body_faces, fitted, faces, path,
                                                     shared_garment_vertices=shared),
                         "image": str(path.relative_to(ROOT))}
    path = out_dir / "WRAP_RADIAL_BLOCKY.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"baseline_edges_over_3x": report["baseline"]["edges"]["over_3x"],
                      "candidate_edges_over_3x": report["candidate"]["edges"]["over_3x"],
                      "multiple_influence_vertices": audit["outer_vertices_with_multiple_influences"]},
                     indent=2))


if __name__ == "__main__":
    main()
