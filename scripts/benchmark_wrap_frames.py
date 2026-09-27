"""Compare cage-frame algorithms on fixed catalog clothes and body cages."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from scripts.experimental_wrap_frames import affine_map, rotation_map, normalized_edges_map
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

ASSETS = (
    "133331049150205",  # shirt
    "72628400373948",   # bomber
    "109837605892174",  # jeans
    "114590471167431",  # dress
    "16185652164",      # oversized sweater
)


def edges_report(before, after, faces):
    edges = np.unique(np.sort(np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1), axis=0)
    source_length = np.linalg.norm(before[edges[:, 0]] - before[edges[:, 1]], axis=1)
    target_length = np.linalg.norm(after[edges[:, 0]] - after[edges[:, 1]], axis=1)
    good = source_length >= .01
    ratio = target_length[good] / source_length[good]
    return {"p99": float(np.quantile(ratio, .99)),
            "over_3x": int(np.count_nonzero(ratio > 3)),
            "edges": int(len(ratio))}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/benchmark_wrap_frames.py LABEL")
    label = sys.argv[1]
    if not label.isidentifier():
        raise ValueError("Label must be a simple identifier")
    variants = {
        "before": {}, "affine": {"_shell_transform": affine_map,
                                  "_mesh_transform": affine_map},
        "rotation": {"_shell_transform": rotation_map},
        "rotation_area": {"_shell_transform": rotation_map,
                          "_shell_area_weighted": True},
        "outer_topology": {"_use_authored_outer_faces": True},
        "normalized_edges": {"_shell_transform": normalized_edges_map,
                             "_shell_area_weighted": True},
        "normalized_bulk": {"_shell_transform": normalized_edges_map,
                            "_shell_area_weighted": True,
                            "_shell_bulk_scale": True},
        "rotation_bulk": {"_shell_transform": rotation_map,
                          "_shell_area_weighted": True,
                          "_shell_bulk_scale": True},
        "mesh_affine": {"_mesh_transform": affine_map},
        "mesh_rotation": {"_mesh_transform": rotation_map},
    }
    if label not in variants:
        raise ValueError(f"Unknown variant: {label}")
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    targets = {"female": engine.r15_female_cages,
               "blocky": load_r15_female_cages(
                   str(ROOT / "artifacts/clothing_audit/BlockyCharacter_OuterCages.obj"),
                   is_source_cage=True)}
    report = {}
    for body_name, cages in targets.items():
        engine.r15_female_cages = cages
        for asset in ASSETS if body_name == "female" else ASSETS[:1]:
            path = next(directory.glob(f"*_{asset}.obj"))
            vertices, faces, _, _ = engine.load_obj(str(path))
            try:
                fitted, info = retarget_garment_with_wrap_layer(
                    engine, vertices, str(next(directory.glob(f"*_{asset}.rbxm"))),
                    directory / "wrap_cages", **variants[label])
                report[f"{body_name}_{asset}"] = {
                    "mesh_edges": edges_report(vertices, fitted, faces),
                    "outer_p99": info["outer_edge_stretch_p99"],
                    "outer_over_3x": info["outer_edges_over_3x"],
                    "runtime_eligible": bool(info["median_source_distance"] <= .05 and
                                             info["p99_source_distance"] <= .2 and
                                             info["outer_edge_stretch_p99"] <= 2.5),
                }
            except Exception as exc:
                report[f"{body_name}_{asset}"] = {"error": str(exc)}
    output = ROOT / f"artifacts/clothing_audit/WRAP_FRAME_{label}.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
