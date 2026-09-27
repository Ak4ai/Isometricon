"""Score the main fitting candidates against every Roblox Studio export in one run.

Usage: python scripts/batch_compare_roblox.py

Studio exports only the highest LOD, so our catalog mesh is cut to the faces
Studio kept and its vertices compacted the same way before comparing.
"""
import glob
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_roblox_globalness import regions
from scripts.compare_roblox_ground_truth import (
    STUD_CM, align_studio_to_engine, heat_color, load_obj_groups, render_row, winding_inside)
from scripts.experiment_adaptive_prism_roblox import shells
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.sweep_radial_radius_roblox import score
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

EXPORTS = Path("C:/Users/Henrique/Pictures/testesroblox")
GT = ROOT / "artifacts/roblox_ground_truth"
CASES = {
    "vestido": ("114590471167431", EXPORTS / "blockyvestido.obj"),
    "jeans com bota": ("109837605892174", EXPORTS / "blockyjeans.obj"),
    "camisa social": ("133331049150205", GT / "blocky_shirt_133331049150205.obj"),
    "jaqueta bomber": ("72628400373948", EXPORTS / "jaqueta.obj"),
    "sueter oversized": ("16185652164", EXPORTS / "sueter oversized tricot.obj"),
    "saia-short": ("132042528605488", EXPORTS / "saia.obj"),
    "calca skater": ("137146416353285", EXPORTS / "calcaskater.obj"),
    "calca cargo": ("16899958482", EXPORTS / "calcarosa.obj"),
    "regata": ("137915688957785", EXPORTS / "regaa.obj"),
    "biquini": ("96314281401899", EXPORTS / "bikini.obj"),
}
METHODS = ("runtime atual", "radial 1x (so local)", "global (so global)", "radial<->global por combined")


def main():
    body, body_faces, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    report, rows = {}, []
    for case, (asset, export) in CASES.items():
        groups = load_obj_groups(export)
        roblox_raw, roblox_faces, _ = groups.pop("Handle1")
        error, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source_path = next(p for p in glob.glob(str(DIRECTORY / f"*_{asset}.obj")) if "fitted" not in p)
        source, faces, _, _ = engine.load_obj(source_path)
        keep, inverse = np.unique(faces[:len(roblox_faces)], return_inverse=True)
        lod0_faces = inverse.reshape(-1, 3)
        entry = {"alinhamento_stud": round(float(error), 6), "lods_extras_no_nosso_obj": int(len(faces) - len(roblox_faces)),
                 "topologia_igual": bool(len(keep) == len(roblox)
                                         and np.array_equal(np.sort(lod0_faces, 1), np.sort(roblox_faces, 1)))}
        try:
            trace = {}
            runtime, _ = retarget_garment_with_wrap_layer(
                engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))), DIRECTORY / "wrap_cages",
                binding_audit=trace)
        except Exception as exc:  # A garment the runtime rejects is itself a result.
            entry["erro"] = f"{type(exc).__name__}: {exc}"
            report[case] = entry
            print(case, entry, flush=True)
            continue
        masks = regions(roblox, (roblox[:, 2].min(), roblox[:, 2].max()))
        garment_source = trace["source_vertices"][keep]
        entry["Roblox dentro do corpo %"] = round(float(winding_inside(roblox, body, body_faces).mean() * 100), 1)
        fitted = {"runtime atual": runtime}
        for label, outer in shells(trace).items():
            if label in METHODS:
                fitted[label] = bind_dual_cage(source, trace, outer)[0]
        for label in METHODS:
            entry[label] = score(fitted[label][keep], roblox, lod0_faces, garment_source, masks)
        report[case] = entry
        print(case, json.dumps(entry, ensure_ascii=False), flush=True)
        for label in ("radial 1x (so local)", "radial<->global por combined"):
            distance = np.linalg.norm(fitted[label][keep] - roblox, axis=1)
            rows.append((f"{case} | {label}", render_row(
                [(body, body_faces, np.tile([218, 187, 164], (len(body_faces), 1))),
                 (fitted[label][keep], lod0_faces, heat_color(distance[lod0_faces].mean(1), .25))],
                (body.min(0), body.max(0)))))
    (GT / "batch_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for start in range(0, len(rows), 8):
        chunk = rows[start:start + 8]
        canvas = Image.new("RGB", (chunk[0][1].width, sum(r.height + 24 for _, r in chunk)), "white")
        y = 0
        for title, row in chunk:
            ImageDraw.Draw(canvas).text((8, y + 6), title + "  (azul 0 -> vermelho >= 7 cm do Roblox)", fill="black")
            canvas.paste(row, (0, y + 24))
            y += row.height + 24
        canvas.save(GT / f"heatmap_lote_{start // 8 + 1}.png")


if __name__ == "__main__":
    main()
