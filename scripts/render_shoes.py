"""Render layered shoes on the female body, close to the feet.

Usage: python scripts/render_shoes.py
Output: artifacts/runtime_female/sapatos.png
Each row: one pair without pants (front, 3/4, side, back), then with the default jeans.
"""
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.render_runtime_before_after as R
from scripts.render_female_tests import look_at, perspective
from src.clothing.character_model import CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType
from src.rendering.shader import Shader

JEANS, TANK_TOP = 109837605892174, 137915688957785
PAIRS = [
    ("tênis", "101914651386350,131149613284268"),
    ("botas", "80102743203860,87917823878878"),
    ("salto alto", "120212561676547,133993828177296"),
    ("bota de pelo", "71890162253609,112948299427250"),
    ("bota plataforma", "98033180899784,79289164241757"),
]
VIEWS = [[0.0, 0.35, 1.1], [-0.8, 0.35, 0.8], [1.1, 0.3, 0.0], [0.0, 0.35, -1.1]]
SIZE = 300


def render(shader, model, eye, target=(0.0, 0.18, 0.0)):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(eye, list(target), [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")


def main():
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "Shoes", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    female = lambda: AvatarCustomization(body_type=BodyType.FEMALE)
    sheet = Image.new("RGB", (SIZE * 5, (SIZE + 22) * len(PAIRS)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, shoes) in enumerate(PAIRS):
        bare = CharacterModel(customization=female(), top_id=TANK_TOP, bottom_id=None, shoes_id=shoes)
        tiles = [render(shader, bare, eye) for eye in VIEWS]
        bare.delete()
        jeans = CharacterModel(customization=female(), top_id=TANK_TOP, bottom_id=JEANS, shoes_id=shoes)
        tiles.append(render(shader, jeans, VIEWS[1]))
        jeans.delete()
        y = row * (SIZE + 22)
        draw.text((6, y + 5), f"{label}: sem calça (frente, 3/4, lado, costas)", fill="black")
        draw.text((4 * SIZE + 6, y + 5), f"{label}: com jeans", fill="black")
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * SIZE, y + 22))
    out = R.OUT / "sapatos.png"
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
