"""Verify this jeans fit reads current code and cached cage data, then moves the target cage in memory."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.import_roblox_clothing import decode_roblox_mesh_to_obj
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer
import src.clothing.wrap_layer_fit as wrap_module

OUT = ROOT / "artifacts/clothing_audit/female_jeans_runtime"
ASSET = "109837605892174"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads((OUT / "SUMMARY.json").read_text(encoding="utf-8"))
    loaded = np.load(OUT / "stages.npz")
    engine = RobloxWearEngine(body_type="female")
    result = {
        "loaded_module_path": str(Path(wrap_module.__file__).resolve()),
        "loaded_module_sha256": digest(wrap_module.__file__),
        "same_code_as_runtime_trace": digest(wrap_module.__file__)
        == summary["sha256"][str(Path("src/clothing/wrap_layer_fit.py"))],
        "cage_mesh_comparisons": {},
    }

    cache = ROOT / "assets/models/clothing/wrap_cages"
    for cage_id in (summary["wrap_metrics"]["reference_id"],
                    summary["wrap_metrics"]["cage_id"]):
        cached = cache / f"{cage_id}.obj"
        decoded = OUT / f"{cage_id}_decoded_from_mesh.obj"
        decode_roblox_mesh_to_obj((cache / f"{cage_id}.mesh").read_bytes(), str(decoded))
        old_verts, old_faces, old_uv, _ = engine.load_obj(str(cached))
        new_verts, new_faces, new_uv, _ = engine.load_obj(str(decoded))
        comparison = {
            "cached_obj_sha256": digest(cached),
            "decoded_obj_sha256": digest(decoded),
            "byte_identical": cached.read_bytes() == decoded.read_bytes(),
            "vertices_identical": np.array_equal(old_verts, new_verts),
            "faces_identical": np.array_equal(old_faces, new_faces),
            "uvs_identical": np.array_equal(old_uv, new_uv),
            "max_vertex_error": float(np.linalg.norm(old_verts - new_verts, axis=1).max()),
        }
        result["cage_mesh_comparisons"][cage_id] = comparison

    garment = loaded["raw_garment"]
    rbxm = next((ROOT / "assets/models/clothing").glob(f"*_{ASSET}.rbxm"))
    original, _ = retarget_garment_with_wrap_layer(engine, garment, str(rbxm), cache)
    result["baseline_vs_runtime_trace_max_error"] = float(
        np.linalg.norm(original - loaded["wrap_before_runtime_postprocess"], axis=1).max())
    # A uniform, in-memory displacement preserves UV seam equality and changes
    # only the destination cage. No project asset or clothing cache is edited.
    delta = np.array([0.01, 0.0, 0.0])
    for part in engine.body_cages.values():
        part["verts"] = np.asarray(part["verts"]) + delta
    changed, _ = retarget_garment_with_wrap_layer(engine, garment, str(rbxm), cache)
    displacement = changed - original
    result["target_cage_perturbation_m"] = delta.tolist()
    result["fit_change_min_m"] = float(np.linalg.norm(displacement, axis=1).min())
    result["fit_change_median_m"] = float(np.median(np.linalg.norm(displacement, axis=1)))
    result["fit_change_max_m"] = float(np.linalg.norm(displacement, axis=1).max())
    result["expected_translation_max_error_m"] = float(
        np.linalg.norm(displacement - delta, axis=1).max())
    (OUT / "CAGE_ACTIVITY.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
