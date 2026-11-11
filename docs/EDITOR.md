# 🗺️ Editor de mapa e objetos voxel

Modo de autoria do Isometricon: constrói um mapa/objeto voxel em uma plataforma
renderizada por shader e permite exportar o objeto e carimbá-lo em outro mapa.
É um modo **aditivo**: não altera `--terrain`, `--char` nem o editor de personagem.

> **Estado:** implementação na branch `feat/voxel-editor`. Cobre `FR-035` a
> `FR-048` (com biblioteca textual sem miniaturas e base plana em vez de terreno
> procedural). `.vox` (`FR-049`) e geração procedural (`FR-050`) continuam fora
> do escopo.

## ▶️ Como abrir

```bash
# editor vazio (16×16×16)
python src/main.py --map-editor

# abre um mapa/objeto existente no editor
python src/main.py --map=assets/objects/casa_exemplo.json
python src/main.py --map-editor=assets/objects/casa_exemplo.json

# joga um mapa salvo no mundo isométrico (com colisão do token)
python src/main.py --terrain --map=saves/mapa.json
```

O modo também funciona com `--frames`/`--screenshot`, útil para capturas:

```bash
python src/main.py --map-editor=assets/objects/casa_exemplo.json \
  --frames=3 --screenshot=artifacts/editor.png
```

## 🕹️ Controles

| Ação | Controle |
|---|---|
| Aplicar ferramenta | Clique esquerdo |
| Trocar ferramenta (construir → apagar → pintar → carimbar → selecionar) | `Tab` / `Shift+Tab` |
| Próxima cor / anterior | `C` / `Shift+C` |
| Cor hexadecimal livre | `H`, digite 6 dígitos, `Enter` |
| Próxima textura / anterior | `X` / `Shift+X` |
| Pincel (1 a 8) | `-` / `=` |
| Espaçamento da grade | `[` / `]` |
| Girar objeto carimbado ou selecionado | `R` |
| Ligar/desligar grade da plataforma | `G` |
| Aumentar / diminuir o volume | `F7` / `F6` |
| Criar piso base plano | `F8` |
| Exportar objeto atual | `F2` |
| Carregar próximo objeto da biblioteca | `F3` |
| Abrir/fechar a lista da biblioteca | `F4` |
| Salvar mapa | `F5` |
| Carregar mapa | `F9` |
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
2. **Material**: escolha cor (`C`) e textura (`X`); a combinação é o material do
   voxel. Cada voxel guarda seu próprio índice de material.
3. **Exportar** com `F2`: grava `saves/objeto.json`.
4. **Carimbar** com `F3`: carrega o próximo JSON de `assets/objects/` (ou o
   exportado), ativa a ferramenta de carimbo, e `R` gira em 90°.
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

No mundo procedural: `P` ou o botão **Colocar** do HUD ativa/desativa a
colocação, `F3` troca o objeto, `R` gira, `Esc` cancela, clique esquerdo coloca
no topo do bloco, `V` ou o botão **Selecionar** seleciona e `Delete` remove.
Ao entrar em uma casa, o cutaway deixa telhado/paredes acima dos pés do token
translúcidos, mantendo o personagem visível — o mesmo comportamento do modo
subterrâneo. A persistência é por seed:
`saves/mundos/mundo_<seed>.json`. Se o arquivo estiver corrompido, o mundo abre
sem objetos e mostra o aviso no HUD.

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
         tests/test_editor_map_world.py tests/test_editor_world_objects.py
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
