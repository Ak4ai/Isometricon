"""Demo: mostra um modelo personalizado (.glb) girando, no shader dos personagens.

Uso:
    python scripts/demo_modelo.py [arquivo.glb] [--altura M] [--giro N] [--frames N] [--capture saida.png]

Sem arquivo mostra um boneco de amostra. ``--giro N`` gira o modelo N quartos de volta, para os que olham para outro
lado que +z. Imprime o tamanho do modelo e os avisos da leitura; ``ModelError`` (arquivo que não serve) vira uma
mensagem, sem erro feio.
"""

import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import OpenGL.GL as gl
from PIL import Image

from src.clothing.custom_model import DEFAULT_HEIGHT, CustomModel, ModelError
from src.clothing.glb_writer import sample_humanoid
from src.clothing.procedural import PROFILE_NAMES, Roles, RolesError
from src.core.window import Window
from src.math import mat4_look_at, mat4_ortho, mat4_rotate_y, vec3
from src.rendering import Shader


def save_frame(path: str, width: int, height: int) -> None:
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    data = gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
    Image.fromarray(np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)).transpose(
        Image.FLIP_TOP_BOTTOM).save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualizador de modelos .glb")
    parser.add_argument("arquivo", nargs="?", default=None)
    parser.add_argument("--altura", type=float, default=DEFAULT_HEIGHT, help="altura do modelo, em metros")
    parser.add_argument("--giro", type=int, default=0, help="quartos de volta em y")
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--capture", default=None)
    parser.add_argument("--yaw", type=float, default=None, help="com --capture, o giro em graus")
    parser.add_argument("--andar", type=float, nargs="?", const=3.0, default=None, metavar="VELOCIDADE",
                        help="anima o modelo andando (m/s; sem valor, 3). Precisa de esqueleto")
    parser.add_argument("--perfil", choices=PROFILE_NAMES + ("clipes",), default=None, help="perfil de movimento (padrão: o sugerido)")
    parser.add_argument("--papeis", default=None, help="arquivo JSON com os papéis dos ossos (padrão: detecção automática)")
    parser.add_argument("--salvar-papeis", default=None, help="grava no arquivo os papéis usados, para editar")
    parser.add_argument("--sem-reparo", action="store_true", help="nao corta os triangulos que esticam ao andar")
    parser.add_argument("--tempo", type=float, default=None, help="com --capture, avança a animação até este segundo")
    args = parser.parse_args()

    window = Window(width=1000, height=700, title="Isometricon - Modelo personalizado", vsync=True)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glClearColor(0.12, 0.13, 0.16, 1.0)

    try:
        if args.arquivo:
            model = CustomModel.from_file(args.arquivo, args.altura, args.giro)
        else:
            model = CustomModel.from_bytes(sample_humanoid(), height=args.altura, yaw_turns=args.giro, name="amostra")
    except ModelError as error:
        print(f"Não consegui usar o modelo: {error}")
        window.close()
        sys.exit(1)
    low, high = model.bounds()
    print(f"Modelo '{model.name}': {len(model.parts)} partes, {model.triangles} triângulos, "
          f"{high[0] - low[0]:.2f} x {high[1] - low[1]:.2f} x {high[2] - low[2]:.2f} m")
    for warning in model.warnings:
        print("Aviso:", warning)
    animate = args.andar is not None or args.papeis or args.perfil or args.salvar_papeis
    if animate:
        try:
            roles = Roles.load(model.rig, args.papeis) if args.papeis and model.rig is not None else None
            roles = model.animate(roles, args.perfil)
        except (ModelError, RolesError) as error:
            print(f"Não consegui animar: {error}")
            window.close()
            sys.exit(1)
        if roles is None:
            print(f"Animação: clipes do arquivo (andar/parado: {model.animator.names}).")
        else:
            print(f"Animação: perfil '{model.animator.profile}', {len(roles.legs)} pernas, {len(roles.arms)} braços, "
                  f"cabeça de {len(roles.head)} ossos, coluna de {len(roles.spine)}.")
        if args.salvar_papeis and roles is not None:
            roles.save(model.rig, args.salvar_papeis)
            print("Papéis gravados em", args.salvar_papeis)
    if animate and model.animator is not None and not args.sem_reparo:
        cut = model.repair_stretch()
        if cut:
            print(f"Cortei {cut} triangulos que esticavam ao andar.")
    speed = args.andar if args.andar is not None else 0.0

    shader = Shader(os.path.join(PROJECT_ROOT, "assets", "shaders", "world_textured.vert"),
                    os.path.join(PROJECT_ROOT, "assets", "shaders", "world_textured.frag"))
    shader.use()
    shader.set_vec3("u_LightDir", 0.5, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.48)

    size = args.altura * 0.62
    centre = vec3(0.0, args.altura / 2.0, 0.0)
    frame = 0
    while not window.should_close():
        dt = window.update_delta_time()
        window.poll_events()
        if animate:
            if args.capture and args.tempo is not None:   # captura reprodutível: passos de tempo fixos
                step = 1.0 / 60.0
                while model.animator.time + step <= args.tempo:
                    model.update(step, speed)
            else:
                model.update(dt, speed)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        aspect = window.get_aspect_ratio()
        projection = mat4_ortho(-size * aspect, size * aspect, -size, size, 0.1, 50.0)
        view = mat4_look_at(vec3(3.0, 3.0 + centre[1], 3.0), centre, vec3(0.0, 1.0, 0.0))
        yaw = np.radians(args.yaw) if (args.capture and args.yaw is not None) else window.get_time() * 0.6
        shader.use()
        shader.set_mat4("u_Projection", projection)
        shader.set_mat4("u_View", view)
        model.draw(shader, mat4_rotate_y(float(yaw)))
        frame += 1
        if args.frames is not None and frame >= args.frames:
            if args.capture:
                save_frame(args.capture, window.width, window.height)
                print(f"Quadro salvo em {args.capture}")
            break
        window.swap_buffers()

    model.delete()
    shader.delete()
    window.close()


if __name__ == "__main__":
    main()
