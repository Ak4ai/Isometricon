# Requisitos atômicos — um arquivo por requisito

Esta pasta contém **108 fichas de requisito**, uma por arquivo, no formato do
[`templates/TEMPLATE_REQUISITO.md`](templates/TEMPLATE_REQUISITO.md) (ISO/IEC/IEEE 29148:2018). Os arquivos mantêm o ID original
(`FR-001`, `EI-001`, …) e seguem a nomenclatura `<ID>.md` (nome do arquivo igual ao ID do requisito).

- **78 requisitos do baseline implementado** (`../SRS.md`), com status
  `Implementado`, `Verificado` ou `Implementado com falha conhecida`.
- **30 requisitos propostos** (`../SRS-INCREMENTO-EDITOR-VOXEL.md`), com status `Proposto`.

Conforme pedido, as fichas **não registram stakeholder nem versionamento**. A rastreabilidade é
feita por fonte, código/teste e documento de origem. Todas têm **critério de aceitação em
Gherkin**, método de verificação e checklist de conformidade com a norma.

## Resumo

| Origem | Quantidade |
|---|---:|
| Baseline implementado (`../SRS.md`) | 78 |
| Incremento proposto (`../SRS-INCREMENTO-EDITOR-VOXEL.md`) | 30 |
| **Total** | **108** |

| Status | Quantidade |
|---|---:|
| Verificado | 43 |
| Implementado | 34 |
| Implementado com falha conhecida | 1 |
| Proposto | 30 |


> **Extensões ao template:** `Implementado com falha conhecida` (apenas `FR-029`, equivalente a
> “Em revisão” com falha registrada) e o tipo “Interface externa” (a ficha usa `Funcional` como
> tipo-base e registra a interface na descrição).
>
> Nenhum arquivo tem stakeholder ou versão, conforme pedido; a data de referência é o commit
> `0b5c1fe` para o baseline e o pedido de 21/10/2026 para o incremento.

## Nomenclatura

| Prefixo | Categoria | Exemplo |
|---|---|---|
| `FR` | Funcional | `FR-001.md` |
| `EI` | Interface externa | `EI-001.md` |
| `UR` | Usabilidade | `UR-001.md` |
| `PR` | Desempenho | `PR-001.md` |
| `DR` | Dados | `DR-001.md` |
| `CR` | Restrição de design | `CR-001.md` |
| `SR` | Conformidade | `SR-001.md` |
| `AR` | Atributo do sistema | `AR-001.md` |

## Índice


