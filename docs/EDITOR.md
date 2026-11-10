# 🗺️ Editor de mapa e objetos voxel

Modo de autoria do Isometricon: constrói um mapa/objeto voxel em uma plataforma
renderizada por shader e permite exportar o objeto e carimbá-lo em outro mapa.
É um modo **aditivo**: não altera `--terrain`, `--char` nem o editor de personagem.

> **Estado:** MVP implementado na branch `feat/voxel-editor`. Cobre a base dos
> requisitos `FR-035` a `FR-042`, `FR-044`, `FR-045`, `FR-046`, `FR-048` e parte
> de `FR-043`/`FR-047`. `.vox` (`FR-049`) e geração procedural (`FR-050`) ainda
> não estão implementados.

## ▶️ Como abrir

```bash
# editor vazio (16×16×16)
python src/main.py --map-editor

# abre um mapa/objeto existente
python src/main.py --map=assets/objects/casa_exemplo.json
python src/main.py --map-editor=assets/objects/casa_exemplo.json
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
| Trocar ferramenta (construir → apagar → pintar → carimbar) | `Tab` / `Shift+Tab` |
| Próxima cor / anterior | `C` / `Shift+C` |
| Próxima textura / anterior | `X` / `Shift+X` |
| Girar objeto carimbado | `R` |
| Ligar/desligar grade da plataforma | `G` |
| Aumentar / diminuir o volume | `F7` / `F6` |
| Exportar objeto atual | `F2` |
| Carregar próximo objeto da biblioteca | `F3` |
| Salvar mapa | `F5` |
| Carregar mapa | `F9` |
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
5. **Colocar** no mapa com clique esquerdo. O objeto é mesclado ao volume do mapa,
   preservando cor e textura de cada voxel.
6. **Salvar** o mapa com `F5`; reabrir com `F9` ou `--map=...`.

Há um exemplo em [`assets/objects/casa_exemplo.json`](../assets/objects/casa_exemplo.json)
(204 voxels, 5 materiais): telhado em três camadas, paredes de tijolo, janelas e
chaminé.

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

## 🏗️ Arquitetura

| Arquivo | Papel |
|---|---|
| `src/editor/voxel_object.py` | grade, paleta de materiais, rotação, colagem, JSON |
| `src/editor/material_atlas.py` | atlas 4×4 de texturas de bloco e UVs |
| `src/editor/object_mesher.py` | malha com face culling, cor e textura por voxel |
| `src/editor/platform.py` | plataforma em um draw, com shader próprio |
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
pytest -q tests/test_editor_voxel_object.py \
         tests/test_editor_mesher.py \
         tests/test_editor_map_editor.py
```

Cobrem: paleta e materiais, get/set, redimensionamento, rotação, colagem,
serialização e arquivos inválidos; faces expostas, UVs e cores; e o controlador
(construir/pintar/apagar, desfazer/refazer, carimbo da casa, salvar/carregar e
atalhos).

## ⚠️ Limites do MVP

- Um volume de mapa por vez; não há lista de objetos independentes para
  selecionar/mover depois de carimbados.
- O carimbo é mesclado ao mapa (não há entidade “instância” com transformação
  persistida).
- Não há colisão do token com o mapa no modo terreno ainda.
- Não há `.vox`, geração procedural, miniaturas de objetos nem edição por face.
- A biblioteca lê `assets/objects/*.json` e o `saves/objeto.json` exportado.
- O teto de materiais é 512 por objeto; o volume máximo é 64³.
