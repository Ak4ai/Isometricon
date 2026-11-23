# 🗺️ Editor de mapa e objetos voxel

Modo de autoria do Isometricon: constrói um mapa/objeto voxel em uma plataforma
renderizada por shader e permite exportar o objeto e carimbá-lo em outro mapa.
É um modo **aditivo**: não altera `--terrain`, `--char` nem o editor de personagem.

> **Estado:** implementação na branch `feat/voxel-editor`. Cobre `FR-035` a
> `FR-073` (com biblioteca textual sem miniaturas e base plana em vez de terreno
> procedural). `.vox` (`FR-049`) e geração procedural (`FR-050`) continuam fora
> do escopo.

## ▶️ Como abrir

O editor também pode ser aberto pelo botão **Editor de mapa** no menu inicial.

```bash
# editor vazio (16×16×16)
python src/main.py --map-editor

# abre um mapa/objeto existente no editor
python src/main.py --map=assets/objects/casa_exemplo.json
python src/main.py --map-editor=assets/objects/casa_exemplo.json

# joga um mapa salvo no mundo isométrico (com colisão do token)
python src/main.py --terrain --map=saves/mapa.json
```

O botão **Editor de mapa** do menu abre o editor vazio. `F9` carrega um mapa
salvo. No editor gráfico, `N` e `F2` abrem o mesmo modal de nome/exportação; o
modal mostra o caminho final, avisa quando vai substituir um arquivo e, após
exportar, lembra o caminho `Menu → Nova aventura → /schem → Exportados`. Ao
terminar:

- `F2` exporta o objeto para `saves/objetos/<nome>.json`;
- `F5` salva o mapa em `saves/mapa.json`;
- `F10` ou o botão **Menu** pede confirmação, salva o mapa e volta ao menu;
- `Shift+F10` volta sem salvar;
- `Esc` abre a mesma confirmação.

Depois de voltar, **Nova aventura** cria o mundo e `/schem` já lista o objeto
exportado, sem fechar a aplicação.

O modo também funciona com `--frames`/`--screenshot`, útil para capturas:

```bash
python src/main.py --map-editor=assets/objects/casa_exemplo.json \
  --frames=3 --screenshot=artifacts/editor.png
```

## 🖥️ Layout tipo editor de imagem

O mundo não ocupa mais a janela inteira. Ele é desenhado num canvas delimitado
por uma moldura, à esquerda; ferramentas, ações, cores e texturas ficam numa
barra lateral sólida à direita. O canvas usa um viewport OpenGL próprio, então
a câmera, o raycast, o arrasto e o clique são calculados dentro dele — clicar na
barra lateral não coloca voxels atrás da UI.

A largura da barra e o canvas se ajustam à janela. O painel é rasterizado em 2×
e a moldura/área de desenho acompanham a resolução.

## 🕹️ Controles

| Ação | Controle |
|---|---|
| Aplicar ferramenta | Clique esquerdo |
| Trocar ferramenta (construir → apagar → pintar → carimbar → selecionar) | `Tab` / `Shift+Tab` |
| Escolher cor na roda HSV | clique na roda; barra abaixo ajusta o brilho |
| Escolher cor na paleta/recentes | clique no quadradinho |
| Alternar abas Cores/Texturas | clique nas abas ou `K` |
| Escolher textura pela grade | clique na miniatura |
| Filtrar texturas | Todas / Pedra / Madeira / Concreto / Natureza / Favoritas |
| Buscar textura | `S` ou clique no campo Buscar |
| Favoritar textura atual | `F` |
| Conta-gotas de material | `Alt` + clique no voxel |
| Ligar/desligar luz do material | `L` |
| Objetos de luz padrão | `lampiao`, `lanterna`, `tocha` (biblioteca `F4`) |
| Próxima cor / anterior | `C` / `Shift+C` |
| Cor hexadecimal livre | `H`, digite 6 dígitos, `Enter` |
| Próxima textura / anterior | `X` / `Shift+X` |
| Pincel (1 a 8) | `-` / `=` |
| Espaçamento da grade | `[` / `]` |
| Girar objeto carimbado ou selecionado | `R` |
| Ligar/desligar grade da plataforma | `G` |
| Aumentar / diminuir o volume | `F7` / `F6` |
| Criar piso base plano | `F8` |
| Nomear/exportar objeto (modal) | `N` ou `F2` |
| Exportar pelo modal | digitar nome, `Enter` ou botão Exportar |
| Exportar objeto atual | `F2`/botão Exportar → modal → `saves/objetos/<nome>.json` |
| Carregar próximo objeto da biblioteca | `F3` |
| Abrir/fechar a lista da biblioteca | `F4` |
| Salvar mapa | `F5` |
| Carregar mapa | `F9` |
| Voltar ao menu (salvando o mapa) | `F10` ou botão **Menu**, confirmar com `F10` |
| Voltar ao menu sem salvar | `Shift+F10` |
| Cancelar a saída | `Esc` |
| Mover objeto selecionado | setas; `PageUp`/`PageDown` no Y |
| Duplicar / excluir objeto | `Ctrl+D` / `Delete` |
| Biblioteca: escolher / carimbar | `↑`/`↓` / `Enter` |
| Biblioteca: duplicar / excluir arquivo | `D` / `Delete` (duas vezes) |
| Desfazer / refazer | `Ctrl+Z` / `Ctrl+Y` |
| Rotacionar câmera | `Q` / `E` |
| Zoom | Scroll |
| Pan | Botão do meio ou `Shift` + arrastar |
| Sair | `Esc` |

