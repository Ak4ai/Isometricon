"""Build a catalog sample of layered clothing grouped by shape, from Roblox catalog keyword searches.

Usage: python scripts/build_catalog_sample.py [name] [per_group]   (default: formatos 5)
Output: artifacts/roblox_ground_truth/<name>_sample.json ({group: [asset ids]}), the input of
robustness_catalog.py. Shoe bundles are expanded into their left and right shoe assets.
"""
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "artifacts/roblox_ground_truth"

# Catalog subcategory ids: 58 T-shirts, 59 shirts, 60 pants, 61 jackets, 62 sweaters,
# 63 shorts, 64 shoe bundles, 65 dresses and skirts.
GROUPS = {
    "Sapatos": [(64, "sneakers"), (64, "boots"), (64, "heels"), (64, "fur boots"), (64, "platform")],
    "Saias e vestidos longos": [(65, "ball gown"), (65, "long dress"), (65, "slit skirt"), (65, "maxi skirt"),
                                (65, "wedding dress")],
    "Casacos compridos e capas": [(61, "trench coat"), (61, "long coat"), (61, "cape"), (61, "lab coat"),
                                  (61, "cloak")],
    "Largas e fofas": [(61, "puffer jacket"), (62, "oversized hoodie"), (60, "cargo pants"), (60, "baggy jeans"),
                       (61, "puffer vest")],
    "Pedaços soltos": [(60, "chains"), (59, "suspenders"), (60, "belt"), (65, "bow"), (59, "harness")],
    "Mínimas e recortes": [(58, "crop top"), (58, "tube top"), (60, "tights"), (60, "leg warmers"), (59, "cutout")],
}


def get_json(url):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            time.sleep(2 + 3 * attempt)  # the catalog rate-limits bursts
    return {}


def search(subcategory, keyword, limit=10):
    query = urllib.parse.urlencode({"Category": 3, "Subcategory": subcategory, "Keyword": keyword,
                                    "Limit": limit, "SortType": 0})
    return get_json(f"https://catalog.roblox.com/v1/search/items/details?{query}").get("data", [])


def shoe_assets(bundle_id):
    details = get_json(f"https://catalog.roblox.com/v1/bundles/{bundle_id}/details")
    return [item["id"] for item in details.get("items", []) if item.get("type") == "Asset"][:2]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "formatos"
    per_group = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    known = set()
    for path in GT.glob("*_sample.json"):
        for ids in json.loads(path.read_text(encoding="utf-8")).values():
            known.update(str(i) for i in ids)
    sample = {}
    for group, queries in GROUPS.items():
        chosen = []
        for subcategory, keyword in queries:
            for item in search(subcategory, keyword):
                if subcategory == 64:
                    if item.get("itemType") != "Bundle":
                        continue
                    ids = [str(i) for i in shoe_assets(item["id"])]
                else:
                    ids = [str(item["id"])] if item.get("itemType") == "Asset" else []
                if ids and not known.intersection(ids):
                    chosen.extend(ids)
                    known.update(ids)
                    print(f"{group} | {keyword}: {item.get('name')} -> {ids}", flush=True)
                    break
            time.sleep(1)
        sample[group] = chosen[:per_group * (2 if group == "Sapatos" else 1)]
    (GT / f"{name}_sample.json").write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
    print({group: len(ids) for group, ids in sample.items()})


if __name__ == "__main__":
    main()
