"""Ponto de entrada principal do Isometricon (OpenGL 3.3 Core Profile)."""

import os
import random
import sys

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

    os.environ.setdefault("SHIM_MCCOMPAT", "0x800000001")

    # --- NVIDIA Optimus ---
    try:
        _nv = ctypes.WinDLL("nvapi64.dll")
        _NvOptimusEnablement = ctypes.c_ulong(0x00000001)
    except OSError:
        pass

    # --- AMD PowerXpress ---
    try:
        _amd = ctypes.WinDLL("amdxx64.dll")
        _AmdPowerXpressRequestHighPerformance = ctypes.c_int(0x00000001)
    except OSError:
        try:
            _amd = ctypes.WinDLL("atiadlxx.dll")
            _AmdPowerXpressRequestHighPerformance = ctypes.c_int(0x00000001)
        except OSError:
            pass


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
from src.interactive import BlockHighlightRenderer, GridOverlayRenderer, PlayerToken
from src.math import mat4_identity, mat4_scale, mat4_translate, vec3
from src.rendering import Shader, TexturedMesh, TextureAtlas
from src.world import (
    BlockType,
    Chunk3D,
    ChunkMesher,
    TerrainGenerator,
    WorldManager,
)


def setup_opengl_state() -> None:
    """Configura o pipeline fixo inicial e estados de profundidade e culling."""
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glDepthFunc(gl.GL_LESS)

    gl.glEnable(gl.GL_CULL_FACE)
    gl.glCullFace(gl.GL_BACK)
    gl.glFrontFace(gl.GL_CCW)

    gl.glClearColor(0.08, 0.10, 0.13, 1.0)


def load_texture(texture_path: str) -> int:
    """Carrega uma textura a partir de um arquivo e retorna o ID da textura OpenGL."""
    img = Image.open(texture_path).convert("RGBA")
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img_data = img.tobytes()

    tex_id = gl.glGenTextures(1)
    gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)

    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_WRAP_S,
        gl.GL_REPEAT,
    )
    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_WRAP_T,
        gl.GL_REPEAT,
    )
    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_MIN_FILTER,
        gl.GL_NEAREST,
    )
    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_MAG_FILTER,
        gl.GL_NEAREST,
    )

    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA,
        img.width,
        img.height,
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        img_data,
    )

    return tex_id


def create_cube_mesh() -> TexturedMesh:
    """Cria uma malha 3D de cubo unitário centralizado para testes de renderização."""
    vertices = np.array(
        [
            # Face Topo (+Y)
            -0.5,
            0.5,
            0.5,
            0.0,
            1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            0.5,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            -0.5,
            0.0,
            1.0,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            0.5,
            -0.5,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,

            # Face Frontal (+Z)
            -0.5,
            -0.5,
            0.5,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            -0.5,
            0.5,
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            0.5,
            0.5,
            0.0,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,

            # Face Direita (+X)
            0.5,
            -0.5,
            0.5,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            -0.5,
            -0.5,
            1.0,
            0.0,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            -0.5,
            1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            0.5,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,

            # Face Traseira (-Z)
            0.5,
            -0.5,
            -0.5,
            0.0,
            0.0,
            -1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            -0.5,
            -0.5,
            0.0,
            0.0,
            -1.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            0.5,
            -0.5,
            0.0,
            0.0,
            -1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            -0.5,
            0.0,
            0.0,
            -1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,

            # Face Esquerda (-X)
            -0.5,
            -0.5,
            -0.5,
            -1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            -0.5,
            0.5,
            -1.0,
            0.0,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            0.5,
            0.5,
            -1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            0.5,
            -0.5,
            -1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,

            # Face Fundo (-Y)
            -0.5,
            -0.5,
            -0.5,
            0.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            -0.5,
            -0.5,
            0.0,
            -1.0,
            0.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.5,
            -0.5,
            0.5,
            0.0,
            -1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            -0.5,
            -0.5,
            0.5,
            0.0,
            -1.0,
            0.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
        ],
        dtype=np.float32,
    )

    indices = np.array(
        [
            0,
            1,
            2,
            2,
            3,
            0,
            4,
            5,
            6,
            6,
            7,
            4,
            8,
            9,
            10,
            10,
            11,
            8,
            12,
            13,
            14,
            14,
            15,
            12,
            16,
            17,
            18,
            18,
            19,
            16,
            20,
            21,
            22,
            22,
            23,
            20,
        ],
        dtype=np.uint32,
    )

    return TexturedMesh(vertices, indices)