### Requisitos funcionais (50)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `FR-001` | [FR-001.md](FR-001.md) | Janela e contexto OpenGL | Funcional | Essencial | Implementado | baseline implementado |
| `FR-002` | [FR-002.md](FR-002.md) | Câmera isométrica ortográfica | Funcional | Essencial | Verificado | baseline implementado |
| `FR-003` | [FR-003.md](FR-003.md) | Modos de operação | Funcional | Essencial | Implementado | baseline implementado |
| `FR-004` | [FR-004.md](FR-004.md) | Geração determinística de terreno | Funcional | Essencial | Verificado | baseline implementado |
| `FR-005` | [FR-005.md](FR-005.md) | Cavernas tridimensionais | Funcional | Desejável | Verificado | baseline implementado |
| `FR-006` | [FR-006.md](FR-006.md) | Chunks e face culling | Funcional | Essencial | Verificado | baseline implementado |
| `FR-007` | [FR-007.md](FR-007.md) | Streaming de chunks | Funcional | Essencial | Verificado | baseline implementado |
| `FR-008` | [FR-008.md](FR-008.md) | Frustum culling | Funcional | Desejável | Verificado | baseline implementado |
| `FR-009` | [FR-009.md](FR-009.md) | Água | Funcional | Desejável | Verificado | baseline implementado |
| `FR-010` | [FR-010.md](FR-010.md) | Texturização de blocos | Funcional | Essencial | Verificado | baseline implementado |
| `FR-011` | [FR-011.md](FR-011.md) | Iluminação e modo subterrâneo | Funcional | Desejável | Implementado | baseline implementado |
| `FR-012` | [FR-012.md](FR-012.md) | Seleção de bloco por cursor | Funcional | Essencial | Verificado | baseline implementado |
| `FR-013` | [FR-013.md](FR-013.md) | Grade tática | Funcional | Essencial | Verificado | baseline implementado |
| `FR-014` | [FR-014.md](FR-014.md) | Destaque de bloco | Funcional | Desejável | Implementado | baseline implementado |
| `FR-015` | [FR-015.md](FR-015.md) | Movimento do token | Funcional | Essencial | Verificado | baseline implementado |
| `FR-016` | [FR-016.md](FR-016.md) | Colisão e gravidade | Funcional | Essencial | Verificado | baseline implementado |
| `FR-017` | [FR-017.md](FR-017.md) | Câmera acompanha o token | Funcional | Essencial | Verificado | baseline implementado |
| `FR-018` | [FR-018.md](FR-018.md) | Overlay de coordenadas | Funcional | Opcional | Implementado | baseline implementado |
| `FR-019` | [FR-019.md](FR-019.md) | Console de chat | Funcional | Essencial | Verificado | baseline implementado |
| `FR-020` | [FR-020.md](FR-020.md) | Comandos de customização e roupas | Funcional | Essencial | Implementado | baseline implementado |
| `FR-021` | [FR-021.md](FR-021.md) | Editor de personagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-022` | [FR-022.md](FR-022.md) | Rosto, olhos, boca e maquiagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-023` | [FR-023.md](FR-023.md) | Proporções do corpo | Funcional | Essencial | Verificado | baseline implementado |
| `FR-024` | [FR-024.md](FR-024.md) | Peças procedurais | Funcional | Desejável | Verificado | baseline implementado |
| `FR-025` | [FR-025.md](FR-025.md) | Raças | Funcional | Desejável | Verificado | baseline implementado |
| `FR-026` | [FR-026.md](FR-026.md) | Cabelo | Funcional | Essencial | Verificado | baseline implementado |
| `FR-027` | [FR-027.md](FR-027.md) | Vestir e encaixar roupas Roblox | Funcional | Essencial | Implementado | baseline implementado |
| `FR-028` | [FR-028.md](FR-028.md) | Ocultação de pele sob a roupa (HSR) | Funcional | Essencial | Verificado | baseline implementado |
| `FR-029` | [FR-029.md](FR-029.md) | Camadas, sapatos e extras | Funcional | Desejável | Implementado com falha conhecida | baseline implementado |
| `FR-030` | [FR-030.md](FR-030.md) | Animação esquelética | Funcional | Essencial | Verificado | baseline implementado |
| `FR-031` | [FR-031.md](FR-031.md) | Salvar e carregar personagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-032` | [FR-032.md](FR-032.md) | Automação por linha de comando | Funcional | Desejável | Implementado | baseline implementado |
| `FR-033` | [FR-033.md](FR-033.md) | Diagnóstico de versão e sincronização | Funcional | Opcional | Verificado | baseline implementado |
| `FR-034` | [FR-034.md](FR-034.md) | Catálogo e miniaturas do editor | Funcional | Desejável | Implementado | baseline implementado |
| `FR-035` | [FR-035.md](FR-035.md) | Modo editor de mapa e objetos | Funcional | Essencial | Proposto | incremento proposto |
| `FR-036` | [FR-036.md](FR-036.md) | Edição de voxels | Funcional | Essencial | Proposto | incremento proposto |
| `FR-037` | [FR-037.md](FR-037.md) | Cor por voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-038` | [FR-038.md](FR-038.md) | Textura individual por voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-039` | [FR-039.md](FR-039.md) | Tamanho do volume de edição | Funcional | Essencial | Proposto | incremento proposto |
| `FR-040` | [FR-040.md](FR-040.md) | Plataforma renderizada por shader | Funcional | Essencial | Proposto | incremento proposto |
| `FR-041` | [FR-041.md](FR-041.md) | Formato e exportação de objeto voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-042` | [FR-042.md](FR-042.md) | Colocar objeto no mundo isométrico | Funcional | Essencial | Proposto | incremento proposto |
| `FR-043` | [FR-043.md](FR-043.md) | Biblioteca de objetos | Funcional | Desejável | Proposto | incremento proposto |
| `FR-044` | [FR-044.md](FR-044.md) | Criar e editar mapa | Funcional | Essencial | Proposto | incremento proposto |
| `FR-045` | [FR-045.md](FR-045.md) | Salvar e carregar mapa | Funcional | Essencial | Proposto | incremento proposto |
| `FR-046` | [FR-046.md](FR-046.md) | Desfazer e refazer | Funcional | Desejável | Proposto | incremento proposto |
| `FR-047` | [FR-047.md](FR-047.md) | Selecionar e transformar objetos | Funcional | Desejável | Proposto | incremento proposto |
| `FR-048` | [FR-048.md](FR-048.md) | Feedback visual do editor | Funcional | Essencial | Proposto | incremento proposto |
| `FR-049` | [FR-049.md](FR-049.md) | Exportar e importar MagicaVoxel (opcional) | Funcional | Opcional | Proposto | incremento proposto |
| `FR-050` | [FR-050.md](FR-050.md) | Geração procedural por regras (opcional) | Funcional | Opcional | Proposto | incremento proposto |

