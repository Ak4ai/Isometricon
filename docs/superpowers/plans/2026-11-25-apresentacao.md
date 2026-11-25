# Modo apresentação — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python src/main.py --terrain --apresentacao` mostra os 13 slides da disciplina como cartões de pergaminho por cima do terreno ao vivo, com a cena de cada slide (giro, zoom, wireframe, modos do shader, contadores).

**Architecture:** Dados e navegação em módulos puros (`presentation_slides.py`, `presentation.py`); o cartão é uma imagem PIL (`presentation_card.py`); o `main.py` só traduz o estado da apresentação em câmera/GL e desenha o cartão com `HudQuad`.

**Tech Stack:** Python, Pillow, NumPy, PyOpenGL/GLFW, GLSL 330, pytest.

**Spec:** `docs/superpowers/specs/2026-11-25-apresentacao-design.md`

## Global Constraints

- Textos, comentários e commits em português.
- Sem `--apresentacao` o jogo se comporta exatamente como antes; `python -m pytest -q` continua verde.
- Não commitar `assets/textures/blocks/*` nem assets da Mojang; nada de `git stash` sem tag, `reset --hard` ou push.
- A fonte do Minecraft (`default_font()`) pode ser `None`; o cartão nunca depende dela.
- Fórmulas em Unicode (Σ, ⊙, λ, ·, ±, ×, ≈, →) numa TTF que tenha os glifos: `C:/Windows/Fonts/cambria.ttc`, depois `seguisym.ttf`/`segoeui.ttf`, depois `ImageFont.load_default(size)`.

## Review Focus

- Janela redimensionada no meio da apresentação: o cartão é refeito no novo tamanho (cache chaveado pelo tamanho), sem esticar.
- Janela muito pequena (ex. 640×360): o texto encolhe/quebra linha e não vaza do cartão.
- Esc sai do modo e devolve câmera (yaw, ortho_size, perspectiva), `glPolygonMode(GL_FILL)` e `u_DebugView = 0`; o jogo segue jogável.
- Teclas consumidas pela apresentação (setas, espaço, PageUp/Down, Home/End, H, Esc) não movem o jogador nem abrem menus; as demais seguem para o jogo.
- Mundo ainda carregando (0 chunks): contadores mostram "0 de 0" sem dividir por zero.

---

### Task 1: Slides e navegação (puro)

**Files:**
- Create: `src/interactive/presentation_slides.py`, `src/interactive/presentation.py`
- Test: `tests/test_presentation.py`

**Interfaces — produz:**
```python
# presentation_slides.py
@dataclass(frozen=True)
class SceneCue:
    spin: float = 0.0                  # graus/s de yaw contínuo
    yaw_steps: float = 0.0             # >0: yaw anda 45° a cada `yaw_steps` s (slide 9)
    zoom: tuple[float, float, float] | None = None   # (de, até, segundos) em fator do ortho_size base
    wobble: float = 0.0                # amplitude relativa do ortho_size, período 6 s
    perspective_every: float = 0.0     # >0: alterna ortográfica/perspectiva a cada N s
    wireframe: bool = False
    views: tuple[int, ...] = ()        # ciclo de u_DebugView, 3 s cada (0 normal, 1 só textura, 2 só luz)
    chunk_outline: bool = False
    counters: tuple[str, ...] = ()     # "faces", "chunks"
    layout: str = "right"              # "center" (capa, obrigado) ou "right"

@dataclass(frozen=True)
class Block:
    kind: str        # "text", "bullets", "formula", "pipeline", "prompt", "heightmap", "subtitle"
    content: tuple[str, ...]

@dataclass(frozen=True)
class Slide:
    title: str
    blocks: tuple[Block, ...]
    scene: SceneCue
    steps: int = 1   # passos internos; o pipeline usa 5

SLIDES: tuple[Slide, ...]   # os 13, na ordem do spec

# presentation.py
@dataclass(frozen=True)
class CameraTargets:
    yaw_degrees: float; ortho_size: float; perspective: bool; debug_view: int; wireframe: bool

class Presentation:
    def __init__(self, slides=SLIDES, start: int = 0) -> None
    index: int; step: int; card_visible: bool; active: bool; elapsed: float  # s desde a entrada no slide
    slide -> Slide (property)
    def next(self) -> None      # avança passo; no último passo, vai ao slide seguinte (step 0); para no fim
    def prev(self) -> None      # volta passo; no passo 0, vai ao slide anterior no seu último passo; para no início
    def first(self) -> None; def last(self) -> None
    def update(self, dt: float) -> None
    def key(self, key: int, action: int) -> bool   # usa constantes glfw; só PRESS/REPEAT; True = consumida
    def camera_targets(self, base_yaw: float, base_ortho: float) -> CameraTargets
```

