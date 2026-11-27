"""Os slides do modo apresentação (``--apresentacao``): os cartões de cada um e o que a cena de fundo faz.

O professor pediu que a apresentação mostre *onde* cada recurso de computação gráfica é usado no projeto, sem
explicar a teoria. Por isso cada slide é uma parte do jogo: o que ela faz, em poucas linhas, e uma fileira de
etiquetas (``tags``) com os recursos de CG usados ali, enquanto a cena de fundo mostra essa parte.

Só dados: ``presentation.py`` navega por eles, ``presentation_card.py`` desenha os cartões e o ``main.py``
traduz a ``SceneCue`` em câmera e estado do OpenGL. Cada slide é um ou mais cartões (``Panel``) posicionados em
frações da tela: coluna à esquerda ou à direita, faixa embaixo, cartões nos cantos.
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
    # a tela do jogo aberta por trás, para quem apresenta mexer com o mouse: "editor" (criação do personagem),
    # "mestre" (painel do /mestre) ou "combate" (uma luta de verdade, com o chat do registro)
    screen: str = ""
    # aonde o personagem vai, um lugar por passo do slide (ver src/interactive/presentation_places.py)
    places: tuple[str, ...] = ()
    # o bioma do terreno de fundo ("deserto", "taiga"); vazio é a planície (src/world/terrain_options.BIOMES)
    biome: str = ""


@dataclass(frozen=True)
class Block:
    """Um trecho de cartão. ``kind``: text, subtitle, bullets, formula, pipeline, prompt, heightmap,
    tags (etiquetas dos recursos de CG), bars (gráfico ao vivo: content = ("faces",) ou ("chunks",)),
    vertex (os 44 bytes de um vértice), code (linhas em fonte fixa), places (os lugares do slide; o do passo
    atual em destaque)."""
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


def cg(*resources: str) -> Block:
    """As etiquetas dos recursos de computação gráfica usados na parte do slide."""
    return Block("tags", resources)


# Composições usadas pelos slides
def center(title: str, *blocks: Block) -> Panel:
    return Panel((0.20, 0.06, 0.60, 0.88), blocks, title, big=True, align="center", anchor="middle")


def right(title: str, *blocks: Block) -> Panel:
    return Panel((0.56, 0.04, 0.42, 0.86), blocks, title, big=True)


def left(title: str, *blocks: Block) -> Panel:
    return Panel((0.02, 0.04, 0.42, 0.86), blocks, title, big=True)


def side(where: str, title: str, *blocks: Block, width: float = 0.30) -> Panel:
    """Uma coluna estreita na borda ``where`` ("l" ou "r"): sobra espaço para a tela do jogo aberta por trás."""
    x = 0.02 if where == "l" else 0.98 - width
    return Panel((x, 0.04, width, 0.86), blocks, title, big=True)


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
    "Buffers gráficos",
    "Shaders e framebuffer",
)

SLIDES: tuple[Slide, ...] = (
    Slide(
        "Isometricon: do voxel à imagem na tela",
        (center(
            "Isometricon: do voxel à imagem na tela",
            _sub("Onde usamos computação gráfica num RPG de mesa em voxels"),
            _t("Henrique de Freitas Araujo", "João Pedro Rodrigues Silva", "Pedro Augusto Gontijo Moura"),
            _t("Computação Gráfica — CEFET-MG Divinópolis — 2026"),
        ),),
        SceneCue(spin=6.0),
    ),
    Slide(
        "O projeto",
        (
            left(
                "O projeto",
                _t("Um RPG de mesa virtual em 3D, com visão isométrica e mundo de blocos. "
                   "Ao fundo, o próprio jogo em execução."),
                _b("Mundo procedural com biomas, cavernas e vegetação",
                   "Personagens personalizáveis, roupas e animações",
                   "NPCs e combate por turnos",
                   "Construções, editor de mapas e objetos interativos",
                   "Ambientação: hora do dia, neblina e névoa de guerra"),
            ),
            corner("br", "Nesta apresentação",
                   _t("Cada slide é uma parte do jogo; as etiquetas dizem quais recursos de "
                      "computação gráfica foram usados ali."), width=0.34),
        ),
        SceneCue(zoom=(1.0, 1.8, 20.0)),
    ),
    Slide(
        "Ferramentas",
        (
            corner("tl", "Ferramentas",
                   _b("Python e NumPy: lógica e cálculos", "GLFW: janela e entrada",
                      "PyOpenGL e GLSL: renderização e shaders", "Pillow: texturas e interface",
                      "Blender: modelagem e preparação de personagens", "pytest: testes automatizados"), big=True, width=0.32),
            corner("tr", "IA generativa",
                   _b("GitHub Copilot", "Claude Code", "ChatGPT Codex"),
                   _t("Apoio na implementação, investigação, testes e revisão; a conferência é nossa."), width=0.30),
            corner("br", "Colaboração", _b("GitHub: repositório, branches, pull requests e wiki"), width=0.32),
        ),
        SceneCue(spin=3.0),
    ),
    Slide(
        "Pipeline gráfico",
        (bottom(
            "Pipeline gráfico",
            Block("pipeline", PIPELINE_STAGES),
            _t("CPU: gera o terreno e constrói as malhas. GPU: processa os dados geométricos e executa os shaders para formar a imagem."),
            cg("Pipeline programável", "VAO / VBO / EBO", "GLSL 330 core", "Framebuffer próprio"),
        ),),
        SceneCue(spin=2.0),
        steps=5,
    ),
    Slide(
        "Mundo: modelagem",
        (
            left(
                "Mundo: modelagem",
                _b("Mundo 3D de voxels, dividido em chunks de 16 × 16 × 16 blocos",
                   "Relevo procedural: Value Noise 2D, interpolação quíntica e 3 oitavas",
                   "Seeds reproduzem o mundo gerado",
                   "Biomas de planície, deserto e taiga, com cavernas, água e vegetação"),
                Block("heightmap", ("1 oitava", "2 oitavas", "3 oitavas")),
                cg("Modelagem por voxels", "Geração procedural", "Ruído e interpolação"),
            ),
        ),
        SceneCue(spin=2.0, chunk_outline=True, biome="deserto"),
    ),
    Slide(
        "Mundo: malha e texturas",
        (
            right("Mundo: malha e texturas",
                   _b("Malhas poligonais representam as superfícies dos blocos",
                      "Face culling elimina faces internas para reduzir a geometria",
                      "Atlas de texturas e coordenadas UV definem a aparência das faces",
                      "Oclusão de ambiente por vértice escurece cantos e encontros"),
                   cg("Malha poligonal", "Face culling", "Mapeamento de textura", "Oclusão de ambiente")),
            corner("bl", "Faces nos chunks carregados", Block("bars", ("faces",)),
                   _t("Ao fundo: a malha em wireframe."), width=0.34),
        ),
        SceneCue(spin=2.0, wireframe=True, counters=("faces",)),
    ),
    Slide(
        "Blocos: modelos e sombras",
        (
            side(
                "r",
                "Blocos: modelos e sombras",
                _b("Blocos têm formas geométricas variadas, como lajes e escadas",
                   "Modelos são compostos por caixas tridimensionais",
                   "Texturas são mapeadas às dimensões de cada modelo",
                   "Ray marching produz sombras que consideram a geometria dos blocos"),
                cg("Modelagem por caixas", "Mapeamento de textura", "Ray marching", "Sombras"),
                _t("Ao fundo, a vitrine de teste: uma amostra de cada forma de bloco."),
                width=0.34,
            ),
        ),
        SceneCue(zoom=(1.0, 0.75, 3.0), places=("formas",)),
    ),
    Slide(
        "Câmera e transformações",
        (
            right(
                "Câmera e transformações",
                _f("p_clip = P·V·M·p_local", "M = T·R·S"),
                _b("**Projeção ortográfica e perspectiva** — a cena alterna as duas · *Aula 18*",
                   "**Look-at** — isométrica: yaw 45°, pitch 35,264° (arctan 1/√2) · *Aula 19*",
                   "**Translação, escala e rotação** — pan, zoom e Q/E · *Aulas 9 a 12*",
                   "**Composição de matrizes** — o giro é em volta do alvo, não da origem · *Aula 14*",
                   "**Interpolação** — Q/E giram 90° de forma suave",
                   "**Frustum culling** — chunk fora da visão não é desenhado · *Assarsson e Möller, 2000*"),
                cg("Projeção ortográfica", "Perspectiva", "Look-at", "Rotação", "Translação",
                   "Escala", "Interpolação", "Frustum culling"),
            ),
        ),
        SceneCue(yaw_steps=2.0, wobble=0.35, perspective_every=8.0),
    ),
    Slide(
        "Iluminação e sombras",
        (
            right("Iluminação e sombras",
                   _f("C_final = (C_amb + d·C_luz) ⊙ (C_textura ⊙ C_base)"),
                   _b("**Modelo de iluminação** — ambiente + difusa nos blocos (sem especular) · *Aula 26, Phong*",
                      "**Half-Lambert** — difusa suavizada · *Mitchell et al., Valve, 2006*",
                      "**Luz direcional (w = 0)** — o sol; a hora do dia move e muda a cor · *Aula 26*",
                      "**Ray marching** — sombra do terreno, com penumbra (slide seguinte)",
                      "**Shadow mapping** — sombra dos personagens vista do sol; dobra no degrau e sobe na "
                      "parede (a sombra planar da aula só cai no plano) · *Williams, 1978*"),
                   cg("Iluminação difusa", "Luz direcional", "Ray marching", "Shadow mapping",
                      "Textura 3D"),
                   _t("No painel do /mestre, à esquerda: arraste a hora do dia e veja o sol, a cor da luz e as "
                      "sombras mudarem. A cena alterna normal → só textura → só iluminação.")),
        ),
        SceneCue(spin=2.0, views=(0, 0, 1, 2), screen="mestre", biome="taiga"),
    ),
    Slide(
        "Sombra do sol: raios e penumbra",
        (
            right(
                "Sombra do sol: raios e penumbra",
                _b("**DDA de voxels** — raio do pixel até o sol, bloco a bloco, numa textura 3D · "
                   "*Amanatides e Woo, 1987*; parente do traçado de reta da *Aula 5*",
                   "**Luz de área por amostragem** — cone de 12 raios borrados e 6 nítidos · "
                   "*Aula 26, sombra suave*; *Cook et al., 1984*",
                   "**Interleaved gradient noise** — gira o cone a cada pixel · *Jimenez, 2014*",
                   "**Mapa de horizonte e salto de espaço vazio** — pulam o ar livre",
                   "Perto do bloco vale a borda nítida; longe dele, a borrada"),
                cg("Ray marching", "Sombras suaves", "Textura 3D", "Amostragem estocástica"),
                _t("Cada ajuste é uma opção em Configurações > Gráficos: qualidade, alcance do raio, "
                   "distância das sombras e o granulado da penumbra."),
            ),
        ),
        SceneCue(spin=2.0, biome="taiga"),
    ),
    Slide(
        "Sombra do sol: acumulação",
        (
            right(
                "Sombra do sol: acumulação",
                _b("O mundo quase não muda entre quadros: refazer 18 raios por pixel a cada um é desperdício",
                   "**Reprojeção temporal** — acha o mesmo ponto no quadro anterior pela matriz P·V antiga · "
                   "*Nehab et al., 2007*",
                   "**Acúmulo de amostras** — 5 raios novos por quadro, média de ~16 quadros",
                   "**Framebuffer próprio** — guarda o histórico da sombra numa textura",
                   "**Pré-passada de profundidade (Z-buffer)** — só o fragmento da frente paga os raios · "
                   "*Catmull, 1974*"),
                cg("Reprojeção temporal", "Acúmulo de amostras", "Framebuffer próprio", "Z-buffer"),
                _t("Na taiga, numa RTX 3050: de 24,6 para 10 ms na passada de cor (40 para 95 fps), com a "
                   "imagem praticamente igual. A sombra acompanha o sol e os blocos em ~1/4 de segundo."),
            ),
        ),
        SceneCue(spin=2.0, biome="taiga"),
    ),
    Slide(
        "Água e névoa",
        (
            right(
                "Água e névoa",
                _b("**Ondas na normal + reflexo do céu** — a superfície da água · *Aula 27, lago*",
                   "**Fresnel** — reflete mais o céu em ângulo raso · *Aula 27*; *Schlick, 1994*",
                   "**Brilho especular** — o sol refletido nas ondas · *Aula 26, Phong*",
                   "**Transparência e blending (canal alfa)** — água translúcida · *Aula 7*",
                   "**Névoa** — de distância, de guerra (nuvens de blocos) e na borda dos chunks",
                   "**Ray marching volumétrico** — neblina do mestre rente ao chão, com feixes de luz "
                   "entre os troncos"),
                cg("Transparência e blending", "Reflexão", "Fresnel", "Névoa", "Ray marching", "Animação"),
                _t("No painel do /mestre: a névoa de guerra (explorado ou em volta) e as cenas prontas."),
            ),
        ),
        SceneCue(spin=3.0, screen="mestre"),
    ),
    Slide(
        "Câmera dentro dos cômodos",
        (
            side(
                "r",
                "Câmera dentro dos cômodos",
                _b("**Flood fill** — acha o ar coberto em volta do personagem",
                   "**Textura 3D** — a máscara do cômodo vai à GPU",
                   "**Cutaway + dither de Bayer 4×4** — teto, andar de cima e terra somem · *Bayer, 1973*",
                   "**Interpolação** — o lado de fora escurece de forma suave"),
                cg("Textura 3D", "Dither", "Recorte (cutaway)", "Interpolação"),
                Block("places", ("Sala de teste (3 andares)", "Caverna do terreno", "Casa medieval")),
                _t("→ leva ao próximo lugar."),
                width=0.30,
            ),
        ),
        SceneCue(zoom=(0.8, 0.8, 1.0), places=("sala-andar", "caverna", "house-medieval")),
        steps=3,
    ),
    Slide(
        "Personagens e animação",
        (
            side(
                "r",
                "Personagens e animação",
                _b("Esqueleto de 16 ossos e skinning por pesos: caminhada e pose de descanso",
                   "Roupas encaixadas por cages e remoção de superfícies escondidas (HSR)",
                   "Modelos glTF (.glb) com esqueleto animado na GPU",
                   "Ajuste fino: escala e rotação de cada osso"),
                cg("Esqueleto e skinning", "Animação", "Hierarquia de transformações", "Rotação",
                   "Escala", "Malhas importadas"),
                _t("Ao fundo, a tela de criação: arraste para girar; W liga a caminhada."),
                width=0.27,
            ),
        ),
        SceneCue(screen="editor"),
    ),
    Slide(
        "Combate por turnos",
        (
            corner("tr", "Combate por turnos",
                   _b("Miniaturas montadas por T·R·S: base, corpo, cabeça e olhos",
                      "Anéis no chão: alvo, vez e o movimento que sobra",
                      "Rastro do caminho e golpe que pisca a peça em vermelho",
                      "Interface da luta desenhada por cima da cena"),
                   cg("Translação", "Rotação", "Escala", "Animação", "Sobreposição 2D", "Picking"),
                   width=0.34, big=True),
        ),
        SceneCue(screen="combate"),
    ),
    Slide(
        "Interação",
        (
            left("Interação",
                   _b("Clique → raio 3D → bloco: picking por DDA na grade de voxels",
                      "Bloco sob o mouse com brilho pulsante",
                      "Grade tática em GL_LINES sobre o relevo",
                      "Portas abrem girando 90° na dobradiça"),
                   cg("Raycasting", "Picking", "Blending aditivo", "Linhas", "Rotação")),
            corner("br", "Ao fundo", _t("O contorno do chunk 16³ sob a câmera."), width=0.28),
        ),
        SceneCue(spin=2.0, chunk_outline=True),
    ),
    Slide(
        "Interface e imagem final",
        (
            bottom(
                "Interface e imagem final",
                _b("A cena vai para um framebuffer próprio: MSAA, FXAA e escala de resolução",
                   "Interface 2D como quads texturizados por cima da cena (estes cartões também)",
                   "Menus com paisagem voxel e prévias do mundo desenhadas de trás para a frente"),
                cg("Render to texture", "Antisserrilhado (MSAA, FXAA)", "Sobreposição 2D",
                   "Algoritmo do pintor"),
            ),
        ),
        SceneCue(spin=4.0),
    ),
    Slide(
        "Otimizações",
        (
            corner("tl", "Na CPU", _t("Face culling, malha numa thread à parte, 1 chunk enviado à GPU "
                                      "por quadro. A distância de render (1 a 6 chunks) carrega e "
                                      "descarrega na hora."), width=0.30),
            corner("tr", "Na GPU", _t("Z-buffer, back-face culling, pré-passada de profundidade e sombra "
                                      "acumulada entre quadros. O mato do chão fica fora da sombra do sol: "
                                      "+15% de fps na taiga."),
                   width=0.30),
            corner("br", "Escolha da placa", _t("Em notebook com duas placas o jogo pede a dedicada ao "
                                                "Windows; dá para trocar em Configurações."),
                   width=0.30),
            corner("bl", "Frustum culling", _t("O chunk sai se os 8 cantos estão fora de um mesmo plano."),
                   Block("bars", ("chunks",)), width=0.34),
        ),
        SceneCue(zoom=(1.0, 3.0, 6.0), counters=("chunks",)),
    ),
    Slide(
        "Conclusão",
        (
            bottom(
                "Conclusão",
                _b("Modelagem: voxels, ruído procedural e malhas importadas",
                   "Transformações: câmera, tabuleiro, personagens e esqueleto",
                   "Iluminação: luz difusa, sombras por raio com penumbra acumulada e por mapa de sombra, água e névoa",
                   "Desempenho: face culling, frustum culling, thread à parte e sombra acumulada"),
                _t("Código, wiki e testes: github.com/Ak4ai/Isometricon"),
                _sub("Obrigado!"),
            ),
        ),
        SceneCue(zoom=(1.0, 2.5, 12.0), spin=3.0),
    ),
)
