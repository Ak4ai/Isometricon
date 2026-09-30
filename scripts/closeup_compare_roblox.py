"""Zoomed side-by-side of Roblox Studio vs our fits for selected garments.

Usage: python scripts/closeup_compare_roblox.py [case names from batch_compare_roblox.CASES]
Rows per garment: Roblox (gray), each method (blue), each method's distance heat map.
"""
import glob
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.batch_compare_roblox import CASES, GT
from scripts.compare_roblox_ground_truth import STUD_CM, align_studio_to_engine, heat_color, load_obj_groups, render_row
from scripts.experiment_adaptive_prism_roblox import shells
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.wear_engine import RobloxWearEngine, load_r15_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

METHODS = ("radial 1x (so local)", "radial<->global por combined")


def main():
    names = sys.argv[1:] or ["saia-short", "regata", "calca skater", "biquini"]
    body, body_faces, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.body_cages = load_r15_cages(str(CAGE_OBJ), is_source_cage=True)
    skin = (body, body_faces, np.tile([218, 187, 164], (len(body_faces), 1)))
    for case in names:
        asset, export = CASES[case]
        groups = load_obj_groups(export)
        roblox_raw, faces, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, all_faces, _, _ = engine.load_obj(next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj"))
                                                       if "fitted" not in p))
        keep = np.unique(all_faces[:len(faces)])
        trace = {}
        retarget_garment_with_wrap_layer(engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))),
                                         DIRECTORY / "wrap_cages", binding_audit=trace)
        outers = shells(trace)
        lo, hi = roblox.min(0), roblox.max(0)
        pad = 0.25 * (hi - lo).max()
        bounds = (lo - pad, hi + pad)
        rows = [("Roblox Studio", render_row([skin, (roblox, faces, np.tile([95, 95, 95], (len(faces), 1)))], bounds))]
        for label in METHODS:
            fitted = bind_dual_cage(source, trace, outers[label])[0][keep]
            distance = np.linalg.norm(fitted - roblox, axis=1)
            rows.append((f"nosso: {label}", render_row([skin, (fitted, faces, np.tile([45, 95, 165], (len(faces), 1)))], bounds)))
            rows.append((f"nosso: {label} | distancia ao Roblox (azul 0 -> vermelho >= 7 cm), mediana "
                         f"{np.median(distance) * STUD_CM:.1f} cm",
                         render_row([(fitted, faces, heat_color(distance[faces].mean(1), .25))], bounds)))
        canvas = Image.new("RGB", (rows[0][1].width, sum(r.height + 24 for _, r in rows)), "white")
        y = 0
        for title, row in rows:
            ImageDraw.Draw(canvas).text((8, y + 6), f"{case} | {title}", fill="black")
            canvas.paste(row, (0, y + 24))
            y += row.height + 24
        path = GT / f"closeup_{case.replace(' ', '_')}.png"
        canvas.save(path)
        print(path, flush=True)


if __name__ == "__main__":
    main()
