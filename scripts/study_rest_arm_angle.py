"""Study: how far the arms must open at rest to clear each local garment, on both bodies.

python scripts/study_rest_arm_angle.py [--only ID ...]
Output: artifacts/robustness/estudo_bracos.json and estudo_bracos.md.

For each garment worn alone it records the rest angle the body alone needs, the smallest angle
at which forearms and hands clear the garment too (searched up to the fitting pose), and how
wide the garment is where the hands hang, so the limit of the rest angle can be chosen from
what the catalogue needs instead of guessed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import glfw
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_animation_robustness import local_garments, slot_of
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.skeleton import rest_arm_angle

OUT = ROOT / "artifacts" / "robustness"
FITTING_POSE = np.radians(45.0)  # the arms of the fitting pose: opening further means nothing


def measure(body, slot, asset_id):
    ids = {"top_id": None, "bottom_id": None}
    ids["bottom_id" if slot == "bottom" else "top_id"] = int(asset_id)
    model = CharacterModel(customization=AvatarCustomization(body_type=body), **ids)
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    skeleton = animator.skeleton
    cage_points, cage_bones = animator._cage_binding
    names = np.array(skeleton.names)[cage_bones].astype(str)
    trunk_and_legs = ~(np.char.find(names, "Arm") >= 0) & ~(np.char.find(names, "Hand") >= 0)
    radius = []
    for bone in ("LowerArm_L", "Hand_L"):
        b = skeleton.index(bone)
        radius.append(animator._around(b, cage_points[cage_bones == b])[1])
    radius = float(np.median(np.concatenate(radius)))
    arms = [b for side in "LR" for b in animator._subtree(skeleton.index("UpperArm_" + side))]
    cloth = [rows[np.where(np.isin(indices, arms), weights, 0.0).sum(1) < 0.05, :3]
             for part, rows, indices, weights in animator._bindings if part.source_obj is not None]
    cloth = np.vstack(cloth) if cloth else np.zeros((0, 3))
    body_points = cage_points[trunk_and_legs]
    alone = rest_arm_angle(skeleton, body_points, radius, largest=FITTING_POSE)
    needed = rest_arm_angle(skeleton, np.vstack([body_points, cloth]), radius, largest=FITTING_POSE)
    # Width of body and garment over the heights where the forearm and hand hang at rest.
    hand = skeleton.tails[skeleton.index("Hand_L")][1]
    elbow = skeleton.heads[skeleton.index("LowerArm_L")][1]
    low, high = min(hand, elbow) - 0.25, max(hand, elbow)
    band = lambda points: points[(points[:, 1] > low) & (points[:, 1] < high)]
    body_width = float(np.abs(band(body_points)[:, 0]).max())
    cloth_width = float(np.abs(band(cloth)[:, 0]).max()) if len(band(cloth)) else 0.0
    model.delete()
    return {"corpo_graus": round(float(np.degrees(alone)), 1), "roupa_graus": round(float(np.degrees(needed)), 1),
            "largura_corpo_cm": round(body_width * 100, 1), "largura_roupa_cm": round(cloth_width * 100, 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()
    garments = local_garments()
    if args.only:
        garments = {k: v for k, v in garments.items() if k in args.only}
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(64, 64, "Study", None, None)
    glfw.make_context_current(window)
    rows = []
    for body_name in ("female", "male"):
        body = BodyType.FEMALE if body_name == "female" else BodyType.MALE
        for index, (asset_id, name) in enumerate(garments.items()):
            slot, _ = slot_of(asset_id, body_name)
            if slot is None:
                continue
            try:
                row = measure(body, slot, asset_id)
            except Exception as exc:
                print(f"[{body_name}] {name}: {type(exc).__name__}: {exc}", flush=True)
                continue
            rows.append({"roupa": name, "id": asset_id, "corpo": body_name, "lugar": slot, **row})
            print(f"[{body_name} {index + 1}/{len(garments)}] {name}: corpo {row['corpo_graus']}°, com a roupa {row['roupa_graus']}°, "
                  f"largura {row['largura_roupa_cm']} cm", flush=True)
            (OUT / "estudo_bracos.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    glfw.destroy_window(window)
    glfw.terminate()
    lines = ["# Quanto os braços precisam abrir em descanso para não tocar na roupa", "",
             "| Roupa | Corpo | Lugar | Largura do corpo (cm) | Largura da roupa (cm) | Só o corpo (°) | Com a roupa (°) |",
             "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (-r["roupa_graus"], r["roupa"])):
        lines.append(f"| {r['roupa']} | {r['corpo']} | {r['lugar']} | {r['largura_corpo_cm']} | {r['largura_roupa_cm']} | "
                     f"{r['corpo_graus']} | {r['roupa_graus']} |")
    (OUT / "estudo_bracos.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] {len(rows)} medidas -> {OUT / 'estudo_bracos.md'}")


if __name__ == "__main__":
    main()