Trocar de slide zera `elapsed`. `key`: RIGHT/SPACE/PAGE_DOWN → next; LEFT/PAGE_UP → prev; HOME/END; H → alterna `card_visible`; ESCAPE → `active = False`. Com `active == False`, `key` devolve False sempre.
`camera_targets`: yaw = base + spin·t, ou base + 45·floor(t/yaw_steps); ortho = base·fator, onde fator interpola `zoom` linear por `smoothstep` até os segundos e depois fica, multiplicado por `1 + wobble·sin(2πt/6)`; perspective = `floor(t/perspective_every)` ímpar; debug_view = `views[floor(t/3) % len]` ou 0.

Textos: os do spec/pedido, com acentos ("Ferramentas", "Geração procedural", "Câmera", "Conclusão", "Obrigado!"); capa com os três autores, "CEFET-MG Divinópolis — 2026"; fórmulas `N(x,z) = Σ pⁱ·n(f·λⁱ·(x,z)) / Σ pⁱ`, `C_final = (C_amb + d·C_luz) ⊙ (C_textura ⊙ C_base)`, `p_clip = P·V·M·p_local`, `M = T·R·S`, `11 floats = 44 B`; as linhas a mais do spec ("Ajustes de conteúdo"). Cenas exatamente como a tabela do spec (slide 4: `steps=5`; 6: bloco `heightmap`; 7: `wireframe=True, counters=("faces",)`; 8: `views=(0,1,2)`; 9: `yaw_steps=2.0, wobble=0.35, perspective_every=8.0`; 10: `zoom=(1.0, 3.0, 6.0), counters=("chunks",)`; 1 e 13: `layout="center"`).

- [ ] **Step 1: Testes que falham** — em `tests/test_presentation.py`:
  - `test_treze_slides_com_titulos_acentuados`: `len(SLIDES) == 13`; títulos contêm "Isometricon", "Ferramentas", "Geração procedural", "Face culling", "Câmera", "Conclusão"; o último bloco do slide 13 contém "Obrigado!".
  - `test_formulas_preservadas`: o texto de todos os blocos junto contém "Σ", "⊙", "P·V·M", "44 B", "4096", "35,264°".
  - `test_next_prev_limites`: `p.prev()` no início fica em 0; `last()` e `next()` ficam em 12.
  - `test_pipeline_avanca_por_passos`: no slide 4 (índice 3), quatro `next()` mantêm `index == 3` com `step == 4`; o quinto vai a `(4, 0)`; `prev()` volta a `(3, 4)`.
  - `test_teclas_consumidas`: RIGHT/SPACE/PAGE_DOWN avançam e devolvem True; RELEASE devolve False e não move; `KEY_W` devolve False; H alterna `card_visible`; ESCAPE põe `active=False` e depois RIGHT devolve False.
  - `test_elapsed_zera_ao_trocar`: `update(5)`, `next()` → `elapsed == 0`.
  - `test_alvos_camera`: slide 9 com `elapsed=4.1` → yaw `base+90`; slide 10 com `elapsed≥6` → ortho `3×base`; slide 8 com `elapsed=3.5` → `debug_view == 1`; slide 7 → `wireframe` True; slide 3 → `debug_view == 0`, `perspective` False.
