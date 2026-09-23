import os
import sys

base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.clothing.wear_engine import RobloxWearEngine

print("Initializing RobloxWearEngine for female body...")
engine = RobloxWearEngine(body_type="female")

assets = [
    (9240757332, "Knit Sweater"),
    (133331049150205, "Flannel Shirt"),
    (109837605892174, "Distressed Jeans"),
]

for asset_id, label in assets:
    print(f"\n==========================================")
    print(f"Wearing {label} ({asset_id})...")
    print(f"==========================================")
    res = engine.wear(asset_id)

    print(f"Result for {label}:")
    print(f"  OBJ exported: {res.get('output_obj')}")
    print(f"  Texture: {res.get('tex_path')}")
    print(f"  Is top: {res.get('is_top')}")
    if 'verts' in res:
        print(f"  Vertices: {len(res['verts'])}")


print("\nALL ASSETS WORN SUCCESSFULLY ON FEMALE UNIFIED CAGE!")