Construir em altura: aponte para o **topo** ou para a **lateral** de um voxel e
clique; a célula alvo é a vizinha na direção da face atingida. Para pintar ou
apagar, aponte diretamente para o voxel.

## 🔁 Fluxo de trabalho

1. **Criar** o objeto/mapa no volume padrão (16×16×16). `F7`/`F6` mudam o volume.
2. **Material**: use a aba **Cores** (roda HSV, paleta de 16 cores, recentes ou
   `C`/`H`) e a aba **Texturas** (grade de miniaturas reais, ou `X`); a combinação
   é o material do voxel. Cada voxel guarda seu próprio índice de material. A
   cor atual aparece no quadrado do topo e o nome da textura fica no HUD. A grade
   tem filtros por categoria, busca textual (`S`), favoritos (`F`) e o
   conta-gotas (`Alt`+clique) copia cor e textura de um voxel existente.
3. **Nomear** com `N`: o nome interno fica no JSON e vira o nome do arquivo
   (sem acentos/espaços). **Exportar** com `F2`: grava
   `saves/objetos/<nome>.json`.
4. **Carimbar** com `F3`: carrega o próximo JSON de `assets/objects/` ou de
   `saves/objetos/`, ativa a ferramenta de carimbo, e `R` gira em 90°.
5. **Colocar** no mapa com clique esquerdo. Cada carimbo vira uma **construção
   independente** (não é achatado na base).
6. **Selecionar** com `Tab` até `Selecionar`, clicar no objeto: setas movem,
   `R` gira, `Ctrl+D` duplica e `Delete` exclui. A base embaixo é preservada.
7. **Salvar** o mapa com `F5`; reabrir com `F9`, `--map=...` ou jogar com
   `--terrain --map=...`.

Há um exemplo em [`assets/objects/casa_exemplo.json`](../assets/objects/casa_exemplo.json)
(207 voxels, 4 materiais): telhado em duas camadas, paredes de tijolo, janelas,
chaminé e **interior oco com 5×5×4 blocos livres**. As duas faces têm vãos de
porta abertos de 2×3 blocos, então o token consegue entrar e sair.

## 📦 Formato do objeto/mapa

JSON versionado, com identificador de formato:

```json
{
  "format": "isometricon-voxel-object",
  "version": 1,
  "kind": "object",
  "name": "casa_exemplo",
  "size": [7, 7, 7],
  "materials": [
    {"color": [172, 94, 76], "texture": "bricks"}
  ],
  "voxels": [[0, 0, 0, 0], [1, 0, 0, 0]]
}
```

- `blocks` vazio é `-1`; cada voxel referencia `materials[indice]`.
- A gravação é atômica (`.tmp` + `os.replace`).
- Mapas e objetos usam o mesmo formato; `kind` distingue os dois.
- Texturas são nomes de tiles do atlas do editor (`src/editor/material_atlas.py`).

## 🌍 Dois destinos: mapa independente ou mundo procedural

O mesmo objeto pode ser usado de duas formas:

```bash
# A) mapa independente finito
python src/main.py --map-editor
# F5 salva saves/mapa.json
python src/main.py --terrain --map=saves/mapa.json

# B) dentro do mundo procedural infinito
python src/main.py --terrain --object=assets/objects/casa_exemplo.json
```

No mundo procedural os objetos entram pelo **painel de construções**, o mesmo dos
`.schem` (ver `src/interactive/construction_panel.py`). Ele fica escondido até
rodar `/schem` no chat (ou abrir com `--object=...`):

- a lista (`F4` ou o botão **Construção**; `F3` pega a próxima) mistura os `.schem`
  de `assets/schematics/`, a vitrine `formas` e os objetos JSON do editor;
