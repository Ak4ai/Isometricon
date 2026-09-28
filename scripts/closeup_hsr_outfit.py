"""Close-up of one outfit around the waist, with and without HSR skin culling.

Usage: python scripts/closeup_hsr_outfit.py <top_id or none> <bottom_id or none> <output name> [zoom]
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
ZOOM_VIEWS = [("frente", [0.0, 0.85, 0.55]), ("3/4 esq", [-0.4, 0.85, 0.4]), ("3/4 dir", [0.4, 0.85, 0.4]),
              ("costas", [0.0, 0.85, -0.55]), ("de baixo", [0.0, 0.55, 0.45])]


def main():
    top_id, bottom_id = (None if arg == "none" else int(arg) for arg in sys.argv[1:3])
    name = sys.argv[3]
    R.SIZE = 420
    zoom = len(sys.argv) > 4 and sys.argv[4] == "zoom"
    views = ZOOM_VIEWS if zoom else VIEWS
    R.VIEWS = views
    if zoom:
        R.TARGET = [0.0, 0.85, 0.0]
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
    sheet = Image.new("RGB", (R.SIZE * len(views), (R.SIZE + 22) * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, tiles) in enumerate((("com HSR", with_hsr), ("sem HSR", without))):
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * R.SIZE, row * (R.SIZE + 22) + 22))
            draw.text((column * R.SIZE + 6, row * (R.SIZE + 22) + 5), f"{label} - {views[column][0]}", fill="black")
    out = R.OUT / f"{name}.png"
    sheet.save(out)
    print("[OK]", out)


if __name__ == "__main__":
    main()
