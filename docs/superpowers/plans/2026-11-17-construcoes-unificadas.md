# Construções unificadas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um só sistema de construções no `--terrain`: o motor do `/schem` (portas, baús, formas, corte do terreno,
cômodos) com o painel e os controles dos objetos do Rafael (mouse, girar, selecionar, remover qualquer uma, nome,
salvar), e o painel escondido até rodar `/schem`.

**Architecture:** `PlacedStructure`/`StructureLayer` continuam sendo o modelo e a colisão; ganham `rotation` e uma
`entry` (de onde veio, para salvar). Um objeto JSON do Rafael vira `Schematic` (com `tints`) e entra pelo mesmo
caminho de um `.schem`. Um painel novo (`ConstructionPanel`, a partir do `WorldObjectHud`) controla o `SchematicTool`;
o `WorldObjectEditor` sai do jogo.

**Tech Stack:** Python 3.12, numpy, PyOpenGL, GLFW, PIL (painel), pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-construcoes-unificadas-design.md`

## Global Constraints

- Texto visível e comentários em português, no estilo dos arquivos vizinhos.
- Painel fechado: não desenha e não consome tecla, caractere nem clique.
- Teclas do painel (só com ele aberto): P colocar, V selecionar, R girar, N nome, F3 próxima construção, ↑/↓+Enter na
  lista, Del/Backspace remover, Esc fechar; setas e Shift+↑/↓ ajustam o holograma como hoje.
- Subcomandos do chat continuam: `/schem load <nome> [x y z]`, `place`, `cancel`, `remove`, `clear`, `list`, `info`.
- Girar: 1 volta = a mesma de `VoxelObject.rotated_y(1)` (célula do lado leste vai para o lado norte).
- Salvar: no save do mundo (chave `structures`) quando há mundo do menu; senão em
  `saves/mundos/mundo_<seed>.json`, formato `isometricon-structures` versão 2. O formato antigo
  (`isometricon-world-objects` versão 1) é lido e convertido.
- `--map-editor` e `--terrain --map=` não mudam (`map_world.py` continua usando `room_structures.py`).
- Commits: só com o OK do usuário, e só com os arquivos desta tarefa (a pasta tem outras mudanças não commitadas).
- Medir desempenho com o notebook **na tomada**.

## Review Focus

1. Painel fechado com o jogador andando: P, V, R, N, Del e cliques voltam a ser do jogo (hoje P/V do Rafael funcionam
   mesmo "desligado"). → teste na Task 6.
2. Arquivo de origem sumiu ou mudou de nome entre uma sessão e outra: o mundo abre, a construção é pulada com aviso.
   → teste na Task 5.
3. Porta aberta numa construção girada, salva e recarregada: volta aberta e no lugar certo. → teste na Task 5.
4. Trocar de mundo/seed (menu ou tecla R): as construções do anterior somem e as do novo carregam; nenhuma é salva no
   mundo errado. → teste na Task 5 (`restore` limpa antes) e checagem manual na Task 8.
5. Clicar no painel não coloca construção atrás dele. → teste na Task 6.

---

### Task 1: Girar blocos e construções

**Files:**
- Create: `src/world/block_rotation.py`
- Test: `tests/test_block_rotation.py`

**Interfaces:**
- Produces: `rotate_block_name(name: str, turns: int) -> str`;
  `rotate_schematic(schematic: Schematic, turns: int) -> Schematic` (cópia; gira `grid`, `tints` se houver, troca
  `width`↔`length` em voltas ímpares; nomes girados com `rotate_block_name`, calculados uma vez por nome distinto).

- [ ] **Step 1: Testes que falham**

```python
@pytest.mark.parametrize("name,turns,expected", [
    ("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]", 1, "minecraft:oak_stairs[facing=north,half=bottom,shape=straight]"),
    ("minecraft:oak_stairs[facing=east,half=bottom,shape=straight]", 2, "minecraft:oak_stairs[facing=west,half=bottom,shape=straight]"),
    ("minecraft:oak_log[axis=x]", 1, "minecraft:oak_log[axis=z]"),
    ("minecraft:oak_log[axis=y]", 1, "minecraft:oak_log[axis=y]"),
    ("minecraft:oak_sign[rotation=0]", 1, "minecraft:oak_sign[rotation=12]"),
    ("minecraft:oak_fence[east=true,north=false,south=false,west=false]", 1, "minecraft:oak_fence[east=false,north=true,south=false,west=false]"),
    ("minecraft:rail[shape=north_south]", 1, "minecraft:rail[shape=east_west]"),
    ("minecraft:rail[shape=ascending_east]", 1, "minecraft:rail[shape=ascending_north]"),
    ("minecraft:rail[shape=south_east]", 1, "minecraft:rail[shape=north_east]"),
    ("minecraft:oak_door[facing=south,half=lower,hinge=left,open=false]", 1, "minecraft:oak_door[facing=east,half=lower,hinge=left,open=false]"),
    ("minecraft:chest[facing=south,type=left]", 1, "minecraft:chest[facing=east,type=left]"),
    ("minecraft:stone", 3, "minecraft:stone"),
])
def test_rotate_block_name(name, turns, expected): ...

