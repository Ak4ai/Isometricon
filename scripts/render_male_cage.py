"""Render the body cage as a wireframe over the rendered body, female and male side by side.

Usage: python scripts/render_male_cage.py [part ...] [--pescoco]   (default: every part built so far)
Output: artifacts/male_cage/cage_sobre_o_corpo.png (or cage_pescoco.png, a close-up of the neck)
Rows: female body + female cage, male body + transferred male cage; columns: front, 3/4, side, back.
Red marks: skin poking out through the cage; yellow marks: cage points inside the skin.
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


def marker_mesh(points, colour, size=0.006):
    """A small octahedron at each point (collision marks)."""
    corners = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float) * size
    tris = np.array([(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)])
    if not len(points):
        return None
    vertices = (np.asarray(points)[:, None] + corners[None]).reshape(-1, 3)
    faces = (tris[None] + 6 * np.arange(len(points))[:, None, None]).reshape(-1, 3)
    rows = np.zeros((len(vertices), 11), dtype=np.float32)
    rows[:, :3] = vertices
    rows[:, 4] = 1.0
    rows[:, 8:11] = colour
    return TexturedMesh(rows.ravel(), faces.astype(np.uint32).ravel())


def render(shader, model, cage, white, eye, markers=(), target=(0.0, 1.2, 0.0)):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(38.0, 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(eye, list(target), [0.0, 1.0, 0.0]))
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
    gl.glDisable(gl.GL_DEPTH_TEST)  # collision marks stay visible through the body
    for marker in markers:
        marker.draw()
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")


def main():
    neck = "--pescoco" in sys.argv
    parts = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(
        p.stem.removesuffix("_male") for p in OUT.glob("*_male.npy"))
    target = (0.0, 1.48, 0.0) if neck else (0.0, 1.2, 0.0)
    views = [(name, [e[0] * 0.4, target[1] + (e[1] - 1.2) * 0.4 + 0.05, e[2] * 0.4]) for name, e in VIEWS] if neck else VIEWS
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
        model = CharacterModel(customization=AvatarCustomization(body_type=body_type), top_id=None, bottom_id=None,
                               hair_id="none")  # bald: the hair hid the collar
        cage = wire_mesh(points, faces, (0.2, 0.55, 1.0))
        poking, inside = [], []
        for part in parts:
            path = OUT / f"{part}_{label}_colisoes.npz"
            if path.exists():
                with np.load(path) as data:
                    poking.append(data["poking"])
                    inside.append(data["inside"])
        markers = [m for m in (marker_mesh(np.concatenate(poking) if poking else [], (1.0, 0.1, 0.1)),
                               marker_mesh(np.concatenate(inside) if inside else [], (1.0, 0.9, 0.1), 0.009)) if m]
        rows.append((label, [render(shader, model, cage, white, eye, markers, target) for _, eye in views]))
        for m in markers:
            m.delete()
        cage.delete()
        model.delete()

    sheet = Image.new("RGB", (SIZE * len(views), (SIZE + 22) * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (label, tiles) in enumerate(rows):
        for column, tile in enumerate(tiles):
            sheet.paste(tile, (column * SIZE, row * (SIZE + 22) + 22))
            draw.text((column * SIZE + 6, row * (SIZE + 22) + 5),
                      f"{label} - cage {', '.join(parts)} - {views[column][0]}", fill="black")
    out = OUT / ("cage_pescoco.png" if neck else "cage_sobre_o_corpo.png")
    sheet.save(out)
    print("[OK]", out)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
