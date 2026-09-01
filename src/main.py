"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import os
import sys

# Garante que o diretório raiz e o diretório 'src' estejam no PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import glfw
import OpenGL.GL as gl
import numpy as np

from src.camera import IsometricCamera
from src.core.version import (
    VersionInfo,
    get_local_version_info,
    start_github_sync_check,
)
from src.core.window import Window
from src.math import vec3
from src.rendering import Mesh, Shader


def setup_opengl_state() -> None:
    """Configura o pipeline fixo inicial e estados de profundidade e culling."""
    # Teste de profundidade (Z-Buffer) para correta oclusão 3D
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_LESS)

    # Face Culling na GPU
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)

    # Cor de fundo padrão
    gl.glClearColor(0.08, 0.10, 0.13, 1.0)


def create_cube_mesh() -> Mesh:
    """Cria uma malha 3D de cubo unitário centralizado para testes de renderização."""
    # Layout por vértice:
    # [x, y, z, nx, ny, nz, r, g, b]
    vertices = np.array([
        # Face Topo (+Y) - Grama verde viva
        -0.5,  0.5, -0.5,   0.0,  1.0,  0.0,   0.34, 0.76, 0.28,
         0.5,  0.5, -0.5,   0.0,  1.0,  0.0,   0.34, 0.76, 0.28,
         0.5,  0.5,  0.5,   0.0,  1.0,  0.0,   0.34, 0.76, 0.28,
        -0.5,  0.5,  0.5,   0.0,  1.0,  0.0,   0.34, 0.76, 0.28,

        # Face Frontal (+Z) - Terra marrom
        -0.5, -0.5,  0.5,   0.0,  0.0,  1.0,   0.55, 0.38, 0.24,
         0.5, -0.5,  0.5,   0.0,  0.0,  1.0,   0.55, 0.38, 0.24,
         0.5,  0.5,  0.5,   0.0,  0.0,  1.0,   0.55, 0.38, 0.24,
        -0.5,  0.5,  0.5,   0.0,  0.0,  1.0,   0.55, 0.38, 0.24,

        # Face Direita (+X) - Terra marrom
         0.5, -0.5,  0.5,   1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
         0.5, -0.5, -0.5,   1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
         0.5,  0.5, -0.5,   1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
         0.5,  0.5,  0.5,   1.0,  0.0,  0.0,   0.50, 0.34, 0.20,

        # Face Traseira (-Z) - Terra marrom
         0.5, -0.5, -0.5,   0.0,  0.0, -1.0,   0.45, 0.30, 0.18,
        -0.5, -0.5, -0.5,   0.0,  0.0, -1.0,   0.45, 0.30, 0.18,
        -0.5,  0.5, -0.5,   0.0,  0.0, -1.0,   0.45, 0.30, 0.18,
         0.5,  0.5, -0.5,   0.0,  0.0, -1.0,   0.45, 0.30, 0.18,

        # Face Esquerda (-X) - Terra marrom
        -0.5, -0.5, -0.5,  -1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
        -0.5, -0.5,  0.5,  -1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
        -0.5,  0.5,  0.5,  -1.0,  0.0,  0.0,   0.50, 0.34, 0.20,
        -0.5,  0.5, -0.5,  -1.0,  0.0,  0.0,   0.50, 0.34, 0.20,

        # Face Fundo (-Y) - Rocha escura
        -0.5, -0.5,  0.5,   0.0, -1.0,  0.0,   0.30, 0.30, 0.32,
         0.5, -0.5,  0.5,   0.0, -1.0,  0.0,   0.30, 0.30, 0.32,
         0.5, -0.5, -0.5,   0.0, -1.0,  0.0,   0.30, 0.30, 0.32,
        -0.5, -0.5, -0.5,   0.0, -1.0,  0.0,   0.30, 0.30, 0.32,
    ], dtype=np.float32)

    # Índices com enrolamento anti-horário (CCW)
    indices = np.array([
         0,  1,  2,   2,  3,  0,    # Topo
         4,  5,  6,   6,  7,  4,    # Frente
         8,  9, 10,  10, 11,  8,    # Direita
        12, 13, 14,  14, 15, 12,    # Traseira
        16, 17, 18,  18, 19, 16,    # Esquerda
        20, 21, 22,  22, 23, 20,    # Fundo
    ], dtype=np.uint32)

    return Mesh(vertices, indices)


def print_system_info(version_info: VersionInfo) -> None:
    """Imprime informações de hardware, versão de build e status do repositório."""
    vendor = gl.glGetString(gl.GL_VENDOR).decode("utf-8")
    renderer = gl.glGetString(gl.GL_RENDERER).decode("utf-8")
    version = gl.glGetString(gl.GL_VERSION).decode("utf-8")
    glsl_version = gl.glGetString(
        gl.GL_SHADING_LANGUAGE_VERSION
    ).decode("utf-8")

    print("=" * 68)
    print("🎲 ISOMETRICON - 3D Voxel Virtual Tabletop Engine")
    print("=" * 68)
    print(f"📦 Versão Build   : {version_info.full_version}")
    print(f"🔗 Status GitHub  : {version_info.status_display}")

    if version_info.commit_date:
        print(f"📅 Data do Commit : {version_info.commit_date}")

    print("-" * 68)
    print(f"🔹 GPU Vendor     : {vendor}")
    print(f"🔹 GPU Renderer   : {renderer}")
    print(f"🔹 OpenGL Version : {version}")
    print(f"🔹 GLSL Version   : {glsl_version}")
    print("=" * 68)
    print("⌨️  [Q/E] Rotacionar | [Mouse Wheel] Zoom | [MMB] Pan | [ESC] Sair\n")


