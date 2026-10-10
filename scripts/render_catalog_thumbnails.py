"""Miniaturas dos itens baixados, para a grade da tela de criação de personagem.

python scripts/render_catalog_thumbnails.py [--only ID ...] [--force]

Veste cada item de ``assets/models/clothing`` num corpo (o feminino, ou o masculino se só nele o
item já foi encaixado), na pose de descanso, enquadra a peça e grava
``assets/models/clothing/thumbs/<id>.png`` (fundo transparente). Itens que já têm miniatura são
pulados, então a execução pode ser interrompida e retomada. Desenha também as raças (``races.RACES``)
em cada corpo, em ``thumbs/racas/<raça>_<corpo>.png``.
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CLOTHING_DIR, MODELS_DIR, CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType, HairStyle
from src.clothing.skeleton import skin
from src.interactive.character_editor import CARD, catalog
from src.rendering.shader import Shader

SIZE = (4 * (CARD[0] - 8), 4 * 72)  # rendered at four times the tile's picture, saved at twice
FOV = 24.0
TURN = math.radians(24.0)           # seen a little from the side
# Slot of the model each kind of item is worn in, and the mesh parts that show it.
SLOTS = {"top": ("top_id", ("top",)), "jacket": ("top_id", ("top",)), "bottom": ("bottom_id", ("bottom",)),
         "shoes": ("shoes_id", ("shoe",)), "hair": ("hair_id", ("hair",))}


def body_for(asset_id: str) -> str:
    """The body the item is already fitted on (the female one first)."""
    first = asset_id.split(",")[0]
    for body in ("female", "male"):
        if os.path.exists(os.path.join(MODELS_DIR, f"character_native_{first}_{body}.obj")):
            return body
    return "female"


def slot_of_dress(asset_id: str, body: str):
    """A dress is worn as a top; a skirt as a bottom (as the wear command decides)."""
    from scripts.audit_animation_robustness import slot_of
    slot, _ = slot_of(asset_id, body)
    return ("bottom_id", ("bottom",)) if slot == "bottom" else ("top_id", ("top",))


def render(shader, item) -> Image.Image:
    body = body_for(item.asset_id)
    slot, prefixes = slot_of_dress(item.asset_id, body) if item.kind == "dress" else SLOTS[item.kind]
    value = item.asset_id if "," in item.asset_id else int(item.asset_id)
    custom = AvatarCustomization(body_type=BodyType(body))
    if item.kind != "hair":
        custom.hair_style = HairStyle.BALD  # nothing in front of the garment
    worn = {"top_id": None, "bottom_id": None, slot: value}
    model = CharacterModel(customization=custom, **worn)
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    matrices = animator.skeleton.pose(animator.rest)
    shown = [skin(rows, indices, weights, matrices)[:, :3] for part, rows, indices, weights in animator._bindings
             if part.name.startswith(prefixes) or (item.kind == "hair" and "hair" in part.name)]
    points = np.vstack(shown) if shown else np.array([[-0.4, 0.0, -0.2], [0.4, 1.8, 0.2]])
    low, high = points.min(0), points.max(0)
    centre = (low + high) / 2
    aspect = SIZE[0] / SIZE[1]
    height = max(high[1] - low[1], np.hypot(high[0] - low[0], high[2] - low[2]) / aspect) * 1.18
    distance = height / (2 * math.tan(math.radians(FOV) / 2))
    eye = centre + distance * np.array([math.sin(TURN), 0.08, math.cos(TURN)])

    gl.glViewport(0, 0, *SIZE)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(FOV, aspect, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(list(eye), list(centre), [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.5, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.70, 0.70, 0.70)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE[0], SIZE[1], gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    model.delete()
    image = Image.frombytes("RGBA", SIZE, pixels).transpose(Image.FLIP_TOP_BOTTOM)
    return image.resize((SIZE[0] // 2, SIZE[1] // 2), Image.LANCZOS)


RACE_FRAME = (1.47, 1.00)  # the middle (height from the ground) and the height framed: the same for every race, so their sizes compare


def render_race(shader, name: str, body: str) -> Image.Image:
    """A race on a body, as the character starts (no clothes, the underwear on the skin), hair cut short to show the ears."""
    from src.clothing import races
    custom = AvatarCustomization(body_type=BodyType(body), hair_style=HairStyle.BUZZ_CUT)
    races.apply(custom, name)
    model = CharacterModel(customization=custom, top_id=None, bottom_id=None)  # as a character starts: in its underwear
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    aspect = SIZE[0] / SIZE[1]
    centre = np.array([0.0, RACE_FRAME[0], 0.0])
    distance = RACE_FRAME[1] / (2 * math.tan(math.radians(FOV) / 2))
    eye = centre + distance * np.array([math.sin(TURN), 0.08, math.cos(TURN)])
    gl.glViewport(0, 0, *SIZE)
    gl.glClearColor(0.0, 0.0, 0.0, 0.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(FOV, aspect, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(list(eye), list(centre), [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.5, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.70, 0.70, 0.70)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE[0], SIZE[1], gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    model.delete()
    image = Image.frombytes("RGBA", SIZE, pixels).transpose(Image.FLIP_TOP_BOTTOM)
    return image.resize((SIZE[0] // 2, SIZE[1] // 2), Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out = Path(CLOTHING_DIR) / "thumbs"
    out.mkdir(parents=True, exist_ok=True)
    items = [item for kind, found in catalog().items() if kind in SLOTS or kind == "dress" for item in found]
    if args.only:
        items = [item for item in items if any(part in args.only for part in item.asset_id.split(","))]

    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.ALPHA_BITS, 8)
    window = glfw.create_window(SIZE[0], SIZE[1], "Thumbnails", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")

    done = failed = 0
    for index, item in enumerate(items):
        path = out / f"{item.asset_id.split(',')[0]}.png"
        if path.exists() and not args.force:
            continue
        try:
            render(shader, item).save(path)
            done += 1
            print(f"[{index + 1}/{len(items)}] {item.name}: ok", flush=True)
        except Exception as exc:
            failed += 1
            print(f"[{index + 1}/{len(items)}] {item.name}: {type(exc).__name__}: {exc}", flush=True)
    # The races, on each body: thumbs/racas/<race>_<body>.png
    from src.clothing.races import RACES
    races_out = out / "racas"
    races_out.mkdir(parents=True, exist_ok=True)
    for name in RACES:
        for body in ("female", "male"):
            path = races_out / f"{name}_{body}.png"
            if (path.exists() and not args.force) or (args.only and name not in args.only):
                continue
            try:
                render_race(shader, name, body).save(path)
                done += 1
                print(f"[raça] {name} ({body}): ok", flush=True)
            except Exception as exc:
                failed += 1
                print(f"[raça] {name} ({body}): {type(exc).__name__}: {exc}", flush=True)
    glfw.destroy_window(window)
    glfw.terminate()
    print(f"[OK] {done} miniaturas novas, {failed} falharam -> {out}")


if __name__ == "__main__":
    main()
