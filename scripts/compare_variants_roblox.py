"""Score the archived wrap experiments against Roblox Studio exports on the Blocky.

Usage: python scripts/compare_variants_roblox.py

Every variant starts from the same runtime trace; only the step the
experiment changed differs. Distances are per vertex against the garment
Roblox placed on the same Blocky (identical vertex order).
"""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.compare_roblox_ground_truth import (
    STUD_CM, align_studio_to_engine, edge_ratio, heat_color, load_obj_groups, render_row)
from scripts.experiment_dual_cage_prism import bind_dual_cage
from scripts.experiment_inner_reference_binding import bind_visible_to_inner
from scripts.experiment_shell_adaptive import shell_weights
from scripts.experiment_shell_global_affine import global_shell, remap_visible
from scripts.test_r15_shirt_transfer import CAGE_OBJ, DIRECTORY, FBX, export_outer_cages_obj, load_classic_body
from src.clothing.experimental_refined_reference import RefinedReferenceField
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

GT = ROOT / "artifacts/roblox_ground_truth"
CASES = {
    "vestido": ("114590471167431", GT / "blocky_dress_114590471167431.obj"),
    "jeans": ("109837605892174", Path("C:/Users/Henrique/Pictures/testesroblox/blockyjeans.obj")),
    "camisa": ("133331049150205", GT / "blocky_shirt_133331049150205.obj"),
}


def variants(engine, source, asset):
    trace = {}
    runtime, _ = retarget_garment_with_wrap_layer(
        engine, source, str(next(DIRECTORY.glob(f"*_{asset}.rbxm"))), DIRECTORY / "wrap_cages", binding_audit=trace)
    out = {"runtime atual": runtime}
    radial = transfer_outer_cage_radial(trace["reference_parent"], trace["outer_parent"], trace["target_body"],
                                        trace["projection_faces"], parity=trace["cage_normal_sign"], radius_factor=1.0)
    out["radial + prisma"] = bind_dual_cage(source, trace, radial)[0]
    global_outer, _ = global_shell(trace)
    out["cage global"] = remap_visible(trace, global_outer)
    weight = shell_weights(trace)["combined"][:, None]
    out["cage adaptativa"] = remap_visible(
        trace, trace["reference_order_target_outer"] * (1 - weight) + global_outer * weight)
    out["cage global + prisma"] = bind_dual_cage(source, trace, global_outer)[0]
    out["vinculo na cage interna"] = bind_visible_to_inner(source, trace)[0]
    for level in (0, 2):
        field = RefinedReferenceField(trace["reference_parent"], trace["target_body"], trace["projection_faces"],
                                      trace["uv_index"], int(trace["cage_normal_sign"]), level)
        out[f"referencia refinada L{level}"] = field.evaluate(trace["source_vertices"])
    return out


def main():
    body, body_faces, _ = load_classic_body(FBX)
    export_outer_cages_obj(FBX, CAGE_OBJ)
    engine = RobloxWearEngine(body_type="female")
    engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
    report = {}
    for case, (asset, export) in CASES.items():
        groups = load_obj_groups(export)
        roblox_raw, _, _ = groups.pop("Handle1")
        _, matrix, shift = align_studio_to_engine(np.vstack([g[0] for g in groups.values()]), body)
        roblox = roblox_raw @ matrix.T + shift
        source, faces, _, _ = engine.load_obj(str(next(DIRECTORY.glob(f"*_{asset}.obj"))))
        # Lower third of the garment as Roblox placed it (skirt hem / trouser cuffs / shirt hem).
        low, high = roblox[:, 2].min(), roblox[:, 2].max()
        hem = roblox[:, 2] < low + (high - low) / 3
        report[case] = {}
        rows = []
        for label, fitted in variants(engine, source, asset).items():
            distance = np.linalg.norm(fitted - roblox, axis=1) * STUD_CM
            ratio = edge_ratio(roblox, fitted, faces)
            report[case][label] = {
                "median_cm": round(float(np.median(distance)), 2),
                "p90_cm": round(float(np.quantile(distance, .9)), 2),
                "over_5cm_pct": round(float((distance > 5).mean() * 100), 1),
                "hem_median_cm": round(float(np.median(distance[hem])), 2),
                "hem_over_5cm_pct": round(float((distance[hem] > 5).mean() * 100), 1),
                "edges_over_3x": int((ratio > 3).sum()),
            }
            if case == "vestido":
                colors = heat_color(distance[faces].mean(1) / STUD_CM, 0.25)
                rows.append((label, render_row([(fitted, faces, colors)], (body.min(0), body.max(0)))))
            print(case, label, report[case][label], flush=True)
        if rows:
            canvas = Image.new("RGB", (rows[0][1].width, sum(r.height + 24 for _, r in rows)), "white")
            y = 0
            for title, row in rows:
                ImageDraw.Draw(canvas).text((8, y + 6), f"{title}: distancia ao Roblox (azul 0 -> vermelho >= 7 cm)", fill="black")
                canvas.paste(row, (0, y + 24))
                y += row.height + 24
            canvas.save(GT / "heatmap_vestido_variantes.png")
    (GT / "variants_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
