"""Compare a continuous cage field against triangle binding on official Blocky."""
from pathlib import Path
import json

import numpy as np

from scripts.experiment_wrap_mls import weighted_affine
from scripts.experiment_wrap_binding import optimize_bindings
from scripts.inspect_classic_mannequin_fbx import export_outer_cages_obj, load_classic_body
from scripts.test_r15_shirt_transfer import ROOT, FBX, CAGE_OBJ, DIRECTORY, ASSET, depth_preview, edge_metrics
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer


def main():
    engine = RobloxWearEngine(body_type="female")
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    garment, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{ASSET}.obj"))))
    trace = {}
    baseline, _ = retarget_garment_with_wrap_layer(
        engine, garment, str(next(DIRECTORY.glob(f"*_{ASSET}.rbxm"))),
        DIRECTORY / "wrap_cages", binding_audit=trace)
    body, body_faces, _ = load_classic_body(FBX)
    source_engine = np.asarray(garment)[:, [0, 2, 1]] * [1, -1, 1]
    report = {"baseline": edge_metrics(source_engine, baseline, faces)}
    coherent, _, changes = optimize_bindings(garment, faces, trace)
    coherent_image = ROOT / "artifacts/clothing_audit/blocky_coherent_binding_depth.png"
    report["coherent_binding"] = {
        "edges": edge_metrics(source_engine, coherent, faces),
        "visibility": depth_preview(body, body_faces, coherent, faces, coherent_image),
        "changes_by_round": changes,
        "image": str(coherent_image.relative_to(ROOT)),
    }
    for neighbours in (8, 16, 32):
        result = weighted_affine(trace["source_outer"], trace["target_outer"],
                                 trace["source_vertices"], neighbours=neighbours)
        output = ROOT / f"artifacts/clothing_audit/blocky_continuous_{neighbours}_depth.png"
        visibility = depth_preview(body, body_faces, result, faces, output)
        report[str(neighbours)] = {"edges": edge_metrics(source_engine, result, faces),
                                   "visibility": visibility, "image": str(output.relative_to(ROOT))}
    output = ROOT / "artifacts/clothing_audit/blocky_continuous_field.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
