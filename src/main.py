"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import os
import random
import sys

# Garante que o diretório raiz e o diretório 'src' estejam no PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Forçar GPU dedicada (NVIDIA Optimus / AMD PowerXpress) ANTES do OpenGL/GLFW
# No Windows, os drivers verificam esses símbolos exportados pelo executável.
# Como Python não exporta esses símbolos nativamente, usamos ctypes para
# carregar as DLLs de hint dos fabricantes antes de qualquer contexto GL.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import ctypes

    # Hint de variável de ambiente para pilhas de driver com suporte a GPU Switchable
    os.environ.setdefault("SHIM_MCCOMPAT", "0x800000001")

    # --- NVIDIA Optimus ---
    # O driver NVIDIA expõe a DLL NvOptimusEnablement via nvapi64.
    # Simplesmente carregar a DLL já sinaliza ao driver que queremos GPU discreta.
    try:
        _nv = ctypes.WinDLL("nvapi64.dll")
        # Exportar o símbolo mágico que o driver verifica
        _NvOptimusEnablement = ctypes.c_ulong(0x00000001)
    except OSError:
        pass  # NVIDIA não instalada ou não disponível

    # --- AMD PowerXpress ---
    # Mesmo mecanismo: carregar a DLL de hint do driver AMD.
    try:
        _amd = ctypes.WinDLL("amdxx64.dll")
        _AmdPowerXpressRequestHighPerformance = ctypes.c_int(0x00000001)
    except OSError:
        try:
            _amd = ctypes.WinDLL("atiadlxx.dll")
            _AmdPowerXpressRequestHighPerformance = ctypes.c_int(0x00000001)
        except OSError:
            pass  # AMD não instalada ou não disponível

# Inicializa o pacote e seleciona o backend antes de importar OpenGL.
import src

import glfw
import OpenGL.GL as gl
import numpy as np
from PIL import Image

from src.camera import IsometricCamera
from src.core.version import (
    VersionInfo,
    get_local_version_info,
    start_github_sync_check,
)
from src.core.window import Window
from src.math import mat4_rotate_y, vec3
from src.rendering import Mesh, Shader, TexturedMesh


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


def load_texture(texture_path: str) -> int:
    """Carrega uma textura a partir de um arquivo e retorna o ID da textura OpenGL."""
    img = Image.open(texture_path).convert("RGBA")
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img_data = img.tobytes()
    
    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)             
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)             
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)        
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D, 0, gl.GL_RGBA,
        img.width, img.height, 0,
        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data
    )
    return tex_id


