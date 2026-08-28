"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import os
import sys

# Garante que o diretório raiz e o diretório 'src' estejam no PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import OpenGL.GL as gl
from src.core.window import Window


def setup_opengl_state() -> None:
    """Configura o pipeline fixo inicial e estados de profundidade e culling."""
    # Teste de profundidade (Z-Buffer) para correta oclusão 3D
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_LESS)

    # Face Culling na GPU (descarta faces traseiras para ganho de performance)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)

    # Cor de fundo padrão (Dark Slate / Mesa de RPG)
    gl.glClearColor(0.08, 0.10, 0.13, 1.0)


def print_system_info() -> None:
    """Imprime informações da GPU e do contexto OpenGL ativo no console."""
    vendor = gl.glGetString(gl.GL_VENDOR).decode("utf-8")
    renderer = gl.glGetString(gl.GL_RENDERER).decode("utf-8")
    version = gl.glGetString(gl.GL_VERSION).decode("utf-8")
    glsl_version = gl.glGetString(gl.GL_SHADING_LANGUAGE_VERSION).decode("utf-8")

    print("=" * 65)
    print("🎲 ISOMETRICON - 3D Voxel Virtual Tabletop Engine")
    print("=" * 65)
    print(f"🔹 GPU Vendor    : {vendor}")
    print(f"🔹 GPU Renderer  : {renderer}")
    print(f"🔹 OpenGL Version: {version}")
    print(f"🔹 GLSL Version  : {glsl_version}")
    print("=" * 65)
    print("⌨️  Pressione [ESC] para sair da aplicação.\n")


def main() -> None:
    """Loop principal de execução da engine gráfica."""
    window = Window(
        width=1280,
        height=720,
        title="Isometricon - Inicializando OpenGL 3.3 Core...",
        vsync=True,
    )

    setup_opengl_state()
    print_system_info()

    # Loop de Renderização
    while not window.should_close():
        dt = window.update_delta_time()

        # Atualizar FPS no título da janela
        window.set_title(
            f"Isometricon - 3D VTT Engine | OpenGL 3.3 Core | FPS: {window.fps:.1f} | Delta: {dt * 1000:.2f}ms"
        )

        # Processar eventos de I/O
        window.poll_events()

        # Limpar buffers de cor e profundidade a cada frame
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # (Aqui os renderizadores de mundo, malha e UI serão chamados nos próximos passos)

        # Apresentar o frame renderizado na tela
        window.swap_buffers()

    window.close()
    print("Aplicação encerrada com sucesso.")


if __name__ == "__main__":
    main()
