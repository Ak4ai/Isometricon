"""Render outfits on the male body next to the same outfit on the female body.

Usage: python scripts/render_male_outfits.py
Output: artifacts/runtime_male/roupas_masculino.png
Each row: the female body from the front (reference), then the male body from the front, 3/4 and back.
"""
from pathlib import Path
import sys

import glfw
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_layered_outfits import SIZE, VIEWS, render
from src.clothing.character_model import CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType
from src.rendering.shader import Shader

JEANS = 109837605892174
OUTFITS = [
    ("sem roupa", dict(top_id=None, bottom_id=None)),
    ("suéter + jeans", dict(top_id=9240757332, bottom_id=JEANS)),
    ("camisa social + jeans", dict(top_id=133331049150205, bottom_id=JEANS)),
    ("regata + jeans + jaqueta bomber", dict(top_id=137915688957785, bottom_id=JEANS, outer_top_id=72628400373948)),
    ("camisa social + sobretudo", dict(top_id=133331049150205, bottom_id=JEANS, outer_top_id=133273151439383)),
    ("regata + jeans + tênis", dict(top_id=137915688957785, bottom_id=JEANS, shoes_id="101914651386350,131149613284268")),
]
OUT = ROOT / "artifacts" / "runtime_male"


def main():
    only = set(sys.argv[1:])
    outfits = [o for o in OUTFITS if not only or o[0] in only]
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "Male", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    sheet = Image.new("RGB", (SIZE * 4, (SIZE + 22) * len(outfits)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, ids) in enumerate(outfits):
        female = CharacterModel(customization=AvatarCustomization(body_type=BodyType.FEMALE), **ids)
        tiles = [render(shader, female, VIEWS[0][1])]
        female.delete()
        male = CharacterModel(customization=AvatarCustomization(body_type=BodyType.MALE), **ids)
        tiles += [render(shader, male, eye) for _, eye in VIEWS]
        male.delete()
        y = row * (SIZE + 22)
        draw.text((6, y + 5), f"{label}: feminino", fill="black")
        draw.text((SIZE + 6, y + 5), f"{label}: masculino frente / 3/4 / costas", fill="black")
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * SIZE, y + 22))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "roupas_masculino.png"
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
