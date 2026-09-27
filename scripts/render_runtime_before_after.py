"""Render outfits on the female body through the real CharacterModel path, before/after the radial + prism fit.

"antes" forces the previous per-triangle WrapLayer fit; "depois" uses the
current runtime. Cached fitted OBJs are regenerated for each pass and the
final cache left on disk is the current runtime's.
Output: artifacts/runtime_female/<outfit>.png (rows: antes/depois; columns: views).
"""
import os
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_model import CharacterModel, MODELS_DIR
from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.wear_engine import RobloxWearEngine
from src.rendering.shader import Shader

OUTFITS = [
    ("padrao_knit_sweater_jeans", 9240757332, 109837605892174),
    ("camisa_social_calca_skater", 133331049150205, 137146416353285),
    ("vestido", 114590471167431, None),
    ("jaqueta_calca_cargo", 72628400373948, 16899958482),
    ("regata_saia_short", 137915688957785, 132042528605488),
    ("biquini_jeans", 96314281401899, 109837605892174),
    ("boxy_shirt_jeans", 89475537632859, 109837605892174),
]
VIEWS = [("frente", [0.0, 1.0, 2.6]), ("3/4", [-1.8, 1.45, 2.0]), ("lado", [2.6, 1.0, 0.0]), ("costas", [0.0, 1.0, -2.6])]
SIZE = 420
OUT = ROOT / "artifacts/runtime_female"


def clear_fit_cache(ids):
    """Delete the female fitted caches only; the male ones are read by tests."""
    for asset in ids:
        if asset is None:
            continue
        path = Path(MODELS_DIR) / f"character_native_{asset}_female.obj"
        if path.exists():
            path.unlink()


def render_outfit(shader, top_id, bottom_id):
    model = CharacterModel(customization=AvatarCustomization(body_type=BodyType.FEMALE),
                           top_id=top_id, bottom_id=bottom_id)
    tiles = []
    for _, eye in VIEWS:
        gl.glClearColor(0.18, 0.19, 0.22, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        shader.use()
        shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.1, 50.0))
        shader.set_mat4("u_View", look_at(eye, [0.0, 0.95, 0.0], [0.0, 1.0, 0.0]))
        shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
        shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
        shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
        shader.set_int("u_TextureAtlas", 0)
        model.draw(shader, np.identity(4, dtype=np.float32))
        gl.glFinish()
        pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        tiles.append(Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB"))
    model.delete()
    return tiles


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not glfw.init():
        raise RuntimeError("GLFW init failed")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "RuntimeBeforeAfter", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")

    current_fit = RobloxWearEngine._fit_asset_wrap_layer
    previous_fit = lambda self, verts, meta, faces=None: current_fit(self, verts, meta, None)
    rows = {}
    for label, fit in (("antes (encaixe por triangulo)", previous_fit), ("depois (radial + prisma)", current_fit)):
        RobloxWearEngine._fit_asset_wrap_layer = fit
        for name, top, bottom in OUTFITS:
            clear_fit_cache((top, bottom))
            rows.setdefault(name, []).append((label, render_outfit(shader, top, bottom)))
    RobloxWearEngine._fit_asset_wrap_layer = current_fit

    for name, passes in rows.items():
        sheet = Image.new("RGB", (SIZE * len(VIEWS), (SIZE + 26) * len(passes) + 22), "white")
        draw = ImageDraw.Draw(sheet)
        for column, (view, _) in enumerate(VIEWS):
            draw.text((column * SIZE + 6, 4), view, fill="black")
        for row, (label, tiles) in enumerate(passes):
            y = 22 + row * (SIZE + 26)
            draw.text((6, y + 6), f"{name} | {label}", fill="black")
            for column, tile in enumerate(tiles):
                sheet.paste(tile, (column * SIZE, y + 26))
        sheet.save(OUT / f"{name}.png")
        print("[OK]", OUT / f"{name}.png", flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
