# SRS — Incremento: objetos no mundo procedural

> **Norma de referência:** ISO/IEC/IEEE 29148:2018
> **Status do incremento:** aprovado e implementado
> **Origem:** pedido para colocar construções criadas no editor dentro do mundo
> gerado por `--terrain`, mantendo também o fluxo de mapa independente.

---

## 1. Escopo

O incremento adiciona **dois destinos opcionais** para um objeto voxel:

- **Fluxo A — mapa independente:** o objeto é salvo como mapa finito e jogado
  com `--terrain --map=...` (preservado do incremento anterior).
- **Fluxo B — mundo procedural:** o objeto é colocado no mundo gerado por seed,
  renderizado como entidade independente, com colisão e persistência por seed.

Os dois fluxos usam o mesmo formato de objeto e a mesma biblioteca. Um não
substitui o outro.

### Fora de escopo

- Editar voxels dentro de um objeto já colocado no mundo procedural.
- Física de objetos, multiplayer e sincronização de rede.
- `.vox` e geração procedural por regras (FR-049/FR-050 permanecem opcionais).
- Terreno procedural como base do editor de mapa independente.

---

## 2. Fluxos de uso

### Fluxo A — mapa independente

```text
editor → F8 base → F3 objeto → clique → F5 salvar mapa
→ --terrain --map=saves/mapa.json
```

### Fluxo B — mundo procedural

```text
--terrain --seed=123
→ P ativa colocação (ou --object=... já abre com o objeto)
→ F3 escolhe objeto, R gira, Esc cancela
→ clique no topo de um bloco confirma
→ objeto é salvo em saves/mundos/mundo_123.json
→ reabrir a seed 123 restaura o objeto
```

---

## 3. Requisitos

