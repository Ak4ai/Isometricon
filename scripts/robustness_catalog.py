"""Download a sample of catalog layered clothing and run it through the female WrapLayer pipeline.

No Roblox ground truth here: this measures robustness (download, cage formats,
WrapLayer acceptance, radial + prism fit, HSR) on garments never tested before.
Usage: python scripts/robustness_catalog.py [name]   (default name: catalog)
Input: artifacts/roblox_ground_truth/<name>_sample.json ({subcategory: [asset ids]}).
Output: artifacts/roblox_ground_truth/<name>_robustness.json
"""
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.clothing.hsr import hidden_body_cage_mask
from src.clothing.radial_prism_fit import fit_radial_prism
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import _unique_uv_positions, read_wrap_layer, retarget_garment_with_wrap_layer

GT = ROOT / "artifacts/roblox_ground_truth"
CLOTHING = ROOT / "assets/models/clothing"


def cage_format(mesh_id):
    obj = CLOTHING / "wrap_cages" / f"{mesh_id}.obj"
    return obj.open(encoding="utf-8", errors="ignore").readline().replace("# Roblox Converted", "").strip() if obj.exists() else "?"


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "catalog"
    sample = json.loads((GT / f"{name}_sample.json").read_text())
    engine = RobloxWearEngine(body_type="female")
    _, cage_positions = _unique_uv_positions(engine.r15_female_cages)
    results = {}
    for category, ids in sample.items():
        for asset in ids:
            row = {"categoria": category}
            try:
                meta = engine.fetch_asset(asset)
                row.update(nome=meta["name"], type_id=meta["type_id"])
                verts, faces, _, _ = engine.load_obj(meta["obj_path"])
                row["malha"] = {"vertices": int(len(verts)), "faces": int(len(faces)),
                                "formato": open(meta["obj_path"], encoding="utf-8", errors="ignore").readline().strip()}
                wrap = read_wrap_layer(meta["rbxm_path"])
                trace = {}
                t0 = time.perf_counter()
                _, info = retarget_garment_with_wrap_layer(engine, verts, meta["rbxm_path"], CLOTHING / "wrap_cages",
                                                           binding_audit=trace)
                row["cages"] = {"referencia": cage_format(wrap["reference_id"]), "externa": cage_format(wrap["cage_id"])}
                row["validacao"] = {k: round(float(info[k]), 3) for k in
                                    ("median_source_distance", "p99_source_distance", "outer_edge_stretch_p99")}
                accepted = info["outer_edge_stretch_p99"] <= 2.5 and info["median_source_distance"] <= 0.1
                row["aceita_pelo_validador_antigo"] = bool(accepted)
                fitted, audit = fit_radial_prism(verts, faces, trace)
                row["radial_prisma"] = {"ok": True, "pendurados": audit["hanging_vertices"],
                                        "finito": bool(np.isfinite(fitted).all())}
                row["tempo_s"] = round(time.perf_counter() - t0, 1)
                try:
                    hidden = hidden_body_cage_mask(meta["rbxm_path"], trace, len(cage_positions), CLOTHING / "hsr")
                    row["hsr"] = "sem HSR" if hidden is None else f"oficial ({int(hidden.sum())} pontos)"
                except ValueError as exc:
                    row["hsr"] = f"geometrico ({exc})"
            except Exception as exc:
                row["erro"] = f"{type(exc).__name__}: {exc}"
                row["onde"] = traceback.extract_tb(exc.__traceback__)[-1].name
            results[asset] = row
            print(asset, json.dumps(row, ensure_ascii=False), flush=True)
    (GT / f"{name}_robustness.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
