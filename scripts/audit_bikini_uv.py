"""Measure why the cached bikini cages fail standard R15 UV matching."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _unique_uv_positions

engine = RobloxWearEngine(body_type="female")
directory = ROOT / "assets/models/clothing/wrap_cages"
reference, faces, ref_uv, _ = engine.load_obj(str(directory / "82250283136857.obj"))
outer, outer_faces, outer_uv, _ = engine.load_obj(str(directory / "97841210530386.obj"))
body_uv, _ = _unique_uv_positions(engine.body_cages)


def compare(name, query, keys):
    unique = np.unique(np.round(query, 5), axis=0)
    distance = np.linalg.norm(unique[:, None, :] - keys[None, :, :], axis=2)
    best = distance.min(axis=1)
    print(name, "unique_uv", len(unique), "max", float(best.max()),
          "over_0.0002", int(np.count_nonzero(best > .0002)),
          "over_0.001", int(np.count_nonzero(best > .001)))
    for index in np.argsort(best)[-8:][::-1]:
        print("  uv", unique[index], "distance", round(float(best[index]), 6))


print("reference vertices/faces", len(reference), len(faces))
print("outer vertices/faces", len(outer), len(outer_faces))
compare("reference -> body", ref_uv, body_uv)
compare("reference -> outer", ref_uv, outer_uv)
compare("outer -> body", outer_uv, body_uv)
