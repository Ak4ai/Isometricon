"""Render every fitted hair (assets/models/clothing/Hair_fitted_*.obj) on the head.

Usage: python scripts/render_hairs.py [asset_id ...] [--corpo male|female]
Output: artifacts/hair/cabelos_<corpo>.png, one row per hair: front, 3/4, side, back.
"""
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_model import CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType
from src.rendering.shader import Shader

VIEWS = [[0.0, 1.66, 0.9], [-0.65, 1.7, 0.65], [-0.9, 1.66, 0.0], [0.0, 1.7, -0.9]]
SIZE = 260
OUT = ROOT / "artifacts" / "hair"


def render(shader, model, eye):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(30.0, 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(eye, [0.0, 1.66, 0.0], [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")


def main():
    args = sys.argv[1:]
    body = BodyType.MALE if "male" in args else BodyType.FEMALE
    ids = [a for a in args if a.isdigit()] or sorted(
        {p.stem.split("_")[2] for p in (ROOT / "assets" / "models" / "clothing").glob("Hair_fitted_*.obj")})
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "Hair", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    sheet = Image.new("RGB", (SIZE * len(VIEWS), (SIZE + 18) * len(ids)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, asset_id in enumerate(ids):
        model = CharacterModel(customization=AvatarCustomization(body_type=body), top_id=None, bottom_id=None,
                               hair_id=asset_id)
        y = row * (SIZE + 18)
        draw.text((6, y + 3), asset_id, fill="black")
        for column, eye in enumerate(VIEWS):
            sheet.paste(render(shader, model, eye), (column * SIZE, y + 18))
        model.delete()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"cabelos_{body.value}.png"
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