| ID | Requisito | Prioridade | Verificação |
|---|---|---|---|
| **FR-051** | O sistema deve oferecer dois destinos para um objeto voxel: salvar como mapa independente e disponibilizar o objeto para colocação no mundo procedural. | Essencial | Teste, demonstração |
| **FR-052** | No modo `--terrain`, o sistema deve permitir ativar o modo de colocação por `P` ou por botão no HUD e escolher um objeto da biblioteca. | Essencial | Teste, demonstração |
| **FR-053** | O sistema deve exibir uma prévia do objeto acompanhando o cursor e indicar se a posição é válida ou inválida. | Essencial | Teste, demonstração |
| **FR-054** | O sistema deve encaixar o objeto na grade e na face superior do terreno, rejeitando posições sobre água, dentro de outro objeto ou sobre o token. | Essencial | Teste, demonstração |
| **FR-055** | O sistema deve permitir rotacionar o objeto em passos de 90° e cancelar a colocação sem alterar o mundo. | Essencial | Teste, demonstração |
| **FR-056** | O sistema deve confirmar a colocação do objeto como entidade independente do terreno. | Essencial | Teste, demonstração |
| **FR-057** | O sistema deve persistir os objetos por seed e recarregá-los ao abrir a mesma seed. | Essencial | Teste, demonstração |
| **FR-058** | O token deve colidir com os objetos colocados, e o raycast deve detectá-los. | Essencial | Teste, demonstração |
| **FR-059** | O sistema deve permitir selecionar e remover um objeto colocado no mundo procedural. | Desejável | Teste, demonstração |
| **FR-060** | O sistema deve renderizar os objetos com o mesmo shader iluminado/texturizado do terreno, independentemente do streaming dos chunks. | Essencial | Inspeção, teste |
| **FR-061** | Quando o token estiver dentro de um objeto ou de um mapa carregado, o sistema deve revelar o cômodo e escurecer o restante, mantendo o personagem visível. | Desejável | Demonstração, teste |
| **FR-062** | O sistema deve permitir nomear o objeto antes/depois da criação e usar esse nome no arquivo exportado, preservando acentos no nome interno e gerando um nome de arquivo seguro. | Desejável | Teste, demonstração |
| **FR-063** | O menu inicial deve oferecer uma opção que abra o editor de mapa sem criar um mundo salvo. | Essencial | Teste, demonstração |
| **FR-064** | O editor deve exibir as texturas como uma grade de miniaturas reais, com seleção por clique e indicação da textura ativa. | Desejável | Teste, demonstração |
| **FR-065** | O editor deve oferecer uma roda HSV com barra de brilho, paleta de atalhos e histórico de cores recentes. | Desejável | Teste, demonstração |
| **FR-066** | O editor deve permitir copiar cor e textura de um voxel existente com `Alt`+clique. | Desejável | Teste, demonstração |
| **FR-067** | A grade de texturas deve permitir filtrar por categoria. | Desejável | Teste, demonstração |
| **FR-068** | A grade de texturas deve permitir busca textual por nome. | Desejável | Teste, demonstração |
| **FR-069** | O usuário deve poder favoritar texturas e filtrar somente as favoritas. | Desejável | Teste, demonstração |
| **FR-070** | A HUD do editor deve reduzir proporcionalmente para caber em janelas menores, mantendo as hitboxes alinhadas à imagem. | Desejável | Teste, demonstração |
| **FR-071** | O fluxo menu → editor → salvar/exportar → menu → nova aventura deve ocorrer na mesma execução, sem encerrar a aplicação, e o objeto exportado deve aparecer na biblioteca de construções. | Essencial | Teste, demonstração |
| **FR-072** | As UIs devem usar fontes empacotadas com a aplicação (Inter e JetBrains Mono, licença OFL), sem depender de fontes instaladas no sistema. | Desejável | Teste, inspeção |
| **FR-073** | As HUDs do editor e das construções devem rasterizar a fonte em 2× para manter legibilidade em telas de alta densidade. | Desejável | Inspeção, demonstração |
| **FR-074** | Em macOS, o mundo normal deve usar uma variante de shader compatível com o driver Metal, preservando máscara de sombra, horizonte e revelação de cômodo. | Essencial | Teste, demonstração |
| **FR-075** | A janela deve separar tamanho de framebuffer (cena 3D) de tamanho lógico (HUDs), mantendo cliques e viewport alinhados em Retina. | Essencial | Teste, demonstração |
| **FR-076** | A biblioteca de construções deve exibir miniatura da construção selecionada e permitir filtrar objetos exportados. | Desejável | Teste, demonstração |
| **FR-077** | A geração de miniaturas e a vinculação das texturas de sombra/cômodo devem ser cacheadas ou feitas uma vez por quadro. | Desejável | Inspeção, medição |
| **FR-078** | O material do editor deve poder ser marcado como luminoso e alimentar luzes pontuais no shader. | Desejável | Teste, demonstração |
| **FR-079** | O editor deve oferecer objetos padrão de lampião, lanterna e tocha, e o mapa jogável deve preservar suas luzes. | Desejável | Teste, demonstração |
| **FR-080** | O editor deve oferecer um modal responsivo para nomear e exportar o objeto, com caminho, aviso de sobrescrita e confirmação. | Desejável | Teste, demonstração |
| **FR-081** | O editor deve separar o canvas 3D da barra lateral de opções, com viewport, raycast e cliques restritos ao canvas. | Desejável | Teste, demonstração |
| **FR-082** | O editor deve remover um carimbo apontado por `Delete`/botão direito; o `/schem` deve abrir a biblioteca e travar o personagem enquanto o painel estiver aberto. | Desejável | Teste, demonstração |
| **PR-011** | A confirmação de um objeto de até 32³ voxels deve concluir em até 1 frame em 95% das medições e não deve pausar a aplicação por mais de 100 ms. | Desejável | Medição |
| **UR-008** | O HUD deve exibir modo, objeto selecionado, posição válida/inválida, rotação e teclas de confirmar/cancelar durante a colocação. | Essencial | Demonstração |
| **DR-008** | Os objetos do mundo procedural devem ser persistidos em JSON versionado com seed, objeto, posição, rotação, nome e origem; a gravação deve ser atômica e arquivo inválido não deve encerrar a aplicação. | Essencial | Teste |
| **CR-013** | Os dois fluxos devem reutilizar o formato de objeto e o pipeline OpenGL do motor, sem engine externa. | Essencial | Inspeção |
| **AR-013** | Nenhuma célula ocupada por um objeto colocado pode ser atravessada pelo token. | Essencial | Teste |
| **AR-014** | Salvar e recarregar um mundo deve preservar posição, rotação, nome e origem de cada objeto. | Desejável | Teste |

