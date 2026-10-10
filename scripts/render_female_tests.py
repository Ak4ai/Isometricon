"""Script 100% Python/OpenGL Headless para Renderização das Imagens de Teste Femininas.
Renderiza os outfits femininos deformados com o novo sistema de cages bilateral R15 canônico Roblox.
"""

import os
import sys
import math
import glfw
import numpy as np
from PIL import Image
import OpenGL.GL as gl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.character_model import CharacterModel
from src.rendering.shader import Shader


def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, center, up):
    eye = np.array(eye, dtype=np.float32)
    center = np.array(center, dtype=np.float32)
    up = np.array(up, dtype=np.float32)
    f = center - eye
    f /= np.linalg.norm(f)
    u = up / np.linalg.norm(up)
    s = np.cross(f, u)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    t = np.identity(4, dtype=np.float32)
    t[:3, 3] = -eye
    return m @ t


def render_all():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "out", "renders")
    os.makedirs(output_dir, exist_ok=True)

    if not glfw.init():
        raise RuntimeError("GLFW init failed")

    width, height = 1024, 1024
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)

    win = glfw.create_window(width, height, "FemaleTestRenderer", None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("Offscreen window creation failed")
    glfw.make_context_current(win)

    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_LESS)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glDisable(gl.GL_CULL_FACE)
    gl.glViewport(0, 0, width, height)

    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")

    views = [
        ("front", [0.0, 1.00, 2.6], [0.0, 0.95, 0.0], 38.0),
        ("iso", [-1.8, 1.45, 2.0], [0.0, 0.95, 0.0], 38.0),
        ("back", [0.0, 1.00, -2.6], [0.0, 0.95, 0.0], 38.0),
    ]

    outfits = [
        {
            "name": "sweater_and_jeans",
            "top_id": 9240757332,
            "bottom_id": 109837605892174,
            "desc": "Knit Sweater (Manga Longa) + Designer Jeans",
        },
        {
            "name": "cropped_shirt_and_jeans",
            "top_id": 101748354579961,
            "bottom_id": 109837605892174,
            "desc": "Cropped Tied Shirt (Manga Curta) + Designer Jeans",
        },
        {
            "name": "tank_top_and_jeans",
            "top_id": 137915688957785,
            "bottom_id": 109837605892174,
            "desc": "Strappy Tank Top (Regata / Sem Manga) + Designer Jeans",
        },
        {
            "name": "red_tucked_shirt_and_jeans",
            "top_id": 97984232018335,
            "bottom_id": 109837605892174,
            "desc": "Red Tucked Shirt (Manga Curta) + Designer Jeans",
        },
        {
            "name": "bikini_top_and_jeans",
            "top_id": 96314281401899,
            "bottom_id": 109837605892174,
            "desc": "Red Bikini Top (Sem Manga) + Designer Jeans",
        },
        {
            "name": "white_sweater_and_jeans",
            "top_id": 16185652164,
            "bottom_id": 109837605892174,
            "desc": "White Oversized Sweater (Manga Longa) + Designer Jeans",
        },
        {
            "name": "bomber_jacket_and_jeans",
            "top_id": 72628400373948,
            "bottom_id": 109837605892174,
            "desc": "Bomber Jacket (Jaqueta) + Designer Jeans",
        },
    ]

    cust = AvatarCustomization(body_type=BodyType.FEMALE)

    for outf in outfits:
        name = outf["name"]
        top_id = outf["top_id"]
        bot_id = outf["bottom_id"]
        print(f"\n=======================================================")
        print(f"  CARREGANDO: {outf['desc']} ({top_id})")
        print(f"=======================================================")

        model = CharacterModel(customization=cust, top_id=top_id, bottom_id=bot_id)

        for view_name, cam_pos, cam_target, fovy in views:
            proj = perspective(fovy, 1.0, 0.1, 50.0)
            view = look_at(cam_pos, cam_target, [0.0, 1.0, 0.0])

            gl.glClearColor(0.18, 0.19, 0.22, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

            shader.use()
            shader.set_mat4("u_Projection", proj)
            shader.set_mat4("u_View", view)
            shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
            shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
            shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
            shader.set_int("u_TextureAtlas", 0)

            base_model = np.identity(4, dtype=np.float32)
            model.draw(shader, base_model)
            gl.glFinish()

            pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            img = Image.frombytes("RGBA", (width, height), pixels).transpose(Image.FLIP_TOP_BOTTOM)

            out_file = os.path.join(output_dir, f"female_{name}_{view_name}.png")
            img.save(out_file)
            print(f"  [OK] Imagem salva: {out_file}")

        model.delete()

    glfw.destroy_window(win)
    glfw.terminate()
    print("\n[SUCESSO] Todas as imagens de teste foram geradas!")


if __name__ == "__main__":
    render_all()
