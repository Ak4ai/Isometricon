"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import os
import sys
import gc
import time
from typing import Optional

# Ao rodar ``python src/main.py``, o diretório do script entra em sys.path[0] e
# ``src/math`` sombreia o módulo padrão ``math``. Remove-o e deixa a raiz do
# projeto no caminho antes de importar qualquer módulo que use ``math``.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(CURRENT_DIR, "..")))
if sys.path:
    first = sys.path[0]
    if first and os.path.normcase(os.path.abspath(first)) == os.path.normcase(CURRENT_DIR):
        sys.path.pop(0)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import math
import random
from typing import Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# A placa de vídeo (Configurações > Gráficos > Placa de vídeo), antes de qualquer OpenGL: num notebook com duas placas
# o Windows dá a integrada a todo programa que não pede a outra. Ver src/core/gpu_preference.py.
# ---------------------------------------------------------------------------
from src import gpu_preference

gpu_preference.ensure(gpu_preference.saved_choice())

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
from src.interactive.fps_overlay import FpsOverlay
from src.interactive.loading_indicator import LoadingIndicator
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
    # --resolucao=1920x1080: o tamanho da janela (para capturar os slides em Full HD)
    window_size = (1280, 720)
    for arg in sys.argv[1:]:
        if arg.startswith("--resolucao="):
            try:
                width_text, height_text = arg.split("=", 1)[1].lower().split("x")
                window_size = (max(320, int(width_text)), max(240, int(height_text)))
            except ValueError:
                pass
    window = Window(
        width=window_size[0],
        height=window_size[1],
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
    argv = sys.argv[1:]
    explicit_editor = "--map-editor" in argv or "--editor-mapa" in argv
    # --apresentacao: os slides da disciplina por cima do terreno ao vivo (ver src/interactive/presentation.py)
    presentation_requested = "--apresentacao" in argv
    terrain_requested = "--terrain" in argv or presentation_requested
    presentation_start = 1
    map_path = None
    world_object_path = None
    for arg in argv:
        if arg.startswith("--map-editor=") or arg.startswith("--editor-mapa="):
            explicit_editor = True
            map_path = arg.split("=", 1)[1]
        elif arg.startswith(("--map=", "--mapa=")):
            map_path = arg.split("=", 1)[1]
        elif arg.startswith(("--object=", "--objeto=")):
            world_object_path = arg.split("=", 1)[1]
        elif arg.startswith("--slide="):
            try:
                presentation_start = int(arg.split("=", 1)[1])
            except ValueError:
                pass
    terrain_demo = terrain_requested
    char_demo = "--char" in argv or "--character" in argv

    screenshot_path = None
    max_frames = None
    custom_seed = None
    custom_yaw = None
    initial_cmd = None
    open_chat = False
    chat_text = None
    for i, arg in enumerate(argv):
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
        elif arg in ("--map", "--mapa") and i + 1 < len(argv):
            map_path = argv[i + 1]
        elif arg in ("--object", "--objeto") and i + 1 < len(argv):
            world_object_path = argv[i + 1]
        elif arg in ("--open-chat", "--chat"):
            open_chat = True
        elif arg in ("--chat-text",) and i + 1 < len(sys.argv[1:]):
            chat_text = sys.argv[1:][i + 1]
            open_chat = True
        elif arg.startswith("--chat-text="):
            chat_text = arg.split("=", 1)[1]
            open_chat = True

    if presentation_requested and custom_seed is None:
        from src.interactive.presentation import PRESENTATION_SEED
        custom_seed = PRESENTATION_SEED   # sempre o mesmo terreno de fundo nos slides
    editor_mode = explicit_editor or (map_path is not None and not terrain_requested)
    if editor_mode:
        terrain_demo = False
        char_demo = False
    else:
        terrain_demo = terrain_requested
        char_demo = ("--char" in argv or "--character" in argv) and not terrain_demo
    from src.interactive.game_menus import GameMenus
    menus = GameMenus(version_info.full_version)
    selected_world = None
    package_smoke = next((arg.partition("=")[2] for arg in argv if arg.startswith("--package-smoke-world=")), None)
    if package_smoke is not None:
        if (package_smoke not in ("create", "reopen") or not max_frames or max_frames < 1
                or not os.environ.get("ISOMETRICON_DATA_DIR")):
            raise ValueError("Package smoke requires create/reopen, --frames and an isolated data directory.")
        smoke_name = "Isometricon package smoke"
        if package_smoke == "create":
            menus.go("create")
            menus.fields.update(name=smoke_name, seed="42")
            menus.activate("create_world")
        else:
            world = next((item for item in menus.library.list() if item["name"] == smoke_name), None)
            if world is None or world.get("position") is None:
                raise ValueError("Package smoke could not find the saved world and player position.")
            menus.activate("load:" + world["id"])
        if menus.result is None:
            raise ValueError(menus.message or "Package smoke could not open the world.")
        selected_world = menus.result[1]
    show_menu = "--menu" in sys.argv or (
        not editor_mode
        and not any(flag in sys.argv for flag in ("--terrain", "--apresentacao", "--char", "--character", "--frames"))
        and not any(a.startswith("--frames=") for a in sys.argv)
    )
    if show_menu and package_smoke is None:
        if screenshot_path:
            menus.prepare_background(wait=True)
        def menu_mouse(button, action, mods):
            if button == glfw.MOUSE_BUTTON_LEFT:
                menus.mouse_button(*window.get_cursor_pos_framebuffer(), action)
        window.add_key_callback(lambda key, scan, action, mods: menus.key(key, action, mods))
        window.add_char_callback(menus.char)
        window.add_mouse_button_callback(menu_mouse)
        window.add_cursor_pos_callback(lambda x, y: menus.hover(*window.get_cursor_pos_framebuffer()))
        window.add_scroll_callback(lambda x_offset, y_offset: menus.wheel(y_offset))
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
        window._scroll_callbacks.clear()
        if window.should_close() or menus.result[0] == 'exit':
            menus.delete()
            shader.delete()
            window.close()
            return
        selected_world = menus.result[1]
    if selected_world is not None:
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
    default_world_character = saved_character
    if selected_world and selected_world.get('character'):
        saved_character = selected_world['character']
    if saved_character is not None:
        print("[Skin] Personagem salvo carregado (use --novo para começar do padrão).")

    map_world = None
    construction_panel = None   # o painel de construções (/schem); só no terreno procedural
    selection_box = None
    if terrain_demo:
        print(f"[Terrain] Modo terreno ativo. Seed inicial: {active_seed['value']} (WASD para andar, Espaço para pular, [R] nova seed)")
        atlas = TextureAtlas()
        # a região da textura da água no atlas: o shader reconhece a água por ela (as duas passadas do terreno)
        water_uv = atlas.uv_table[int(BlockType.WATER)].reshape(-1, 2)
        water_rect = (float(water_uv[:, 0].min()), float(water_uv[:, 1].min()),
                      float(water_uv[:, 0].max()), float(water_uv[:, 1].max()))
        # e as das folhas: o buraco das folhas (leafHole no shader) as reconhece por elas
        leaf_rects = []
        for leaf in (BlockType.LEAVES, BlockType.SPRUCE_LEAVES):
            leaf_uv = atlas.uv_table[int(leaf)].reshape(-1, 2)
            leaf_rects.append((float(leaf_uv[:, 0].min()), float(leaf_uv[:, 1].min()),
                               float(leaf_uv[:, 0].max()), float(leaf_uv[:, 1].max())))
        from src.world.terrain_options import make_generator
        # as opções de criação do mundo (tela "Uma nova aventura"); sem elas, o relevo de sempre
        active_terrain = {"options": selected_world.get("terrain") if selected_world else None}
        biome_arg = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--bioma=")), "")
        if biome_arg:   # --bioma=taiga: abre o modo terreno nesse bioma (para ver e tirar prints)
            from src.world.terrain_options import defaults, water_default
            active_terrain["options"] = dict(active_terrain["options"] or defaults(), bioma=biome_arg,
                                             agua=water_default(biome_arg))
        generator = make_generator(active_seed["value"], active_terrain["options"])
        world_manager = WorldManager(generator=generator,
                                     render_distance=menus.preferences.data['render_distance'], atlas=atlas)
        start_surface_y = generator.get_height(0, 0)
        avatar = None
        if "--token-antigo" not in sys.argv[1:]:
            # The player is the dressed character of the viewer (--char), walking with the token.
            # Body, hair and clothes take the same options (--male, --top, --bottom...).
            from src.clothing.character_model import CharacterModel, parse_character_cli_args
            char_customization, top_id, bottom_id, tool_id, _ = parse_character_cli_args(sys.argv[1:])
            worn = dict(customization=char_customization, top_id=top_id, bottom_id=bottom_id, tool_id=tool_id)
            if default_world_character is None:
                from types import SimpleNamespace
                default_world_character = character_save.to_dict(SimpleNamespace(**worn))
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
        if map_path is not None:
            # um mapa do editor para jogar (--map=...), no lugar do terreno procedural
            from src.editor.map_world import MapWorld
            try:
                map_world = MapWorld(map_path, create_gl=True)
                player_token.position[:] = map_world.spawn_position()
                if pos_arg:   # --pos=x,y,z vale também no mapa
                    player_token.position[:] = [float(v) for v in pos_arg.split(",")]
                print(f"[Map] Mapa carregado para jogar: {os.path.basename(map_path)} ({map_world.project.voxel_count} voxels).")
            except Exception as exc:
                print(f"[Map] Falha ao carregar mapa: {exc}")
                map_world = None
        if map_world is None:
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
        terrain_lookup = lambda x, y, z: schematic_tool.lookup(world_manager.neighbor_at, x, y, z)
        if map_world is not None:
            voxel_provider = VoxelGridProvider(block_lookup=map_world.get_block_at)
        else:
            # O painel de construções: escondido até o /schem; coloca .schem e objetos do editor com o mouse
            from src.editor.object_names import object_library_paths
            from src.editor.selection import SelectionBoxRenderer
            from src.interactive.construction_panel import ConstructionPanel
            from src.world.structure_sources import entry_for_text, library as construction_library

            def construction_entries():
                # os objetos de exemplo (assets/objects), os exportados pelo editor e o saves/objeto.json antigo
                return construction_library(schematic_tool.schematics_dir, object_library_paths())

            construction_panel = ConstructionPanel(schematic_tool, construction_entries)
            selection_box = SelectionBoxRenderer()
            if world_object_path:
                entry = entry_for_text(world_object_path, schematic_tool.schematics_dir)
                if entry is None:
                    print(f"[Construções] Objeto não encontrado: {world_object_path}")
                else:
                    construction_panel.open(entry)
            voxel_provider = VoxelGridProvider(block_lookup=terrain_lookup)
        # Revela só o espaço fechado do jogador (cômodo, caverna) e escurece o resto
        from src.rendering.room_reveal import RoomRevealRenderer
        from src.world.room_reveal import RoomRevealTracker
        from src.rendering.sun_shadows import SunShadowRenderer
        shadow_renderer = SunShadowRenderer()
        from src.rendering.shadow_accum import ShadowAccumulator
        shadow_accum = ShadowAccumulator()   # a sombra do sol somada entre quadros (Configurações > Sombra acumulada)
        from src.rendering.cast_shadow import CharacterShadowMap
        character_shadows = CharacterShadowMap()   # a sombra do personagem e dos NPCs em qualquer face de bloco
        # a cena do jogo num framebuffer próprio: MSAA, escala de resolução e FXAA mudam na hora (Configurações)
        from src.rendering.scene_target import SceneTarget
        scene_target = SceneTarget()
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
        room_tracker = room_renderer = shadow_renderer = shadow_accum = scene_target = None
        character_shadows = None
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
        room_tracker = room_renderer = shadow_renderer = shadow_accum = scene_target = None
        character_shadows = None
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
    skin_command_handler.construction_panel = construction_panel
    skin_command_handler.room_reveal = room_renderer
    skin_command_handler.sun_shadows = shadow_renderer
    skin_command_handler.world_shader = shader
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
    if construction_panel is not None:
        # as construções salvas: no mundo do menu, ou no arquivo da seed (--terrain direto)
        from src.world.structure_save import SeedStore, restore as restore_structures, seed_store_path
        saved = (selected_world.get("structures") or []) if selected_world else             SeedStore(seed_store_path(active_seed["value"])).read()
        for warning in restore_structures(schematic_tool, saved):
            chat_console.add_message("[Schem] " + warning, (255, 85, 85))
    # Combate por turnos (src/combat): /inimigo põe criaturas no tabuleiro; clicar numa ou chegar perto abre a luta
    from src.combat.bestiary import PlayerSheet
    from src.interactive.combat_controller import CombatController, WorldTerrain
    from src.world.block import is_solid
    combat = CombatController(PlayerSheet.from_dict(selected_world.get("combat")
                                                    if isinstance(selected_world, dict) else None))
    combat.terrain = WorldTerrain(lambda x, y, z: is_solid(voxel_provider.get_block_at(x, y, z)))
    # A ambientação do mestre (/mestre): hora do dia, claridade, névoa... guardada no mundo
    from src.rendering.ambience import Ambience
    from src.interactive.master_panel import MasterPanel
    ambience = Ambience.from_dict(selected_world.get("ambiente") if isinstance(selected_world, dict) else None)
    master_panel = MasterPanel(ambience) if terrain_demo else None
    from src.rendering.fog_of_war import FogOfWar
    fog_war = FogOfWar()   # o explorado (névoa de guerra do /mestre), guardado no mundo
    from src.rendering.mist import MistField
    early_z = {"ok": "--no-early-z" not in sys.argv}   # a passada de cor com o teste de profundidade antecipado
    accum_state = {"on": False, "ok": True}            # a sombra acumulada: pedida nas Configurações; a placa aceita
    mist_field = MistField()   # o mapa da neblina de ambientação (/mestre > Neblina)
    fog_war.explored.load(selected_world.get("nevoa_explorada") if isinstance(selected_world, dict) else None)
    if master_panel is not None:
        master_panel.on_recover = fog_war.explored.clear
    cloud_fog = None   # a névoa de guerra em nuvens de blocos (criada no terreno, com o GL pronto)
    if terrain_demo:
        skin_command_handler.combat = combat
        skin_command_handler.master_panel = master_panel
        combat.load_npcs(selected_world.get("npcs") if isinstance(selected_world, dict) else None)
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
    from src.interactive.character_editor import CharacterEditor, PANEL_WIDTH as character_editor_panel_width
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
    if map_world is not None:
        cam_target = vec3(
            float(player_token.position[0]),
            max(float(map_world.size[1]) * 0.5, float(player_token.position[1]) * 0.5),
            float(player_token.position[2]),
        )
        cam_ortho = max(map_world.size) * 1.15
    elif terrain_demo:
        cam_target = vec3(0.5, float(start_surface_y) + 1.0, 0.5)
        cam_ortho = 4.5
        zoom_arg = next((a.partition("=")[2] for a in sys.argv[1:] if a.startswith("--zoom=")), "")
        if zoom_arg:   # --zoom=12: começa com a câmera mais afastada (meia-altura visível, em blocos)
            cam_ortho = float(zoom_arg)
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

    # Modo apresentação: a câmera parte da isométrica exata dos slides (yaw 45°, pitch 35,264°, ortográfica);
    # a de antes volta quando o Esc encerra a apresentação.
    presentation = None
    presentation_view: dict = {}
    if terrain_demo and presentation_requested:
        from src.interactive.presentation import BASE_ZOOM, Presentation
        presentation = Presentation(start=presentation_start - 1)
        for arg in argv:      # --step=N: abre o slide já no passo N (1 é o primeiro), para capturar cada passo
            if arg.startswith("--step="):
                try:
                    presentation.step = min(max(int(arg.split("=", 1)[1]) - 1, 0), presentation.slide.steps - 1)
                except ValueError:
                    pass
        presentation.fullscreen = "--janela" not in argv   # tela cheia por padrão; F11 alterna
        presentation_view.update(
            saved=(camera.yaw, camera.pitch, camera.ortho_size, camera.perspective, camera.fov_degrees),
            base_yaw=45.0, base_ortho=camera.ortho_size * BASE_ZOOM, slide=presentation.index, targets=None, drawn=0,
            faces=(0, 0), faces_at=-10.0, footer=None, footer_key=None)
        camera.perspective = False
        camera.pitch = math.radians(IsometricCamera.DEFAULT_PITCH_DEGREES)
        camera.yaw = math.radians(45.0)

    def show_presentation_screen(want: str) -> None:
        """Abre por trás do slide a tela do jogo que ele pede (e fecha a do slide anterior).

        Quem apresenta mexe nela com o mouse; nada é gravado: a tela de criação não salva o personagem e os
        inimigos da luta de demonstração somem ao trocar de slide."""
        had = presentation_view.get("screen", "")
        if had == want:
            return
        presentation_view["screen"] = want
        if had == "editor" and character_editor.is_open:
            character_editor.close()
            character_editor.autosave = presentation_view["editor_autosave"]
        elif had == "mestre" and master_panel is not None:
            master_panel.close()
        elif had == "combate":
            combat.clear(keep_npcs=True)
        if want == "editor" and not character_editor.is_open:
            presentation_view["editor_autosave"] = character_editor.autosave
            character_editor.autosave = False
            character_editor.open()
        elif want == "mestre" and master_panel is not None:
            master_panel.open()
        elif want == "combate" and player_token is not None:
            combat.clear(keep_npcs=True)
            position = [float(v) for v in player_token.position]
            first = combat.spawn("zumbi", 1, position)[0]
            combat.spawn("esqueleto", 1, position)
            combat.start(position, first)

    def presentation_solid(x: int, y: int, z: int) -> bool:
        return is_solid(voxel_provider.get_block_at(x, y, z))

    def presentation_place(name: str):
        """O ponto de pé do lugar ``name``; a construção é posta na primeira vez (sem gravar no mundo)."""
        from src.interactive.presentation_places import CAVE, ENTRIES, choose_site, find_cave_spot, find_floor_spot
        places = presentation_view.setdefault("places", {})
        if name in places:
            return places[name][1]
        home = presentation_view["home"]
        spot, placed = None, None
        if name == CAVE:
            spot = find_cave_spot(presentation_solid, lambda x, z: world_manager.get_height(x, z), home)
        elif schematic_tool is not None and name in ENTRIES:
            entry = ENTRIES[name]
            try:
                schematic = schematic_tool.schematic_for(entry)
            except Exception as error:   # o .schem pode ter sumido da pasta
                print(f"[Apresentação] {name}: {error}")
                schematic = None
            if schematic is not None:
                taken = [p.bounds() for p, _ in places.values() if p is not None]
                wet = lambda x, z: voxel_provider.get_block_at(
                    x, world_manager.get_height(x, z) + 1, z) == int(BlockType.WATER)
                origin = choose_site(lambda x, z: world_manager.get_height(x, z), wet, home,
                                     (schematic.width, schematic.length), taken)
                saving, schematic_tool.on_change = schematic_tool.on_change, (lambda: None)
                try:                                  # a construção da apresentação não vai para o save
                    schematic_tool.load_entry(entry, origin)
                    schematic_tool.confirm()
                finally:
                    schematic_tool.on_change = saving
                placed = schematic_tool.layer.structures[-1]
                lo, hi = placed.bounds()
                spot = find_floor_spot(presentation_solid, lo, hi, roofed=entry["kind"] == "schem")
                if spot is None:
                    spot = (lo[0] - 1.5, float(lo[1]), (lo[2] + hi[2]) / 2.0)
        places[name] = (placed, spot)
        return spot

    def go_to_presentation_place(name: str) -> None:
        """Leva o personagem ao lugar do passo do slide (ou de volta ao começo, com ``name`` vazio)."""
        if presentation_view.get("at", "") == name or player_token is None:
            return
        presentation_view["at"] = name
        spot = presentation_place(name) if name else presentation_view["home"]
        if spot is None:
            chat_console.add_message(f"[Apresentação] Não achei onde mostrar: {name}", (255, 170, 85))
            return
        player_token.position[:] = [float(v) for v in spot]
        camera.target[:] = player_token.position

    def set_presentation_biome(biome: str) -> None:
        """Refaz o terreno no bioma do slide (vazio: o do jogo). A seed é a mesma; os lugares postos saem (a troca
        repõe as construções salvas) e voltam no chão novo quando o slide pedir. Nada vai para o save."""
        pv = presentation_view
        if pv.get("biome", "") == biome or player_token is None:
            return
        pv["biome"] = biome
        from src.world.terrain_options import defaults, water_default
        original = active_terrain["options"]
        options = original if not biome else dict(original or defaults(), bioma=biome, agua=water_default(biome))
        go_to_presentation_place("")
        pv.pop("places", None)                     # o restore abaixo já tira as construções da apresentação
        regenerate_terrain(active_seed["value"], options, keep_world_structures=True)
        pv["home"] = tuple(float(v) for v in player_token.position)   # o começo, no chão novo
        pv["at"] = ""

    def end_presentation() -> None:
        """Esc na apresentação: a câmera volta a ser a do jogo e o HUD normal reaparece."""
        show_presentation_screen("")
        set_presentation_biome("")
        go_to_presentation_place("")
        if schematic_tool is not None:   # as construções postas só para a apresentação saem do mundo
            saving, schematic_tool.on_change = schematic_tool.on_change, (lambda: None)
            try:
                for placed, _ in presentation_view.pop("places", {}).values():
                    if placed is not None:
                        schematic_tool.remove(placed)
            finally:
                schematic_tool.on_change = saving
        camera.yaw, camera.pitch, camera.ortho_size, camera.perspective, camera.fov_degrees = (
            presentation_view["saved"])
        presentation_view["targets"] = None
        window.set_fullscreen(False)   # de volta ao jogo como ele estava

    map_editor = None
    if editor_mode:
        from src.editor.map_editor import MapEditor
        map_editor = MapEditor(camera=camera, map_path=map_path, create_gl=True)
        camera.board_rotation = 0
        camera.current_rotation = 0.0
        gl.glClearColor(0.055, 0.070, 0.095, 1.0)
        print("[Editor] Modo editor de mapa/objetos ativo.")

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

    from src.interactive.chest_session import ChestSession
    from src.world.chests import distance_to, find_chest
    chest_session = ChestSession()  # F abre e fecha um baú: a tela escurece e o personagem para (sem inventário ainda)
    chest_dim = {"quad": None}

    def pick_interactable():
        """O que o F usa agora: o baú aberto (para fechar), a porta sob o cursor, ou a porta ou o baú mais perto."""
        if chest_session.is_open:
            return "chest", chest_session.chest
        door = hovered_door_in_reach()
        if door is not None:
            return "door", door
        position = player_token.position
        door = schematic_tool.door_near(position)
        chest = find_chest(schematic_tool.layer.structures, position)
        if door is not None and chest is not None:
            return ("door", door) if distance_to(door, position) <= distance_to(chest, position) else ("chest", chest)
        if door is not None:
            return "door", door
        return ("chest", chest) if chest is not None else (None, None)

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

    def save_structures():
        """Grava as construções: no mundo do menu, se há um; senão no arquivo da seed."""
        from src.world.structure_save import SeedStore, seed_store_path, to_data
        items = to_data(schematic_tool.layer)
        try:
            if menus.world is not None:
                world = dict(menus.world, structures=items)
                menus.library.save(world)
                menus.world = world
            else:
                SeedStore(seed_store_path(active_seed["value"])).write(items, active_seed["value"])
        except (OSError, ValueError) as error:
            chat_console.add_message(f"[Schem] Não consegui salvar as construções: {error}", (255, 85, 85))

    if construction_panel is not None:
        schematic_tool.on_change = save_structures

    def save_world():
        if not terrain_demo:
            return
        if menus.world is not None:
            world = dict(menus.world)
        else:
            seed = active_seed['value']
            world = menus.library.create('Mundo ' + str(seed), seed, active_terrain["options"], write=False)
            world['seed'] = seed  # mantém a seed exata nos mundos iniciados pela CLI
        world['position'] = [float(v) for v in player_token.position]
        if construction_panel is not None:
            from src.world.structure_save import to_data
            world['structures'] = to_data(schematic_tool.layer)
        if character_model is not None:
            world['character'] = character_save.to_dict(character_model)
        world['combat'] = combat.sheet.to_dict()
        world['npcs'] = combat.npc_list()
        world['ambiente'] = ambience.to_dict()
        world['nevoa_explorada'] = fog_war.explored.to_data()
        menus.library.save(world)
        menus.world = world
        if not menus.active:
            menus.capture_scene(window.width,window.height)
        if menus.scene_image is not None and menus.scene_owner == menus.world["id"]:
            from PIL import ImageOps
            thumbnail = ImageOps.fit(menus.scene_image.convert('RGB'), (480,300))
            try:
                thumbnail.save(menus.library.directory/(menus.world['id']+'.png'))
            except OSError as error:
                print(f'[Menu] Não foi possível gravar a miniatura: {error}')

    def load_world(world, *, persist_new=False, unnamed=False):
        """Prepara terreno, construções e NPCs antes de trocar os recursos da sessão."""
        nonlocal world_manager, voxel_provider
        from src.core.game_storage import validate_world_state
        from src.world.structure_save import restore as restore_structures

        validate_world_state(world)
        seed, options = world['seed'], world.get('terrain')
        next_manager = WorldManager(make_generator(seed, options),
                                    render_distance=menus.preferences.data['render_distance'], atlas=atlas)
        next_tool = SchematicTool(mesh_factory=schematic_tool._mesh_factory, schematics_dir=schematic_tool.schematics_dir)
        next_tool.on_place = lambda placed: next_manager.clear_box(*placed.bounds())
        try:
            x, z = (float(player_token.position[0]), float(player_token.position[2])) if unnamed else (.5, .5)
            position = world.get('position') or [x, next_manager.get_height(x, z) + 1., z]
            position = [float(v) for v in position]
            warnings = restore_structures(next_tool, world.get('structures') or [])
            next_manager.load_initial_region(position[0], position[2])
            next_lookup = next_tool.layer.wrap_lookup(next_manager.neighbor_at)
            next_combat = CombatController(combat.sheet if unnamed else PlayerSheet.from_dict(world.get('combat')))
            next_combat.terrain = WorldTerrain(lambda x, y, z: is_solid(next_lookup(x, y, z)))
            next_combat.load_npcs(world.get('npcs'))
            next_ambience = None if unnamed else Ambience.from_dict(world.get('ambiente'))
            character = world.get('character') or default_world_character
            if persist_new:
                menus.library.save(world)
            if character_model is not None and character != character_save.to_dict(character_model):
                character_save.apply(character_model, character)
        except Exception:
            next_tool.discard_scene()
            next_manager.delete()
            raise

        chest_session.close()
        schematic_tool.discard_scene()
        schematic_tool.layer = next_tool.layer
        world_manager.delete()
        world_manager = next_manager
        active_seed['value'], active_terrain["options"] = seed, options
        player_token.position[:] = position
        player_token.vertical_velocity = 0.0
        player_token._collision_controller = None
        player_token.ladder_grip = None
        if construction_panel is not None:
            construction_panel.close()
        room_tracker.reset()
        voxel_provider = VoxelGridProvider(
            block_lookup=lambda x, y, z: schematic_tool.lookup(world_manager.neighbor_at, x, y, z)
        )
        camera.target[:] = player_token.position
        keys_pressed.clear()
        pan_state.update(active=False, shift_pressed=False)
        picking_state.update(click_pending=False, hover_hit=None, clicked_hit=None, aim=None, door=None, door_in_reach=False)
        grid_renderer.sync_chunks({}, -1)
        combat.clear()
        combat.sheet = next_combat.sheet
        combat.enemies = next_combat.enemies
        npc_models.delete()
        if next_ambience is not None:
            ambience.load(next_ambience.to_dict())
        fog_war.explored.load(world.get('nevoa_explorada'))
        if cloud_fog is not None:
            cloud_fog.field.reset()
        menus.world = None if unnamed else world
        for warning in warnings:
            chat_console.add_message("[Schem] " + warning, (255, 85, 85))

    def regenerate_world():
        """R cria outro mundo quando há uma sessão nomeada, gravando a sessão anterior primeiro."""
        from src.world.structure_save import SeedStore, seed_store_path

        seed = (active_seed['value'] + random.randrange(1, 999_999)) % 999_999 + 1
        if seed == active_seed['value']:
            seed = seed % 999_999 + 1
        previous = menus.world
        if previous is not None:
            save_world()
            name = previous['name'][:48] + ' (nova seed)'
            world = menus.library.create(name, seed, active_terrain["options"], write=False)
            world['character'] = menus.world.get('character')
            load_world(world, persist_new=True)
        else:
            world = dict(seed=seed, terrain=active_terrain["options"],
                         structures=SeedStore(seed_store_path(seed)).read(),
                         character=character_save.to_dict(character_model) if character_model is not None else None)
            load_world(world, unnamed=True)
        chat_console.add_message(f"[Terrain] Mundo regenerado. Nova seed: {seed}", (85, 255, 85))
        print(f"[Terrain] Mundo regenerado. Nova Seed: {seed}")


    def regenerate_terrain(new_seed: int, options, keep_world_structures: bool = False) -> None:
        """Refaz o terreno com outra seed ou outras opções (o R, e a apresentação ao trocar de bioma).

        ``keep_world_structures``: num mundo do menu, as construções dele voltam (a seed não mudou)."""
        world_manager.delete()
        room_tracker.reset()
        world_manager.generator = make_generator(new_seed, options)
        # Reposiciona o token no topo do novo relevo
        new_surface = world_manager.get_height(player_token.position[0], player_token.position[2])
        player_token.position[1] = float(new_surface) + 1.0
        world_manager.load_initial_region(player_token.position[0], player_token.position[2])
        combat.clear()                     # os inimigos ficavam no relevo antigo
        fog_war.explored.clear()           # o explorado era de outro relevo
        if cloud_fog is not None:
            cloud_fog.field.reset()
        # o relevo muda: as construções da seed anterior saem; sem mundo do menu, voltam as salvas da seed nova
        from src.world.structure_save import SeedStore, restore as restore_structures, seed_store_path
        saved = SeedStore(seed_store_path(new_seed)).read() if menus.world is None else (
            (menus.world.get("structures") or []) if keep_world_structures else [])
        for warning in restore_structures(schematic_tool, saved):
            chat_console.add_message("[Schem] " + warning, (255, 85, 85))
        if construction_panel is not None:
            construction_panel.close()

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

        # A apresentação fica com as setas, PageUp/Down, Home/End, H e Esc; o resto segue para o jogo
        if presentation is not None and presentation.active and presentation.key(key, action):
            if not presentation.active:
                end_presentation()
            return True

        # O editor de mapa consome os atalhos próprios; Q/E, WASD e o chat continuam
        # disponíveis para a câmera e para o console.
        if map_editor is not None and not chat_console.is_open:
            if map_editor.handle_key(key, action, mods):
                return True

        if (master_panel is not None and master_panel.is_open and not chat_console.is_open
                and key == glfw.KEY_ESCAPE and action == glfw.PRESS):
            master_panel.close()
            return True

        if construction_panel is not None and not chat_console.is_open and not character_editor.is_open:
            if construction_panel.handle_key(key, action, mods):
                keys_pressed.clear()
                return True

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

        # no combate, 1-6 escolhem a ação, Tab troca o alvo e Enter encerra a vez (o WASD continua andando)
        if terrain_demo and combat.in_combat and combat.handle_key(menus.preferences.canonical(key), action):
            return True

        if schematic_tool is not None and schematic_tool.handle_key(key, action, mods):
            keys_pressed.clear()
            return True

        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            chest_session.close()
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
                kind, target = (None, None) if (player_token.ladder_grip is not None
                                                and not chest_session.is_open) else pick_interactable()
                if kind == "chest" and combat.in_combat and not chest_session.is_open:
                    pass                               # no meio da luta não se mexe em baú
                elif kind == "chest":
                    chest_session.toggle(target)       # abre o baú ao alcance, ou fecha o que está aberto
                elif kind == "door":
                    toggle_door_for_player(target)
                else:
                    player_token.grab_ladder(voxel_provider)
            return True
        keys_pressed[key] = (action != glfw.RELEASE)

        if terrain_demo and map_world is None and not character_editor.is_open and key == glfw.KEY_R and action == glfw.PRESS:
            try:
                regenerate_world()
            except (OSError, ValueError, RuntimeError) as error:
                chat_console.add_message(f"[Terrain] Não consegui regenerar o mundo: {error}", (255, 85, 85))
            return True

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

        if map_editor is not None:
            if map_editor.handle_mouse_button(button, action, window.is_key_pressed(glfw.KEY_LEFT_SHIFT)):
                return

        if (master_panel is not None and master_panel.is_open and not character_editor.is_open
                and button == glfw.MOUSE_BUTTON_LEFT and action in (glfw.PRESS, glfw.RELEASE)):
            if master_panel.handle_mouse_button(*window.get_cursor_pos(), action == glfw.PRESS):
                return

        if construction_panel is not None and not chat_console.is_open and not character_editor.is_open:
            if construction_panel.handle_mouse_button(button, action, window.is_key_pressed(glfw.KEY_LEFT_SHIFT),
                                                      window.get_cursor_pos(), window.width):
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
        if master_panel is not None and not character_editor.is_open and master_panel.handle_cursor(*window.get_cursor_pos()):
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
            menus.wheel(y_offset)
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
        if map_editor is not None and not chat_console.is_open and map_editor.handle_char(codepoint):
            return
        if (construction_panel is not None and not chat_console.is_open and not character_editor.is_open
                and construction_panel.handle_char(codepoint)):
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

    # --gpu-times (com --frametimes): o tempo que a PLACA leva em cada trecho, por consultas de carimbo de tempo do
    # OpenGL (o tempo do processador só mostra onde ele espera a placa, não quanto ela trabalha em cada etapa)
    gpu_times = "--gpu-times" in sys.argv and bool(frametimes_path)
    gpu_marks = []          # (nome, consulta) do quadro atual
    gpu_frames = []         # as listas de cada quadro, lidas no fim

    def mark(name):
        if frametimes_path:
            frame_marks.append((name, time.perf_counter()))
            if gpu_times:
                query = int(np.asarray(gl.glGenQueries(1)).ravel()[0])
                gl.glQueryCounter(query, gl.GL_TIMESTAMP)
                gpu_marks.append((name, query))
    # O que a inicialização deixou (módulos, atlas, roupas) vive até o fim: congelado, sai da varredura da
    # geração 2 do coletor, que passava por tudo isso a cada poucos segundos (15-17 ms de quadro parado).
    # O que sobrevive a uma varredura completa também é congelado: a próxima passa só pelo que é novo. A contagem
    # de referências segue liberando tudo; só um ciclo entre objetos congelados ficaria sem coletar.
    gc.collect()
    gc.freeze()
    gc.callbacks.append(lambda phase, info: gc.freeze() if phase == "stop" and info["generation"] == 2 else None)
    # Configurações > Gráficos: aplicadas quando mudam (o /sombras do chat continua valendo até a próxima mudança)
    from src.core.frame_limiter import FrameLimiter
    from src.core.game_storage import GRAPHICS
    frame_limiter = FrameLimiter()
    graphics_applied = {"key": None}
    edge_fog = {"on": True}   # Configurações > Gráficos > Névoa na borda

    # Granulado da penumbra (Configurações): o valor salvo -> o bloco de pixels (largura, altura) que gira o cone junto
    SPIN_TILES = {1: (1.0, 1.0), 2: (2.0, 2.0), 4: (4.0, 2.0), 8: (8.0, 4.0)}

    def apply_graphics():
        prefs = menus.preferences.data
        key = tuple(prefs[name] for name in GRAPHICS)
        if key == graphics_applied["key"]:
            return
        graphics_applied["key"] = key
        if world_manager is not None:
            world_manager.render_distance = int(prefs["render_distance"])
        edge_fog["on"] = bool(prefs.get("edge_fog", True))
        if shadow_renderer is not None:
            shadow_renderer.enabled = prefs["shadows"] != "off"
            shadow_renderer.quality = {"low": 0, "medium": 1, "high": 2}.get(prefs["shadows"], 2)
            shadow_renderer.steps = int(prefs["shadow_range"])
            shadow_renderer.set_detail(int(prefs["shadow_detail"]), shader)
            shadow_renderer.strength = float(prefs["shadow_strength"])
            shadow_renderer.set_distance(int(prefs.get("shadow_distance", 1)))
            shadow_renderer.spin_tile = SPIN_TILES.get(int(prefs.get("shadow_grain", 1)), (1.0, 1.0))
            cone = prefs["shadows"] in ("medium", "high")
            accum_state["on"] = bool(prefs.get("shadow_accum", True)) and cone
            # com a acumulada ligada a meia resolução não vale: a acumulada já traça poucos raios por quadro
            half = bool(prefs.get("shadow_half", False)) and cone and not accum_state["on"]
            try:
                shader.set_define("SHADOW_HALF", half)
            except RuntimeError as error:      # a placa não tem as derivadas finas: fica a sombra inteira
                print(f"[Render] Sombra em meia resolução indisponível: {error}")
                shader.set_define("SHADOW_HALF", False)


    fps_overlay = FpsOverlay()

    def coords_on_screen() -> bool:
        """As coordenadas do canto de cima à esquerda: ligadas em Configurações > Geral e sem o painel do /mestre ali."""
        return (coordinate_overlay is not None and menus.preferences.data.get('show_coords', True)
                and not (master_panel is not None and master_panel.is_open) and not presenting())

    def presenting() -> bool:
        return presentation is not None and presentation.active

    def update_presentation(dt: float) -> None:
        """Leva a câmera, suavemente, ao que a cena do slide pede (giro, zoom, ortográfica ou perspectiva)."""
        pv = presentation_view
        presentation.update(dt)
        if pv["slide"] != presentation.index:   # o giro continua de onde parou em vez de voltar ao início
            pv["slide"] = presentation.index
            pv["base_yaw"] = math.degrees(camera.yaw)
        show_presentation_screen(presentation.slide.scene.screen)
        set_presentation_biome(presentation.slide.scene.biome)
        if "home" not in pv and player_token is not None:
            pv["home"] = tuple(float(v) for v in player_token.position)
        places = presentation.slide.scene.places
        go_to_presentation_place(places[min(presentation.step, len(places) - 1)] if places else "")
        targets = presentation.camera_targets(pv["base_yaw"], pv["base_ortho"])
        pv["targets"] = targets
        if character_editor.is_open:   # a tela de criação cuida da câmera (gira em volta do personagem)
            return
        k = 1.0 - math.exp(-6.0 * dt)
        current = math.degrees(camera.yaw)
        camera.yaw = math.radians(current + ((targets.yaw_degrees - current + 180.0) % 360.0 - 180.0) * k)
        camera.ortho_size += (targets.ortho_size - camera.ortho_size) * k
        camera.perspective = targets.perspective
        camera.fov_degrees = 40.0 if targets.perspective else pv["saved"][4]   # com 18° quase não se distingue

    def draw_presentation() -> None:
        """Os cartões do slide (um quad por cartão) e o número do slide, por cima de tudo."""
        from src.interactive.presentation import face_stats
        from src.interactive.presentation_card import render_footer, render_slide
        from src.rendering.hud_quad import HudQuad
        pv = presentation_view
        if window.is_fullscreen != presentation.fullscreen:
            window.set_fullscreen(presentation.fullscreen)
        slide = presentation.slide
        live = {}
        if "faces" in slide.scene.counters:
            if window.time - pv["faces_at"] > 1.0:   # soma os chunks carregados no máximo uma vez por segundo
                pv["faces"] = face_stats([c.blocks for c in list(world_manager.chunks.values())],
                                         [m.index_count for m, _ in list(world_manager.meshes.values())])
                pv["faces_at"] = window.time
            live["faces"] = pv["faces"]
        if "chunks" in slide.scene.counters:
            live["chunks"] = (pv["drawn"], len(world_manager.meshes))
        if presentation.card_visible:
            pieces = render_slide(slide, presentation.step, window.width, window.height, live)
            quads = pv.setdefault("quads", [])
            shown = pv.setdefault("shown", [])
            while len(quads) < len(pieces):
                quads.append(HudQuad())
                shown.append(None)
            for i, (x, y, image) in enumerate(pieces):
                if shown[i] is not image:           # a imagem vem do cache: só envia à GPU quando mudou
                    quads[i].set_image(image)
                    shown[i] = image
                quads[i].draw(x, y, window.width, window.height)
        if pv["footer"] is None:
            pv["footer"] = HudQuad()
        if pv["footer_key"] != presentation.index:
            pv["footer"].set_image(render_footer(presentation.index, len(presentation.slides), window.width))
            pv["footer_key"] = presentation.index
        # com a tela de criação aberta o canto de baixo à esquerda tem os botões dela: o número vai para a direita;
        # no combate o chat ocupa o canto de baixo à esquerda: o número sobe para o canto de cima
        footer_x = window.width - pv["footer"].size[0] - 16 if character_editor.is_open else 16
        footer_y = 4 if slide.scene.screen == "combate" else window.height - pv["footer"].size[1] - 12
        pv["footer"].draw(footer_x, footer_y, window.width, window.height)

    # o diamante do canto de cima à direita enquanto a roupa se ajusta ou uma importação roda
    loading_indicator = LoadingIndicator(lambda: skin_command_handler.busy_status)
    from src.interactive.combat_hud import CombatHud, chat_log_view
    from src.interactive.enemy_tokens import EnemyTokenRenderer
    enemy_renderer = EnemyTokenRenderer()
    from src.interactive.npc_models import NpcModels
    npc_models = NpcModels()
    # /criar npc e /npc editar: o NPC na tela de criação (a ficha, o corpo e quem a tela editava antes)
    npc_edit: dict = {}
    combat_hud = CombatHud()
    while not window.should_close():
        dt = window.update_delta_time()
        fps_overlay.update(dt)
        loading_indicator.update(dt)
        if frametimes_path:
            if frame_marks:
                frame_sections.append({n: (t - frame_marks[i - 1][1]) * 1000.0
                                       for i, (n, t) in enumerate(frame_marks) if i})
            frame_marks.clear()
            if gpu_marks:
                gpu_frames.append(list(gpu_marks))
                gpu_marks.clear()
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
                        if not terrain_demo or map_world is not None:
                            raise ValueError('Reabra pelo menu inicial para jogar um mundo procedural.')
                        load_world(world)
                        menus.go('game')
                except (OSError, ValueError, RuntimeError) as error:
                    menus.message = 'Falha ao salvar/abrir: ' + str(error)
            window.set_vsync(menus.preferences.data['vsync'])
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            menus.render(window.width, window.height)
            window.swap_buffers()
            frame_limiter.wait(menus.preferences.data["fps_limit"])
            continue
        if menus.world is not None:
            menus.world['played'] += dt
        camera.update(dt)
        if presenting():
            update_presentation(dt)
        if menus.preferences.data['reduce_motion']:
            camera.current_rotation = float(camera.board_rotation)
        chat_console.update(dt)

        # Abrir e fechar a tela de criação: a câmera enquadra o personagem e volta ao sair.
        if skin_command_handler.editor_requested:
            skin_command_handler.editor_requested = False
            character_editor.open()
        if terrain_demo and skin_command_handler.npc_request is not None and not npc_edit \
                and not character_editor.is_open:
            # /criar npc (um corpo novo do sexo pedido) ou /npc editar (o corpo que ele já tem): a tela do /skin
            # passa a vestir o NPC; o personagem volta para ela quando a tela fecha
            from src.clothing.character_animation import CharacterAnimator
            from src.interactive.npc_models import CustomHolder, build_model
            request, skin_command_handler.npc_request = skin_command_handler.npc_request, None
            editing_token = combat.token(request["editar"]) if "editar" in request else None
            holder = CustomHolder()   # o modelo .glb do NPC (o /skin modelo põe nele enquanto a tela veste o NPC)
            if editing_token is not None:
                spec = dict(editing_token.npc)        # a aba NPC muda uma cópia; o NPC é refeito ao fechar
                body = npc_models.release(editing_token.id)
                if body is not None and body.model is not None:
                    npc_model, npc_animator = body.model, body.animator
                else:                                 # o NPC só tinha o modelo .glb: o corpo montado vem agora
                    npc_model = build_model(spec["id"], spec.get("personagem"))
                    npc_animator = CharacterAnimator(npc_model, walking=False)
                holder.custom_model = body.custom if body is not None else None
            elif "editar" not in request:
                spec = dict(request, id=combat.new_npc_id())
                npc_model = build_model(spec["id"], None, spec.pop("corpo", "masculino"))
                npc_animator = CharacterAnimator(npc_model, walking=False)
            else:
                spec = None
            if spec is not None:
                npc_edit.update(spec=spec, model=npc_model, animator=npc_animator, token=editing_token,
                                player_model=skin_command_handler.character_model, holder=holder,
                                player_choice=(skin_command_handler.model_choice, skin_command_handler.want_custom,
                                               skin_command_handler.save_model_choice))
                # a escolha do modelo .glb passa a ser a do NPC, sem gravar por cima da do personagem
                skin_command_handler.model_choice = dict(spec["modelo"]) if spec.get("modelo") else None
                skin_command_handler.want_custom = False
                skin_command_handler.save_model_choice = False
                skin_command_handler.model_target = holder
                skin_command_handler.character_model = npc_model
                skin_command_handler.npc_editing = spec  # a aba NPC da tela muda nome, lado, ficha e fala
                character_editor.autosave = False      # fechar a tela não grava o NPC como o personagem
                character_editor.open()
        elif npc_edit and not character_editor.is_open:
            # a tela fechou: o NPC leva a aparência e aparece (ou volta) no mundo; a tela volta a vestir o personagem
            spec, npc_model = npc_edit["spec"], npc_edit["model"]
            spec["personagem"] = character_save.to_dict(npc_model)
            custom = npc_edit["holder"].custom_model if skin_command_handler.model_choice is not None else None
            if custom is not None:
                spec["modelo"] = dict(skin_command_handler.model_choice)
            else:
                spec.pop("modelo", None)
                if npc_edit["holder"].custom_model is not None:
                    npc_edit["holder"].custom_model.delete()
            skin_command_handler.character_model = npc_edit["player_model"]
            (skin_command_handler.model_choice, skin_command_handler.want_custom,
             skin_command_handler.save_model_choice) = npc_edit["player_choice"]
            skin_command_handler.model_target = None
            skin_command_handler.npc_editing = None
            character_editor.autosave = True
            token = npc_edit["token"]
            if token is not None:
                token = combat.replace_npc(token.id, spec) or token
            else:
                ally = spec.get("lado") == "amigavel"
                ahead = 2.5 if ally else 7.0           # o hostil aparece fora do alcance de vista dele
                px, py, pz = (float(v) for v in player_token.position)
                yaw = float(player_token.yaw)
                spot = [px + math.sin(yaw) * ahead, py, pz + math.cos(yaw) * ahead]
                token = combat.add_npc(spec, spot, yaw + math.pi)
                chat_console.add_message(f"[NPC] {token.combatant.name} chegou "
                                         f"({'amigável' if ally else 'hostil'}).", (85, 255, 85))
            npc_models.adopt(token.id, npc_model, npc_edit["animator"], spec.get("personagem"),
                             custom=custom, choice=spec.get("modelo"))
            npc_edit.clear()
        edited_model = npc_edit["model"] if npc_edit else character_model   # quem a tela de criação mostra
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
            if npc_edit:
                editor_animator = npc_edit["animator"]
            if editor_animator is not None:
                editor_animator.arms_out = character_editor.arms_raised  # braços a 90 graus, no ajuste fino
            if terrain_demo and editor_animator is not None:
                editor_animator.walking = character_editor.walk_preview  # W liga o andar na tela
                editor_animator.update(dt)
            elif char_demo:
                character_animator.update(dt)
            if terrain_demo and player_token.custom_model is not None:
                player_token.custom_model.update(dt, player_token.speed if character_editor.walk_preview else 0.0)  # W anda
            if npc_edit and npc_edit["holder"].custom_model is not None:
                npc_edit["holder"].custom_model.update(dt, player_token.speed if character_editor.walk_preview else 0.0)
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
        elif map_editor is not None:
            map_editor.update(dt)
        elif terrain_demo:
            # 1. Movimentação do token de personagem com WASD e aderência ao relevo
            movement_forward, movement_right = camera.get_movement_directions()
            facing_before = player_token.yaw
            chest_session.update(dt)
            lid_update = chest_session.take_lid_update()
            if lid_update is not None:
                schematic_tool.set_chest_lid(*lid_update)   # a tampa do baú gira: refaz a malha dos baús
            step_from = [float(v) for v in player_token.position]
            player_token.update(
                dt,
                # baú aberto, ou no combate fora da vez (ou sem movimento): o teclado de movimento fica mudo
                {} if (chest_session.locks_movement or combat.locks_movement) else keys_pressed,
                movement_forward,
                movement_right,
                voxel_provider,
            )
            if combat.in_combat:
                # na vez do personagem o passo gasta o movimento da vez; o que passa da reserva não anda
                player_token.position[:] = combat.limit_step(step_from, player_token.position)
            combat.update(dt, player_token.position)
            npc_models.sync(combat, dt, skip=npc_edit["spec"]["id"] if npc_edit else None)
            enemy_renderer.skip = npc_models.ready_ids()   # quem tem corpo pronto não mostra a miniatura
            for combat_text, combat_color in combat.take_messages():
                chat_console.add_message(combat_text, combat_color)
            if picking_state["aim"] is not None and player_token.ladder_grip is None:
                # com o cursor na cena, o personagem olha para ele (andando ou parado), não para onde anda
                # (agarrado à escada, olha para ela)
                from src.interactive.context_cursor import face_toward
                player_token.yaw = face_toward(facing_before, player_token.position, picking_state["aim"], dt)

            if map_world is None:
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

            if map_editor is not None:
                mode_badge = "🗺️ Editor de mapa | "
            elif map_world is not None:
                mode_badge = "Mapa carregado | "
            elif terrain_demo:
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
        apply_graphics()
        if scene_target is not None and not editing:
            prefs = menus.preferences.data
            scene_target.begin(window.width, window.height, samples=prefs["msaa"], scale=prefs["render_scale"],
                               fxaa=prefs["fxaa"])

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
            combat.set_hover(None)
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
            # o inimigo sob o mouse ganha anel, dica e o cursor de ataque
            combat.set_hover(combat.pick(mouse_ray.origin, mouse_ray.direction))
            if picking_state["click_pending"]:
                # um clique num inimigo começa a luta (de surpresa), ou mira e ataca nela
                clicked_enemy = combat.hovered()
                if clicked_enemy is not None:
                    combat.click_enemy(clicked_enemy, player_token.position)
                    picking_state["click_pending"] = False
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
            Ambience.neutral(shader)
            if editor_animator is not None:
                editor_animator.sync()  # a pele recortada por um clique deste quadro já entra na pose
            shown_body = player_token.custom_model if terrain_demo and player_token.custom_model is not None \
                else character_model
            if npc_edit:   # o NPC na tela: o modelo .glb dele, se escolheu um, ou o corpo montado
                shown_body = npc_edit["holder"].custom_model or edited_model
            shown_body.draw(shader, model @ mat4_rotate_y(math.radians(turntable_state["yaw"])))
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glViewport(0, 0, fb_w, fb_h)
            # O pincel de pele: os pontos da cage do corpo na tela, para pintar e para mostrar.
            character_editor.picker = character_editor.overlay = None
            character_editor.bones_view = None
            shown_custom = (npc_edit["holder"].custom_model if npc_edit else player_token.custom_model) \
                if terrain_demo else None
            if shown_custom is not None and shown_custom.rig is not None:
                # os ossos do modelo personalizado na tela, para a aba Modelo mostrar e deixar clicar
                from src.clothing import role_editor
                bone_points = role_editor.posed_positions(
                    shown_custom.rig, shown_custom.animator.matrices if shown_custom.animator is not None else None)
                bone_xy, bone_depth = role_editor.screen_positions(
                    bone_points, model @ mat4_rotate_y(math.radians(turntable_state["yaw"])), view, projection,
                    (scene_x, 0, scene_right, window.height))
                character_editor.bones_view = {"xy": bone_xy, "depth": bone_depth, "parents": shown_custom.rig.parents,
                                               "names": shown_custom.rig.names}
            skin_cage = getattr(edited_model, "hsr_cage", None)
            if character_editor.brushing and skin_cage is not None:
                from src.interactive import skin_brush
                brush_view = skin_brush.BrushView(
                    skin_cage[0], skin_cage[2], model @ mat4_rotate_y(math.radians(turntable_state["yaw"])), view,
                    projection, (scene_x, 0, scene_right, window.height), pose=getattr(editor_animator, "posed", None),
                    skin=getattr(edited_model, "hsr_skin", None))
                brush_custom = edited_model.customization
                character_editor.picker = brush_view.pick
                character_editor.overlay = (brush_view.xy, brush_view.facing, skin_brush.states(
                    getattr(edited_model, "hsr_hidden", skin_cage[1]), getattr(brush_custom, "hsr_hide", ()),
                    getattr(brush_custom, "hsr_show", ())))
            if not char_demo:
                shader.set_vec3("u_LightDir", 0.5, 1.0, 0.7)
                shader.set_vec3("u_LightColor", 0.9, 0.9, 0.9)
                shader.set_vec3("u_AmbientColor", 0.35, 0.35, 0.35)
                gl.glClearColor(0.08, 0.10, 0.13, 1.0)
        elif map_editor is not None:
            gl.glClearColor(0.055, 0.070, 0.095, 1.0)
            shader.use()
            shader.set_vec3("u_LightDir", 0.5, 1.0, 0.7)
            shader.set_vec3("u_LightColor", 0.95, 0.95, 0.95)
            shader.set_vec3("u_AmbientColor", 0.38, 0.38, 0.40)
            mouse_x, mouse_y = window.get_cursor_pos_framebuffer()
            map_editor.update_cursor(mouse_x, mouse_y, window.width, window.height, view, projection, model,
                                     mouse_window=window.get_cursor_pos())
            map_editor.process_click()
            map_editor.update_drag()
            map_editor.render(shader, projection, view, model, window.time,
                              window.width, window.height)
        elif terrain_demo:
            # Espaço fechado do jogador: a máscara e a suavização do efeito. Enxerga o terreno, as construções do
            # /schem e também os objetos e o mapa do editor (viram construções só para este cálculo).
            mark("misc")
            chunk_revision, loaded_chunks = world_manager.get_loaded_chunks_snapshot()
            room_structures = list(schematic_tool.layer.structures)
            if map_world is not None:
                room_structures += map_world.room_structures()
            if len(room_structures) > len(schematic_tool.layer.structures):
                schematic_tool.ensure_atlas()   # as tampas dos objetos e do mapa usam o atlas das construções
            room_tracker.update(dt, player_token.position, loaded_chunks, chunk_revision, room_structures)
            mark("room_tracker")
            room_renderer.update(dt, room_tracker)
            mark("room_renderer")
            shadow_renderer.update(room_tracker, player_token.position, loaded_chunks, chunk_revision, room_structures)
            mark("shadows")
            if construction_panel is not None and construction_panel.is_open:
                # o bloco que o mouse aponta (terreno e construções) e as células ocupadas pelo jogador
                cursor_x, cursor_y = window.get_cursor_pos_framebuffer()
                ray = screen_to_world_ray(cursor_x, cursor_y, window.width, window.height, view, projection, model)
                px, py, pz = (float(v) for v in player_token.position)
                body = ((math.floor(px - 0.35), math.floor(py), math.floor(pz - 0.35)),
                        (math.floor(px + 0.35), math.floor(py + 1.79), math.floor(pz + 0.35)))
                construction_panel.update_cursor(raycast_voxels(ray, voxel_provider, max_distance=512.0), body)
            # Configuração do modo subterrâneo (cutaway de caverna) e água
            underground_mode = False
            if map_world is None and voxel_provider is not None and not room_renderer.visible:
                # Só há "subsolo" com chão de verdade por cima do jogador: a água não cobre ninguém (nadar num lago
                # não recorta o que está acima), mas o teto de uma caverna sob o lago cobre.
                underground_mode = (
                    player_token.position[1]
                    < float(
                        voxel_provider.get_top_solid_block(
                            int(np.floor(float(player_token.position[0]))),
                            int(np.floor(float(player_token.position[2]))),
                            skip_water=True,
                            skip_foliage=True,  # a copa de uma árvore não faz do chão embaixo dela uma caverna
                        )
                    ) + 0.25
                )
            shader.set_bool("u_UndergroundMode", underground_mode)
            shader.set_float("u_PlayerY", float(player_token.position[1]))
            shader.set_float("u_CutawayAlpha", 0.38)
            shader.set_float("u_CutawayFade", 0.45)
            shader.set_bool("u_WaterMode", player_token.in_water)
            shader.set_int("u_CutawayPass", 0)

            # 0. A sombra dos personagens: eles vistos do sol num mapa de profundidade que o terreno lê a seguir
            # a ambientação do mestre: a hora move o sol (e as sombras), o resto é a correção no fim do shader
            ambience.update(dt)
            sun_now = ambience.light_direction()
            shader.set_vec3("u_LightDir", *sun_now)
            if shadow_renderer is not None:
                shadow_renderer.sun_direction = sun_now
            ambience.apply(shader, (model @ np.array([float(v) for v in player_token.position] + [1.0]))[:3])
            fog_war.update(ambience.fog_war, float(player_token.position[0]), float(player_token.position[2]))
            # na superfície, a névoa de guerra são nuvens de blocos (cloud_fog); numa caverna, a névoa do shader
            clouds_on = bool(ambience.fog_war) and not underground_mode and ambience.war_style != 1
            if clouds_on and cloud_fog is None:
                from src.rendering.cloud_fog import CloudFog
                cloud_fog = CloudFog(lambda bx, bz: world_manager.get_height(bx, bz), fog_war.explored,
                                     lambda: [placed.bounds() for placed in schematic_tool.layer.structures]
                                     if schematic_tool is not None else [])
                shader.use()  # o construtor de Shader muda o programa ativo durante a compilação
            fog_war_args = (0 if clouds_on else ambience.fog_war, np.linalg.inv(np.asarray(model, dtype=np.float64)), ambience.war_color(),
                            (float(player_token.position[0]), float(player_token.position[2])))
            fog_war.apply(shader, *fog_war_args)
            grid_renderer.fog_war = lambda grid_shader, args=fog_war_args: fog_war.apply(grid_shader, *args)
            # a neblina de ambientação: ao ar livre (numa caverna ou num cômodo a de fora não entra)
            mist_on = ambience.mist > 0 and not underground_mode and room_renderer.level <= 0.001
            shader.set_define("MIST", mist_on)
            shader.set_define("MIST_RAYS", mist_on and ambience.mist_rays > 0)
            if mist_on:
                layers = getattr(world_manager.generator, "column_layers", lambda: (0,))()
                mist_field.update(float(player_token.position[0]), float(player_token.position[2]), chunk_revision,
                                  loaded_chunks.get, layers)
                mist_field.apply(shader, fog_war_args[1],
                                 np.asarray(camera._camera_position(), dtype=np.float64) - np.asarray(camera.target, dtype=np.float64),
                                 ambience.mist_height)
            else:
                shader.set_float("u_MistAmount", 0.0)
            gl.glClearColor(*ambience.background(), 1.0)
            edge_on = edge_fog["on"] and world_manager is not None and not underground_mode
            shader.set_define("EDGE_FOG", edge_on)
            shader.use()       # a troca de variante devolve o programa que estava em uso, e aqui não é o do mundo
            if edge_on:
                px, pz = float(player_token.position[0]), float(player_token.position[2])
                shader.set_vec4("u_EdgeRect", *world_manager.loaded_rect(px, pz))
                shader.set_vec2("u_EdgePlayer", px, pz)
                shader.set_float("u_EdgeRadius", world_manager.render_distance * 16.0 + 10.0)
                shader.set_vec3("u_EdgeColor", *ambience.background())
                shader.set_mat4("u_EdgeInvModel", np.asarray(fog_war_args[1], dtype=np.float32))
            if character_shadows is not None:
                shadow_casters = []
                if shadow_renderer.enabled and not character_editor.is_open:
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
                    shader.set_int("u_TextureAtlas", 0)
                    shader.set_bool("u_WorldStyle", False)
                    shadow_casters = [lambda: player_token.draw(
                        shader=shader, base_model=model @ player_token.get_model_matrix())]
                    shadow_casters += npc_models.casters(shader, combat, model)
                feet_drawn = model @ np.array([float(v) for v in player_token.position] + [1.0])
                character_shadows.strength = shadow_renderer.strength
                character_shadows.render(shader, feet_drawn[:3], shadow_renderer.sun_direction, shadow_casters)
                shader.set_mat4("u_Projection", projection)
                shader.set_mat4("u_View", view)
                character_shadows.apply(shader)

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
            from src.world.sight import leaf_hole_radius, sight_cover, sight_needed
            sight_world_dir = np.linalg.inv(np.asarray(model, dtype=np.float64))[:3, :3] @ (
                np.array(camera._camera_position(), dtype=np.float64) - sight_target[:3])
            window_cells = room_tracker.mask.window if room_tracker.mask is not None else None

            def sight_blocked_far() -> bool:
                """De longe: uma árvore alta lá na frente, fora da janela em volta do personagem (nos chunks)."""
                from src.world.sight import CHEST, HEAD, START, sight_blocked_world
                d = sight_world_dir / max(float(np.linalg.norm(sight_world_dir)), 1e-9)
                if d[1] <= 0.05:
                    return False
                layers = getattr(world_manager.generator, "column_layers", lambda: (0,))()
                top = (max(layers) + 1) * 16          # acima disso não há bloco: o raio pode parar
                for rise in (CHEST, HEAD):
                    start = (feet[0], feet[1] + rise, feet[2])
                    if sight_blocked_world(loaded_chunks.get, start, d, START, min((top - start[1]) / d[1], 240.0)):
                        return True
                return False
            outdoors_target = 1.0 if (
                room_renderer.level > 0.001 or window_cells is None
                or sight_needed(sight_cover(window_cells), room_tracker.mask.origin, feet, sight_world_dir)
                or sight_blocked_far()) else 0.0
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
            if map_world is not None:
                # Mapa do editor (--map=...): o volume base e os objetos, no lugar do terreno procedural; as construções
                # do /schem, os cômodos e as tampas seguem abaixo, como no terreno.
                map_world.render(shader, model)

            def draw_solids():
                """O que é opaco no mundo: o terreno e as tampas dele, as construções do /schem e as tampas delas.
                As construções usam outro atlas, em que a região da água do terreno pode ser outra textura: nada delas
                é tratado como água."""
                if map_world is None:
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, atlas.texture_id)
                    shader.set_int("u_TextureAtlas", 0)
                    shader.set_bool("u_UndergroundMode", underground_mode)   # as construções desligam: volta aqui
                    shader.set_bool("u_WaterMode", player_token.in_water)
                    shader.set_int("u_CutawayPass", 0)
                    shader.set_int("u_WaterPass", 1)
                    # ao ar livre, a copa entre a câmera e o personagem abre num círculo (num cômodo ou numa caverna,
                    # os cortes de lá cuidam da vista)
                    shader.set_float("u_LeafHole", 0.0 if underground_mode or room_renderer.level > 0.001
                                     else leaf_hole_radius(camera.ortho_size))
                    shader.set_vec4("u_LeafRect0", *leaf_rects[0])
                    shader.set_vec4("u_LeafRect1", *leaf_rects[1])
                    presentation_view["drawn"] = world_manager.render(shader, model, view_projection)
                    shader.set_float("u_LeafHole", 0.0)             # as construções usam outro atlas
                    room_renderer.draw_terrain_caps(shader, model)  # as faces que o corte deixou sem tampa
                shader.set_int("u_WaterPass", 0)
                schematic_tool.draw(shader, model, window.time, preview=False)
                room_renderer.draw_structure_caps(shader, model)

            # Pré-passada de profundidade: os descartes do shader (transparência, cortes) desligam o teste de
            # profundidade antecipado da placa, e sem ele cada fragmento escondido pagaria os raios do sol. A 1ª
            # passada só escreve a profundidade; a 2ª, sem escrever, sombreia só o que ficou na frente. Vale para o
            # terreno e para as construções (de dentro de uma casa, quase tudo na tela é parede, piso e móvel dela).
            # Apresentação: o wireframe do face culling e os modos "só textura" / "só luz" valem para o mundo
            slide_targets = presentation_view.get("targets") if presenting() else None
            wireframe = slide_targets is not None and slide_targets.wireframe
            shader.set_int("u_DebugView", slide_targets.debug_view if slide_targets is not None else 0)
            if wireframe:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
            mark("sight_and_cuts")
            shader.set_bool("u_DepthOnly", True)
            gl.glColorMask(gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)
            draw_solids()
            mark("depth_prepass")
            gl.glColorMask(gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
            shader.set_bool("u_DepthOnly", False)
            gl.glDepthFunc(gl.GL_LEQUAL)
            gl.glDepthMask(gl.GL_FALSE)
            if early_z["ok"]:
                try:
                    shader.set_define("EARLY_Z", True)   # a variante com o teste de profundidade antes do shader
                except RuntimeError as error:            # a placa não aceita: segue sem
                    early_z["ok"] = False
                    print(f"[Render] Sem teste de profundidade antecipado: {error}")
            # a sombra acumulada (src/rendering/shadow_accum.py): precisa do teste antecipado (um fragmento por pixel)
            # e da cena no framebuffer dela (as texturas têm o tamanho da cena)
            accum_now = (accum_state["on"] and accum_state["ok"] and early_z["ok"] and shadow_accum is not None
                         and scene_target is not None and scene_target.active and shadow_renderer is not None
                         and shadow_renderer.active)
            if accum_now:
                try:
                    shader.set_define("SHADOW_ACCUM", True)
                    shader.use()
                    shadow_accum.begin(shader, scene_target.size, projection @ view @ model)
                except Exception as error:             # a placa não aceita: segue com a sombra de sempre
                    accum_state["ok"] = accum_now = False
                    shader.set_define("SHADOW_ACCUM", False)
                    print(f"[Render] Sem sombra acumulada: {error}")
            elif shadow_accum is not None:
                shadow_accum.reset()                   # sem ela neste quadro, o histórico fica velho
            shader.use()       # a variante pode ter trocado com outro programa em uso (as tampas, as construções)
            draw_solids()
            if accum_now:
                shadow_accum.end()
                shader.set_define("SHADOW_ACCUM", False)
            shader.set_define("EARLY_Z", False)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDepthFunc(gl.GL_LESS)
            mark("story_and_world_draw")

            if map_world is None and underground_mode:
                # 2. Segundo passe: terreno acima do jogador translúcido (cutaway de caverna)
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, atlas.texture_id)
                shader.set_int("u_TextureAtlas", 0)
                shader.set_bool("u_UndergroundMode", True)
                shader.set_bool("u_WaterMode", player_token.in_water)
                shader.set_int("u_WaterPass", 1)
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

            # 2b. A prévia do /schem (holograma translúcido), depois do que é opaco
            mark("underground_pass")
            shader.set_int("u_WaterPass", 0)
            schematic_tool.draw(shader, model, window.time, solids=False)
            if cursor_state["hidden"] and not pan_state["active"] and cursor_in_use():
                # a profundidade do que está sob o mouse (terreno e construções, já cortados): o hover do próximo
                # quadro começa nela
                depth_probe.read(window.get_cursor_pos_framebuffer(), window.width, window.height,
                                 projection @ view @ model, scale=scene_target.scale if scene_target.active else 1.0)
            else:
                depth_probe.clear()
            mark("structures_draw")

            if map_world is None:
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
            if wireframe:
                gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
            shader.set_int("u_DebugView", 0)
            gl.glDisable(gl.GL_BLEND)
            shader.set_int("u_WaterPass", 0)
            shader.set_float("u_SightActive", 0.0)
            room_renderer.disable(shader)
            shadow_renderer.disable(shader)
            shader.set_bool("u_WorldStyle", False)

            # 3. Grade tática: um draw GL_LINES, mesmas matrizes do terreno.
            grid_renderer.fog = (ambience.fog / 100.0,
                                 tuple((model @ np.array([float(v) for v in player_token.position] + [1.0]))[:3]))
            grid_renderer.render(projection, view, model)
            mark("grid_draw")
            if presenting() and presentation.slide.scene.chunk_outline and selection_box is not None:
                # slide "Voxel e chunk": o contorno do chunk 16³ para onde a câmera olha
                low = tuple(int(math.floor(float(v) / 16.0)) * 16 for v in camera.target)
                selection_box.render(projection, view, model, low, tuple(v + 15 for v in low), (1.0, 0.85, 0.25))

            if construction_panel is not None and construction_panel.is_open and selection_box is not None:
                # a caixa da construção selecionada (amarela) e a do holograma (verde se cabe, vermelha se não)
                chosen = construction_panel.selected
                if chosen is not None:
                    low, high = chosen.bounds()
                    selection_box.render(projection, view, model, low, high, (1.0, 0.85, 0.25))
                preview = schematic_tool.preview
                if preview is not None and construction_panel.cursor is not None:
                    low = tuple(preview.origin)
                    high = (low[0] + preview.schematic.width - 1, low[1] + preview.schematic.height - 1,
                            low[2] + preview.schematic.length - 1)
                    colour = (0.45, 1.0, 0.55) if construction_panel.valid else (1.0, 0.35, 0.30)
                    selection_box.render(projection, view, model, low, high, colour)

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
            if combat.hover is not None:          # em cima de um inimigo: o cursor de ataque, sem destacar o bloco
                from src.interactive.context_cursor import CursorMode
                cursor_mode, hover_hit = CursorMode.ATTACK, None
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
            shader.set_bool("u_WaterMode", player_token.in_water)  # nadando, o personagem leva o tom da água como o resto da cena
            shader.set_int("u_CutawayPass", 0)
            shader.set_mat4("u_Projection", projection)
            shader.set_mat4("u_View", view)
            base_model = model @ player_token.get_model_matrix()
            shader.set_mat4("u_Model", base_model)
            mark("highlight")
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
            shader.set_int("u_TextureAtlas", 0)
            if character_shadows is not None:
                character_shadows.disable(shader)   # o personagem não lê a própria sombra
            player_token.draw(shader=shader, base_model=base_model)
            mark("player_draw")
            if npc_models.bodies:
                npc_models.draw(shader, model, combat)       # os NPCs com o corpo montado no /skin (ou o .glb)
                gl.glEnable(gl.GL_CULL_FACE)                  # o modelo .glb desenha com as duas faces
            if combat.enemies:
                # as miniaturas dos inimigos (e os anéis de alvo, vez e movimento), com a textura branca da miniatura
                shader.set_bool("u_WaterMode", False)
                shader.set_bool("u_Skinned", False)
                shader.set_float("u_Alpha", 1.0)
                shader.set_float("u_Vitiligo", 0.0)
                shader.set_int("u_Underwear", 0)
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, token_tex_id)
                shader.set_int("u_TextureAtlas", 0)
                enemy_renderer.draw(shader, model, combat)
                mark("enemy_draw")
            if cloud_fog is not None and (clouds_on or cloud_fog.field.cover):
                # a névoa de guerra: a manta de nuvens translúcida sobre o que ninguém viu, por último (quem está
                # debaixo da beira rala aparece através dela)
                cloud_fog.field.configure(ambience.war_height, ambience.war_objects)
                cloud_fog.update(ambience.fog_war if clouds_on else 0, float(player_token.position[0]),
                                 float(player_token.position[2]), dt, soft=ambience.war_style == 2)
                cloud_fog.render(projection, view, model, ambience.tint(), window.time,
                                 light=ambience.light_direction(), soft=ambience.war_style == 2,
                                 focus=player_token.position)
                shader.use()
                mark("clouds")
            # a cena vai para a tela; daqui em diante (coordenadas, rótulos, chat, cursor) desenha-se direto nela
            scene_target.finish()

            if coords_on_screen():
                coordinate_overlay.render(window.width, window.height, player_token.position)   # o painel fica ali
                shader.use()

            # 7. A tecla F ao lado do personagem, se há uma porta ou uma escada de mão ao alcance
            # (com uma porta ao alcance sob o cursor, o rótulo vai em cima dela, no cursor de contexto)
            near_door = None if character_editor.is_open else schematic_tool.door_near(player_token.position)
            near_ladder = (not character_editor.is_open and near_door is None and player_token.ladder_grip is None
                           and player_token.ladder_near(voxel_provider) is not None)
            picked_kind, _ = (None, None) if (character_editor.is_open or player_token.ladder_grip is not None
                                              and not chest_session.is_open) else pick_interactable()
            near_chest = picked_kind == "chest"
            if near_chest:
                prompt_label = "Fechar" if chest_session.is_open else "Abrir"
            elif near_door is not None:
                prompt_label = "Fechar" if near_door.is_open else "Abrir"
            else:
                prompt_label = "Escada" if near_ladder else ""
            interact_prompt.letter = interact_key_name()
            interact_prompt.update(
                dt, near_chest or (near_door is not None and hovered_door_in_reach() is None) or near_ladder,
                prompt_label)
            interact_prompt.render(player_token.position, projection @ view @ model, window.width, window.height)
            combat_hud.render(combat, window.width, window.height, projection @ view @ model)
            # o registro da luta vai na caixa do chat, que se estica até a borda do menu de combate
            chat_console.set_combat_log(chat_log_view(combat, combat_hud.menu_left))
            context_cursor.update(dt, cursor_mode)
            shader.use()
            if construction_panel is not None:
                construction_panel.render(window.width, window.height)
            if master_panel is not None and not character_editor.is_open:
                master_panel.render(window.width, window.height)
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

        if scene_target is not None:
            scene_target.finish()   # sem efeito se a cena já foi para a tela
        # Restaurar estados OpenGL (o HUD pode ter deixado outro programa ativo)
        gl.glDisable(gl.GL_BLEND)
        gl.glDepthMask(gl.GL_TRUE)
        shader.use()
        shader.set_bool("u_UndergroundMode", False)
        shader.set_int("u_CutawayPass", 0)

        # --------------------------------------------------------------
        # Renderizar interface 2D do Console de Chat (HUD estilo Minecraft)
        # --------------------------------------------------------------
        mark("hud_prompt")
        if chest_session.dim > 0.001:
            # baú aberto: um véu preto sobre a cena (o chat e o resto da interface ficam por cima dele)
            if chest_dim["quad"] is None:
                from src.rendering.hud_quad import HudQuad
                chest_dim["quad"] = HudQuad()
                chest_dim["quad"].set_image(Image.new("RGBA", (1, 1), (0, 0, 0, 255)))
            chest_dim["quad"].draw(0, 0, window.width, window.height, size=(window.width, window.height),
                                   opacity=chest_session.dim)
        if menus.preferences.data.get('show_fps') and not presenting():   # Configurações > Mostrar FPS
            # sob as coordenadas, quando elas estão na tela (uma linha de 18 pixels mais a folga)
            fps_overlay.render(window.width, window.height,
                               FpsOverlay.MARGIN + (22 if coords_on_screen() else 0))
        character_editor.render(window.width, window.height)
        # com a tela de criação aberta, o chat fica ao lado do painel dela (por cima, tapava os botões do rodapé)
        chat_console.set_left(character_editor_panel_width + 16 if character_editor.is_open
                              else master_panel.right + 16 if master_panel is not None and master_panel.is_open
                              else 16)
        # na apresentação o chat só aparece no slide do combate (o registro da luta faz parte da interface dela)
        if (map_editor is None or chat_console.is_open) and (
                not presenting() or presentation.slide.scene.screen == "combate"):
            chat_console.render(window.width, window.height)
        loading_indicator.render(window.width, window.height)
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

        if presenting():
            draw_presentation()

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
                if gpu_frames:
                    import ctypes
                    rows = []
                    for marks in gpu_frames:
                        stamps = []
                        for name, query in marks:
                            value = ctypes.c_uint64(0)
                            gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(value))
                            stamps.append((name, value.value))
                        rows.append({n: (t - stamps[i - 1][1]) / 1e6 for i, (n, t) in enumerate(stamps) if i})
                    with open(frametimes_path + ".gpu.csv", "w", encoding="utf-8") as handle:
                        handle.write(",".join(names) + chr(10))
                        for row in rows:
                            handle.write(",".join(f"{row.get(n, 0.0):.3f}" for n in names) + chr(10))
            break

        mark("rest_draw")
        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()
        mark("swap")
        frame_limiter.wait(menus.preferences.data["fps_limit"])

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    if terrain_demo and menus.world is not None and (max_frames is None or package_smoke == "create"):
        try:
            save_world()
        except (OSError, ValueError) as error:
            if package_smoke == "create":
                raise
            print(f'[Save] Não foi possível salvar ao fechar: {error}')
    menus.delete()
    character_editor.delete()
    gl.glDeleteTextures(1, [current_texture["id"]])
    gl.glDeleteTextures(1, [token_tex_id])
    chat_console.delete()
    if schematic_tool is not None:
        schematic_tool.on_change = lambda: None   # apagar as malhas ao sair não é tirar as construções do save
        schematic_tool.delete()
    if room_tracker is not None:
        room_tracker.close()
    if room_renderer is not None:
        room_renderer.delete()
    if shadow_renderer is not None:
        shadow_renderer.shutdown()
    if shadow_accum is not None:
        shadow_accum.delete()
    if character_shadows is not None:
        character_shadows.delete()
    if scene_target is not None:
        scene_target.delete()
    if map_editor is not None:
        map_editor.delete()
    if map_world is not None:
        map_world.delete()
    if construction_panel is not None:
        construction_panel.delete()
    if master_panel is not None:
        master_panel.delete()
    fog_war.delete()
    if cloud_fog is not None:
        cloud_fog.delete()
    if selection_box is not None:
        selection_box.delete()
    fps_overlay.delete()
    loading_indicator.delete()
    enemy_renderer.delete()
    npc_models.delete()
    if npc_edit:
        npc_edit["model"].delete()
        if npc_edit["holder"].custom_model is not None:
            npc_edit["holder"].custom_model.delete()
    combat_hud.delete()
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
