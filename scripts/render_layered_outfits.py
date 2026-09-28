"""Render outfits with a second top worn over the first (jacket over shirt) on the female body.

Usage: python scripts/render_layered_outfits.py
Output: artifacts/runtime_female/camadas_jaqueta_sobre_camisa.png
Each row: the shirt alone (reference), then shirt + jacket from the front, 3/4 and back.
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

JEANS = 109837605892174
OUTFITS = [
    ("camisa social + jaqueta bomber", 133331049150205, 72628400373948),
    ("regata + moletom laranja", 137915688957785, 7192553841),
    ("cropped + jaleco", 110977031470293, 111428495474261),
    ("camisa social + sobretudo", 133331049150205, 133273151439383),
    ("regata + puffer", 137915688957785, 138103576309875),
    ("tomara-que-caia + moletom oversized", 72014673044643, 88473821300242),
]
VIEWS = [("frente", [0.0, 1.0, 2.2]), ("3/4", [-1.5, 1.2, 1.6]), ("costas", [0.0, 1.0, -2.2])]
SIZE = 330


def render(shader, model, eye):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.1, 50.0))
    shader.set_mat4("u_View", look_at(eye, [0.0, 1.0, 0.0], [0.0, 1.0, 0.0]))
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
    window = glfw.create_window(SIZE, SIZE, "Layers", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    sheet = Image.new("RGB", (SIZE * 4, (SIZE + 22) * len(OUTFITS)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, shirt, jacket) in enumerate(OUTFITS):
        female = lambda: AvatarCustomization(body_type=BodyType.FEMALE)
        alone = CharacterModel(customization=female(), top_id=shirt, bottom_id=JEANS)
        tiles = [render(shader, alone, VIEWS[0][1])]
        alone.delete()
        layered = CharacterModel(customization=female(), top_id=shirt, bottom_id=JEANS, outer_top_id=jacket)
        tiles += [render(shader, layered, eye) for _, eye in VIEWS]
        layered.delete()
        y = row * (SIZE + 22)
        draw.text((6, y + 5), f"{label}: só a peça de baixo", fill="black")
        draw.text((SIZE + 6, y + 5), f"{label}: frente / 3/4 / costas", fill="black")
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * SIZE, y + 22))
    out = R.OUT / "camadas_jaqueta_sobre_camisa.png"
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
