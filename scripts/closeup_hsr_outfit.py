"""Close-up of one outfit around the waist, with and without HSR skin culling.

Usage: python scripts/closeup_hsr_outfit.py <top_id> <bottom_id or none> <output name>
Output: artifacts/runtime_female/<output name>.png (top row with HSR, bottom row without).
"""
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.render_runtime_before_after as R
from src.clothing.character_model import CharacterModel
from src.rendering.shader import Shader

VIEWS = [("frente", [0.0, 0.9, 1.3]), ("3/4", [-0.9, 0.9, 0.9]), ("lado", [1.3, 0.9, 0.0]),
         ("costas", [0.0, 0.9, -1.3]), ("de baixo", [0.0, 0.3, 1.1])]


def main():
    top_id, bottom_id, name = int(sys.argv[1]), (None if sys.argv[2] == "none" else int(sys.argv[2])), sys.argv[3]
    R.SIZE = 420
    R.VIEWS = VIEWS
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(R.SIZE, R.SIZE, "closeup", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, R.SIZE, R.SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    with_hsr = R.render_outfit(shader, top_id, bottom_id)
    original = CharacterModel._apply_hsr_skin
    CharacterModel._apply_hsr_skin = lambda *a, **k: False
    without = R.render_outfit(shader, top_id, bottom_id)
    CharacterModel._apply_hsr_skin = original
    sheet = Image.new("RGB", (R.SIZE * len(VIEWS), (R.SIZE + 22) * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, tiles) in enumerate((("com HSR", with_hsr), ("sem HSR", without))):
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * R.SIZE, row * (R.SIZE + 22) + 22))
            draw.text((column * R.SIZE + 6, row * (R.SIZE + 22) + 5), f"{label} - {VIEWS[column][0]}", fill="black")
    out = R.OUT / f"{name}.png"
    sheet.save(out)
    print("[OK]", out)


if __name__ == "__main__":
    main()
