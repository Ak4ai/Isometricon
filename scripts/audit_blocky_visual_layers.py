"""Bound the visual effect of body occlusion on the frozen Blocky shirt.

Rendering without body triangles is an upper bound, not a reproduction of
Roblox's precomputed hidden-surface-removal mask.
"""
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.test_r15_shirt_transfer import depth_preview

SOURCE = ROOT / "artifacts/clothing_audit/radial_frames"
OUT = ROOT / "artifacts/clothing_audit/blocky_visual_layers"
CASE = "blocky_133331049150205"


def main():
    OUT.mkdir(exist_ok=True)
    data = np.load(SOURCE / f"{CASE}.npz")
    outputs = np.load(SOURCE / f"{CASE}_outputs.npz")
    garment = outputs["radial_previous"]
    body, body_faces = data["body"], data["body_faces"]
    garment_faces = data["garment_faces"]
    versions = (("full_body", body_faces),
                ("no_body_triangles", np.empty((0, 3), dtype=int)))
    coverage, panels = {}, []
    for label, triangles in versions:
        path = OUT / f"{label}.png"
        coverage[label] = depth_preview(body, triangles, garment, garment_faces,
                                        path, shared_garment_vertices=garment)
        panels.append(Image.open(path).convert("RGB"))
    sheet = Image.new("RGB", (panels[0].width, sum(p.height + 25 for p in panels)), "white")
    y = 0
    for (label, _), panel in zip(versions, panels):
        ImageDraw.Draw(sheet).text((8, y + 4), label, fill="black")
        sheet.paste(panel, (0, y + 25))
        y += panel.height + 25
    sheet.save(OUT / "comparison.png")
    report = {"method": "all body triangles vs none; no HSR data decoded",
              "mesh_unchanged": True, "coverage": coverage}
    (OUT / "SUMMARY.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
