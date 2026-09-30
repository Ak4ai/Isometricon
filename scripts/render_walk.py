"""Render the walk cycle of both bodies with clothes (CharacterAnimator), side and 3/4 views.

Usage: python scripts/render_walk.py [--top ID] [--bottom ID]
Output: artifacts/animation/caminhada.png, one row per body and view, one column per phase.
"""
from pathlib import Path
import math
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CharacterModel, parse_character_cli_args
from src.rendering.shader import Shader

SIZE = 300
PHASES = 6
VIEWS = [("lado", [3.2, 0.9, 0.0]), ("3/4", [-2.3, 1.0, 2.3])]


def render(shader, model, eye):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.1, 50.0))
    shader.set_mat4("u_View", look_at(eye, [0.0, 0.85, 0.0], [0.0, 1.0, 0.0]))
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
    window = glfw.create_window(SIZE, SIZE, "Walk", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    rows = []
    for flag in ("--female", "--male"):
        customization, top, bottom, tool, _ = parse_character_cli_args(["--char", flag] + sys.argv[1:])
        model = CharacterModel(customization=customization, top_id=top, bottom_id=bottom)
        animator = CharacterAnimator(model)
        for label, eye in VIEWS:
            tiles = []
            for phase in range(PHASES):
                animator.walk_time = 2 * math.pi * phase / PHASES
                animator.update(0.0)
                tiles.append(render(shader, model, eye))
            rows.append((f"{flag[2:]} {label}", tiles))
        model.delete()
    sheet = Image.new("RGB", (SIZE * PHASES, (SIZE + 18) * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for r, (label, tiles) in enumerate(rows):
        y = r * (SIZE + 18)
        draw.text((6, y + 3), label, fill="black")
        for c, tile in enumerate(tiles):
            sheet.paste(tile, (c * SIZE, y + 18))
    out = ROOT / "artifacts" / "animation" / "caminhada.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
