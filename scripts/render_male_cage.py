"""Render the body cage as a wireframe over the rendered body, female and male side by side.

Usage: python scripts/render_male_cage.py [part ...]   (default: every part built so far)
Output: artifacts/male_cage/cage_sobre_o_corpo.png
Rows: female body + female cage, male body + transferred male cage; columns: front, 3/4, side, back.
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
from src.clothing.character_model import CharacterModel, upload_texture_rgba
from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.hsr import engine_to_body_mesh
from src.clothing.wear_engine import RobloxWearEngine
from src.rendering.mesh import TexturedMesh
from src.rendering.shader import Shader

OUT = ROOT / "artifacts/male_cage"
SIZE = 360
VIEWS = [("frente", [0.0, 1.2, 1.5]), ("3/4", [-1.1, 1.35, 1.05]), ("lado", [1.5, 1.2, 0.0]), ("costas", [0.0, 1.2, -1.5])]


def wire_mesh(points, faces, colour):
    """Cage triangles as a TexturedMesh (drawn with glPolygonMode lines)."""
    rows = np.zeros((len(points), 11), dtype=np.float32)
    rows[:, :3] = points
    rows[:, 4] = 1.0  # normal up: flat lighting for the lines
    rows[:, 8:11] = colour
    return TexturedMesh(rows.ravel(), np.asarray(faces, dtype=np.uint32).ravel())


def render(shader, model, cage, white, eye):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(eye, [0.0, 1.2, 0.0], [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    identity = np.identity(4, dtype=np.float32)
    model.draw(shader, identity)
    shader.set_mat4("u_Model", identity)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, white)
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
    gl.glLineWidth(1.5)
    cage.draw()
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")


def main():
    parts = sys.argv[1:] or sorted(p.stem.removesuffix("_male") for p in OUT.glob("*_male.npy"))
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "Cage", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    white = upload_texture_rgba(Image.new("RGBA", (4, 4), (255, 255, 255, 255)))
    cages = RobloxWearEngine(body_type="female").r15_female_cages

    female_points, male_points, faces, offset = [], [], [], 0
    for part in parts:
        female_points.append(engine_to_body_mesh(np.asarray(cages[part]["verts"], dtype=np.float64)))
        male_points.append(np.load(OUT / f"{part}_male.npy"))
        faces.append(np.asarray(cages[part]["faces"]) + offset)
        offset += len(female_points[-1])
    faces = np.concatenate(faces)

    rows = []
    for label, body_type, points in (("feminino", BodyType.FEMALE, np.concatenate(female_points)),
                                     ("masculino", BodyType.MALE, np.concatenate(male_points))):
        model = CharacterModel(customization=AvatarCustomization(body_type=body_type), top_id=None, bottom_id=None)
        cage = wire_mesh(points, faces, (0.2, 0.55, 1.0))
        rows.append((label, [render(shader, model, cage, white, eye) for _, eye in VIEWS]))
        cage.delete()
        model.delete()

    sheet = Image.new("RGB", (SIZE * len(VIEWS), (SIZE + 22) * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, tiles) in enumerate(rows):
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * SIZE, row * (SIZE + 22) + 22))
            draw.text((column * SIZE + 6, row * (SIZE + 22) + 5),
                      f"{label} - cage {', '.join(parts)} - {VIEWS[column][0]}", fill="black")
    out = OUT / "cage_sobre_o_corpo.png"
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