### Critérios de aceitação principais

```gherkin
Funcionalidade: Colocar objeto no mundo procedural
  Cenário: Confirmar uma casa no topo do terreno
    Dado o modo --terrain carregado com a seed 123
    E a casa selecionada na biblioteca
    Quando o usuário aponta para o topo de um bloco e clica
    Então a casa é renderizada como entidade independente na posição encaixada
    E o token colide com as células ocupadas pela casa
    E o arquivo saves/mundos/mundo_123.json contém a casa

  Cenário: Cancelar a colocação
    Dado o modo de colocação ativo
    Quando o usuário pressiona Esc
    Então nenhum objeto é adicionado e o mundo permanece inalterado

  Cenário: Reabrir a seed
    Dado uma casa salva na seed 123
    Quando o usuário abre --terrain --seed=123 novamente
    Então a casa reaparece na mesma posição e rotação

  Cenário: Manter o mapa independente
    Dado uma casa exportada
    Quando o usuário salva um mapa independente e usa --terrain --map=...
    Então o mapa finito continua funcionando sem depender do mundo procedural
```

---

## 4. Decisões confirmadas

1. Persistência **por seed**, em `saves/mundos/mundo_<seed>.json`.
2. Ao trocar de seed com `R`, a seed anterior permanece salva e a nova carrega os
   objetos dela.
3. Encaixe apenas na **face superior** de um bloco; paredes/lateral ficam fora do MVP.
4. O objeto **sobrepõe** o terreno; não remove blocos.
5. Depois de colocado, o objeto pode ser **selecionado, rotacionado e removido**;
   mover célula a célula fica para um próximo incremento.
6. A colocação é limitada a superfícies atingidas pelo raycast em chunks
   carregados.
7. O painel de construções é aberto por **`/schem`** ou por `--object=...`;
   dentro dele, `P`/botão Colocar, `V`, `F3`/`F4`, `R`, `N`, `Delete` e `Esc`.
8. Ao entrar em um objeto/mapa, vale a revelação de cômodo do modo terreno
   (a mesma das construções `/schem`): o espaço fechado se revela e o resto
   escurece, e o corredor da câmera abre onde algo tapa o personagem.

---

## 5. Rastreabilidade

