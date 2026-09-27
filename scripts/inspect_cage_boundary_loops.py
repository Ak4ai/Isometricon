"""Inspect temporary source outer-cage boundary loops before capping."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer
from src.clothing.volumetric_cage import _oriented_boundary_loops, _stitch_uv_boundary_edges, _triangulate_loop

engine = RobloxWearEngine(body_type="female")
directory = ROOT / "assets/models/clothing"
cache = directory / "wrap_cages"
for asset in sys.argv[1:] or ["109837605892174", "133331049150205", "72628400373948", "16899958482"]:
    wrap = read_wrap_layer(next(directory.glob(f"*_{asset}.rbxm")))
    vertices, faces, uv, _ = engine.load_obj(str(cache / (wrap["cage_id"] + ".obj")))
    vertices = np.asarray(vertices, dtype=float)
    faces = np.asarray(faces, dtype=int)
    inverse = _stitch_uv_boundary_edges(vertices, vertices, faces, np.asarray(uv), 5, .005)
    count = np.bincount(inverse)
    positions = np.stack([np.bincount(inverse, weights=vertices[:, axis]) / count
                          for axis in range(3)], axis=1)
    loops = _oriented_boundary_loops(inverse[faces])
    print(asset, "loops", [len(loop) for loop in loops])
    for loop in loops:
        points = positions[loop]
        center = points.mean(axis=0)
        _, _, basis = np.linalg.svd(points - center, full_matrices=False)
        plane_error = np.abs((points - center) @ basis[2]).max()
        flat = (points - center) @ basis[:2].T
        try:
            triangles, _ = _triangulate_loop(positions, loop)
            status = f"ok:{len(triangles)}"
        except Exception as exc:
            status = str(exc)
        print(" ", len(loop), "center", center.round(3), "plane_error", round(float(plane_error), 5), status)
        if status.startswith("Contorno"):
            print("   flat", np.round(flat, 4).tolist())