def create_terrain_meshes(
    seed: int = 0,
) -> list[tuple[TexturedMesh, np.ndarray]]:
    """Demonstração finita 2x2 com cavernas 3D, culling entre vizinhos e sem WorldManager."""
    chunks = TerrainGenerator(
        seed=seed,
        enable_caves=True,
    ).generate_region(
        (x, 0, z)
        for x in (-1, 0)
        for z in (-1, 0)
    )

    def neighbor_at(x: int, y: int, z: int) -> BlockType:
        size = Chunk3D.SIZE
        chunk = chunks.get(
            (
                x // size,
                y // size,
                z // size,
            )
        )

        if chunk is None:
            return BlockType.AIR

        return chunk.get_block(
            *chunk.world_to_local(x, y, z)
        )

    meshes = []

    try:
        for chunk in chunks.values():
            data = ChunkMesher().build(
                chunk,
                neighbor_at,
            )

            mesh = TexturedMesh(
                data.vertices,
                data.indices,
            )

            transform = mat4_scale(
                0.2,
                0.2,
                0.2,
            ) @ mat4_translate(
                *chunk.local_to_world(0, 0, 0)
            )

            meshes.append(
                (
                    mesh,
                    transform,
                )
            )

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
    print(
        "⌨️  [Q/E] Rotacionar | [G] Grid | [Mouse Wheel] Zoom | "
        "[Espaço + Arrastar / MMB] Pan | [ESC] Sair\n"
    )


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

    shader = Shader(
        shader_vert,
        shader_frag,
    )

    terrain_demo = "--terrain" in sys.argv[1:]

    custom_seed = None

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--seed" and i + 1 < len(sys.argv[1:]):
            try:
                custom_seed = int(
                    sys.argv[1:][i + 1]
                )
            except ValueError:
                pass

        elif arg.startswith("--seed="):
            try:
                custom_seed = int(
                    arg.split("=", 1)[1]
                )
            except ValueError:
                pass

    active_seed = {
        "value": (
            custom_seed
            if custom_seed is not None
            else random.randint(1, 999_999)
        )
    }

    if terrain_demo:
        print(
            f"[Terrain] Modo terreno ativo. "
            f"Seed inicial: {active_seed['value']} "
            f"(WASD para andar, [R] nova seed)"
        )

        atlas = TextureAtlas()

        generator = TerrainGenerator(
            seed=active_seed["value"],
            enable_caves=True,
        )

        world_manager = WorldManager(
            generator=generator,
            render_distance=2,
            atlas=atlas,
        )

        start_surface_y = generator.get_height(
            0,
            0,
        )

        player_token = PlayerToken(
            start_x=0.5,
            start_z=0.5,
            speed=5.0,
        )

        player_token.position[1] = (
            float(start_surface_y) + 1.0
        )

        world_manager.load_initial_region(
            player_token.position[0],
            player_token.position[2],
        )

        voxel_provider = VoxelGridProvider(
            block_lookup=world_manager.neighbor_at
        )

        highlight_renderer = BlockHighlightRenderer()
        grid_renderer = GridOverlayRenderer()
        meshes = []

    else:
        atlas = None
        world_manager = None
        player_token = None
        voxel_provider = None
        highlight_renderer = None
        grid_renderer = None

        meshes = [
            (
                create_cube_mesh(),
                mat4_identity(),
            )
        ]

    # Carregar lista de texturas PNG de assets
    textures_dir = os.path.join(
        PROJECT_ROOT,
        "assets",
        "textures",
        "blocks",
    )

    all_pngs = [
        f
        for f in os.listdir(textures_dir)
        if f.lower().endswith(".png")
    ]

    # Exclui itens conhecidos que não são blocos sólidos
    non_solid_keywords = (
        "door",
        "trapdoor",
        "torch",
        "flower",
        "sapling",
        "pane",
        "glass",
        "leaves",
        "rail",
        "chain",
        "lantern",
        "vine",
        "bush",
        "wire",
        "lever",
        "button",
        "crop",
        "stem",
        "roots",
        "fungus",
        "coral",
        "fan",
        "dust",
        "redstone",
        "candle",
        "bars",
        "ladder",
        "sprout",
        "lichen",
        "egg",
    )

    png_files = [
        f
        for f in all_pngs
        if not any(
            keyword in f
            for keyword in non_solid_keywords
        )
    ]

    if not png_files:
        png_files = all_pngs

    initial_png = (
        "white_concrete.png"
        if terrain_demo
        else random.choice(png_files)
    )

    current_texture = {
        "id": load_texture(
            os.path.join(
                textures_dir,
                initial_png,
            )
        ),
        "name": initial_png,
    }

    # Textura sólida 1x1 branca para a miniatura
    white_pixel = np.array(
        [255, 255, 255, 255],
        dtype=np.uint8,
    )

    token_tex_id = gl.glGenTextures(1)

    gl.glBindTexture(
        gl.GL_TEXTURE_2D,
        token_tex_id,
    )

    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_MIN_FILTER,
        gl.GL_NEAREST,
    )

    gl.glTexParameteri(
        gl.GL_TEXTURE_2D,
        gl.GL_TEXTURE_MAG_FILTER,
        gl.GL_NEAREST,
    )

    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA,
        1,
        1,
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        white_pixel,
    )

    texture_timer = 0.0
    TEXTURE_CHANGE_INTERVAL = 0.5

    # ------------------------------------------------------------------
    # 4. Inicializar câmera isométrica
    # ------------------------------------------------------------------
    camera = IsometricCamera(
        target=(
            vec3(
                0.5,
                float(start_surface_y) + 1.0,
                0.5,
            )
            if terrain_demo
            else vec3(
                0.0,
                0.0,
                0.0,
            )
        ),
        ortho_size=(
            4.5
            if terrain_demo
            else 2.0
        ),
        near=0.1,
        far=400.0,
    )

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
    ) -> None:
        """Encaminha eventos de teclado para a câmera e registra teclas ativas."""
        del scancode, mods

        keys_pressed[key] = (
            action != glfw.RELEASE
        )

        if terrain_demo and key == glfw.KEY_R and action == glfw.PRESS:
            new_seed = random.randint(
                1,
                999_999,
            )

            active_seed["value"] = new_seed

            print(
                f"[Terrain] Regenerando mundo... "
                f"Nova Seed: {new_seed}"
            )

            world_manager.delete()

            world_manager.generator = TerrainGenerator(
                seed=new_seed,
                enable_caves=True,
            )

            new_surface = world_manager.get_height(
                player_token.position[0],
                player_token.position[2],
            )

            player_token.position[1] = (
                float(new_surface) + 1.0
            )

            player_token.vertical_velocity = 0.0
            player_token.grounded = True

            world_manager.load_initial_region(
                player_token.position[0],
                player_token.position[2],
            )

        if terrain_demo and key == glfw.KEY_G and action == glfw.PRESS:
            visible = grid_renderer.toggle_visibility()

            print(
                f"[Grid] {'Ativado' if visible else 'Desativado'}."
            )

        if key == glfw.KEY_LEFT_SHIFT:
            pan_state["shift_pressed"] = (
                action != glfw.RELEASE
            )

            if (
                action == glfw.RELEASE
                and not window.is_mouse_button_pressed(
                    glfw.MOUSE_BUTTON_MIDDLE
                )
            ):
                pan_state["active"] = False

        camera.handle_key(
            key,
            action,
        )

    def handle_mouse_button(
        button: int,
        action: int,
        mods: int,
    ) -> None:
        """Controla o início e fim do pan com o botão central."""
        del mods

        is_middle = (
            button == glfw.MOUSE_BUTTON_MIDDLE
        )

        is_left_with_shift = (
            button == glfw.MOUSE_BUTTON_LEFT
            and window.is_key_pressed(
                glfw.KEY_LEFT_SHIFT
            )
        )

        if action == glfw.PRESS:

            if is_middle or is_left_with_shift:
                pan_state["active"] = True
                picking_state["hover_hit"] = None

                x, y = window.get_cursor_pos()

                pan_state["last_x"] = x
                pan_state["last_y"] = y

            elif (
                terrain_demo
                and button == glfw.MOUSE_BUTTON_LEFT
            ):
                picking_state["click_pending"] = True

        elif action == glfw.RELEASE:

            if button in (
                glfw.MOUSE_BUTTON_MIDDLE,
                glfw.MOUSE_BUTTON_LEFT,
            ):
                pan_state["active"] = False

    def handle_cursor_position(
        x: float,
        y: float,
    ) -> None:
        """Move o ponto focal enquanto o botão central estiver pressionado."""
        if (
            pan_state["active"]
            and not window.is_mouse_button_pressed(
                glfw.MOUSE_BUTTON_MIDDLE
            )
        ):
            if not window.is_key_pressed(
                glfw.KEY_LEFT_SHIFT
            ):
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

    # Controles do modo de visualização subterrânea.
    shader.set_bool(
        "u_UndergroundMode",
        False,
    )

    shader.set_float(
        "u_PlayerY",
        0.0,
    )

    shader.set_float(
        "u_CutawayAlpha",
        0.16,
    )

    shader.set_int(
        "u_CutawayPass",
        0,
    )

    # ------------------------------------------------------------------
    # 7. Game Loop de Renderização
    # ------------------------------------------------------------------
    title_update_timer = 0.25

    while not window.should_close():

        dt = window.update_delta_time()

        camera.update(dt)

        if terrain_demo:

            # ----------------------------------------------------------
            # 1. Movimentação do token com colisão voxel e gravidade
            # ----------------------------------------------------------
            movement_forward, movement_right = (
                camera.get_movement_directions()
            )

            player_token.update(
                dt,
                keys_pressed,
                movement_forward,
                movement_right,
                voxel_provider,
            )

            # ----------------------------------------------------------
            # 2. Atualização contínua do streaming dos chunks
            # ----------------------------------------------------------
            world_manager.update(
                player_token.position[0],
                player_token.position[2],
            )

            grid_revision = (
                world_manager.get_loaded_chunk_revision()
            )

            if (
                not world_manager.has_pending_streaming_work()
                and grid_renderer.should_sync(grid_revision)
            ):
                revision, loaded_chunks = (
                    world_manager.get_loaded_chunks_snapshot()
                )

                grid_renderer.sync_chunks(
                    loaded_chunks,
                    revision,
                )

            # ----------------------------------------------------------
            # 3. Câmera acompanha o personagem
            # ----------------------------------------------------------
            if not pan_state["active"]:

                cam_speed = 8.0
                cam_vertical_speed = 14.0

                camera.target[0] += (
                    player_token.position[0]
                    - camera.target[0]
                ) * min(
                    dt * cam_speed,
                    1.0,
                )

                camera.target[2] += (
                    player_token.position[2]
                    - camera.target[2]
                ) * min(
                    dt * cam_speed,
                    1.0,
                )

                camera.target[1] += (
                    player_token.position[1]
                    - camera.target[1]
                ) * min(
                    dt * cam_vertical_speed,
                    1.0,
                )

        else:

            texture_timer += dt

            if texture_timer >= TEXTURE_CHANGE_INTERVAL:

                texture_timer = 0.0

                random_png = random.choice(
                    png_files
                )

                gl.glDeleteTextures(
                    1,
                    [current_texture["id"]],
                )

                current_texture["id"] = load_texture(
                    os.path.join(
                        textures_dir,
                        random_png,
                    )
                )

                current_texture["name"] = random_png

        # --------------------------------------------------------------
        # Atualizar título da janela
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

            seed_badge = (
                f"Seed: {active_seed['value']} "
                f"(WASD: mover | [R]: reload) | "
                if terrain_demo
                else ""
            )

            window.set_title(
                f"Isometricon {version_info.full_version} | "
                f"{sync_badge} | "
                f"{seed_badge}"
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

        # --------------------------------------------------------------
        # Picking / Hover
        # --------------------------------------------------------------
        if terrain_demo and not pan_state["active"]:

            mouse_x, mouse_y = (
                window.get_cursor_pos_framebuffer()
            )

            mouse_ray = screen_to_world_ray(
                mouse_x,
                mouse_y,
                window.width,
                window.height,
                view,
                projection,
                model,
            )

            picking_state["hover_hit"] = (
                raycast_voxels(
                    mouse_ray,
                    voxel_provider,
                )
            )

            if picking_state["click_pending"]:

                picking_state["clicked_hit"] = (
                    picking_state["hover_hit"]
                )

                clicked_hit = (
                    picking_state["clicked_hit"]
                )

                if clicked_hit is None:

                    print(
                        "[Picking] Clique sem bloco atingido."
                    )

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

        gl.glActiveTexture(
            gl.GL_TEXTURE0
        )

        gl.glBindTexture(
            gl.GL_TEXTURE_2D,
            current_texture["id"],
        )

        shader.set_int(
            "u_TextureAtlas",
            0,
        )

        if terrain_demo:

            # ----------------------------------------------------------
            # Determinar modo subterrâneo
            # ----------------------------------------------------------
            surface_y = world_manager.get_height(
                player_token.position[0],
                player_token.position[2],
            )

            underground_mode = (
                player_token.position[1]
                < float(surface_y) + 0.25
            )

            shader.use()

            shader.set_bool(
                "u_UndergroundMode",
                underground_mode,
            )

            shader.set_float(
                "u_PlayerY",
                float(player_token.position[1]),
            )

            shader.set_float(
                "u_CutawayAlpha",
                0.16,
            )

            shader.set_int(
                "u_CutawayPass",
                0,
            )

            # ----------------------------------------------------------
            # 1. Primeiro passe:
            # terreno abaixo do jogador completamente opaco.
            # ----------------------------------------------------------
            gl.glActiveTexture(
                gl.GL_TEXTURE0
            )

            gl.glBindTexture(
                gl.GL_TEXTURE_2D,
                atlas.texture_id,
            )

            shader.set_int(
                "u_TextureAtlas",
                0,
            )

            view_projection = (
                projection @ view
            )

            shader.set_int(
                "u_CutawayPass",
                0,
            )

            gl.glDisable(
                gl.GL_BLEND
            )

            gl.glDepthMask(
                gl.GL_TRUE
            )

            world_manager.render(
                shader,
                model,
                view_projection,
            )

            # ----------------------------------------------------------
            # 2. Segundo passe:
            # terreno acima do jogador translúcido.
            # ----------------------------------------------------------
            if underground_mode:

                gl.glEnable(
                    gl.GL_BLEND
                )

                gl.glBlendFunc(
                    gl.GL_SRC_ALPHA,
                    gl.GL_ONE_MINUS_SRC_ALPHA,
                )

                gl.glDepthMask(
                    gl.GL_FALSE
                )

                shader.set_int(
                    "u_CutawayPass",
                    1,
                )

                world_manager.render(
                    shader,
                    model,
                    view_projection,
                )

                gl.glDepthMask(
                    gl.GL_TRUE
                )

                gl.glDisable(
                    gl.GL_BLEND
                )

                shader.set_int(
                    "u_CutawayPass",
                    0,
                )

            # ----------------------------------------------------------
            # 3. Grade tática
            # ----------------------------------------------------------
            grid_renderer.render(
                projection,
                view,
                model,
            )

            # ----------------------------------------------------------
            # 4. Highlight do bloco atual do jogador
            # ----------------------------------------------------------
            bx, by, bz = (
                player_token.get_current_block()
            )

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

            # ----------------------------------------------------------
            # 5. Highlight do bloco sob o cursor
            # ----------------------------------------------------------
            hover_hit = (
                picking_state["hover_hit"]
            )

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
                    base_color=(
                        1.0,
                        0.72,
                        0.18,
                    ),
                )

            # ----------------------------------------------------------
            # 6. Renderizar miniatura
            # ----------------------------------------------------------
            shader.use()

            # A miniatura não deve herdar o cutaway do terreno.
            shader.set_bool(
                "u_UndergroundMode",
                False,
            )

            shader.set_int(
                "u_CutawayPass",
                0,
            )

            shader.set_mat4(
                "u_Projection",
                projection,
            )

            shader.set_mat4(
                "u_View",
                view,
            )

            base_model = (
                model
                @ player_token.get_model_matrix()
            )

            shader.set_mat4(
                "u_Model",
                base_model,
            )

            gl.glActiveTexture(
                gl.GL_TEXTURE0
            )

            gl.glBindTexture(
                gl.GL_TEXTURE_2D,
                token_tex_id,
            )

            shader.set_int(
                "u_TextureAtlas",
                0,
            )

            player_token.draw(
                shader=shader,
                base_model=base_model,
            )

        else:

            gl.glActiveTexture(
                gl.GL_TEXTURE0
            )

            gl.glBindTexture(
                gl.GL_TEXTURE_2D,
                current_texture["id"],
            )

            shader.set_int(
                "u_TextureAtlas",
                0,
            )

            for mesh, transform in meshes:

                shader.set_mat4(
                    "u_Model",
                    model @ transform,
                )

                mesh.draw()

        # --------------------------------------------------------------
        # Restaurar estados OpenGL
        # --------------------------------------------------------------
        gl.glDisable(
            gl.GL_BLEND
        )

        gl.glDepthMask(
            gl.GL_TRUE
        )

        shader.set_bool(
            "u_UndergroundMode",
            False,
        )

        shader.set_int(
            "u_CutawayPass",
            0,
        )

        # --------------------------------------------------------------
        # Apresentar frame
        # --------------------------------------------------------------
        window.swap_buffers()

    # ------------------------------------------------------------------
    # 8. Liberar recursos
    # ------------------------------------------------------------------
    gl.glDeleteTextures(
        1,
        [current_texture["id"]],
    )

    gl.glDeleteTextures(
        1,
        [token_tex_id],
    )

    if terrain_demo:

        if atlas is not None:
            atlas.delete()

        world_manager.delete()
        player_token.delete()
        highlight_renderer.delete()
        grid_renderer.delete()

    else:

        for mesh, _ in meshes:
            mesh.delete()

    shader.delete()
    window.close()

    print(
        "Aplicação encerrada com sucesso."
    )


if __name__ == "__main__":
    main()