| Requisito | Requisitos relacionados | Implementação |
|---|---|---|
| FR-051 | FR-041, FR-042, FR-045 | `docs/EDITOR.md`, `src/editor/map_project.py`, `src/interactive/construction_panel.py` |
| FR-052 | FR-035, FR-043 | `ConstructionPanel`, `--object` |
| FR-053 | FR-012, FR-048 | `ConstructionPanel.update_cursor`, HUD |
| FR-054 | FR-012, FR-016 | `SchematicTool.fits`, `StructureLayer` |
| FR-055 | FR-042 | `ConstructionPanel.handle_key`, `SchematicTool.rotate` |
| FR-056 | FR-042, FR-047 | `SchematicTool.confirm`, `StructureLayer` |
| FR-057 | FR-045, FR-007 | `SeedStore`, `structure_save`, save do mundo |
| FR-058 | FR-016, FR-012 | `SchematicTool.lookup`, `player_token.update` |
| FR-059 | FR-047 | seleção/remoção no `ConstructionPanel` |
| FR-060 | FR-010, FR-011, FR-007 | `StructureMeshes`, `StructureMesher` |
| FR-061 | FR-011, FR-058 | `RoomRevealRenderer`, `world.room_reveal` |
| FR-062 | FR-041, FR-043 | `MapEditor` (`N`), `ConstructionPanel` (`N`), `object_names.py` |
| FR-063 | FR-035, FR-003 | `GameMenus`, `main.py` |
| FR-064 | FR-038, FR-043 | `EditorHud` (aba Texturas), `MaterialAtlas.atlas_image` |
| FR-065 | FR-037, FR-048 | `color_wheel.py`, `EditorHud` (aba Cores) |
| FR-066 | FR-037, FR-038 | `MapEditor._pick_material` |
| FR-067 | FR-038, FR-043 | `MapEditor.texture_entries`, `EditorHud` filtros |
| FR-068 | FR-038, FR-043 | `MapEditor.open_texture_search`, `EditorHud` busca |
| FR-069 | FR-038, FR-043 | `MapEditor.favourite_textures`, `EditorHud` favoritos |
| FR-070 | FR-048 | `fit_panel_scale`, `EditorHud.local_point`, `ConstructionPanel._panel_scale` |
| FR-071 | FR-063, FR-067 | `run_editor_session`, loop do menu, `ConstructionPanel` |
| FR-072 | — | `src/core/fonts.py`, `assets/fonts/` |
| FR-073 | FR-048 | `src/rendering/scaled_draw.py`, `EditorHud`, `ConstructionPanel` |
| FR-074 | FR-052, FR-056 | `world_textured.frag`, `SunShadowRenderer.compat`, `--compat-shadows` |
| FR-075 | FR-048 | `Window`, `get_window_size`, `SceneTarget` |
| FR-076 | FR-038, FR-043 | `ConstructionPanel`, `construction_thumb.py` |
| FR-077 | FR-052, FR-056 | `ConstructionPanel`, `bind_samplers` |
| FR-078 | FR-037, FR-038 | `VoxelMaterial.light`, `lighting.py`, `world_textured.frag` |
| FR-079 | FR-038, FR-043 | `assets/objects/lampiao.json`, `lanterna.json`, `tocha.json`, `MapWorld` |
| FR-080 | FR-042, FR-043 | `ExportDialog`, `MapEditor.open_export_dialog` |
| FR-081 | FR-048 | `EditorHud.canvas_rect`, `MapEditor.render_world`, `run_editor_session` |
| FR-082 | FR-043, FR-044 | `MapEditor._delete_object_at_cursor`, `ConstructionPanel._remove_target`, `main` |
| PR-011 | FR-056 | medição manual |
| UR-008 | FR-048 | `ConstructionPanel` |
| DR-008 | FR-041 | JSON `isometricon-structures` (v2; lê o formato antigo) |
| CR-013 | CR-010, CR-011 | mesmo `VoxelObject`/OpenGL |
| AR-013 | FR-016, FR-058 | testes de colisão |
| AR-014 | FR-057 | round-trip de objetos |

---

## 6. Testes

- `tests/test_construction_panel.py, tests/test_structure_save.py` — persistência, colisão do provider,
  colocação, remoção, arquivo inválido, sobreposição com token e atalhos.
- `tests/test_game_menus.py` — opção **Editor de mapa** no menu.
- `tests/test_editor_color_wheel.py` — roda HSV e conversão de cor.
- `test_texture_search_and_favourites` — busca e favoritos.
- `test_f10_asks_then_saves_and_requests_menu` — retorno do editor.
- `tests/test_fonts.py` — fontes empacotadas e monoespaçamento.
- Teste manual: `--terrain --object=assets/objects/casa_exemplo.json`.
- Regressão: fluxo de mapa independente (`--map-editor` e `--terrain --map`).