### Interfaces externas (6)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `EI-001` | [EI-001.md](EI-001.md) | Teclado e mouse | Funcional | Essencial | Implementado | baseline implementado |
| `EI-002` | [EI-002.md](EI-002.md) | Vídeo | Funcional | Essencial | Implementado | baseline implementado |
| `EI-003` | [EI-003.md](EI-003.md) | Sistema de arquivos | Funcional | Essencial | Implementado | baseline implementado |
| `EI-004` | [EI-004.md](EI-004.md) | GitHub | Funcional | Essencial | Implementado | baseline implementado |
| `EI-005` | [EI-005.md](EI-005.md) | Roblox | Funcional | Essencial | Implementado | baseline implementado |
| `EI-006` | [EI-006.md](EI-006.md) | Linha de comando | Funcional | Essencial | Implementado | baseline implementado |

### Usabilidade (7)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `UR-001` | [UR-001.md](UR-001.md) | Controles de teclado e mouse | Usabilidade | Essencial | Implementado | baseline implementado |
| `UR-002` | [UR-002.md](UR-002.md) | Feedback de comandos | Usabilidade | Essencial | Verificado | baseline implementado |
| `UR-003` | [UR-003.md](UR-003.md) | Autocompletar e ajuda | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-004` | [UR-004.md](UR-004.md) | Idioma e apelidos | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-005` | [UR-005.md](UR-005.md) | Editor: seleção, rolagem e arraste | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-006` | [UR-006.md](UR-006.md) | Barra de ferramentas e atalhos | Usabilidade | Essencial | Proposto | incremento proposto |
| `UR-007` | [UR-007.md](UR-007.md) | Prévia de cor e textura | Usabilidade | Desejável | Proposto | incremento proposto |

### Desempenho (10)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `PR-001` | [PR-001.md](PR-001.md) | Upload e liberação amortizados | Performance | Essencial | Verificado | baseline implementado |
| `PR-002` | [PR-002.md](PR-002.md) | Geração de chunks em segundo plano | Performance | Essencial | Verificado | baseline implementado |
| `PR-003` | [PR-003.md](PR-003.md) | Montagem do personagem em segundo plano | Performance | Essencial | Verificado | baseline implementado |
| `PR-004` | [PR-004.md](PR-004.md) | Skinning na GPU | Performance | Desejável | Implementado | baseline implementado |
| `PR-005` | [PR-005.md](PR-005.md) | Grade em uma chamada e por revisão | Performance | Desejável | Verificado | baseline implementado |
| `PR-006` | [PR-006.md](PR-006.md) | Limites de raycast e colisão | Performance | Essencial | Verificado | baseline implementado |
| `PR-007` | [PR-007.md](PR-007.md) | Raio de streaming de 25 colunas | Performance | Essencial | Verificado | baseline implementado |
| `PR-008` | [PR-008.md](PR-008.md) | Resposta de edição no quadro seguinte | Performance | Essencial | Proposto | incremento proposto |
| `PR-009` | [PR-009.md](PR-009.md) | Plataforma e objeto em poucas chamadas | Performance | Essencial | Proposto | incremento proposto |
| `PR-010` | [PR-010.md](PR-010.md) | Colocação multi-chunk sem travar | Performance | Desejável | Proposto | incremento proposto |

### Dados (7)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `DR-001` | [DR-001.md](DR-001.md) | Save do personagem em JSON | Funcional | Essencial | Verificado | baseline implementado |
| `DR-002` | [DR-002.md](DR-002.md) | Cache de roupa e sidecars | Funcional | Essencial | Verificado | baseline implementado |
| `DR-003` | [DR-003.md](DR-003.md) | Assets de roupa por ID | Funcional | Essencial | Verificado | baseline implementado |
| `DR-004` | [DR-004.md](DR-004.md) | Sem persistência de mundo no modo atual | Funcional | Essencial | Implementado | baseline implementado |
| `DR-005` | [DR-005.md](DR-005.md) | Miniaturas do catálogo | Funcional | Opcional | Implementado | baseline implementado |
| `DR-006` | [DR-006.md](DR-006.md) | Formato de objeto voxel | Funcional | Essencial | Proposto | incremento proposto |
| `DR-007` | [DR-007.md](DR-007.md) | Formato de mapa | Funcional | Essencial | Proposto | incremento proposto |

### Restrições de design (12)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `CR-001` | [CR-001.md](CR-001.md) | Stack Python e dependências | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-002` | [CR-002.md](CR-002.md) | OpenGL 3.3 Core e GLSL 330 | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-003` | [CR-003.md](CR-003.md) | Chunks 16³ e streaming em Y=0 | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-004` | [CR-004.md](CR-004.md) | Um token por execução | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-005` | [CR-005.md](CR-005.md) | Sem regras de RPG, IA ou multiplayer | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-006` | [CR-006.md](CR-006.md) | Vestuário restrito ao sistema Roblox | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-007` | [CR-007.md](CR-007.md) | Sem áudio | Restrição de Design | Opcional | Implementado | baseline implementado |
| `CR-008` | [CR-008.md](CR-008.md) | Catálogo de exemplo sem credencial | Restrição de Design | Desejável | Implementado | baseline implementado |
| `CR-009` | [CR-009.md](CR-009.md) | Licença MIT e assets de terceiros | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-010` | [CR-010.md](CR-010.md) | Modo editor aditivo | Restrição de Design | Essencial | Proposto | incremento proposto |
| `CR-011` | [CR-011.md](CR-011.md) | Formatos abertos e versionados | Restrição de Design | Essencial | Proposto | incremento proposto |
| `CR-012` | [CR-012.md](CR-012.md) | Sem ferramenta externa obrigatória | Restrição de Design | Essencial | Proposto | incremento proposto |

