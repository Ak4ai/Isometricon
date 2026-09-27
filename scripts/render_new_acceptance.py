"""Garments the previous WrapLayer validation rejected, rendered on the female body before/after.

"antes" re-applies the previous rule (garment within 0.05 median / 0.2 p99 of its
outer cage, else the older non-WrapLayer fit); "depois" is the current runtime.
Output: artifacts/runtime_female/aceitas_<outfit>.png
"""
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_runtime_before_after import OUT, SIZE, VIEWS, clear_fit_cache, render_outfit
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer
from src.rendering.shader import Shader

OUTFITS = [
    ("regata_saia_short", 137915688957785, 132042528605488),
    ("camiseta_76ers_jeans", 97346273111638, 109837605892174),
    ("sueter_brooklyn_jeans", 16809419146, 109837605892174),
    ("camisa_cropped_jeans", 101748354579961, 109837605892174),
    ("regata_moletom", 137915688957785, 110437430397470),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "NewAcceptance", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")

    current = RobloxWearEngine._fit_asset_wrap_layer

    def previous(self, verts, meta, faces=None):
        import os
        try:
            info = retarget_garment_with_wrap_layer(self, verts, meta["rbxm_path"],
                                                    os.path.join(os.path.dirname(meta["obj_path"]), "wrap_cages"))[1]
            if info["median_source_distance"] > 0.05 or info["p99_source_distance"] > 0.2:
                return None
        except Exception:
            return None
        return current(self, verts, meta, faces)

    rows = {}
    for label, fit in (("antes (regra anterior)", previous), ("depois (regra do radial + prisma)", current)):
        RobloxWearEngine._fit_asset_wrap_layer = fit
        for name, top, bottom in OUTFITS:
            clear_fit_cache((top, bottom))
            rows.setdefault(name, []).append((label, render_outfit(shader, top, bottom)))
    RobloxWearEngine._fit_asset_wrap_layer = current
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
        sheet.save(OUT / f"aceitas_{name}.png")
        print("[OK]", OUT / f"aceitas_{name}.png", flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
