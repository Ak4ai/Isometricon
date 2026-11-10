"""Demo: mostra uma construção Schematic (.schem) em 3D, girando em projeção isométrica.

Uso:
    python scripts/demo_schematic.py [arquivo.schem] [--frames N] [--capture saida.png]

Sem argumentos abre assets/schematics/31422.schem. Com --frames N a janela fecha sozinha
depois de N quadros; com --capture salva o último quadro em PNG (para conferir sem olhar a tela).
"""

import argparse
import os
import sys

# Garante acesso aos módulos de 'src'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import OpenGL.GL as gl
from PIL import Image

from src.core.window import Window
from src.math import mat4_look_at, mat4_ortho, mat4_rotate_y, vec3
from src.rendering import SchematicAtlas, Shader
from src.world import Schematic, StructureMesher

DEFAULT_SCHEMATIC = os.path.join(PROJECT_ROOT, "assets", "schematics", "31422.schem")


def save_frame(path: str, width: int, height: int) -> None:
    """Salva o framebuffer atual em PNG."""
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    data = gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
    image = Image.fromarray(np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3))
    image.transpose(Image.FLIP_TOP_BOTTOM).save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualizador 3D de schematics (.schem)")
    parser.add_argument("schematic", nargs="?", default=DEFAULT_SCHEMATIC)
    parser.add_argument("--frames", type=int, default=None, help="fecha depois de N quadros")
    parser.add_argument("--capture", default=None, help="salva o último quadro neste PNG")
    args = parser.parse_args()

    window = Window(
        width=1280,
        height=720,
        title="Isometricon - Visualizador de Schematics (.schem)",
        vsync=True,
    )

    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)
    gl.glEnable(gl.GL_BLEND)  # vidro, folhas e outras transparências
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    gl.glClearColor(0.10, 0.12, 0.16, 1.0)

    shader = Shader(
        os.path.join(PROJECT_ROOT, "assets", "shaders", "world_textured.vert"),
        os.path.join(PROJECT_ROOT, "assets", "shaders", "world_textured.frag"),
    )
    atlas = SchematicAtlas(create_gl=True)

    schematic = Schematic.load_from_file(args.schematic)
    print(f"Estrutura: {schematic.name} ({schematic.width}x{schematic.height}x{schematic.length})")
    mesh = StructureMesher.build_mesh(schematic, atlas, center=True)
    print(f"Malha: {mesh.index_count // 3} triângulos, com as faces ocultas descartadas.")

    shader.use()
    shader.set_int("u_TextureAtlas", 0)
    shader.set_vec3("u_LightDir", 0.6, 1.0, 0.4)
    shader.set_vec3("u_LightColor", 1.0, 0.98, 0.92)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.48)

    max_dim = max(schematic.width, schematic.height, schematic.length)
    ortho_size = max_dim * 0.75
    cam_dist = max_dim * 2.0

    frame = 0
    while not window.should_close():
        window.update_delta_time()
        window.poll_events()
        window.set_title(
            f"Isometricon | {schematic.name} "
            f"({schematic.width}x{schematic.height}x{schematic.length}) | {window.fps:.0f} FPS"
        )

        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        aspect = window.get_aspect_ratio()
        projection = mat4_ortho(-ortho_size * aspect, ortho_size * aspect, -ortho_size, ortho_size, 0.1, 500.0)
        view = mat4_look_at(
            eye=vec3(cam_dist, cam_dist, cam_dist),
            target=vec3(0.0, 0.0, 0.0),
            up=vec3(0.0, 1.0, 0.0),
        )
        # Gira devagar em torno do eixo Y; com --capture fica parado num ângulo fixo
        model = mat4_rotate_y(0.6 if args.capture else window.get_time() * 0.4)

        shader.use()
        atlas.bind(0)
        shader.set_mat4("u_Projection", projection)
        shader.set_mat4("u_View", view)
        shader.set_mat4("u_Model", model)
        mesh.draw()

        frame += 1
        if args.frames is not None and frame >= args.frames:
            if args.capture:
                width, height = 1280, 720
                save_frame(args.capture, width, height)
                print(f"Quadro salvo em {args.capture}")
            break
        window.swap_buffers()

    mesh.delete()
    atlas.delete()
    shader.delete()
    window.close()


if __name__ == "__main__":
    main()
