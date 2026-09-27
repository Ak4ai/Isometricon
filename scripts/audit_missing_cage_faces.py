"""Find garment inner-cage triangles missing from the paired outer cage."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer

engine = RobloxWearEngine(body_type="female")
directory = ROOT / "assets/models/clothing"
cache = directory / "wrap_cages"


def face_keys(uv, faces, canonical):
    distance = np.sum((uv[:, None, :] - canonical[None, :, :]) ** 2, axis=2)
    indices = distance.argmin(axis=1)
    return {tuple(sorted(int(indices[i]) for i in face)): index
            for index, face in enumerate(faces)}


for asset_id in sys.argv[1:] or ["114590471167431", "109837605892174"]:
    rbxm = next(directory.glob(f"*_{asset_id}.rbxm"))
    wrap = read_wrap_layer(rbxm)
    ref, ref_faces, ref_uv, _ = engine.load_obj(str(cache / (wrap["reference_id"] + ".obj")))
    outer, outer_faces, outer_uv, _ = engine.load_obj(str(cache / (wrap["cage_id"] + ".obj")))
    canonical = np.unique(np.round(ref_uv, 4), axis=0)
    ref_keys = face_keys(ref_uv, ref_faces, canonical)
    outer_keys = face_keys(outer_uv, outer_faces, canonical)
    print(asset_id, "inner_faces", len(ref_faces), "outer_faces", len(outer_faces),
          "missing", len(ref_keys.keys() - outer_keys.keys()),
          "extra", len(outer_keys.keys() - ref_keys.keys()))
    for key in list(ref_keys.keys() - outer_keys.keys())[:12] if "--verbose" in sys.argv else []:
        index = ref_keys[key]
        print(" missing_face", index, "center", np.asarray(ref)[ref_faces[index]].mean(axis=0).round(4), "uv_ids", key)
