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
| **FR-061** | Quando o token estiver dentro de um objeto ou de um mapa carregado, o sistema deve tornar translúcidas as partes acima dos pés do token, mantendo o personagem visível. | Desejável | Demonstração, teste |
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
7. O modo é ativado por **`P` no teclado ou pelo botão “Colocar” no HUD**;
   o HUD também expõe Selecionar, Objeto, Girar, Remover e Sair.
8. Ao entrar em um objeto/mapa, as partes acima dos pés do token ficam
   translúcidas para o personagem continuar visível, reutilizando o cutaway do
   modo terreno.

---

## 5. Rastreabilidade

| Requisito | Requisitos relacionados | Implementação |
|---|---|---|
| FR-051 | FR-041, FR-042, FR-045 | `docs/EDITOR.md`, `src/editor/map_project.py`, `src/editor/world_objects.py` |
| FR-052 | FR-035, FR-043 | `WorldObjectEditor`, `--object` |
| FR-053 | FR-012, FR-048 | `WorldObjectEditor.update_cursor`, HUD |
| FR-054 | FR-012, FR-016 | `WorldObjectProvider`, validação de células |
| FR-055 | FR-042 | `WorldObjectEditor.handle_key` |
| FR-056 | FR-042, FR-047 | `WorldObjectStore`, `PlacedObject` |
| FR-057 | FR-045, FR-007 | `WorldObjectStore.load_seed/save` |
| FR-058 | FR-016, FR-012 | `WorldObjectProvider`, `player_token.update` |
| FR-059 | FR-047 | seleção/remoção no `WorldObjectEditor` |
| FR-060 | FR-010, FR-011, FR-007 | `WorldObjectRenderer` |
| FR-061 | FR-011, FR-058 | `WorldObjectRenderer`, `MapWorld.render` |
| PR-011 | FR-056 | medição manual |
| UR-008 | FR-048 | `WorldObjectHud` |
| DR-008 | FR-041 | JSON `isometricon-world-objects` |
| CR-013 | CR-010, CR-011 | mesmo `VoxelObject`/OpenGL |
| AR-013 | FR-016, FR-058 | testes de colisão |
| AR-014 | FR-057 | round-trip de objetos |

---

## 6. Testes

- `tests/test_editor_world_objects.py` — persistência, colisão do provider,
  colocação, remoção, arquivo inválido, sobreposição com token e atalhos.
- Teste manual: `--terrain --object=assets/objects/casa_exemplo.json`.
- Regressão: fluxo de mapa independente (`--map-editor` e `--terrain --map`).
