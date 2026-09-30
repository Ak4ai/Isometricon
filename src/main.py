"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import math
import os
import random
import sys
from typing import Optional

# Garante que o diretório raiz e o diretório 'src' estejam no PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
from src.integration import VoxelGridProvider
from src.interaction import raycast_voxels, screen_to_world_ray
from src.interactive import BlockHighlightRenderer, PlayerToken
from src.math import mat4_identity, mat4_rotate_y, mat4_scale, mat4_translate, vec3
from src.rendering import Shader, TexturedMesh, TextureAtlas
from src.world import BlockType, Chunk3D, ChunkMesher, TerrainGenerator, WorldManager



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


def create_terrain_meshes(seed: int = 0) -> list[tuple[TexturedMesh, np.ndarray]]:
    """Demonstração finita 2x2 com cavernas 3D, culling entre vizinhos e sem WorldManager."""
    chunks = TerrainGenerator(seed=seed, enable_caves=True).generate_region(
        (x, 0, z) for x in (-1, 0) for z in (-1, 0)
    )



    def neighbor_at(x: int, y: int, z: int) -> BlockType:
        size = Chunk3D.SIZE
        chunk = chunks.get((x // size, y // size, z // size))
        if chunk is None:
            return BlockType.AIR
        return chunk.get_block(*chunk.world_to_local(x, y, z))

    meshes = []
    try:
        for chunk in chunks.values():
            data = ChunkMesher().build(chunk, neighbor_at)
            mesh = TexturedMesh(data.vertices, data.indices)
            # Escala apenas visual para enquadrar o tabuleiro na câmera existente.
            transform = mat4_scale(0.2, 0.2, 0.2) @ mat4_translate(
                *chunk.local_to_world(0, 0, 0)
            )
            meshes.append((mesh, transform))
    except Exception:
        for mesh, _ in meshes:
            mesh.delete()
        raise
    return meshes


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
    terrain_demo = "--terrain" in sys.argv[1:]
    char_demo = "--char" in sys.argv[1:] or "--character" in sys.argv[1:]

    screenshot_path = None
    max_frames = None
    custom_seed = None
    custom_yaw = None
    initial_cmd = None
    open_chat = False
    chat_text = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--seed" and i + 1 < len(sys.argv[1:]):
            try:
                custom_seed = int(sys.argv[1:][i + 1])
            except ValueError:
                pass
        elif arg.startswith("--seed="):
            try:
                custom_seed = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg == "--screenshot" and i + 1 < len(sys.argv[1:]):
            screenshot_path = sys.argv[1:][i + 1]
        elif arg.startswith("--screenshot="):
            screenshot_path = arg.split("=", 1)[1]
        elif arg == "--frames" and i + 1 < len(sys.argv[1:]):
            try:
                max_frames = int(sys.argv[1:][i + 1])
            except ValueError:
                pass
        elif arg.startswith("--frames="):
            try:
                max_frames = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg in ("--cmd", "--command") and i + 1 < len(sys.argv[1:]):
            initial_cmd = sys.argv[1:][i + 1]
        elif arg.startswith("--cmd="):
            initial_cmd = arg.split("=", 1)[1]
        elif arg in ("--yaw", "--angle") and i + 1 < len(sys.argv[1:]):
            try:
                custom_yaw = float(sys.argv[1:][i + 1])
            except ValueError:
                pass
        elif arg.startswith(("--yaw=", "--angle=")):
            try:
                custom_yaw = float(arg.split("=", 1)[1])
            except ValueError:
                pass
        elif arg in ("--open-chat", "--chat"):
            open_chat = True
        elif arg in ("--chat-text",) and i + 1 < len(sys.argv[1:]):
            chat_text = sys.argv[1:][i + 1]
            open_chat = True
        elif arg.startswith("--chat-text="):
            chat_text = arg.split("=", 1)[1]
            open_chat = True

    active_seed = {
        "value": custom_seed if custom_seed is not None else random.randint(1, 999_999)
    }

    if terrain_demo:
        print(f"[Terrain] Modo terreno ativo. Seed inicial: {active_seed['value']} (WASD para andar, [R] nova seed)")
        atlas = TextureAtlas()
        generator = TerrainGenerator(seed=active_seed["value"], enable_caves=True)
        world_manager = WorldManager(generator=generator, render_distance=2, atlas=atlas)
        start_surface_y = generator.get_height(0, 0)
        player_token = PlayerToken(start_x=0.5, start_z=0.5, speed=5.0)
        player_token.position[1] = float(start_surface_y) + 1.0
        world_manager.load_initial_region(player_token.position[0], player_token.position[2])
        voxel_provider = VoxelGridProvider(block_lookup=world_manager.neighbor_at)
        highlight_renderer = BlockHighlightRenderer()
        meshes = []
        character_model = None
        turntable_state = {"active": False, "yaw": 0.0}
    elif char_demo:
        from src.clothing.character_model import CharacterModel, parse_character_cli_args
        char_customization, top_id, bottom_id, tool_id, auto_spin = parse_character_cli_args(sys.argv[1:])
        print("=" * 68)
        print("👤 ISOMETRICON - Modo Personagem 3D (Renderizador Nativo)")
        print("=" * 68)
        print(f"🔹 Cabeça     : {char_customization.head_type_str.upper()}")
        print(f"🔹 Rosto      : Boca={char_customization.resolved_mouth_style} | Olhos={char_customization.resolved_eye_style}")
        print(f"🔹 Cabelo     : {char_customization.hair_style_str} ({char_customization.hair_color_str})")
        print(f"🔹 Roupas     : Top={top_id} | Bottom={bottom_id}")
        if tool_id:
            print(f"🔹 Tool/Arma  : {tool_id}")
        print("-" * 68)
        print("⌨️  [Q/E] Girar 90° | [Espaço] Turntable ON/OFF | [C] Wireframe Cage ON/OFF | [W] Andar ON/OFF | [Mouse Wheel] Zoom | [Shift+Drag/MMB] Pan | [R] Reset Câmera\n")

        character_model = CharacterModel(
            customization=char_customization,
            top_id=top_id,
            bottom_id=bottom_id,
            tool_id=tool_id,
            create_mesh=True,
        )
        from src.clothing.character_animation import CharacterAnimator
        # Walk in place, clothes skinned to the body's game rig ([W] toggles it).
        character_animator = CharacterAnimator(character_model, walking="--andar" in sys.argv or "--walk" in sys.argv)
        if "--cage" in sys.argv or "--debug-cage" in sys.argv:
            character_model.show_cage = True
            print("[Debug] Modo de Depuração da Cage ATIVADO por linha de comando.")
        turntable_state = {"active": auto_spin, "yaw": custom_yaw if custom_yaw is not None else 0.0}
        atlas = None
        world_manager = None
        player_token = None
        voxel_provider = None
        highlight_renderer = None
        meshes = []
    else:
        atlas = None
        world_manager = None
        player_token = None
        voxel_provider = None
        highlight_renderer = None
        character_model = None
        turntable_state = {"active": False, "yaw": 0.0}
        meshes = [(create_cube_mesh(), mat4_identity())]

    # Inicializa o console de comando e chat estilo Minecraft
    from src.interactive.chat_console import ChatConsole, SkinCommandHandler
    skin_command_handler = SkinCommandHandler(
        character_model=character_model,
        turntable_state=turntable_state,
    )
    chat_console = ChatConsole(
        command_handler=skin_command_handler,
        create_gl=True,
        glfw_window=window._window,
    )
    if initial_cmd:
        for single_cmd in initial_cmd.split(";"):
            single_cmd = single_cmd.strip()
            if single_cmd:
                _, feedback, color = skin_command_handler.execute(single_cmd)
                if feedback:
                    chat_console.add_message(feedback, color)
    if open_chat:
        chat_console.open(chat_text or "")
    
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

    # Textura neutra modula as cores dos BlockTypes sem criar um atlas/material.
    initial_png = "white_concrete.png" if terrain_demo else random.choice(png_files)
    # Estado de textura ativa
    current_texture = {
        "id": load_texture(os.path.join(textures_dir, initial_png)),
        "name": initial_png,
    }
    # Textura sólida 1x1 branca (RGBA 255, 255, 255, 255) para renderizar a miniatura com cores puras e opacidade 100%
    white_pixel = np.array([255, 255, 255, 255], dtype=np.uint8)
    token_tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, 1, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, white_pixel)

    texture_timer = 0.0
    TEXTURE_CHANGE_INTERVAL = 0.5  # Alterar textura a cada 0.5 segundos

    # ------------------------------------------------------------------
    # 4. Inicializar câmera isométrica
    # ------------------------------------------------------------------
    if terrain_demo:
        cam_target = vec3(0.5, float(start_surface_y) + 1.0, 0.5)
        cam_ortho = 4.5
    elif char_demo:
        cam_target = vec3(0.0, 0.95, 0.0)
        cam_ortho = 1.18
    else:
        cam_target = vec3(0.0, 0.0, 0.0)
        cam_ortho = 2.0

    camera = IsometricCamera(
        target=cam_target,
        ortho_size=cam_ortho,
        near=0.1,
        far=400.0,
    )


    # Estado utilizado pelo pan com botão central do mouse.
    pan_state = {
        "active": False,
        "last_x": 0.0,
        "last_y": 0.0,
        "shift_pressed": False,
    }
    picking_state = {
        "click_pending": False,
        "hover_hit": None,
        "clicked_hit": None,
    }

    # ------------------------------------------------------------------
    # 5. Callbacks de entrada
    # ------------------------------------------------------------------

    keys_pressed: dict[int, bool] = {}

    def handle_camera_key(
        key: int,
        scancode: int,
        action: int,
        mods: int,
    ) -> Optional[bool]:
        """Encaminha eventos de teclado para a câmera e registra teclas ativas."""
        del scancode

        # Intercepta eventos de teclado para o console de chat estilo Minecraft
        try:
            if chat_console.handle_key(key, action, mods):
                return True
        except Exception as e:
            print(f"[Input] Erro ao processar tecla no console de chat: {e}")
            return True

        keys_pressed[key] = (action != glfw.RELEASE)
        
        if terrain_demo and key == glfw.KEY_R and action == glfw.PRESS:
            new_seed = random.randint(1, 999_999)
            active_seed["value"] = new_seed
            print(f"[Terrain] Regenerando mundo... Nova Seed: {new_seed}")
            world_manager.delete()
            world_manager.generator = TerrainGenerator(seed=new_seed, enable_caves=True)
            # Reposiciona o token no topo do novo relevo
            new_surface = world_manager.get_height(player_token.position[0], player_token.position[2])
            player_token.position[1] = float(new_surface) + 1.0
            world_manager.load_initial_region(player_token.position[0], player_token.position[2])

        if char_demo:
            if key == glfw.KEY_SPACE and action == glfw.PRESS:
                turntable_state["active"] = not turntable_state["active"]
                st = "ATIVADO" if turntable_state["active"] else "PAUSADO"
                print(f"[Turntable] Rotação automática {st}")
            elif key == glfw.KEY_W and action == glfw.PRESS:
                character_animator.walking = not character_animator.walking
                print(f"[Animação] Caminhada {'ATIVADA' if character_animator.walking else 'PAUSADA'}")
            elif key == glfw.KEY_C and action == glfw.PRESS:
                character_model.show_cage = not character_model.show_cage
                st = "ATIVADA" if character_model.show_cage else "DESATIVADA"
                print(f"[Debug] Visualização Wireframe da Cage: {st}")
            elif key == glfw.KEY_R and action == glfw.PRESS:
                camera.target = vec3(0.0, 0.95, 0.0)
                camera.ortho_size = 1.18
                camera.board_rotation = 0
                camera.current_rotation = 0.0
                turntable_state["yaw"] = 0.0
                print("[Câmera] Posição e enquadramento resetados.")

        if key == glfw.KEY_LEFT_SHIFT:
            pan_state["shift_pressed"] = action != glfw.RELEASE
            if action == glfw.RELEASE and not window.is_mouse_button_pressed(glfw.MOUSE_BUTTON_MIDDLE):
                pan_state["active"] = False

        camera.handle_key(key, action)
        return None



    def handle_mouse_button(
        button: int,
        action: int,
        mods: int,
    ) -> None:
        """Controla o início e fim do pan com o botão central."""
        del mods
        if chat_console.is_open:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                cx, cy = window.get_cursor_pos()
                chat_console.handle_mouse_click(cx, cy)
            return
        
        is_middle = (button == glfw.MOUSE_BUTTON_MIDDLE)
        is_left_with_shift = (button == glfw.MOUSE_BUTTON_LEFT and window.is_key_pressed(glfw.KEY_LEFT_SHIFT)) 

        if action == glfw.PRESS:
            if is_middle or is_left_with_shift:
                pan_state["active"] = True
                picking_state["hover_hit"] = None

                x, y = window.get_cursor_pos()

                pan_state["last_x"] = x
                pan_state["last_y"] = y
            elif terrain_demo and button == glfw.MOUSE_BUTTON_LEFT:
                picking_state["click_pending"] = True

        elif action == glfw.RELEASE:
            if button in (glfw.MOUSE_BUTTON_MIDDLE, glfw.MOUSE_BUTTON_LEFT):
                pan_state["active"] = False

    def handle_cursor_position(
        x: float,
        y: float,
    ) -> None:
        """Move o ponto focal enquanto o botão central estiver pressionado."""
        if chat_console.is_open:
            return
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

    window.add_char_callback(
        chat_console.handle_char
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

    if char_demo:
        shader.set_vec3("u_LightDir", 0.5, 1.2, 0.8)
        shader.set_vec3("u_LightColor", 0.70, 0.70, 0.70)
        shader.set_vec3("u_AmbientColor", 0.38, 0.38, 0.38)
        gl.glClearColor(0.12, 0.13, 0.16, 1.0)


    else:
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
    title_update_timer = 0.25  # Atualiza imediatamente no primeiro frame
    frame_index = 0
    while not window.should_close():
        dt = window.update_delta_time()
        camera.update(dt)
        chat_console.update(dt)

        if terrain_demo:
            # 1. Movimentação do token de personagem com WASD e aderência ao relevo
            player_token.update(
                dt,
                keys_pressed,
                camera._forward_direction(),
                camera._right_direction(),
                world_manager.get_height,
            )

            # 2. Atualização contínua de streaming de chunks ao redor do jogador (Mapa Infinito)
            world_manager.update(player_token.position[0], player_token.position[2])

            # 3. Câmera acompanha o personagem fora do gesto de pan.
            if not pan_state["active"]:
                cam_speed = 8.0
                camera.target[0] += (player_token.position[0] - camera.target[0]) * min(dt * cam_speed, 1.0)
                camera.target[2] += (player_token.position[2] - camera.target[2]) * min(dt * cam_speed, 1.0)
                camera.target[1] += (player_token.position[1] - camera.target[1]) * min(dt * cam_speed, 1.0)
        elif char_demo:
            if turntable_state["active"]:
                turntable_state["yaw"] = (turntable_state["yaw"] + dt * 45.0) % 360.0
            character_animator.update(dt)
        else:
            texture_timer += dt
            if texture_timer >= TEXTURE_CHANGE_INTERVAL:
                texture_timer = 0.0
                random_png = random.choice(png_files)
                gl.glDeleteTextures(1, [current_texture["id"]])
                current_texture["id"] = load_texture(os.path.join(textures_dir, random_png))
                current_texture["name"] = random_png

        # --------------------------------------------------------------
        # Atualizar título da janela (amortizado a cada 0.25s para evitar micro-stutters no Win32)
        # --------------------------------------------------------------
        title_update_timer += dt
        if title_update_timer >= 0.25:
            title_update_timer = 0.0
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

            if terrain_demo:
                mode_badge = f"Seed: {active_seed['value']} (WASD: mover | [R]: reload) | "
            elif char_demo:
                spin_str = "Auto-spin: ON" if turntable_state["active"] else "Auto-spin: OFF"
                mode_badge = f"👤 {char_customization.head_type_str.capitalize()} | {spin_str} | "
            else:
                mode_badge = ""

            window.set_title(
                f"Isometricon {version_info.full_version} | "
                f"{sync_badge} | "
                f"{mode_badge}"
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
        projection = camera.get_projection_matrix(
            window.width,
            window.height,
        )
        view = camera.get_view_matrix()
        model = camera.get_animated_model_matrix()

        # O hover fica suspenso durante o drag para não disputar o gesto de pan.
        # Como os eventos são processados acima, ele retorna no frame do release.
        if terrain_demo and not pan_state["active"]:
            mouse_x, mouse_y = window.get_cursor_pos_framebuffer()
            mouse_ray = screen_to_world_ray(
                mouse_x,
                mouse_y,
                window.width,
                window.height,
                view,
                projection,
                model,
            )
            picking_state["hover_hit"] = raycast_voxels(
                mouse_ray,
                voxel_provider,
            )
            if picking_state["click_pending"]:
                picking_state["clicked_hit"] = picking_state["hover_hit"]
                clicked_hit = picking_state["clicked_hit"]
                if clicked_hit is None:
                    print("[Picking] Clique sem bloco atingido.")
                else:
                    print(
                        f"[Picking] Bloco {clicked_hit.block} "
                        f"({clicked_hit.block_type.name}), "
                        f"face {clicked_hit.normal}, "
                        f"distância {clicked_hit.distance:.3f}."
                    )
                picking_state["click_pending"] = False

        # --------------------------------------------------------------
        # Renderizar
        # --------------------------------------------------------------
        gl.glDisable(gl.GL_BLEND)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)

        shader.use()
        shader.set_mat4("u_Projection", projection)
        shader.set_mat4("u_View", view)
        shader.set_mat4("u_Model", model)

        # Vincular a textura ativa
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, current_texture["id"])
        shader.set_int("u_TextureAtlas", 0)    

        if terrain_demo:
            # 1. Renderiza os chunks de terreno e cavernas com Frustum Culling ativo
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, atlas.texture_id)
            shader.set_int("u_TextureAtlas", 0)
            view_projection = projection @ view
            world_manager.render(shader, model, view_projection)

            # 2. Renderiza o bloco abaixo do token reluzindo em branco pulsante (no chão)
            bx, by, bz = player_token.get_current_block()
            highlight_renderer.render(
                view,
                projection,
                model,
                bx,
                by,
                bz,
                time=window.time,
                base_color=(1.0, 1.0, 1.0),
            )

            # 3. Destaca em amarelo o primeiro voxel sob o cursor.
            hover_hit = picking_state["hover_hit"]
            if hover_hit is not None:
                hx, hy, hz = hover_hit.block
                highlight_renderer.render(
                    view,
                    projection,
                    model,
                    hx,
                    hy,
                    hz,
                    time=window.time,
                    base_color=(1.0, 0.72, 0.18),
                )

            # 4. Renderiza a miniatura 3D do personagem SOBRE o bloco e o highlight
            shader.use()
            shader.set_mat4("u_Projection", projection)
            shader.set_mat4("u_View", view)
            base_model = model @ player_token.get_model_matrix()
            shader.set_mat4("u_Model", base_model)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
            shader.set_int("u_TextureAtlas", 0)
            player_token.draw(shader=shader, base_model=base_model)
        elif char_demo:
            # 1. Renderiza o modelo 3D modular completo do personagem com iluminação
            spin_mat = mat4_rotate_y(math.radians(turntable_state["yaw"]))
            char_base_model = model @ spin_mat
            character_model.draw(shader, char_base_model)
        else:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, current_texture["id"])
            shader.set_int("u_TextureAtlas", 0)
            for mesh, transform in meshes:
                shader.set_mat4("u_Model", model @ transform)
                mesh.draw()

        # --------------------------------------------------------------
        # Renderizar interface 2D do Console de Chat (HUD estilo Minecraft)
        # --------------------------------------------------------------
        chat_console.render(window.width, window.height)

        # --------------------------------------------------------------
        # Captura de screenshot e limite de frames (para testes e automação)
        # --------------------------------------------------------------
        frame_index += 1
        if max_frames is not None and frame_index >= max_frames:
            if screenshot_path:
                fb_w, fb_h = glfw.get_framebuffer_size(window._window)
                gl.glFinish()
                pixels = gl.glReadPixels(0, 0, fb_w, fb_h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
                img = Image.frombytes("RGBA", (fb_w, fb_h), pixels).transpose(Image.FLIP_TOP_BOTTOM)
                os.makedirs(os.path.dirname(os.path.abspath(screenshot_path)), exist_ok=True)
                img.save(screenshot_path)
                print(f"[Screenshot] Frame capturado salvo em: {screenshot_path}")
            break

        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    gl.glDeleteTextures(1, [current_texture["id"]])
    gl.glDeleteTextures(1, [token_tex_id])
    chat_console.delete()
    if terrain_demo:
        if atlas is not None:
            atlas.delete()
        world_manager.delete()
        player_token.delete()
        highlight_renderer.delete()
    elif char_demo:
        if character_model is not None:
            character_model.delete()
    else:
        for mesh, _ in meshes:
            mesh.delete()
    shader.delete()
    window.close()


    print("Aplicação encerrada com sucesso.")


if __name__ == "__main__":
    main()