- [ ] **Step 2:** `python -m pytest tests/test_presentation.py -q` → falha por import.
- [ ] **Step 3:** implementar os dois módulos.
- [ ] **Step 4:** `python -m pytest tests/test_presentation.py -q` → passa.
- [ ] **Step 5:** commit `feat(apresentacao): slides e navegação do modo apresentação`.

### Task 2: Cartão PIL e mapa de altura

**Files:**
- Create: `src/interactive/presentation_card.py`
- Test: `tests/test_presentation_card.py`

**Interfaces — consome:** `Slide`, `Block` (Task 1); `menu_style.panel(image, bounds)`; `default_font()`; `make_generator(seed, None, vegetation=False)` de `src/world/terrain_options.py`.
**Produz:**
```python
def card_bounds(layout: str, width: int, height: int) -> tuple[int, int, int, int]
    # "center": 62% × 56% centrado; "right": 44% da largura, margem 32 px, altura toda menos 96 px (rodapé)
def render_card(slide: Slide, step: int, width: int, height: int) -> Image.Image   # RGBA width×height, fundo transparente
def render_footer(index: int, total: int, counters: dict[str, tuple[int, int]], width: int) -> Image.Image
    # "7/13" à esquerda; "faces desenhadas: X de Y", "chunks desenhados: X de Y" à direita
def heightmap_strip(seed: int, octaves: tuple[int, ...] = (1, 2, 3), size: int = 96) -> Image.Image
    # três mapas lado a lado (mesmas cores de menu_style.seed_map), legenda "1 oitava", "2 oitavas", "3 oitavas"
```
Medida do texto proporcional a `height` (título ≈ height/18, corpo ≈ height/34, mínimo 12 px); quebra de linha por largura com `ImageDraw.textlength`; se o conteúdo não couber, reduz o corpo em passos de 10% até caber. Bloco `pipeline`: 5 caixas em coluna com setas, as de índice ≤ `step` em cor viva, as demais esmaecidas, rótulo "CPU" nas 3 primeiras e "GPU" nas 2 últimas. `render_card` com cache `lru_cache` por `(id do slide, step, width, height)`.
`heightmap_strip` usa o gerador com `octaves` trocado (`dataclasses.replace`).

- [ ] **Step 1: Testes que falham:**
  - `test_cartao_tem_tamanho_da_janela`: para cada slide de `SLIDES`, `render_card(s, 0, 1280, 720).size == (1280, 720)` e o pixel do centro de `card_bounds` tem alfa 255.
  - `test_cartao_janela_pequena`: `render_card(SLIDES[7], 0, 640, 360)` não lança e o canto (2, 2) tem alfa 0 para layout "right".
  - `test_bounds_center_e_right`: `card_bounds("center", 1000, 800)` centrado; `card_bounds("right", 1000, 800)[2] == 1000 - 32`.
  - `test_pipeline_muda_com_passo`: `render_card(SLIDES[3], 0, …)` ≠ `render_card(SLIDES[3], 4, …)` (bytes diferentes).
  - `test_heightmap_oitavas_diferem`: `heightmap_strip(1234)` tem largura ≥ 3×96 e as três regiões diferem.
  - `test_rodape_zero_de_zero`: `render_footer(0, 13, {"faces": (0, 0)}, 800)` não lança.
  - `test_sem_fontes_do_windows` (monkeypatch da lista de TTFs para caminhos inexistentes e `default_font` → None): `render_card` ainda devolve imagem.
- [ ] **Step 2:** rodar → falha por import.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** `python -m pytest tests/test_presentation_card.py -q` → passa. Salvar `render_card` dos 13 slides em PNG no scratchpad e olhar.
- [ ] **Step 5:** commit `feat(apresentacao): cartão de pergaminho e mapa de altura por oitavas`.