### Conformidade (4)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `SR-001` | [SR-001.md](SR-001.md) | Shaders com #version e GLSL 330 | Conformidade | Essencial | Verificado | baseline implementado |
| `SR-002` | [SR-002.md](SR-002.md) | Estrutura ISO/IEC/IEEE 29148 | Conformidade | Desejável | Implementado | baseline implementado |
| `SR-003` | [SR-003.md](SR-003.md) | Licença MIT | Conformidade | Essencial | Implementado | baseline implementado |
| `SR-004` | [SR-004.md](SR-004.md) | Especificação MagicaVoxel | Conformidade | Opcional | Proposto | incremento proposto |

### Atributos do sistema (12)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `AR-001` | [AR-001.md](AR-001.md) | Determinismo de geração e encaixe | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-002` | [AR-002.md](AR-002.md) | Fallback de roupa e HSR | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-003` | [AR-003.md](AR-003.md) | Invalidação de cache v37 | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-004` | [AR-004.md](AR-004.md) | Save atômico | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-005` | [AR-005.md](AR-005.md) | Falha de montagem mantém modelo | Confiabilidade | Essencial | Implementado | baseline implementado |
| `AR-006` | [AR-006.md](AR-006.md) | Portabilidade Windows/Linux/WSL | Portabilidade | Essencial | Implementado | baseline implementado |
| `AR-007` | [AR-007.md](AR-007.md) | Sem telemetria e rede limitada | Segurança | Essencial | Implementado | baseline implementado |
| `AR-008` | [AR-008.md](AR-008.md) | Credenciais em .env ignorado | Segurança | Essencial | Implementado | baseline implementado |
| `AR-009` | [AR-009.md](AR-009.md) | Lógica testável sem OpenGL | Manutenibilidade | Essencial | Verificado | baseline implementado |
| `AR-010` | [AR-010.md](AR-010.md) | Round-trip de objeto e mapa | Confiabilidade | Essencial | Proposto | incremento proposto |
| `AR-011` | [AR-011.md](AR-011.md) | Arquivo inválido recusado | Confiabilidade | Essencial | Proposto | incremento proposto |
| `AR-012` | [AR-012.md](AR-012.md) | Trabalho preservado em falha de gravação | Confiabilidade | Desejável | Proposto | incremento proposto |

## Como usar

1. Abra o arquivo do requisito pelo ID (`FR-012.md` para `FR-012`).
2. Leia a ficha: identificação, descrição, rastreabilidade, justificativa, Gherkin e conformidade.
3. Use o Gherkin como base do teste de aceitação e o campo "Casos de Teste Associados" para localizar a suíte existente.

## Manutenção

- Um requisito por arquivo: não junte dois comportamentos no mesmo arquivo.
- Ao mudar um requisito implementado, atualize o texto, o Gherkin e o teste associado.
- Ao promover um requisito proposto, troque `Proposto` por `Implementado` ou `Verificado` e registre o teste.
- O índice acima é a visão de navegação; o `INDICE.csv` é a versão para ferramentas.