"""Read-only compatibility matrix for cached Roblox layered clothes/cages."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer, retarget_garment_with_wrap_layer

directory = ROOT / "assets/models/clothing"
cache = directory / "wrap_cages"
engine = RobloxWearEngine(body_type="female")
records = []
for rbxm in sorted(directory.glob("*.rbxm")):
    try:
        wrap = read_wrap_layer(rbxm)
    except Exception:
        continue
    item = {"asset": rbxm.stem, "reference_id": wrap["reference_id"],
            "cage_id": wrap["cage_id"]}
    obj = rbxm.with_suffix(".obj")
    if not obj.exists():
        item["status"] = "visible_mesh_missing"
    elif not (cache / (wrap["reference_id"] + ".obj")).exists() or not (cache / (wrap["cage_id"] + ".obj")).exists():
        item["status"] = "cage_not_cached"
    else:
        try:
            verts, _, _, _ = engine.load_obj(str(obj))
            _, info = retarget_garment_with_wrap_layer(engine, verts, str(rbxm), cache)
            item.update(info)
            item["status"] = "accepted" if (
                info["median_source_distance"] <= .05 and
                info["p99_source_distance"] <= .2 and
                info["outer_edge_stretch_p99"] <= 2.5) else "quality_rejected"
        except Exception as exc:
            item["status"] = "incompatible"
            item["reason"] = str(exc)
    records.append(item)

out = ROOT / "artifacts/clothing_audit/CACHED_WRAP_COMPATIBILITY.json"
out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
for item in records:
    print(item["asset"], item["status"], item.get("reason", ""))
print("total", len(records))