### Task 3: Contadores e modo de visualização do shader

**Files:**
- Modify: `src/interactive/presentation.py` (função pura de contagem)
- Modify: `assets/shaders/world_textured.frag` (uniform `u_DebugView`)
- Test: `tests/test_presentation.py`

**Produz:**
```python
def face_stats(chunk_blocks: Iterable[np.ndarray], mesh_index_counts: Iterable[int]) -> tuple[int, int]
    # (faces desenhadas = Σ index_count // 6, possíveis = 6 × Σ count_nonzero(CUBE_LUT[blocks]))
```
Shader: `uniform int u_DebugView = 0;` — no fim do `main()`, no ramo normal e no da água: 1 → `FragColor = vec4(albedo, alpha)`; 2 → `FragColor = vec4(lighting * vec3(0.8), alpha)`. Valor 0 não muda nada.

- [ ] **Step 1:** teste `test_face_stats`: um chunk 16³ todo STONE e malha com `index_count = 6·16·16·6` → `(1536, 24576)`; listas vazias → `(0, 0)`.
- [ ] **Step 2:** rodar → falha. **Step 3:** implementar + shader. **Step 4:** passa.
- [ ] **Step 5:** commit `feat(apresentacao): contagem de faces e modo de visualização no shader`.

### Task 4: Integração no `main.py`

**Files:** Modify: `src/main.py`

**Consome:** `Presentation`, `CameraTargets`, `face_stats` (Tasks 1, 3); `render_card`, `render_footer`, `card_bounds` (Task 2); `HudQuad`; `BlockHighlightRenderer` ou linhas GL para o contorno.

- Argumentos: `--apresentacao` (implica `--terrain`) e `--slide=N` (1..13, início; para capturas).
- Criar `Presentation` depois do mundo carregar; guardar yaw/ortho_size/perspectiva base para restaurar.
- Primeiro callback de tecla registrado (antes de `handle_camera_key`): se `presentation.key(...)` → `return True`. Ao sair (`active` vira False), restaurar câmera, `GL_FILL`, `u_DebugView = 0`, mostrar HUD.
- Por quadro, com `active`: `update(dt)`; aplicar `camera_targets` com suavização exponencial (`k = 1 - exp(-6·dt)`) no yaw e ortho_size; `camera.perspective` direto; `glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)` em volta das chamadas `world_manager.render` quando `wireframe`; `shader.set_int("u_DebugView", …)` antes do mundo; contorno do chunk sob `camera.target` quando `chunk_outline`.
- Contadores: `chunks` = (valor devolvido pelo `world_manager.render` do quadro, `len(world_manager.meshes)`); `faces` = `face_stats` recalculado no máximo 1×/s.
- HUD: com a apresentação ativa, não desenhar FPS, coordenadas, chat, cursor de contexto nem indicador de carga; desenhar o cartão (se `card_visible`) e o rodapé com dois `HudQuad`, trocando a imagem só quando (slide, passo, tamanho, contadores) mudam.

- [ ] **Step 1:** implementar.
- [ ] **Step 2:** para N em 1..13: `python src/main.py --apresentacao --slide=N --frames 240 --screenshot <scratchpad>/slide_N.png`; olhar cada PNG (cartão legível, cena conforme a tabela; 7 em wireframe; 8 em um dos modos).
- [ ] **Step 3:** rodar manualmente: avançar/voltar com setas e espaço, H, Esc (jogo volta ao normal), redimensionar a janela.
- [ ] **Step 4:** commit `feat(apresentacao): modo --apresentacao com o jogo ao fundo`.

### Task 5: Fechamento

- [ ] `python -m pytest -q` → tudo passa.
- [ ] Atualizar `README.md` (seção de uso) com `--apresentacao`, `--slide=N` e as teclas.
- [ ] Commit `docs: como usar o modo apresentação`. Sem push.
