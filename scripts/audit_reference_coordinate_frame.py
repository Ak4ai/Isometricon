"""Fit axis/scale/origin between each asset reference cage and canonical R15."""
from itertools import permutations, product
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import (
    _match_reference_to_body_uv, _unique_uv_positions, read_wrap_layer,
)


def fit_frames(source, target):
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    fits = []
    for order in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            oriented = source[:, order] * signs
            centered = oriented - oriented.mean(axis=0)
            dst_centered = target - target.mean(axis=0)
            scale = float(np.sum(centered * dst_centered) / np.sum(centered * centered))
            if scale <= 0:
                continue
            translation = target.mean(axis=0) - scale * oriented.mean(axis=0)
            error = np.linalg.norm(scale * oriented + translation - target, axis=1)
            fits.append((float(np.median(error)), order, signs, scale, translation,
                         float(np.quantile(error, .95)), float(error.max())))
    return min(fits, key=lambda fit: fit[0])


def audit(engine, asset_id):
    directory = ROOT / "assets/models/clothing"
    wrap = read_wrap_layer(next(directory.glob(f"*_{asset_id}.rbxm")))
    reference, _, uv, _ = engine.load_obj(str(directory / "wrap_cages" / (wrap["reference_id"] + ".obj")))
    body_uv, body_position = _unique_uv_positions(engine.r15_source_cages)
    matched = _match_reference_to_body_uv(uv, body_uv)
    rotation, translation = wrap["reference_origin"]
    parent = np.asarray(reference) @ rotation.T + translation
    median, order, signs, scale, offset, p95, maximum = fit_frames(parent, body_position[matched])
    print(asset_id, {"order": order, "signs": signs, "scale": scale,
                     "translation": offset.round(5).tolist(), "median_m": median,
                     "p95_m": p95, "max_m": maximum})


if __name__ == "__main__":
    engine = RobloxWearEngine(body_type="female")
    for item in sys.argv[1:] or ("114590471167431", "109837605892174"):
        audit(engine, item)
