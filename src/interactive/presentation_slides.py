"""Os slides do modo apresentação (``--apresentacao``): os cartões de cada um e o que a cena de fundo faz.

Só dados: ``presentation.py`` navega por eles, ``presentation_card.py`` desenha os cartões e o ``main.py``
traduz a ``SceneCue`` em câmera e estado do OpenGL. Cada slide é um ou mais cartões (``Panel``) posicionados em
frações da tela, para variar a composição: coluna à esquerda ou à direita, faixa embaixo, cartões nos cantos.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SceneCue:
    """O que a cena de fundo faz enquanto o slide está na tela (tempos em segundos desde a entrada nele)."""
    spin: float = 0.0                  # graus/s de yaw contínuo
    yaw_steps: float = 0.0             # >0: o yaw anda 45° a cada ``yaw_steps`` s
    zoom: tuple[float, float, float] | None = None   # (de, até, segundos), em fator do ortho_size de partida
    wobble: float = 0.0                # amplitude relativa da oscilação do ortho_size (período de 6 s)
    perspective_every: float = 0.0     # >0: alterna ortográfica/perspectiva a cada N s
    wireframe: bool = False
    views: tuple[int, ...] = ()        # ciclo de u_DebugView, 3 s cada (0 normal, 1 só textura, 2 só luz)
    chunk_outline: bool = False
    counters: tuple[str, ...] = ()     # dados ao vivo que os gráficos usam: "faces", "chunks"


@dataclass(frozen=True)
class Block:
    """Um trecho de cartão. ``kind``: text, subtitle, bullets, formula, pipeline, prompt, heightmap,
    bars (gráfico ao vivo: content = ("faces",) ou ("chunks",)), vertex (os 44 bytes de um vértice)."""
    kind: str
    content: tuple[str, ...] = ()


@dataclass(frozen=True)
class Panel:
    """Um cartão. ``box``: (x, y, largura, altura máxima) em frações da tela; ele encolhe até o conteúdo,
    preso em cima, embaixo ou no meio da caixa (``anchor``)."""
    box: tuple[float, float, float, float]
    blocks: tuple[Block, ...]
    title: str = ""
    big: bool = False          # título grande (o do slide) ou de cartão
    align: str = "left"        # "left" ou "center"
    anchor: str = "top"        # "top", "bottom" ou "middle"

    @property
    def live(self) -> bool:
        return any(block.kind == "bars" for block in self.blocks)


@dataclass(frozen=True)
class Slide:
    title: str
    panels: tuple[Panel, ...]
    scene: SceneCue = SceneCue()
    steps: int = 1   # passos internos (o pipeline acende uma caixa por toque)


def _t(*lines: str) -> Block:
    return Block("text", lines)


def _b(*lines: str) -> Block:
    return Block("bullets", lines)


def _f(*lines: str) -> Block:
    return Block("formula", lines)


def _sub(text: str) -> Block:
    return Block("subtitle", (text,))


# Composições usadas pelos slides
def center(title: str, *blocks: Block) -> Panel:
    return Panel((0.20, 0.06, 0.60, 0.88), blocks, title, big=True, align="center", anchor="middle")


def right(title: str, *blocks: Block) -> Panel:
    return Panel((0.56, 0.04, 0.42, 0.86), blocks, title, big=True)


def left(title: str, *blocks: Block) -> Panel:
    return Panel((0.02, 0.04, 0.42, 0.86), blocks, title, big=True)


def bottom(title: str, *blocks: Block) -> Panel:
    return Panel((0.04, 0.40, 0.92, 0.52), blocks, title, big=True, anchor="bottom")


def corner(where: str, title: str, *blocks: Block, width: float = 0.32, big: bool = False) -> Panel:
    """Um cartão num canto: ``where`` em "tl", "tr", "bl", "br"."""
    x = 0.02 if where[1] == "l" else 0.98 - width
    if where[0] == "t":
        return Panel((x, 0.04, width, 0.43), blocks, title, big=big)
    return Panel((x, 0.49, width, 0.43), blocks, title, big=big, anchor="bottom")


PIPELINE_STAGES = (
    "Terreno procedural",
    "Chunks de voxels",
    "Malha das faces visíveis",
    "VAO / VBO / EBO",
    "Shaders e framebuffer",
)

SLIDES: tuple[Slide, ...] = (
    Slide(
        "Isometricon: do voxel à imagem na tela",
        (center(
            "Isometricon: do voxel à imagem na tela",
            _sub("Modelagem 3D, câmera virtual e pipeline gráfico"),
            _t("Henrique de Freitas Araujo", "João Pedro Rodrigues Silva", "Pedro Augusto Gontijo Moura"),
            _t("Computação Gráfica — CEFET-MG Divinópolis — 2026"),
        ),),
        SceneCue(spin=6.0),
    ),
    Slide(
        "O que vamos demonstrar",
        (
            left(
                "O que vamos demonstrar",
                _b("Uma grade de voxels vira um ambiente 3D em tempo real",
                   "Como os dados do terreno são gerados",
                   "Como a geometria desnecessária é descartada",
                   "A divisão de trabalho entre CPU, OpenGL e shaders",
                   "A câmera e as matrizes de transformação"),
                _t("Recorte: modelagem e renderização básicas."),
            ),
            corner("br", "Pergunta central",
                   _t("Como sair de milhares de células discretas para uma cena 3D coerente "
                      "sem desenhar todos os lados de todos os cubos?"), width=0.34),
        ),
        SceneCue(zoom=(1.0, 1.8, 20.0)),
    ),
    Slide(
        "Ferramentas",
        (
            corner("tl", "Ferramentas",
                   _b("Python e NumPy", "GLFW (janela e entrada)", "PyOpenGL e GLSL 330 core",
                      "Pillow (atlas de texturas)", "pytest (testes automatizados)"), big=True, width=0.30),
            corner("tr", "IA generativa", _b("GitHub Copilot", "Claude Code", "ChatGPT Codex"), width=0.26),
            corner("br", "Colaboração", _b("GitHub: repositório, branches e pull requests"), width=0.30),
        ),
        SceneCue(spin=3.0),
    ),
    Slide(
        "Pipeline",
        (bottom(
            "Pipeline",
            Block("pipeline", PIPELINE_STAGES),
            _t("CPU: gera o terreno, guarda os voxels e monta a malha. "
               "GPU: recebe os buffers e executa os shaders até o framebuffer."),
        ),),
        SceneCue(spin=2.0),
        steps=5,
    ),
    Slide(
        "Voxel e chunk",
        (
            right(
                "Voxel e chunk",
                _b("Chunk de 16 × 16 × 16 voxels",
                   "1 byte (uint8) por voxel: 16³ = 4096 bytes por chunk",
                   "Índice linear: x + 16·(y + 16·z)"),
                _sub("Tipos básicos"),
                _t("AIR, DIRT, GRASS, STONE, WATER, WOOD, LEAVES"),
            ),
            corner("bl", "Hoje",
                   _t("São 18 tipos: plantas, tocha, escadas e fogo têm forma própria "
                      "e geram a sua geometria à parte."), width=0.30),
        ),
        SceneCue(spin=2.0, chunk_outline=True),
    ),
    Slide(
        "Geração procedural",
        (left(
            "Geração procedural",
            _b("Value Noise 2D (não é Perlin): valores pseudoaleatórios nos pontos da grade",
               "Interpolação com fade quíntica: 6t⁵ − 15t⁴ + 10t³",
               "Soma de oitavas (frequência ×λ, peso ×p a cada oitava)"),
            _f("N(x,z) = Σ pⁱ·n(f·λⁱ·(x,z)) / Σ pⁱ"),
            Block("heightmap", ("1 oitava", "2 oitavas", "3 oitavas")),
            _t("A mesma seed reproduz o mesmo mundo."),
        ),),
        SceneCue(spin=2.0),
    ),
    Slide(
        "Face culling na CPU",
        (
            corner("tl", "Face culling na CPU",
                   _b("O ChunkMesher olha os 6 vizinhos de cada voxel: ±X, ±Y, ±Z",
                      "Vizinho opaco esconde a face: ela nem vira geometria",
                      "Só DIRT, GRASS, STONE e WOOD ocultam faces",
                      "WATER, LEAVES e os blocos com forma geram geometria, mas não ocultam"),
                   big=True, width=0.40),
            corner("br", "Faces nos chunks carregados", Block("bars", ("faces",)),
                   _t("Ao fundo: a malha em wireframe, só com as faces que sobraram."), width=0.36),
        ),
        SceneCue(spin=2.0, wireframe=True, counters=("faces",)),
    ),
    Slide(
        "Da malha aos shaders",
        (
            corner("tr", "Da malha aos shaders",
                   _b("Quad = 4 vértices e 6 índices (dois triângulos)",
                      "VAO / VBO / EBO; world_textured.vert / .frag"),
                   Block("vertex", ("Vértice: posição 3 + normal 3 + UV 2 + cor 3 = 11 floats = 44 B",)),
                   big=True, width=0.42),
            corner("bl", "Iluminação",
                   _f("C_final = (C_amb + d·C_luz) ⊙ (C_textura ⊙ C_base)"),
                   _t("d: Half-Lambert ao quadrado na superfície, Lambert no subsolo.",
                      "Hoje também: sombras do sol por raio e oclusão de ambiente por vértice.",
                      "Ao fundo: normal → só textura → só iluminação."),
                   width=0.42),
        ),
        SceneCue(spin=2.0, views=(0, 1, 2)),
    ),
    Slide(
        "Câmera",
        (left(
            "Câmera",
            _f("p_clip = P·V·M·p_local", "M = T·R·S"),
            _b("V: look-at do olho para o alvo",
               "P: projeção ortográfica (há também um modo perspectiva)",
               "Yaw 45°, pitch 35,264° = asen(tan 30°)",
               "Pan move o alvo; zoom altera ortho_size"),
            _t("Ao fundo: giros de 45°, zoom e ortográfica ↔ perspectiva."),
        ),),
        SceneCue(yaw_steps=2.0, wobble=0.35, perspective_every=8.0),
    ),
    Slide(
        "Outras otimizações",
        (
            corner("tl", "Z-buffer", _t("Por pixel, o fragmento mais próximo vence; a ordem de desenho não importa "
                                       "para o que é opaco."), width=0.30),
            corner("tr", "Back-face culling", _t("A GPU descarta os triângulos de costas para a câmera "
                                                "(GL_CULL_FACE)."), width=0.30),
            corner("bl", "Frustum culling", _t("O chunk sai se os 8 cantos estão fora de um mesmo plano."),
                   Block("bars", ("chunks",)), width=0.34),
            corner("br", "Processamento assíncrono", _t("Terreno e malha numa thread; a GPU recebe 1 chunk "
                                                        "por quadro."), width=0.30),
        ),
        SceneCue(zoom=(1.0, 3.0, 6.0), counters=("chunks",)),
    ),
    Slide(
        "IA como apoio",
        (
            corner("tl", "IA como apoio",
                   Block("prompt", ("Analise src/world/terrain.py e explique qual ruído o terreno usa de verdade: "
                                    "é Perlin ou outro? Mostre as linhas que provam.",)),
                   big=True, width=0.40),
            corner("br", "",
                   Block("prompt", ("Explique como P·V·M é montado em src/camera/camera.py e usado em "
                                    "assets/shaders/world_textured.vert, passo a passo.",)),
                   _t("A IA acelera a leitura do código; a conferência é nossa."), width=0.40),
        ),
        SceneCue(spin=3.0),
    ),
    Slide(
        "Conclusão",
        (bottom(
            "Conclusão",
            _b("Voxels em chunks dão uma representação compacta e fácil de editar",
               "Descartar faces escondidas na CPU reduz muito o que vai para a GPU",
               "Shaders e matrizes transformam a malha na imagem final",
               "Câmera ortográfica isométrica com pan e zoom"),
        ),),
        SceneCue(spin=4.0),
    ),
    Slide(
        "Fontes",
        (center(
            "Fontes",
            _sub("github.com/Ak4ai/Isometricon"),
            _b("src/world/terrain.py", "src/world/chunk.py", "src/world/mesher.py", "src/rendering/mesh.py",
               "src/camera/camera.py", "assets/shaders/world_textured.vert",
               "assets/shaders/world_textured.frag", "src/world/manager.py"),
            _sub("Obrigado!"),
        ),),
        SceneCue(zoom=(1.0, 2.5, 12.0), spin=3.0),
    ),
)