def main() -> None:
    """Loop principal de execução da engine gráfica."""

    # ------------------------------------------------------------------
    # 1. Carregar versão local e iniciar checagem assíncrona com o GitHub
    # ------------------------------------------------------------------
    version_info = get_local_version_info()
    sync_thread = start_github_sync_check(version_info)

    # ------------------------------------------------------------------
    # 2. Inicializar janela GLFW e contexto OpenGL 3.3 Core
    # ------------------------------------------------------------------
    window = Window(
        width=1280,
        height=720,
        title=f"Isometricon {version_info.full_version} - Inicializando...",
        vsync=True,
    )

    setup_opengl_state()

    # Aguardar até 0.2s para a thread de sync responder
    sync_thread.join(timeout=0.2)

    print_system_info(version_info)

    # ------------------------------------------------------------------
    # 3. Inicializar pipeline de renderização
    # ------------------------------------------------------------------
    shader_vert = os.path.join(
        PROJECT_ROOT,
        "assets",
        "shaders",
        "world.vert",
    )

    shader_frag = os.path.join(
        PROJECT_ROOT,
        "assets",
        "shaders",
        "world.frag",
    )

    shader = Shader(shader_vert, shader_frag)
    cube_mesh = create_cube_mesh()

    # ------------------------------------------------------------------
    # 4. Inicializar câmera isométrica
    # ------------------------------------------------------------------
    camera = IsometricCamera(
        target=vec3(0.0, 0.0, 0.0),
        ortho_size=2.0,
        near=0.1,
        far=100.0,
    )

    # Estado utilizado pelo pan com botão central do mouse.
    pan_state = {
        "active": False,
        "last_x": 0.0,
        "last_y": 0.0,
    }

    # ------------------------------------------------------------------
    # 5. Callbacks de entrada
    # ------------------------------------------------------------------

    def handle_camera_key(
        key: int,
        scancode: int,
        action: int,
        mods: int,
    ) -> None:
        """Encaminha eventos de teclado para a câmera."""
        del scancode
        del mods

        camera.handle_key(key, action)

    def handle_mouse_button(
        button: int,
        action: int,
        mods: int,
    ) -> None:
        """Controla o início e fim do pan com o botão central."""
        del mods

        if button != glfw.MOUSE_BUTTON_MIDDLE:
            return

        if action == glfw.PRESS:
            pan_state["active"] = True

            x, y = window.get_cursor_pos()

            pan_state["last_x"] = x
            pan_state["last_y"] = y

        elif action == glfw.RELEASE:
            pan_state["active"] = False

    def handle_cursor_position(
        x: float,
        y: float,
    ) -> None:
        """Move o ponto focal enquanto o botão central estiver pressionado."""
        if not pan_state["active"]:
            return

        dx = x - pan_state["last_x"]
        dy = y - pan_state["last_y"]

        camera.pan_screen(
            dx,
            dy,
        )

        pan_state["last_x"] = x
        pan_state["last_y"] = y

    # Registrar callbacks na janela.
    window.add_scroll_callback(
        camera.handle_scroll
    )

    window.add_key_callback(
        handle_camera_key
    )

    window.add_mouse_button_callback(
        handle_mouse_button
    )

    window.add_cursor_pos_callback(
        handle_cursor_position
    )

    # ------------------------------------------------------------------
    # 6. Configuração de iluminação
    # ------------------------------------------------------------------
    shader.use()

    shader.set_vec3(
        "u_LightDir",
        0.6,
        1.0,
        0.4,
    )

    shader.set_vec3(
        "u_LightColor",
        1.0,
        0.98,
        0.90,
    )

    shader.set_vec3(
        "u_AmbientColor",
        0.35,
        0.35,
        0.38,
    )

    shader.set_bool(
        "u_UseInstancing",
        False,
    )

    # ------------------------------------------------------------------
    # 7. Game Loop de Renderização
    # ------------------------------------------------------------------
    while not window.should_close():
        dt = window.update_delta_time()

        # --------------------------------------------------------------
        # Atualizar título da janela
        # --------------------------------------------------------------
        sync_badge = (
            "✅ Synced"
            if version_info.sync_status == "synced"
            else (
                "⚠️ Outdated"
                if version_info.sync_status == "outdated"
                else (
                    "📝 Modified"
                    if version_info.sync_status == "modified"
                    else "🔄 Checking"
                )
            )
        )

        window.set_title(
            f"Isometricon {version_info.full_version} | "
            f"{sync_badge} | "
            f"{window.fps:.1f} FPS "
            f"({dt * 1000:.1f}ms)"
        )

        # --------------------------------------------------------------
        # Processar eventos de I/O
        # --------------------------------------------------------------
        window.poll_events()

        # --------------------------------------------------------------
        # Limpar buffers
        # --------------------------------------------------------------
        gl.glClear(
            gl.GL_COLOR_BUFFER_BIT
            | gl.GL_DEPTH_BUFFER_BIT
        )

        # --------------------------------------------------------------
        # Matrizes da câmera
        # --------------------------------------------------------------

        # Projeção ortográfica.
        projection = camera.get_projection_matrix(
            window.width,
            window.height,
        )

        # View Matrix da câmera isométrica.
        view = camera.get_view_matrix()

        # Matriz do tabuleiro.
        # Rotação em passos de 90° através de Q/E.
        model = camera.get_model_matrix()

        # --------------------------------------------------------------
        # Renderizar
        # --------------------------------------------------------------
        shader.use()

        shader.set_mat4(
            "u_Projection",
            projection,
        )

        shader.set_mat4(
            "u_View",
            view,
        )

        shader.set_mat4(
            "u_Model",
            model,
        )

        cube_mesh.draw()

        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    cube_mesh.delete()
    shader.delete()
    window.close()

    print("Aplicação encerrada com sucesso.")


if __name__ == "__main__":
    main()
