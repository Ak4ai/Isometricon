"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import math
import os
import random
import sys
import gc
import time
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

import OpenGL  # depois do bootstrap do ``src`` (ele escolhe a plataforma do PyOpenGL)

# O PyOpenGL confere glGetError depois de CADA chamada (~3 ms por quadro aqui); --gl-debug liga de volta.
OpenGL.ERROR_CHECKING = "--gl-debug" in sys.argv
# A thread dos chunks e da água é Python puro: com a troca padrão (5 ms) o quadro esperava o GIL várias vezes
# seguidas a cada passo pequeno do numpy. Trocando mais vezes, o quadro volta logo.
sys.setswitchinterval(0.0005)

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
from src.interactive import BlockHighlightRenderer, GridOverlayRenderer, PlayerToken
from src.interactive.coordinate_overlay import CoordinateOverlayRenderer
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
    print("⌨️  [Q/E] Rotacionar | [G] Grid | [Mouse Wheel] Zoom | [Shift + Arrastar / MMB] Pan | [ESC] Pausar\n")


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

    from src.interactive.game_menus import GameMenus
    menus = GameMenus(version_info.full_version)
    selected_world = None
    show_menu = "--menu" in sys.argv or (
        not any(flag in sys.argv for flag in ("--terrain", "--char", "--character", "--frames"))
        and not any(a.startswith("--frames=") for a in sys.argv)
    )
    if show_menu:
        if screenshot_path:
            menus.prepare_background(wait=True)
        def menu_mouse(button, action, mods):
            if button == glfw.MOUSE_BUTTON_LEFT:
                menus.mouse_button(*window.get_cursor_pos_framebuffer(), action)
        window.add_key_callback(lambda key, scan, action, mods: menus.key(key, action, mods))
        window.add_char_callback(menus.char)
        window.add_mouse_button_callback(menu_mouse)
        window.add_cursor_pos_callback(lambda x, y: menus.hover(*window.get_cursor_pos_framebuffer()))
        menu_frames = 0
        while not window.should_close() and menus.result is None:
            window.poll_events()
            window.set_vsync(menus.preferences.data['vsync'])
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            menus.render(window.width, window.height)
            menu_frames += 1
            if max_frames is not None and menu_frames >= max_frames:
                if screenshot_path:
                    os.makedirs(os.path.dirname(os.path.abspath(screenshot_path)), exist_ok=True)
                    pixels = gl.glReadPixels(0, 0, window.width, window.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
                    Image.frombytes('RGBA', (window.width, window.height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(screenshot_path)
                menus.result = ('exit', None)
            window.swap_buffers()
        window._key_callbacks.clear()
        window._char_callbacks.clear()
        window._mouse_button_callbacks.clear()
        window._cursor_pos_callbacks.clear()
        if window.should_close() or menus.result[0] == 'exit':
            menus.delete()
            shader.delete()
            window.close()
            return
        selected_world = menus.result[1]
        custom_seed = selected_world['seed']
        terrain_demo, char_demo = True, False
    menus.go('game')
    menus.result = None
    if "--no-vsync" in sys.argv:  # medir o custo real do quadro, sem esperar a tela
        menus.preferences.data['vsync'] = False
    window.set_vsync(menus.preferences.data['vsync'])

    active_seed = {
        "value": custom_seed if custom_seed is not None else random.randint(1, 999_999)
    }

    # O personagem gravado (saves/personagem.json) volta, a menos que a linha de comando escolha outro.
    from src.clothing import character_save
    saved_character = character_save.load() if character_save.wanted(sys.argv[1:]) else None
    if selected_world and selected_world.get('character'):
        saved_character = selected_world['character']
    if saved_character is not None:
        print("[Skin] Personagem salvo carregado (use --novo para começar do padrão).")

    if terrain_demo:
        print(f"[Terrain] Modo terreno ativo. Seed inicial: {active_seed['value']} (WASD para andar, Espaço para pular, [R] nova seed)")
        atlas = TextureAtlas()
        # a região da textura da água no atlas: o shader reconhece a água por ela (as duas passadas do terreno)
        water_uv = atlas.uv_table[int(BlockType.WATER)].reshape(-1, 2)
        water_rect = (float(water_uv[:, 0].min()), float(water_uv[:, 1].min()),
                      float(water_uv[:, 0].max()), float(water_uv[:, 1].max()))
        generator = TerrainGenerator(seed=active_seed["value"], enable_caves=True, vegetation=True)
        world_manager = WorldManager(generator=generator, render_distance=2, atlas=atlas)
        start_surface_y = generator.get_height(0, 0)
        avatar = None
        if "--token-antigo" not in sys.argv[1:]:
            # The player is the dressed character of the viewer (--char), walking with the token.
            # Body, hair and clothes take the same options (--male, --top, --bottom...).
            from src.clothing.character_model import CharacterModel, parse_character_cli_args
            char_customization, top_id, bottom_id, tool_id, _ = parse_character_cli_args(sys.argv[1:])
            worn = dict(customization=char_customization, top_id=top_id, bottom_id=bottom_id, tool_id=tool_id)
            if saved_character is not None:
                worn = character_save.model_arguments(saved_character)  # the character of the last time
            # Built off the main thread, so the window stays responsive; a screenshot run waits for the
            # finished character instead (it was taken with the loading notice up and no character yet).
            avatar = CharacterModel(create_mesh=True, async_loading=screenshot_path is None, **worn)
        player_token = PlayerToken(start_x=0.5, start_z=0.5, speed=5.0, avatar=avatar)
        player_token.position[1] = float(start_surface_y) + 1.0
        if selected_world and selected_world.get('position'):
            player_token.position[:] = selected_world['position']
        pos_arg = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--pos=")), "")
        if pos_arg:  # --pos=x,y,z: começa nesse ponto (conferências)
            player_token.position[:] = [float(v) for v in pos_arg.split(",")]
        world_manager.load_initial_region(player_token.position[0], player_token.position[2])
        # Construções (.schem) colocadas com /schem: aparecem por cima do terreno e têm colisão
        from src.interactive.schematic_tool import SchematicTool

        def schematic_view_axes():
            try:
                return camera.get_movement_directions()
            except NameError:  # um --cmd de abertura roda antes de a câmera existir
                return vec3(0.0, 0.0, -1.0), vec3(1.0, 0.0, 0.0)

        schematic_tool = SchematicTool(
            ground_height=lambda x, z: world_manager.get_height(x, z),
            player_position=lambda: tuple(player_token.position),
            view_axes=schematic_view_axes,
        )
        # a construção fixada ocupa a caixa dela: o terreno ali dentro vira ar (como colar no Minecraft)
        schematic_tool.on_place = lambda placed: world_manager.clear_box(*placed.bounds())
        schematic_tool.on_remove = lambda placed: world_manager.restore_box(*placed.bounds())
        voxel_provider = VoxelGridProvider(
            block_lookup=lambda x, y, z: schematic_tool.lookup(world_manager.neighbor_at, x, y, z)
        )
        # Revela só o espaço fechado do jogador (cômodo, caverna) e escurece o resto
        from src.rendering.room_reveal import RoomRevealRenderer
        from src.world.room_reveal import RoomRevealTracker
        from src.rendering.sun_shadows import SunShadowRenderer
        shadow_renderer = SunShadowRenderer()
        room_tracker = RoomRevealTracker(background=True)
        room_renderer = RoomRevealRenderer(terrain_atlas=atlas, structure_atlas=lambda: schematic_tool.atlas_if_ready(),
                                           background=True)
        # A tecla E ao lado do personagem quando há uma porta ao alcance
        from src.interactive.interact_prompt import InteractPrompt
        interact_prompt = InteractPrompt()
        # O cursor de contexto (no lugar da seta do sistema) e a mira do personagem, como no Isocraft
        from src.interactive.context_cursor import ContextCursor
        context_cursor = ContextCursor()
        from src.interactive.context_cursor import DepthProbe
        depth_probe = DepthProbe()  # o que aparece sob o mouse: o cursor não para nos blocos que o corte escondeu
        story_state = {"level": 0.0, "cut_y": 1_000_000, "sight": 1.0}  # corte do andar de cima e corredor (suavizados)
        highlight_renderer = BlockHighlightRenderer()
        coordinate_overlay = CoordinateOverlayRenderer()
        grid_renderer = GridOverlayRenderer()
        meshes = []
        character_model = avatar  # chat commands (/import, /corpo...) dress the player
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

        worn = dict(customization=char_customization, top_id=top_id, bottom_id=bottom_id, tool_id=tool_id)
        if saved_character is not None:
            worn = character_save.model_arguments(saved_character)  # the character of the last time
            char_customization = worn["customization"]
        character_model = CharacterModel(
            **worn,
            create_mesh=True,
            # Clothes are fitted and the model assembled off the main thread, so the window
            # stays responsive (a screenshot run waits for the finished model instead).
            async_loading=screenshot_path is None,
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
        schematic_tool = None
        room_tracker = room_renderer = shadow_renderer = None
        interact_prompt = None
        context_cursor = None
        player_token = None
        voxel_provider = None
        highlight_renderer = None
        coordinate_overlay = None
        grid_renderer = None
        meshes = []
    else:
        atlas = None
        world_manager = None
        schematic_tool = None
        room_tracker = room_renderer = None
        interact_prompt = None
        context_cursor = None
        player_token = None
        voxel_provider = None
        highlight_renderer = None
        coordinate_overlay = None
        character_model = None
        turntable_state = {"active": False, "yaw": 0.0}
        grid_renderer = None
        meshes = [(create_cube_mesh(), mat4_identity())]

    # Inicializa o console de comando e chat estilo Minecraft
    from src.interactive.chat_console import ChatConsole, SkinCommandHandler
    skin_command_handler = SkinCommandHandler(
        character_model=character_model,
        turntable_state=turntable_state,
    )
    skin_command_handler.schematic_tool = schematic_tool
    skin_command_handler.room_reveal = room_renderer
    skin_command_handler.sun_shadows = shadow_renderer
    skin_command_handler.world_seed = (lambda: active_seed["value"]) if terrain_demo else None
    if terrain_demo:
        skin_command_handler.place_water = lambda x, y, z: world_manager.place_water(x, y, z)
        skin_command_handler.place_block = lambda x, y, z, block: world_manager.place_block(x, y, z, block)
        skin_command_handler.player_cell = lambda: tuple(int(np.floor(float(v))) for v in player_token.position)
        skin_command_handler.player_token = player_token
        skin_command_handler.save_model_choice = max_frames is None  # uma execução automática não mexe na escolha
        if "--sem-modelo" not in sys.argv[1:]:
            # o modelo .glb da última vez (/skin modelo), no lugar do personagem montado
            from src.clothing import custom_model_store
            saved_model = custom_model_store.load_choice()
            if saved_model is not None:
                _, model_feedback, _ = skin_command_handler.apply_custom_model(saved_model)
                print(model_feedback)
    chat_console = ChatConsole(
        command_handler=skin_command_handler,
        create_gl=True,
        glfw_window=window._window,
    )
    if schematic_tool is not None:
        # Enter/Esc na prévia respondem no chat, como o resto dos comandos
        schematic_tool.notify = lambda text: chat_console.add_message("[Schem] " + text, (85, 255, 85))
    if initial_cmd:
        for single_cmd in initial_cmd.split(";"):
            single_cmd = single_cmd.strip()
            if single_cmd:
                _, feedback, color = skin_command_handler.execute(single_cmd)
                if feedback:
                    chat_console.add_message(feedback, color)
    if open_chat:
        chat_console.open(chat_text or "")

    # Tela de criação de personagem (/skin interface, ou --editor para já abrir nela).
    from src.interactive.character_editor import CharacterEditor
    character_editor = CharacterEditor(skin_command_handler, turntable_state, create_gl=True)
    character_editor.autosave = max_frames is None  # an automated run (--frames) leaves the save alone
    character_editor.clipboard = chat_console._get_clipboard_string
    editor_camera = {"saved": None, "focus": "body"}
    EDITOR_FACE_HEIGHT, EDITOR_FACE_ZOOM = 1.65, 0.30  # altura do rosto sem esqueleto ainda; meia altura enquadrada
    editor_arg = next((a for a in sys.argv[1:] if a == "--editor" or a.startswith("--editor=")), None)
    if editor_arg is not None and character_model is not None:
        skin_command_handler.editor_requested = True
        wanted = editor_arg.partition("=")[2].lower()  # --editor=cabelo abre nessa seção
        for index, section in enumerate(character_editor.sections):
            if wanted and section.title.lower().startswith(wanted):
                character_editor.select_section(index)
                break
        brush_arg = next((a.partition("=")[2].lower() for a in sys.argv[1:] if a.startswith("--pincel=")), "")
        if brush_arg in ("esconder", "mostrar", "apagar"):  # o pincel de pele já ligado (capturas de tela)
            character_editor.brush, character_editor.brush_on, character_editor.clear_clothes = brush_arg, True, True
            turntable_state["active"] = False
    
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
    if terrain_demo and "--cam=ortho" not in sys.argv[1:]:
        # câmera do terreno no padrão do Isocraft: yaw 45°, pitch 30°, FOV estreito de 18° (quase ortográfica).
        # Page Up/Down inclinam de 15° a 75°; --cam=ortho volta à isométrica exata
        camera.perspective = True
        camera.pitch = math.radians(30.0)
        camera.yaw = math.radians(45.0)


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
        "aim": None,          # para onde o cursor aponta (mundo): o personagem vira para lá
        "door": None,         # a porta sob o cursor
        "door_in_reach": False,
    }
    # a seta do sistema escondida (o cursor de contexto no lugar) e quando o mouse se mexeu por último: parado
    # por alguns segundos, o cursor some e o jogo segue só no teclado (o personagem vira para onde anda)
    cursor_state = {"hidden": False, "last_used": -1e9}

    def mouse_used() -> None:
        cursor_state["last_used"] = window.time

    def cursor_idle() -> float:
        """Segundos desde que o mouse (ou o touchpad) foi usado."""
        return window.time - cursor_state["last_used"]

    def cursor_in_use() -> bool:
        from src.interactive.context_cursor import CURSOR_IDLE
        return cursor_idle() < CURSOR_IDLE

    def interact_key_name() -> str:
        """A letra da tecla de interagir (F por padrão, ou a das preferências)."""
        code = menus.preferences.data['bindings'].get('interact', glfw.KEY_F)
        try:
            name = glfw.get_key_name(code, 0)
        except Exception:
            name = None
        return (name or "F").upper()

    def hovered_door_in_reach():
        """A porta sob o cursor, se está ao alcance da mão do personagem (ou None)."""
        return picking_state["door"] if picking_state["door_in_reach"] else None

    def toggle_door_for_player(door) -> None:
        px, py, pz = (float(v) for v in player_token.position)
        body = {(int(np.floor(px + dx)), int(np.floor(py + dy)), int(np.floor(pz + dz)))
                for dx in (-0.3, 0.3) for dz in (-0.3, 0.3) for dy in (0.05, 1.0, 1.75)}
        schematic_tool.toggle_door(door, player_cells=body)

    # ------------------------------------------------------------------
    # 5. Callbacks de entrada
    # ------------------------------------------------------------------

    keys_pressed: dict[int, bool] = {}
    if terrain_demo and selected_world is None:
        # Modos de diagnóstico via CLI só criam um save quando o usuário pede.
        menus.world = None
    else:
        menus.world = selected_world

    def save_world():
        if not terrain_demo:
            return
        if menus.world is None:
            menus.world = menus.library.create('Mundo ' + str(active_seed['value']), active_seed['value'])
        menus.world['seed'] = active_seed['value']
        menus.world['position'] = [float(v) for v in player_token.position]
        if character_model is not None and not getattr(character_model, 'is_loading', False):
            menus.world['character'] = character_save.to_dict(character_model)
        menus.library.save(menus.world)
        if not menus.active:
            menus.capture_scene(window.width,window.height)
        if menus.scene_image is not None and menus.scene_owner == menus.world["id"]:
            from PIL import ImageOps
            thumbnail = ImageOps.fit(menus.scene_image.convert('RGB'), (480,300))
            try:
                thumbnail.save(menus.library.directory/(menus.world['id']+'.png'))
            except OSError as error:
                print(f'[Menu] Não foi possível gravar a miniatura: {error}')

    def load_world(world):
        nonlocal world_manager, voxel_provider
        world_manager.delete()
        active_seed['value'] = world['seed']
        world_manager = WorldManager(TerrainGenerator(seed=world["seed"], enable_caves=True, vegetation=True),
                                     render_distance=2, atlas=atlas)
        x, z = .5, .5
        player_token.position[:] = world.get('position') or [x, world_manager.get_height(x, z) + 1., z]
        player_token.vertical_velocity = 0.0
        player_token._collision_controller = None
        world_manager.load_initial_region(player_token.position[0], player_token.position[2])
        schematic_tool.clear()  # as construções pertencem ao mundo anterior
        room_tracker.reset()
        voxel_provider = VoxelGridProvider(
            block_lookup=lambda x, y, z: schematic_tool.lookup(world_manager.neighbor_at, x, y, z)
        )
        camera.target[:] = player_token.position
        picking_state.update(click_pending=False, hover_hit=None, clicked_hit=None)
        # Invalida o cache de revisão da grade ao substituir o WorldManager.
        grid_renderer.sync_chunks({}, -1)
        if world.get('character') and character_model is not None:
            character_save.apply(character_model, world['character'])
        menus.world = world


    def handle_camera_key(
        key: int,
        scancode: int,
        action: int,
        mods: int,
    ) -> Optional[bool]:
        """Encaminha eventos de teclado para a câmera e registra teclas ativas."""
        del scancode
        if action == glfw.RELEASE:
            keys_pressed[menus.preferences.canonical(key)] = False
        if menus.active:
            return menus.key(key, action, mods)

        # Intercepta eventos de teclado para o console de chat estilo Minecraft
        try:
            if character_editor.typing and character_editor.handle_key(key, action, mods):
                return True  # o campo de adicionar item da tela de criação tem o teclado
            chat_key = key if chat_console.is_open else menus.preferences.canonical(key)
            if chat_console.handle_key(chat_key, action, mods):
                keys_pressed.clear()
                return True
        except Exception as e:
            print(f"[Input] Erro ao processar tecla no console de chat: {e}")
            return True

        if character_editor.handle_key(key, action, mods):
            return True

        if schematic_tool is not None and schematic_tool.handle_key(key, action, mods):
            keys_pressed.clear()
            return True

        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            keys_pressed.clear()
            pan_state['active'] = False
            picking_state['click_pending'] = False
            menus.capture_scene(window.width, window.height)
            menus.go('pause')
            return True
        key = menus.preferences.canonical(key)
        if terrain_demo and key == glfw.KEY_F and not character_editor.is_open:
            # F interage: a porta sob o cursor, se ao alcance; senão a mais perto do personagem; senão a escada de
            # mão (agarra; agarrado, solta)
            if action == glfw.PRESS:
                door = None if player_token.ladder_grip is not None else (
                    hovered_door_in_reach() or schematic_tool.door_near(player_token.position))
                if door is not None:
                    toggle_door_for_player(door)
                else:
                    player_token.grab_ladder(voxel_provider)
            return True
        keys_pressed[key] = (action != glfw.RELEASE)

        if terrain_demo and not character_editor.is_open and key == glfw.KEY_R and action == glfw.PRESS:
            new_seed = random.randint(1, 999_999)
            active_seed["value"] = new_seed
            print(f"[Terrain] Regenerando mundo... Nova Seed: {new_seed}")
            world_manager.delete()
            schematic_tool.clear()  # o relevo muda: as construções não fazem mais sentido onde estavam
            room_tracker.reset()
            world_manager.generator = TerrainGenerator(seed=new_seed, enable_caves=True, vegetation=True)
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

        if terrain_demo and key == glfw.KEY_G and action == glfw.PRESS:
            labels = {"contour": "Contorno do relevo", "grid": "Grade completa", "off": "Desativado"}
            print(f"[Grid] {labels[grid_renderer.cycle_mode()]}.")

        if key == glfw.KEY_LEFT_SHIFT:
            pan_state["shift_pressed"] = action != glfw.RELEASE
            if action == glfw.RELEASE and not window.is_mouse_button_pressed(glfw.MOUSE_BUTTON_MIDDLE):
                pan_state["active"] = False

        camera_key = key
        if menus.preferences.data['invert_rotation'] and key in (glfw.KEY_Q, glfw.KEY_E):
            camera_key = glfw.KEY_E if key == glfw.KEY_Q else glfw.KEY_Q
        camera.handle_key(camera_key, action)
        if menus.preferences.data['reduce_motion']:
            camera.current_rotation = float(camera.board_rotation)
        return None



    def handle_mouse_button(
        button: int,
        action: int,
        mods: int,
    ) -> None:
        """Controla o início e fim do pan com o botão central."""
        del mods
        mouse_used()
        if menus.active:
            if button == glfw.MOUSE_BUTTON_LEFT:
                menus.mouse_button(*window.get_cursor_pos_framebuffer(), action)
            return
        if chat_console.is_open:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                cx, cy = window.get_cursor_pos()
                chat_console.handle_mouse_click(cx, cy)
            return
        
        if character_editor.is_open:
            cx, cy = window.get_cursor_pos()
            character_editor.ctrl = window.is_key_pressed(glfw.KEY_LEFT_CONTROL)
            if character_editor.handle_mouse_button(cx, cy, button, action, window.is_key_pressed(glfw.KEY_LEFT_SHIFT)):
                return

        is_middle = (button == glfw.MOUSE_BUTTON_MIDDLE)
        is_left_with_shift = (button == glfw.MOUSE_BUTTON_LEFT and window.is_key_pressed(menus.preferences.data['bindings']['pan_modifier']))

        if action == glfw.PRESS:
            if is_middle or is_left_with_shift:
                pan_state["active"] = True
                picking_state["hover_hit"] = None

                x, y = window.get_cursor_pos()

                pan_state["last_x"] = x
                pan_state["last_y"] = y
            elif terrain_demo and not character_editor.is_open and button == glfw.MOUSE_BUTTON_LEFT:
                picking_state["click_pending"] = True
            elif terrain_demo and not character_editor.is_open and button == glfw.MOUSE_BUTTON_RIGHT:
                door = hovered_door_in_reach()  # o botão direito usa o que está sob o cursor (a porta)
                if door is not None:
                    toggle_door_for_player(door)

        elif action == glfw.RELEASE:
            if button in (glfw.MOUSE_BUTTON_MIDDLE, glfw.MOUSE_BUTTON_LEFT):
                pan_state["active"] = False

    def handle_cursor_position(
        x: float,
        y: float,
    ) -> None:
        """Move o ponto focal enquanto o botão central estiver pressionado."""
        mouse_used()
        if menus.active:
            menus.hover(*window.get_cursor_pos_framebuffer())
            return
        if chat_console.is_open:
            return
        character_editor.handle_cursor(x, y)
        if pan_state["active"] and not window.is_mouse_button_pressed(glfw.MOUSE_BUTTON_MIDDLE):
            if not window.is_key_pressed(menus.preferences.data['bindings']['pan_modifier']):
                pan_state["active"] = False
                return
        
        if not pan_state["active"]:
            return

        dx = x - pan_state["last_x"]
        dy = y - pan_state["last_y"]

        camera.pan_screen(
            dx * menus.preferences.data['sensitivity'],
            dy * menus.preferences.data['sensitivity'],
        )

        pan_state["last_x"] = x
        pan_state["last_y"] = y

    # Registrar callbacks na janela.
    def handle_scroll(x_offset: float, y_offset: float) -> None:
        """A roda do mouse rola a grade da tela de criação; fora dela, é o zoom da câmera."""
        mouse_used()
        if menus.active:
            return
        if character_editor.handle_scroll(window.get_cursor_pos()[0], y_offset):
            return
        camera.handle_scroll(x_offset, y_offset)

    window.add_scroll_callback(
        handle_scroll
    )

    window.add_key_callback(
        handle_camera_key
    )

    def handle_char(codepoint: int) -> None:
        if menus.active:
            menus.char(codepoint)
            return
        if not character_editor.handle_char(codepoint):
            chat_console.handle_char(codepoint)

    window.add_char_callback(
        handle_char
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
            0.55,
            0.26,
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
    # --mouse="700,300,press;720,310;720,310,release": o mouse movido e clicado por um roteiro, um
    # passo por quadro a partir do décimo, pelos mesmos caminhos do mouse de verdade (conferências).
    mouse_script = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--mouse=")), "")
    mouse_steps = [step.split(",") for step in mouse_script.split(";") if step.strip()]
    # --keys="150:E;200:Q": teclas apertadas (e soltas) num quadro, pelos mesmos caminhos do teclado (conferências)
    key_script = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--keys=")), "")
    key_steps = {}
    key_holds = {}  # "120-300:W": a tecla fica apertada do quadro 120 ao 300 (andar num roteiro)
    for step in key_script.split(";"):
        frame_text, _, key_name = step.strip().partition(":")
        key_code = getattr(glfw, "KEY_" + key_name.strip().upper(), None)
        if key_code is None:
            continue
        start, _, end = frame_text.partition("-")
        if start.isdigit() and end.isdigit():
            key_holds.setdefault(int(start), []).append((key_code, glfw.PRESS))
            key_holds.setdefault(int(end), []).append((key_code, glfw.RELEASE))
        elif frame_text.isdigit():
            key_steps.setdefault(int(frame_text), []).append(key_code)
    # --frametimes=arquivo.csv: o tempo de cada quadro (ms), para achar os travamentos
    frametimes_path = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--frametimes=")), "")
    frametimes = []
    frame_marks = []  # (seção, tempo) do quadro atual, com --frametimes
    frame_sections = []

    def mark(name):
        if frametimes_path:
            frame_marks.append((name, time.perf_counter()))
    # O que a inicialização deixou (módulos, atlas, roupas) vive até o fim: congelado, sai da varredura da
    # geração 2 do coletor, que passava por tudo isso a cada poucos segundos (15-17 ms de quadro parado).
    # O que sobrevive a uma varredura completa também é congelado: a próxima passa só pelo que é novo. A contagem
    # de referências segue liberando tudo; só um ciclo entre objetos congelados ficaria sem coletar.
    gc.collect()
    gc.freeze()
    gc.callbacks.append(lambda phase, info: gc.freeze() if phase == "stop" and info["generation"] == 2 else None)
    while not window.should_close():
        dt = window.update_delta_time()
        if frametimes_path:
            if frame_marks:
                frame_sections.append({n: (t - frame_marks[i - 1][1]) * 1000.0
                                       for i, (n, t) in enumerate(frame_marks) if i})
            frame_marks.clear()
            mark("start")
        if menus.active:
            window.poll_events()
            if menus.result:
                action, world = menus.result
                menus.result = None
                try:
                    if action == 'exit':
                        break
                    if action == 'save_exit':
                        save_world()
                        if not terrain_demo:
                            break
                        menus.go('welcome')
                    elif action == 'play':
                        load_world(world)
                except (OSError, ValueError) as error:
                    menus.go('pause')
                    menus.message = 'Falha ao salvar/abrir: ' + str(error)
            window.set_vsync(menus.preferences.data['vsync'])
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            menus.render(window.width, window.height)
            window.swap_buffers()
            continue
        if menus.world is not None:
            menus.world['played'] += dt
        camera.update(dt)
        if menus.preferences.data['reduce_motion']:
            camera.current_rotation = float(camera.board_rotation)
        chat_console.update(dt)

        # Abrir e fechar a tela de criação: a câmera enquadra o personagem e volta ao sair.
        if skin_command_handler.editor_requested:
            skin_command_handler.editor_requested = False
            character_editor.open()
        editing = character_editor.is_open and character_model is not None
        if not editing:  # os braços a 90 graus são só do ajuste fino da tela de criação
            for posed_animator in (character_animator if char_demo else None, getattr(player_token, "animator", None)):
                if posed_animator is not None:
                    posed_animator.arms_out = False
        if editing and editor_camera["saved"] is None:
            editor_camera["saved"] = (camera.target.copy(), camera.ortho_size, camera.pitch)
            turntable_state["pitch"] = math.degrees(camera.pitch)  # o arraste vertical inclina a câmera
            camera.target = vec3(0.0, 0.95, 0.0)
            camera.ortho_size = 1.18
            keys_pressed.clear()
        elif not editing and editor_camera["saved"] is not None:
            camera.target, camera.ortho_size, camera.pitch = editor_camera["saved"]
            turntable_state.pop("pitch", None)
            editor_camera["saved"] = None
            editor_camera["focus"] = "body"
            editor_camera.pop("body", None)
            if not char_demo:
                turntable_state["active"], turntable_state["yaw"] = False, 0.0

        if editing:
            character_editor.update(dt)
            editor_animator = character_animator if char_demo else getattr(player_token, "animator", None)
            if editor_animator is not None:
                editor_animator.arms_out = character_editor.arms_raised  # braços a 90 graus, no ajuste fino
            if terrain_demo and editor_animator is not None:
                editor_animator.walking = character_editor.walk_preview  # W liga o andar na tela
                editor_animator.update(dt)
            elif char_demo:
                character_animator.update(dt)
            if terrain_demo and player_token.custom_model is not None:
                player_token.custom_model.update(dt, player_token.speed if character_editor.walk_preview else 0.0)  # W anda
            # Nas seções do rosto a câmera vai para o rosto: na altura da cabeça, de perto, na
            # horizontal e com o personagem parado de frente para ela. Ao sair, volta ao que era.
            if character_editor.focus != editor_camera.get("focus", "body"):
                editor_camera["focus"] = character_editor.focus
                if character_editor.focus == "face":
                    editor_camera["body"] = (camera.target.copy(), camera.ortho_size, turntable_state["pitch"],
                                             turntable_state["active"], turntable_state["yaw"])
                    face_height = EDITOR_FACE_HEIGHT
                    bones = getattr(character_model, "bones", None)
                    skeleton = getattr(editor_animator, "skeleton", None)
                    if bones is not None and skeleton is not None:  # the head as posed, with the body's adjustments
                        head = skeleton.index("Head")
                        middle = np.append((skeleton.heads[head] + skeleton.tails[head]) / 2.0, 1.0)
                        face_height = float((np.asarray(bones[head], dtype=np.float64) @ middle)[1])
                    camera.target = vec3(0.0, face_height, 0.0)
                    camera.ortho_size = EDITOR_FACE_ZOOM
                    turntable_state["pitch"] = 0.0
                    turntable_state["active"] = False
                    turntable_state["yaw"] = (camera.yaw_degrees - camera.current_rotation) % 360.0
                elif "body" in editor_camera:
                    (camera.target, camera.ortho_size, turntable_state["pitch"], turntable_state["active"],
                     turntable_state["yaw"]) = editor_camera.pop("body")
            camera.pitch = math.radians(turntable_state["pitch"])
        elif terrain_demo:
            # 1. Movimentação do token de personagem com WASD e aderência ao relevo
            movement_forward, movement_right = camera.get_movement_directions()
            facing_before = player_token.yaw
            player_token.update(
                dt,
                keys_pressed,
                movement_forward,
                movement_right,
                voxel_provider,
            )
            if picking_state["aim"] is not None and player_token.ladder_grip is None:
                # com o cursor na cena, o personagem olha para ele (andando ou parado), não para onde anda
                # (agarrado à escada, olha para ela)
                from src.interactive.context_cursor import face_toward
                player_token.yaw = face_toward(facing_before, player_token.position, picking_state["aim"], dt)

            # 2. Atualização contínua de streaming de chunks ao redor do jogador (Mapa Infinito)
            world_manager.update(player_token.position[0], player_token.position[2])
            mark("world_update")
            grid_revision = world_manager.get_loaded_chunk_revision()
            if (
                not world_manager.has_pending_streaming_work()
                and grid_renderer.should_sync(grid_revision)
            ):
                revision, loaded_chunks = world_manager.get_loaded_chunks_snapshot()
                grid_renderer.sync_chunks(loaded_chunks, revision)
            mark("grid_sync")

            # 3. Câmera acompanha o personagem fora do gesto de pan.
            if not pan_state["active"]:
                camera.follow_target(player_token.position, dt, response=10.0)
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
                mode_badge = f"Seed: {active_seed['value']} (WASD: mover | Espaço: pular | [R]: reload) | "
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
        for scripted_key, key_action in key_holds.pop(frame_index, ()):
            window._on_key(window._window, scripted_key, 0, key_action, 0)
        if frametimes_path:
            frametimes.append(dt * 1000.0)
        for scripted_key in key_steps.pop(frame_index, ()):
            window._on_key(window._window, scripted_key, 0, glfw.PRESS, 0)
            window._on_key(window._window, scripted_key, 0, glfw.RELEASE, 0)
        if mouse_steps and frame_index >= 10:  # onde os eventos do mouse de verdade chegam
            step = mouse_steps.pop(0)
            at = (float(step[0]), float(step[1]))
            window.get_cursor_pos = lambda at=at: at
            handle_cursor_position(*at)
            if len(step) > 2:
                handle_mouse_button(int(step[3]) if len(step) > 3 else glfw.MOUSE_BUTTON_LEFT,
                                    glfw.PRESS if step[2].strip() == "press" else glfw.RELEASE, 0)

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
        scene_x, _, scene_right, _ = character_editor.scene_rect(window.width, window.height) if editing \
            else (0, 0, window.width, window.height)
        projection = camera.get_projection_matrix(
            max(scene_right - scene_x, 1),
            window.height,
        )
        view = camera.get_view_matrix()
        model = camera.get_animated_model_matrix()

        # O hover fica suspenso durante o drag para não disputar o gesto de pan.
        # Como os eventos são processados acima, ele retorna no frame do release.
        picking_state.update(aim=None, door=None, door_in_reach=False)
        if not cursor_in_use():
            picking_state["hover_hit"] = None
        if terrain_demo and not editing and not pan_state["active"] and cursor_in_use():
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
            from src.interactive.context_cursor import raycast_visible
            picking_state["hover_hit"] = raycast_visible(mouse_ray, voxel_provider, depth_probe.surface, raycast_voxels)
            from src.interactive.context_cursor import aim_point, door_in_reach
            from src.world.doors import door_at
            hit = picking_state["hover_hit"]
            hovered_door = None if hit is None else door_at(schematic_tool.layer.structures, hit.block)
            picking_state.update(aim=aim_point(hit, mouse_ray, float(player_token.position[1])), door=hovered_door,
                                 door_in_reach=door_in_reach(hovered_door, player_token.position))
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

        if editing:
            # Só o personagem, ao lado do painel, com a luz e o fundo do visualizador.
            fb_w, fb_h = glfw.get_framebuffer_size(window._window)
            scale = fb_w / max(window.width, 1)
            gl.glClearColor(0.12, 0.13, 0.16, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            gl.glViewport(int(scene_x * scale), 0, int((scene_right - scene_x) * scale), fb_h)
            shader.set_vec3("u_LightDir", 0.5, 1.2, 0.8)
            shader.set_vec3("u_LightColor", 0.70, 0.70, 0.70)
            shader.set_vec3("u_AmbientColor", 0.38, 0.38, 0.38)
            if editor_animator is not None:
                editor_animator.sync()  # a pele recortada por um clique deste quadro já entra na pose
            shown_body = player_token.custom_model if terrain_demo and player_token.custom_model is not None \
                else character_model
            shown_body.draw(shader, model @ mat4_rotate_y(math.radians(turntable_state["yaw"])))
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glViewport(0, 0, fb_w, fb_h)
            # O pincel de pele: os pontos da cage do corpo na tela, para pintar e para mostrar.
            character_editor.picker = character_editor.overlay = None
            skin_cage = getattr(character_model, "hsr_cage", None)
            if character_editor.brushing and skin_cage is not None:
                from src.interactive import skin_brush
                brush_view = skin_brush.BrushView(
                    skin_cage[0], skin_cage[2], model @ mat4_rotate_y(math.radians(turntable_state["yaw"])), view,
                    projection, (scene_x, 0, scene_right, window.height), pose=getattr(editor_animator, "posed", None),
                    skin=getattr(character_model, "hsr_skin", None))
                brush_custom = character_model.customization
                character_editor.picker = brush_view.pick
                character_editor.overlay = (brush_view.xy, brush_view.facing, skin_brush.states(
                    getattr(character_model, "hsr_hidden", skin_cage[1]), getattr(brush_custom, "hsr_hide", ()),
                    getattr(brush_custom, "hsr_show", ())))
            if not char_demo:
                shader.set_vec3("u_LightDir", 0.5, 1.0, 0.7)
                shader.set_vec3("u_LightColor", 0.9, 0.9, 0.9)
                shader.set_vec3("u_AmbientColor", 0.35, 0.35, 0.35)
                gl.glClearColor(0.08, 0.10, 0.13, 1.0)
        elif terrain_demo:
            # Espaço fechado do jogador: a máscara e a suavização do efeito
            mark("misc")
            chunk_revision, loaded_chunks = world_manager.get_loaded_chunks_snapshot()
            room_tracker.update(dt, player_token.position, loaded_chunks, chunk_revision,
                                schematic_tool.layer.structures)
            mark("room_tracker")
            room_renderer.update(dt, room_tracker)
            mark("room_renderer")
            shadow_renderer.update(room_tracker)
            mark("shadows")
            # Configuração do modo subterrâneo (cutaway) e água
            underground_mode = False
            if voxel_provider is not None and not room_renderer.visible:
                underground_mode = (
                    player_token.position[1]
                    < float(
                        voxel_provider.get_top_solid_block(
                            int(np.floor(float(player_token.position[0]))),
                            int(np.floor(float(player_token.position[2]))),
                        )
                    ) + 0.25
                )
            shader.set_bool("u_UndergroundMode", underground_mode)
            shader.set_float("u_PlayerY", float(player_token.position[1]))
            shader.set_float("u_CutawayAlpha", 0.38)
            shader.set_float("u_CutawayFade", 0.45)
            shader.set_bool("u_WaterMode", player_token.in_water)
            shader.set_int("u_CutawayPass", 0)

            # 1. Renderiza os chunks de terreno e cavernas com Frustum Culling ativo
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, atlas.texture_id)
            shader.set_int("u_TextureAtlas", 0)
            view_projection = projection @ view
            shader.set_bool("u_WorldStyle", True)  # luz e cor do mundo (o personagem usa a luz de sempre)
            shadow_renderer.apply(shader, model)
            room_renderer.apply(shader, model, view)
            mark("room_apply_caps")
            # água: na passada 1 (esta) ela é descartada e o fundo recebe a luz que a atravessa; a 2 vem no fim
            shader.set_vec4("u_WaterRect", *water_rect)
            shader.set_float("u_Time", float(window.time))
            shader.set_vec3("u_CameraPos", *(float(v) for v in camera._camera_position()))
            shader.set_int("u_WaterPass", 1)
            # o corredor da câmera: o que tapa o personagem some (ver sightCarved no shader)
            feet = [float(v) for v in player_token.position]
            # no ar (um pulo), os cortes ficam no chão de onde saiu: pular não muda o que aparece; numa escada de
            # mão ou caindo para baixo do chão, seguem o personagem
            floor_y = int(np.floor(feet[1] + 0.05))
            if (player_token.grounded or player_token.on_ladder or story_state.get("ground_y") is None
                    or floor_y < story_state["ground_y"]):
                story_state["ground_y"] = floor_y
            feet[1] = float(story_state["ground_y"])
            sight_target = model @ np.array([feet[0], feet[1] + 1.1, feet[2], 1.0])
            # Ao ar livre o corredor só liga quando algo bloqueia a vista do peito ou da cabeça (se só as pernas ficam
            # atrás de um degrau, não abre buraco); ligado, corta o cilindro inteiro, dos pés para cima, e os pés
            # aparecem. Num cômodo fica sempre ligado (só corta o que tapa o cômodo: ver o shader).
            from src.world.sight import sight_needed
            sight_world_dir = np.linalg.inv(np.asarray(model, dtype=np.float64))[:3, :3] @ (
                np.array(camera._camera_position(), dtype=np.float64) - sight_target[:3])
            window_cells = room_tracker.mask.window if room_tracker.mask is not None else None
            outdoors_target = 1.0 if (
                room_renderer.level > 0.001 or window_cells is None
                or sight_needed(window_cells.solid, room_tracker.mask.origin, feet, sight_world_dir)) else 0.0
            story_state["sight"] += (outdoors_target - story_state["sight"]) * (1.0 - 0.5 ** (max(dt, 0.0) / 0.10))
            if abs(outdoors_target - story_state["sight"]) < 0.01:
                story_state["sight"] = outdoors_target
            shader.set_float("u_SightActive", story_state["sight"])
            shader.set_vec3("u_SightTarget", *(float(v) for v in sight_target[:3]))
            shader.set_float("u_SightFeetY", float(np.floor(feet[1] + 0.05)))
            shader.set_float("u_SightRadius", 2.6)
            # o corte do andar: debaixo de teto, do teto para cima some em volta do personagem
            from src.world.room_reveal import story_ceiling, story_center
            ceiling = story_ceiling(room_tracker.mask, feet)
            if ceiling is not None:
                story_state["cut_y"] = ceiling
            story_target = 1.0 if ceiling is not None and room_renderer.enabled else 0.0
            story_state["level"] += (story_target - story_state["level"]) * (1.0 - 0.5 ** (max(dt, 0.0) / 0.10))
            if abs(story_target - story_state["level"]) < 0.01:
                story_state["level"] = story_target
            shader.set_float("u_StoryActive", story_state["level"])
            shader.set_float("u_StoryCutY", float(story_state["cut_y"]))
            center_key = (room_tracker.version, story_state["cut_y"], int(np.floor(feet[1] + 0.05)))
            if story_state.get("center_key") != center_key:
                story_state["center_key"] = center_key
                story_state["center"] = story_center(room_tracker.mask, int(np.floor(feet[1] + 0.05)),
                                                     int(story_state["cut_y"]))
            center = story_state["center"] or (feet[0], feet[2])  # fora de cômodo, o próprio personagem
            shader.set_vec2("u_StoryCenter", float(center[0]), float(center[1]))
            # as tampas seguem os mesmos cortes (o corte do andar só quando ele está inteiro, sem o fade)
            from src.world.room_caps import SightCut, StoryCut
            room_renderer.story = (StoryCut(int(story_state["cut_y"]), int(np.floor(feet[1] + 0.05)),
                                            (float(center[0]), float(center[1])), 24.0)
                                   if story_state["level"] >= 0.999 else None)
            room_renderer.center = (float(center[0]), float(center[1]))
            room_renderer.sight = SightCut((feet[0], feet[1] + 1.1, feet[2]), (0.0, 0.0, 0.0), 2.6,
                                           int(np.floor(feet[1] + 0.05)))
            shader.set_float("u_StoryRadius", 24.0)
            story_view = np.linalg.inv(np.asarray(model, dtype=np.float64))[:3, :3] @ (-np.asarray(view, dtype=np.float64)[2, :3])
            story_view /= max(float(np.linalg.norm(story_view)), 1e-9)
            shader.set_vec3("u_StoryView", *(float(v) for v in story_view))
            shader.set_mat4("u_SightModel", np.asarray(model, dtype=np.float32))
            shader.set_mat4("u_SightInvModel", np.linalg.inv(np.asarray(model, dtype=np.float64)).astype(np.float32))
            world_manager.render(shader, model, view_projection)
            room_renderer.draw_terrain_caps(shader, model)  # as faces que o corte deixou sem tampa
            mark("story_and_world_draw")

            # 2. Segundo passe: terreno acima do jogador translúcido (cutaway)
            if underground_mode:
                gl.glEnable(gl.GL_BLEND)
                gl.glDepthFunc(gl.GL_ALWAYS)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDepthMask(gl.GL_FALSE)
                shader.set_int("u_CutawayPass", 1)
                world_manager.render(shader, model, view_projection)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDepthFunc(gl.GL_LESS)
                gl.glDisable(gl.GL_BLEND)
                shader.set_int("u_CutawayPass", 0)

            gl.glEnable(gl.GL_CULL_FACE)

            # 2b. Construções fixadas com /schem (opacas) e a prévia em holograma. Usam outro atlas, em que a
            # região da água do terreno pode ser outra textura: nada delas é tratado como água.
            mark("underground_pass")
            shader.set_int("u_WaterPass", 0)
            schematic_tool.draw(shader, model, window.time)
            room_renderer.draw_structure_caps(shader, model)
            if cursor_state["hidden"] and not pan_state["active"] and cursor_in_use():
                # a profundidade do que está sob o mouse (terreno e construções, já cortados): o hover do próximo
                # quadro começa nela
                depth_probe.read(window.get_cursor_pos_framebuffer(), window.width, window.height,
                                 projection @ view @ model)
            else:
                depth_probe.clear()
            mark("structures_draw")

            # 2c. A água, translúcida, sobre tudo o que já está na tela (sem escrever profundidade)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, atlas.texture_id)
            shader.set_int("u_TextureAtlas", 0)
            shader.set_int("u_WaterPass", 2)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            world_manager.render(shader, model, view_projection)
            gl.glDepthMask(gl.GL_TRUE)
            mark("water_pass")
            gl.glDisable(gl.GL_BLEND)
            shader.set_int("u_WaterPass", 0)
            shader.set_float("u_SightActive", 0.0)
            room_renderer.disable(shader)
            shadow_renderer.disable(shader)
            shader.set_bool("u_WorldStyle", False)

            # 3. Grade tática: um draw GL_LINES, mesmas matrizes do terreno.
            grid_renderer.render(projection, view, model)
            mark("grid_draw")

            # 4. Renderiza o bloco abaixo do token reluzindo em branco pulsante (no chão)
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

            # 5. Destaca o primeiro voxel sob o cursor na cor do cursor (cinza: um bloco; dourado: uma porta)
            from src.interactive.context_cursor import block_name_at, classify, highlight_box
            hover_hit = picking_state["hover_hit"]
            cursor_mode = classify(hover_hit, picking_state["door"])
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
                    base_color=tuple(c / 255.0 for c in cursor_mode.color[:3]),
                    box=highlight_box(block_name_at(schematic_tool.layer.structures, voxel_provider,
                                                    hover_hit.block)),
                )

            # 6. Renderiza a miniatura 3D do personagem SOBRE o bloco e o highlight
            shader.use()
            # A miniatura não deve herdar o cutaway do terreno
            shader.set_bool("u_UndergroundMode", False)
            shader.set_bool("u_WaterMode", False)
            shader.set_int("u_CutawayPass", 0)
            shader.set_mat4("u_Projection", projection)
            shader.set_mat4("u_View", view)
            base_model = model @ player_token.get_model_matrix()
            shader.set_mat4("u_Model", base_model)
            mark("highlight")
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
            shader.set_int("u_TextureAtlas", 0)
            player_token.draw(shader=shader, base_model=base_model)
            mark("player_draw")

            if coordinate_overlay is not None:
                coordinate_overlay.render(window.width, window.height, player_token.position)
                shader.use()

            # 7. A tecla F ao lado do personagem, se há uma porta ou uma escada de mão ao alcance
            # (com uma porta ao alcance sob o cursor, o rótulo vai em cima dela, no cursor de contexto)
            near_door = None if character_editor.is_open else schematic_tool.door_near(player_token.position)
            near_ladder = (not character_editor.is_open and near_door is None and player_token.ladder_grip is None
                           and player_token.ladder_near(voxel_provider) is not None)
            if near_door is not None:
                prompt_label = "Fechar" if near_door.is_open else "Abrir"
            else:
                prompt_label = "Escada" if near_ladder else ""
            interact_prompt.letter = interact_key_name()
            interact_prompt.update(dt, (near_door is not None and hovered_door_in_reach() is None) or near_ladder,
                                   prompt_label)
            interact_prompt.render(player_token.position, projection @ view @ model, window.width, window.height)
            context_cursor.update(dt, cursor_mode)
            shader.use()
        elif char_demo:
            # 1. Renderiza o modelo 3D modular completo do personagem com iluminação
            spin_mat = mat4_rotate_y(math.radians(turntable_state["yaw"]))
            char_base_model = model @ spin_mat
            character_animator.sync()  # um comando do chat deste quadro que trocou malhas já entra na pose
            character_model.draw(shader, char_base_model)
        else:
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, current_texture["id"])
            shader.set_int("u_TextureAtlas", 0)
            for mesh, transform in meshes:
                shader.set_mat4("u_Model", model @ transform)
                mesh.draw()

        # Restaurar estados OpenGL
        gl.glDisable(gl.GL_BLEND)
        gl.glDepthMask(gl.GL_TRUE)
        shader.set_bool("u_UndergroundMode", False)
        shader.set_int("u_CutawayPass", 0)

        # --------------------------------------------------------------
        # Renderizar interface 2D do Console de Chat (HUD estilo Minecraft)
        # --------------------------------------------------------------
        mark("hud_prompt")
        character_editor.render(window.width, window.height)
        chat_console.render(window.width, window.height)
        if context_cursor is not None:
            # No terreno, jogando, a seta do sistema dá lugar ao cursor de contexto
            playing = not (menus.active or chat_console.is_open or character_editor.is_open or pan_state["active"])
            if playing != cursor_state["hidden"]:
                glfw.set_input_mode(window._window, glfw.CURSOR, glfw.CURSOR_HIDDEN if playing else glfw.CURSOR_NORMAL)
                cursor_state["hidden"] = playing
            if playing:
                from src.interactive.context_cursor import PROMPT_HEIGHT
                from src.interactive.interact_prompt import project
                door = hovered_door_in_reach()
                prompt_at, verb = None, ""
                if door is not None:
                    wx, wy, wz = door.world
                    prompt_at = project((wx + 0.5, wy + 1.0 + PROMPT_HEIGHT, wz + 0.5), projection @ view @ model,
                                        window.width, window.height)
                    verb = "Fechar" if door.is_open else "Abrir"
                from src.interactive.context_cursor import cursor_opacity
                context_cursor.render(window.get_cursor_pos_framebuffer(), window.width, window.height,
                                      prompt_at, interact_key_name(), verb, opacity=cursor_opacity(cursor_idle()))

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
            if frametimes_path:
                with open(frametimes_path, "w", encoding="utf-8") as handle:
                    handle.write(chr(10).join(f"{value:.3f}" for value in frametimes))
                names = sorted({n for row in frame_sections for n in row})
                with open(frametimes_path + ".sections.csv", "w", encoding="utf-8") as handle:
                    handle.write(",".join(names) + chr(10))
                    for row in frame_sections:
                        handle.write(",".join(f"{row.get(n, 0.0):.3f}" for n in names) + chr(10))
            break

        mark("rest_draw")
        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()
        mark("swap")

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    if terrain_demo and menus.world is not None and max_frames is None:
        try:
            save_world()
        except (OSError, ValueError) as error:
            print(f'[Save] Não foi possível salvar ao fechar: {error}')
    menus.delete()
    character_editor.delete()
    gl.glDeleteTextures(1, [current_texture["id"]])
    gl.glDeleteTextures(1, [token_tex_id])
    chat_console.delete()
    if schematic_tool is not None:
        schematic_tool.delete()
    if room_tracker is not None:
        room_tracker.close()
    if room_renderer is not None:
        room_renderer.delete()
    if shadow_renderer is not None:
        shadow_renderer.delete()
    if terrain_demo:
        if atlas is not None:
            atlas.delete()
        world_manager.delete()
        player_token.delete()
        highlight_renderer.delete()
        if coordinate_overlay is not None:
            coordinate_overlay.delete()
        interact_prompt.delete()
        context_cursor.delete()
        depth_probe.delete()
        grid_renderer.delete()
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