def test_four_turns_is_identity_for_every_name_in_the_shape_showcase(): ...  # showcase_schematic(), todos os nomes
def test_grid_rotation_matches_voxel_object_rotation(): ...  # mesma grade de células ocupadas que VoxelObject.rotated_y, voltas 1..3
def test_block_on_the_east_edge_facing_east_still_faces_its_edge_after_a_turn(): ...  # vai para z=0 com facing=north
def test_tints_rotate_with_the_grid(): ...
```

A ordem das propriedades no nome girado é a mesma do nome original (só os valores mudam).

- [ ] **Step 2:** `pytest tests/test_block_rotation.py -q` → FAIL (módulo não existe).
- [ ] **Step 3: Implementar** em `src/world/block_rotation.py`. Uma volta: `facing` e as propriedades
  `north/east/south/west` (qualquer valor) seguem east→north→west→south→east; `axis` x↔z; `rotation` =
  `(r - 4) % 16`; `shape` de trilho troca cada direção pelo mapa acima e reordena a curva como no Minecraft
  (`north_east`, `north_west`, `south_east`, `south_west`). Grade, com `[y, z, x]`:
  `new = grid[:, :, ::-1].transpose(0, 2, 1)` por volta (o mesmo para `tints[..., :]`).
- [ ] **Step 4:** `pytest tests/test_block_rotation.py -q` → PASS.
- [ ] **Step 5:** commit (com OK): `feat(construcoes): girar blocos e construções em 90°`.

### Task 2: Cor por célula na malha das construções

**Files:**
- Modify: `src/world/structure_mesher.py` (`build_arrays`)
- Test: `tests/test_structure_mesher_tints.py`

**Interfaces:**
- Consumes: `schematic.tints` opcional, `float32 (h, l, w, 3)`, como em `src/editor/room_structures.py`.
- Produces: vértices com a cor da célula nas colunas 8:11 (cubos e caixas de forma); sem `tints`, 1.0 como hoje.

- [ ] **Step 1:** testes: um `Schematic` 2×1×1 de `minecraft:white_concrete` com `tints` vermelho/azul → as faces de
  cada cubo levam a cor da sua célula; sem `tints` todas as cores são 1.0 (igual à malha de antes, byte a byte).
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** em `build_arrays`, ler `tints = getattr(schematic, "tints", None)` e usar `tints[y, z, x]` no lugar
  de `1.0, 1.0, 1.0`; para `box_face_quad`/`quad_vertices`, escrever a cor nas colunas 8:11 do quad devolvido.
- [ ] **Step 4:** `pytest tests/test_structure_mesher_tints.py tests/test_schematic.py tests/test_block_shapes.py -q` → PASS.
- [ ] **Step 5:** commit (com OK).

### Task 3: De onde vem uma construção (biblioteca e entradas)

**Files:**
- Create: `src/world/structure_sources.py`
- Modify: `src/editor/room_structures.py` (extrair `object_schematic`)
- Test: `tests/test_structure_sources.py`

**Interfaces:**
- Produces:
  - `object_schematic(obj: VoxelObject, name: str) -> Schematic` em `room_structures.py` (o miolo de
    `object_structure`, que passa a chamá-la).
  - `Entry = dict`: `{"kind": "schem", "name": str}` | `{"kind": "object", "object": dict, "name": str}` |
    `{"kind": "formas"}`.
  - `library(schematics_dir: str, object_paths: list[str]) -> list[tuple[str, Entry]]` — rótulo e entrada, `.schem`
    primeiro (ordem alfabética), depois `formas`, depois os objetos (nome do arquivo sem `.json`); um JSON inválido
    fica de fora.
  - `entry_for_text(text: str, schematics_dir: str) -> Entry | None` — o que `/schem load <texto>` aceita hoje
    (nome da pasta, caminho `.schem`, `formas|vitrine|shapes`) e também caminho de um `.json` de objeto.
  - `load_entry(entry: Entry, schematics_dir: str) -> Schematic` — levanta `FileNotFoundError`/`ValueError`.
- Consumes: `object_library_paths()` (`src/editor/object_names.py`), `VoxelObject.load/from_dict`,
  `Schematic.load_from_file`, `showcase_schematic()`.

- [ ] **Step 1:** testes: a biblioteca lista `.schem` de uma pasta temporária, `formas` e um objeto JSON; `load_entry`
  de um objeto dá um `Schematic` com as mesmas células ocupadas e `tints` com as cores dos materiais;
  `entry_for_text("formas")` e `entry_for_text("sala-teste")`; `load_entry` de `.schem` sumido levanta
  `FileNotFoundError`. `tests/test_editor_room_structures.py` continua passando.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar. A entrada de objeto guarda o objeto inteiro (`VoxelObject.to_dict()`), como o Rafael já
  guardava: o que foi colocado não muda se o arquivo da biblioteca for editado.
- [ ] **Step 4:** rodar → PASS.
- [ ] **Step 5:** commit (com OK).

### Task 4: Ferramenta — colocar no mouse, girar, selecionar, remover qualquer uma

**Files:**
- Modify: `src/world/structure_layer.py`, `src/interactive/schematic_tool.py`
- Test: `tests/test_schematic_tool.py` (acrescentar)

**Interfaces:**
- Consumes: Task 1 (`rotate_schematic`), Task 3 (`load_entry`, `entry_for_text`).
- Produces:
  - `PlacedStructure` ganha `rotation: int = 0` e `entry: dict | None = None` (depois de `mesh`, com default).
  - `StructureLayer.add(name, schematic, origin, mesh=None, *, rotation=0, entry=None)`,
    `StructureLayer.remove(placed: PlacedStructure) -> bool`,
    `StructureLayer.structure_at(x, y, z) -> PlacedStructure | None` (célula ocupada, a de cima na lista ganha).
  - `Preview` ganha `entry`, `rotation`, e `base: Schematic` (sem giro); `preview.schematic` é sempre a girada.
  - `SchematicTool.load_entry(entry, origin=None) -> tuple[bool, str]`; `load(text, origin)` passa a usar
    `entry_for_text` + `load_entry`.
  - `SchematicTool.rotate_preview() -> None` (gira 90°, refaz a malha, mantém o centro da base no lugar).
  - `SchematicTool.aim(cell: tuple[int, int, int]) -> None` — põe o holograma com o centro da base em cima de `cell`
    (`origin = (cx - width // 2, cy + 1, cz - length // 2)`).
  - `SchematicTool.fits(player_box=None) -> bool` — a prévia não ocupa célula ocupada de outra construção nem a caixa
    do jogador (`player_box = ((x0, y0, z0), (x1, y1, z1))`, em células).
  - `SchematicTool.remove(placed) -> tuple[bool, str]` (chama `on_remove`); `remove_last` passa a usá-lo.
  - `SchematicTool.rotate_placed(placed) -> tuple[bool, str]` — tira, gira em volta do centro da base e põe de volta
    (chama `on_remove` e `on_place`; mantém portas abertas como estavam).
  - `SchematicTool.on_change: Callable[[], None]` — chamado depois de fixar, remover, girar, limpar e abrir/fechar
    porta (quem salva escuta aqui).

- [ ] **Step 1:** testes (com `mesh_factory=lambda s: None`, sem OpenGL): `aim` centraliza uma construção 5×3×7;
  `rotate_preview` troca largura e comprimento e mantém o centro; `fits` falso por cima de outra construção e falso
  na caixa do jogador; `structure_at` acha a construção pela célula; `remove` tira a do meio e chama `on_remove`;
  `rotate_placed` chama `on_remove` com a caixa velha e `on_place` com a nova; `on_change` é chamado uma vez em cada
  operação; `/schem load` de um caminho de objeto JSON abre a prévia.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar. `confirm()` passa `rotation` e `entry` para `layer.add`.
- [ ] **Step 4:** `pytest tests/test_schematic_tool.py tests/test_structure_clearing.py -q` → PASS.
- [ ] **Step 5:** commit (com OK).

### Task 5: Salvar e recarregar

**Files:**
- Create: `src/world/structure_save.py`
- Test: `tests/test_structure_save.py`

**Interfaces:**
- Consumes: Task 3 (`load_entry`), Task 4 (`PlacedStructure.entry/rotation`, `SchematicTool`), `src/world/doors.py`
  (`is_door`, `is_open_door`, `DoorRef`, `toggle_door`).
- Produces:
  - `to_data(layer: StructureLayer) -> list[dict]` — cada item:
    `{"entry": Entry, "name": str, "origin": [x, y, z], "rotation": int, "open_doors": [[x, y, z], ...]}`
    (células locais, já na grade girada, da metade de baixo das portas abertas).
  - `restore(tool: SchematicTool, items: list[dict]) -> list[str]` — limpa o que havia (`tool.clear()`), recoloca
    cada item (carrega, gira, abre as portas, `on_place`) e devolve avisos dos que não deu para carregar.
  - `SeedStore(path)` com `read() -> list[dict]` e `write(items: list[dict]) -> None` (escrita atômica, como
    `WorldObjectStore.save`); `read` aceita o formato novo e converte o antigo do Rafael
    (`objects[*]` → `{"entry": {"kind": "object", "object": ..., "name": ...}, "origin": position, "rotation": ...}`).
  - `seed_store_path(seed: int) -> str` = `saves/mundos/mundo_<seed>.json` na raiz do projeto.

- [ ] **Step 1:** testes: ida e volta de uma `sala-dupla` girada 1 vez com uma porta aberta (volta aberta, mesma
  célula, mesma origem); item com `.schem` que não existe → aviso e os outros carregam; `restore` duas vezes não
  duplica; arquivo no formato antigo do Rafael (montar um com `WorldObjectStore(seed).to_dict()` e um objeto) → um
  item `object` com a posição e a rotação dele; arquivo corrompido → `read()` devolve `[]` e não levanta.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** rodar → PASS.
- [ ] **Step 5:** commit (com OK).

### Task 6: Painel de construções

**Files:**
- Create: `src/interactive/construction_panel.py`
- Test: `tests/test_construction_panel.py`

**Interfaces:**
- Consumes: Task 3 (`library`), Task 4 (`SchematicTool` inteiro).
- Produces: `ConstructionPanel(tool: SchematicTool, library: Callable[[], list[tuple[str, Entry]]], create_gl=True)`
  - `is_open: bool`; `open(entry: Entry | None = None) -> None` (abre em modo `place`; sem entrada e sem prévia,
    pega a primeira da biblioteca); `close() -> None` (cancela a prévia; o que foi fixado fica).
  - `mode: str` em `"place" | "select"`; `selected: PlacedStructure | None`.
  - `handle_key(key, action, mods) -> bool`, `handle_char(codepoint) -> bool`,
    `handle_mouse_button(button, action, shift, mouse_window) -> bool` — **todos devolvem False com o painel fechado**.
  - `update_cursor(hit, player_box) -> None` — `hit` é o `raycast_voxels` do mouse (ou `None`); em `place` com
    `hit.normal == (0, 1, 0)` e bloco que não é água chama `tool.aim(hit.block)`; guarda `valid = tool.fits(...)`.
  - `render(window_width, window_height) -> None` — desenha o painel (o desenho do `WorldObjectHud`, mesmo
    tamanho e lugar: canto superior direito, 440×220) só quando aberto; `contains(x, y, window_width) -> bool`.
  - Botões: Colocar, Selecionar, Construção (abre a lista: ↑/↓, Enter pega), Girar, Remover, Sair.
  - Linhas: modo e construção; contagem e selecionada; cursor e "válida/inválida"; nome [N]; status; ajuda.

- [ ] **Step 1:** testes com `create_gl=False` e uma ferramenta sem OpenGL:
  - fechado: `handle_key` de P, V, R, N, Del, Esc e `handle_mouse_button` devolvem False (Review Focus 1);
  - `open()` e um clique esquerdo com `valid` fixam a construção; com `valid` falso não fixam;
  - clique dentro da área do painel não fixa nada atrás dele (Review Focus 5);
  - R em `place` gira a prévia; V + clique numa célula de uma construção a seleciona; Del a remove;
  - lista: abrir, ↓ duas vezes, Enter → a prévia é a terceira da biblioteca;
  - N, digitar "Casa", Enter → a construção selecionada passa a se chamar "Casa" e `on_change` é chamado;
  - Esc fecha o painel e cancela a prévia.
- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar, movendo o desenho de `WorldObjectHud` para cá (fonte, cores e botões iguais).
- [ ] **Step 4:** rodar → PASS.
- [ ] **Step 5:** commit (com OK).

### Task 7: `/schem` abre o painel

**Files:**
- Modify: `src/interactive/skin_commands.py` (`schem`, `COMMAND_TREE`, texto de uso)
- Test: `tests/test_chat_console.py` (acrescentar)

**Interfaces:**
- Consumes: Task 6 (`ConstructionPanel.open`).
- Produces: `SkinCommandHandler.construction_panel` (atributo, `None` fora do terreno, como `schematic_tool`).
  - `/schem` sem nada → `panel.open()`, mensagem "Painel de construções aberto. Esc fecha.".
  - `/schem load <nome> [x y z]` → `tool.load(...)` como hoje e, se deu certo, `panel.open()` (com a prévia já feita).
  - `/schem list` passa a listar a biblioteca inteira (rótulos).
  - Os outros subcomandos não mudam.

- [ ] **Step 1:** testes: `/schem` abre o painel; `/schem load sala-teste` abre o painel com a prévia;
  `/schem load nada` não abre; `/schem place` continua fixando.
- [ ] **Step 2:** rodar → FAIL. **Step 3:** implementar. **Step 4:** PASS.
- [ ] **Step 5:** commit (com OK).

### Task 8: Ligar no jogo e tirar os objetos do Rafael do jogo

**Files:**
- Modify: `src/main.py`, `docs/EDITOR.md`, `src/editor/README.md`
- Delete: `src/editor/world_objects.py`, `tests/test_editor_world_objects.py` (o que ainda valer vai para os testes das
  Tasks 4–6)
- Test: suíte completa + jogo

**Interfaces:**
- Consumes: Tasks 4–7.

- [ ] **Step 1: `main.py`**
  - criar o `ConstructionPanel` ao lado do `schematic_tool` (só no terreno, sem `--map`); `skin_commands.construction_panel`;
    a biblioteca usa `SCHEMATICS_DIR` e, como objetos, `assets/objects/*.json` + `object_library_paths()` +
    `saves/objeto.json` se existir (a mesma lista que o `WorldObjectEditor._library_paths` montava);
  - `--object=<caminho>`: abrir o painel com essa entrada;
  - teclado/caractere/mouse: o painel no lugar do `world_objects` (mesma posição na ordem, mesmas condições de chat e
    editor de personagem fechados); `schematic_tool.handle_key` continua depois;
  - cursor: onde hoje está `world_objects.update_cursor`, fazer o raio (`screen_to_world_ray` + `raycast_voxels` com
    `voxel_provider`) e chamar `panel.update_cursor(hit, player_box)`; caixa do jogador = células de
    `player_token.position` (largura 0,7, altura 1,8, como `_overlaps_token`);
  - desenho: tirar `world_objects.render_objects/render`; caixa da seleção com `SelectionBoxRenderer` e a cor verde/
    vermelha do Rafael na prévia; `panel.render` no lugar de `world_objects.render_hud`;
  - cômodo: `room_structures = list(schematic_tool.layer.structures)` (+ `map_world` como hoje);
  - `voxel_provider` = `schematic_tool.lookup(world_manager.neighbor_at, …)` em todos os lugares;
  - salvar: `schematic_tool.on_change` grava — no `menus.world["structures"] = to_data(layer)` + `library.save` quando
    há mundo, senão `SeedStore(seed_store_path(seed)).write(...)`; `save_world()` também grava `structures`;
  - carregar: ao iniciar e em `load_world`, `restore(schematic_tool, world.get("structures") or [])` (mundo do menu)
    ou `restore(..., SeedStore(...).read())` (`--terrain` direto); avisos vão para o chat; na troca de seed (R),
    `restore` com o arquivo da seed nova.
- [ ] **Step 2:** apagar `world_objects.py` e o teste dele; `grep -rn "world_objects\|WorldObject" src tests` → nada.
- [ ] **Step 3:** documentação: `docs/EDITOR.md` (seção "objetos no mundo" vira "construções: /schem") e
  `src/editor/README.md` (tirar a linha do `world_objects.py`).
- [ ] **Step 4:** `python -m pytest -q -p no:cacheprovider` → tudo passa.
- [ ] **Step 5: no jogo (na tomada)** `python src/main.py --terrain --seed=4242`:
  - sem `/schem` não há painel; P/V/R não fazem nada de construção;
  - `/schem` → painel; escolher `sala-dupla`, colocar com o mouse, girar, abrir a porta; fechar e abrir o jogo → a
    casa volta girada com a porta aberta;
  - `--object=assets/objects/casa_exemplo.json`: comparar com o mesmo objeto no `--map-editor` (cores e texturas);
  - selecionar e remover a casa; o terreno volta;
  - medir como na otimização anterior (`--frames=3000 --keys="400-1600:W"`) com uma casa colocada: sem queda.
- [ ] **Step 6:** commit (com OK).

---

## Fora deste plano

Inventário do baú, edição de blocos dentro da construção, desfazer/refazer no jogo, miniaturas na lista.
