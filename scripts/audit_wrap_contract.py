"""Audit deformation contracts using cached assets, without altering runtime."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import read_wrap_layer, retarget_garment_with_wrap_layer, _local_map


def errors(actual, expected):
    d = np.linalg.norm(actual - expected, axis=1)
    return {"max": float(d.max()), "p99": float(np.quantile(d, .99)),
            "rms": float(np.sqrt(np.mean(d * d)))}


def main():
    engine = RobloxWearEngine(body_type="female")
    directory = ROOT / "assets/models/clothing"
    asset = "133331049150205"
    rbxm = next(directory.glob(f"*_{asset}.rbxm"))
    garment, _, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset}.obj"))))
    wrap = read_wrap_layer(rbxm)
    ref, faces, uv, face_uv = engine.load_obj(str(directory / "wrap_cages" / (wrap["reference_id"] + ".obj")))
    rotation, translation = wrap["reference_origin"]
    reference = ref @ rotation.T + translation
    controls = {}
    for name, matrix in {
        "identity": np.eye(3),
        "rotation": np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]]),
        "reflection": np.diag([1., -1., 1.]),
        "scale_2": np.eye(3) * 2,
    }.items():
        engine.r15_female_cages = {"Control": {
            "verts": reference @ matrix.T, "faces": faces, "face_uvs": uv[face_uv]}}
        trace = {}
        output, _ = retarget_garment_with_wrap_layer(engine, garment, str(rbxm), directory / "wrap_cages", trace)
        controls[name] = {"outer": errors(trace["target_outer"], trace["outer_parent"] @ matrix.T),
                          "garment": errors(output, garment @ matrix.T)}

    source = np.array([[0., 0., 0.], [1., 0., 0.], [.2, 1., 0.]])
    target = np.array([[0., 0., 0.], [1., 0., 0.], [.9, 1., 0.]])
    maps = [_local_map(*np.roll(source, i, axis=0), *np.roll(target, i, axis=0)) for i in range(3)]
    permutation_difference = max(float(np.linalg.norm(m - maps[0])) for m in maps)

    cage_path = ROOT / "artifacts/clothing_audit/BlockyCharacter_OuterCages.obj"
    engine.r15_female_cages = load_r15_female_cages(str(cage_path), is_source_cage=True)
    trace = {}
    _, fit = retarget_garment_with_wrap_layer(engine, garment, str(rbxm), directory / "wrap_cages", trace)
    parts_by_uv = {tuple(np.round(u, 5)): name for name, part in engine.r15_female_cages.items()
                   if not name.endswith("Forearm") for u in part["face_uvs"].reshape(-1, 2)}
    labels = np.array([parts_by_uv[tuple(trace["target_uv"][i])] for i in trace["uv_index"]])
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    before = np.linalg.norm(reference[edges[:, 0]] - reference[edges[:, 1]], axis=1)
    after = np.linalg.norm(trace["target_body"][edges[:, 0]] - trace["target_body"][edges[:, 1]], axis=1)
    selected = trace["projection_faces"][trace["face_indices"]]
    per_part = {}
    for name in np.unique(labels):
        valid = (labels[edges[:, 0]] == name) & (labels[edges[:, 1]] == name) & (before >= .01)
        ratio = after[valid] / before[valid]
        per_part[str(name)] = {"edge_p99": float(np.quantile(ratio, .99)) if len(ratio) else None,
                              "bound_garment_vertices": int(np.count_nonzero(labels[selected[:, 0]] == name))}
    # A positional field cannot map one input location to two different outputs.
    _, groups = np.unique(np.round(trace["source_outer"], 5), axis=0, return_inverse=True)
    counts = np.bincount(groups)
    centers = np.stack([np.bincount(groups, weights=trace["target_outer"][:, i]) / counts for i in range(3)], axis=1)
    spread = np.zeros(len(counts))
    np.maximum.at(spread, groups, np.linalg.norm(trace["target_outer"] - centers[groups], axis=1))
    report = {"units": "native asset coordinates, not asserted to be metres",
              "controls": controls, "cyclic_triangle_map_difference": permutation_difference,
              "blocky_per_part": per_part,
              "blocky_coincident_source_outer_targets": {"max_spread": float(spread.max()),
                  "groups_over_0_01": int(np.count_nonzero(spread > .01))}, "blocky_fit": fit}
    out = ROOT / "artifacts/clothing_audit/WRAP_CONTRACT_AUDIT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
