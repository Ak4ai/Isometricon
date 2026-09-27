"""Render outfits on the female body with the rule-based skin cuts vs Roblox HSR masks.

Uses the same outfits and cameras as render_runtime_before_after.py. Fitted
garments are regenerated once (the cache version changed); both passes then
reuse them, so only the skin differs.
Output: artifacts/runtime_female/hsr_<outfit>.png
"""
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_runtime_before_after import OUTFITS, OUT, SIZE, VIEWS, clear_fit_cache, render_outfit
from src.clothing.character_model import CharacterModel
from src.rendering.shader import Shader


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "HsrBeforeAfter", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    for _, top, bottom in OUTFITS:
        clear_fit_cache((top, bottom))
    with_hsr = CharacterModel._apply_hsr_skin
    rows = {}
    for label, method in (("sem HSR (cortes por regra)", lambda *a, **k: False), ("com HSR do Roblox", with_hsr)):
        CharacterModel._apply_hsr_skin = method
        for name, top, bottom in OUTFITS:
            rows.setdefault(name, []).append((label, render_outfit(shader, top, bottom)))
    CharacterModel._apply_hsr_skin = with_hsr
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
        sheet.save(OUT / f"hsr_{name}.png")
        print("[OK]", OUT / f"hsr_{name}.png", flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