- o holograma segue o mouse no topo do terreno (caixa verde se cabe, vermelha se
  não) e o clique esquerdo fixa; as setas e `Shift`+`↑`/`↓` ajustam bloco a bloco;
- `R` gira (portas, escadas e baús giram junto), `V` ou **Selecionar** escolhe uma
  construção já colocada, `Delete` a remove, `N` dá nome, `Esc` fecha o painel.

Um objeto do editor vira uma construção como um `.schem`: tem colisão, entra na
revelação de cômodo e o terreno da caixa dele é cortado ao fixar. As cores dos
materiais vão junto; a textura de cada material é a do Minecraft com o mesmo nome.

As construções colocadas são salvas: no save do mundo (aberto pelo menu) ou, no
`--terrain` direto, em `saves/mundos/mundo_<seed>.json` (o arquivo antigo dos
objetos é lido e convertido). Uma construção cujo arquivo sumiu é pulada com um
aviso no chat.

Detalhes de requisitos em
[`SRS-INCREMENTO-MUNDO-PROCEDURAL.md`](SRS-INCREMENTO-MUNDO-PROCEDURAL.md).

## 🧱 Objetos independentes e base

A partir desta versão o carimbo **não é mais achatado** na base: ele vira um
`PlacedObject` com posição e rotação próprias. A tecla `F8` cria um piso base
plano; excluir uma construção revela a base que estava embaixo. O mapa salvo
guarda `base` + `objects`, e `--terrain --map=...` reconstrói os dois com
colisão do token.

O painel do editor tem botões clicáveis para ferramentas, salvar/carregar,
exportar, biblioteca, undo/redo, grade e base. A lista da biblioteca (`F4`) ainda
não gera miniaturas voxel; mostra nome e seleção por teclado.

## 📐 HUD adaptativa

O painel do editor usa uma escala lógica que diminui quando a janela é pequena.
A escala é aplicada à imagem e às hitboxes juntas, então clicar em uma miniatura
ou na roda continua funcionando em qualquer resolução. Em janelas grandes o
tamanho lógico é mantido; em janelas estreitas o painel encolhe para não sair da
tela. O painel de construções do `--terrain` segue a mesma regra para a largura.

## 🏗️ Arquitetura

| Arquivo | Papel |
|---|---|
| `src/editor/voxel_object.py` | grade, paleta de materiais, rotação, colagem, JSON |
| `src/editor/map_project.py` | volume base + `PlacedObject` (posição/rotação), JSON do mapa |
| `src/editor/map_world.py` | mapa estático jogável (`--terrain --map`), colisão |
| `src/editor/material_atlas.py` | atlas 4×4 de texturas de bloco e UVs |
| `src/editor/object_mesher.py` | malha com face culling, cor e textura por voxel |
| `src/editor/platform.py` | plataforma em um draw, com shader próprio |
| `src/editor/selection.py` | caixa delimitadora do objeto selecionado |
| `src/editor/map_editor.py` | ferramentas, picking, histórico, arquivos, render |
| `src/editor/editor_hud.py` | painel 2D (PIL + `HudQuad`) |
| `assets/shaders/platform.vert/.frag` | superfície, grade, borda e célula do cursor |

O objeto é renderizado com o mesmo `world_textured` do terreno, então herda
iluminação ambiente/direcional e o pipeline de textura. A plataforma é desenhada
antes dos voxels, com blending e sem escrita de profundidade; a grade é calculada
no fragment shader em coordenadas locais, para continuar alinhada quando o
tabuleiro gira com `Q/E`.

## 🧪 Testes

```bash
pytest -q tests/test_editor_voxel_object.py tests/test_editor_mesher.py \
         tests/test_editor_map_editor.py tests/test_editor_map_project.py \
         tests/test_editor_map_world.py tests/test_construction_panel.py
```

Cobrem: paleta e materiais, get/set, redimensionamento, rotação, colagem,
serialização e arquivos inválidos; faces expostas, UVs e cores; e o controlador
(construir/pintar/apagar, desfazer/refazer, carimbo da casa, salvar/carregar e
atalhos).

## ⚠️ Limites do MVP

- A biblioteca tem lista textual (`F4`) com escolher/carimbar/duplicar/excluir,
  mas ainda não gera miniaturas voxel, categorias, busca nem importação por
  caminho digitado.
- Não há `.vox` nem geração procedural.
- O objeto colocado é transformado como um todo; não há edição de voxels dentro
  dele depois de carimbado (edite, exporte e carimbe de novo).
- O piso base é plano (`F8`); ainda não há terreno procedural como base do mapa.
- A base e os objetos colidem no `--terrain --map`, mas não há grid tático sobre
  o mapa carregado.
- O teto de materiais é 512 por objeto; o volume máximo é 64³.
