"""Test WrapLayer against its own reference cage in a known rotated frame."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer, retarget_garment_with_wrap_layer


def rotate(points):
    points = np.asarray(points, dtype=np.float64)
    return points[:, [0, 2, 1]] * np.array([1, -1, 1])


def audit(engine, asset_id):
    directory = ROOT / "assets/models/clothing"
    wrap_path = next(directory.glob(f"*_{asset_id}.rbxm"))
    garment, _, _, _ = engine.load_obj(str(next(directory.glob(f"*_{asset_id}.obj"))))
    wrap = read_wrap_layer(wrap_path)
    reference, faces, uv, _ = engine.load_obj(str(directory / "wrap_cages" / (wrap["reference_id"] + ".obj")))
    ref_rotation, ref_origin = wrap["reference_origin"]
    parent = np.asarray(reference) @ ref_rotation.T + ref_origin
    engine.body_cages = {"Reference": {
        "verts": rotate(parent), "faces": faces, "face_uvs": uv[faces],
    }}
    trace = {}
    output, fit = retarget_garment_with_wrap_layer(
        engine, garment, str(wrap_path), directory / "wrap_cages", binding_audit=trace)
    outer_expected = rotate(trace["outer_parent"])
    # The visible OBJ is already in the mesh parent's frame; only the cage
    # vertices need CageOrigin applied to reach that frame.
    garment_expected = rotate(garment)
    outer_error = np.linalg.norm(trace["target_outer"] - outer_expected, axis=1)
    garment_error = np.linalg.norm(output - garment_expected, axis=1)
    if outer_error.max() > 1e-5 or garment_error.max() > 1e-5:
        raise AssertionError(f"Identity wrap failed for {asset_id}: "
                             f"outer={outer_error.max():.6g}, garment={garment_error.max():.6g}")
    print(asset_id, {"outer_max_m": float(outer_error.max()),
                     "outer_p99_m": float(np.quantile(outer_error, .99)),
                     "garment_max_m": float(garment_error.max()),
                     "garment_p99_m": float(np.quantile(garment_error, .99)),
                     "fit": fit})


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    original = engine.body_cages
    for item in sys.argv[1:] or ("114590471167431", "109837605892174"):
        audit(engine, item)
        engine.body_cages = original