def create_cube_mesh() -> TexturedMesh:
    """Cria uma malha 3D de cubo unitário centralizado para testes de renderização."""
    # Layout: [x, y, z, nx, ny, nz, u, v, r, g, b] (11 floats por vértice)               
    vertices = np.array([                                                                
        # Face Topo (+Y)                                                                 
        -0.5,  0.5,  0.5,   0.0,  1.0,  0.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
         0.5,  0.5,  0.5,   0.0,  1.0,  0.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
         0.5,  0.5, -0.5,   0.0,  1.0,  0.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
        -0.5,  0.5, -0.5,   0.0,  1.0,  0.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
                                                                                            
        # Face Frontal (+Z)                                                              
        -0.5, -0.5,  0.5,   0.0,  0.0,  1.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
         0.5, -0.5,  0.5,   0.0,  0.0,  1.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
         0.5,  0.5,  0.5,   0.0,  0.0,  1.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
        -0.5,  0.5,  0.5,   0.0,  0.0,  1.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
                                                                                            
        # Face Direita (+X)                                                              
         0.5, -0.5,  0.5,   1.0,  0.0,  0.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
         0.5, -0.5, -0.5,   1.0,  0.0,  0.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
         0.5,  0.5, -0.5,   1.0,  0.0,  0.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
         0.5,  0.5,  0.5,   1.0,  0.0,  0.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
                                                                                            
        # Face Traseira (-Z)                                                             
         0.5, -0.5, -0.5,   0.0,  0.0, -1.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
        -0.5, -0.5, -0.5,   0.0,  0.0, -1.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
        -0.5,  0.5, -0.5,   0.0,  0.0, -1.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
         0.5,  0.5, -0.5,   0.0,  0.0, -1.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
                                                                                            
        # Face Esquerda (-X)                                                             
        -0.5, -0.5, -0.5,  -1.0,  0.0,  0.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
        -0.5, -0.5,  0.5,  -1.0,  0.0,  0.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
        -0.5,  0.5,  0.5,  -1.0,  0.0,  0.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
        -0.5,  0.5, -0.5,  -1.0,  0.0,  0.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
                                                                                            
        # Face Fundo (-Y)                                                                
        -0.5, -0.5, -0.5,   0.0, -1.0,  0.0,   0.0, 0.0,   1.0, 1.0, 1.0,                
         0.5, -0.5, -0.5,   0.0, -1.0,  0.0,   1.0, 0.0,   1.0, 1.0, 1.0,                
         0.5, -0.5,  0.5,   0.0, -1.0,  0.0,   1.0, 1.0,   1.0, 1.0, 1.0,                
        -0.5, -0.5,  0.5,   0.0, -1.0,  0.0,   0.0, 1.0,   1.0, 1.0, 1.0,                
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

    return TexturedMesh(vertices, indices)


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
    print("⌨️  [Q/E] Rotacionar | [Mouse Wheel] Zoom | [Espaço + Arrastar / MMB] Pan | [ESC] Sair\n")


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
        "world_textured.vert",
    )

    shader_frag = os.path.join(
        PROJECT_ROOT,
        "assets",
        "shaders",
        "world_textured.frag",
    )

    shader = Shader(shader_vert, shader_frag)
    cube_mesh = create_cube_mesh()
    
    # Carregar lista de texturas PNG de assets filtrando apenas blocos sólidos quadrados (100% opacos)
    textures_dir = os.path.join(PROJECT_ROOT, "assets", "textures", "blocks")
    all_pngs = [f for f in os.listdir(textures_dir) if f.lower().endswith(".png")]
    
    # Exclui itens conhecidos que não são blocos sólidos (plantas, tochas, portas, trilhos, etc.)
    non_solid_keywords = (
        "door", "trapdoor", "torch", "flower", "sapling", "pane", "glass",
        "leaves", "rail", "chain", "lantern", "vine", "bush", "wire", "lever",
        "button", "crop", "stem", "roots", "fungus", "coral", "fan", "dust",
        "redstone", "candle", "bars", "ladder", "sprout", "lichen", "egg"
    )
    png_files = [f for f in all_pngs if not any(k in f for k in non_solid_keywords)]
    if not png_files:
        png_files = all_pngs

    initial_png = random.choice(png_files)
    # Estado de textura ativa
    current_texture = {
        "id": load_texture(os.path.join(textures_dir, initial_png)),
        "name": initial_png,
    }
    texture_timer = 0.0
    TEXTURE_CHANGE_INTERVAL = 0.5  # Alterar textura a cada 0.5 segundos

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
        "shift_pressed": False,
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
        del scancode,mods
        
        if key == glfw.KEY_LEFT_SHIFT:
            pan_state["shift_pressed"] = action != glfw.RELEASE
            if action == glfw.RELEASE and not window.is_mouse_button_pressed(glfw.MOUSE_BUTTON_MIDDLE):
                pan_state["active"] = False

        camera.handle_key(key, action)

    def handle_mouse_button(
        button: int,
        action: int,
        mods: int,
    ) -> None:
        """Controla o início e fim do pan com o botão central."""
        del mods
        
        is_middle = (button == glfw.MOUSE_BUTTON_MIDDLE)
        is_left_with_shift = (button == glfw.MOUSE_BUTTON_LEFT and window.is_key_pressed(glfw.KEY_LEFT_SHIFT)) 

        if action == glfw.PRESS:
            if is_middle or is_left_with_shift:
                pan_state["active"] = True

                x, y = window.get_cursor_pos()

                pan_state["last_x"] = x
                pan_state["last_y"] = y

        elif action == glfw.RELEASE:
            if button in (glfw.MOUSE_BUTTON_MIDDLE, glfw.MOUSE_BUTTON_LEFT):
                pan_state["active"] = False

    def handle_cursor_position(
        x: float,
        y: float,
    ) -> None:
        """Move o ponto focal enquanto o botão central estiver pressionado."""
        if pan_state["active"] and not window.is_mouse_button_pressed(glfw.MOUSE_BUTTON_MIDDLE):
            if not window.is_key_pressed(glfw.KEY_LEFT_SHIFT):
                pan_state["active"] = False
                return
        
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
        0.5,
        1.0,
        0.7,
    )

    shader.set_vec3(
        "u_LightColor",
        0.9,
        0.9,
        0.9,
    )

    shader.set_vec3(
        "u_AmbientColor",
        0.35,
        0.35,
        0.35,
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
        camera.update(dt)
        texture_timer += dt
        
        if texture_timer >= TEXTURE_CHANGE_INTERVAL:
            texture_timer = 0.0
            random_png = random.choice(png_files)
            
            # Libera textura anterior
            gl.glDeleteTextures(1, [current_texture["id"]])
            current_texture["id"] = load_texture(os.path.join(textures_dir, random_png))
            current_texture["name"] = random_png

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
        model = camera.get_animated_model_matrix()

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
        
        # Vincular a textura atual
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, current_texture["id"])
        shader.set_int("u_TextureAtlas", 0)    

        cube_mesh.draw()

        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    gl.glDeleteTextures(1, [current_texture["id"]])
    cube_mesh.delete()
    shader.delete()
    window.close()

    print("Aplicação encerrada com sucesso.")


if __name__ == "__main__":
    main()
