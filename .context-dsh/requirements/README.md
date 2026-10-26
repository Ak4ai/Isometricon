# Requisitos atômicos — um arquivo por requisito

Esta pasta contém **108 fichas de requisito**, uma por arquivo, no formato do
`TEMPLATE_REQUISITO.md` (ISO/IEC/IEEE 29148:2018). Os arquivos mantêm o ID original
(`FR-001`, `EI-001`, …) e seguem a nomenclatura `REQ-<CATEGORIA>-<NNN>.md`.

- **78 requisitos do baseline implementado** (`requirements.md`), com status
  `Implementado`, `Verificado` ou `Implementado com falha conhecida`.
- **30 requisitos propostos** (`requirements-voxel-editor.md`), com status `Proposto`.

Conforme pedido, as fichas **não registram stakeholder nem versionamento**. A rastreabilidade é
feita por fonte, código/teste e documento de origem. Todas têm **critério de aceitação em
Gherkin**, método de verificação e checklist de conformidade com a norma.

## Resumo

| Origem | Quantidade |
|---|---:|
| Baseline implementado (`requirements.md`) | 78 |
| Incremento proposto (`requirements-voxel-editor.md`) | 30 |
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
| `FR` | Funcional | `REQ-FUNC-001.md` |
| `EI` | Interface externa | `REQ-INT-001.md` |
| `UR` | Usabilidade | `REQ-USA-001.md` |
| `PR` | Desempenho | `REQ-PERF-001.md` |
| `DR` | Dados | `REQ-DATA-001.md` |
| `CR` | Restrição de design | `REQ-CONS-001.md` |
| `SR` | Conformidade | `REQ-CONF-001.md` |
| `AR` | Atributo do sistema | `REQ-ATTR-001.md` |

## Índice


### Requisitos funcionais (50)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `FR-001` | [REQ-FUNC-001.md](REQ-FUNC-001.md) | Janela e contexto OpenGL | Funcional | Essencial | Implementado | baseline implementado |
| `FR-002` | [REQ-FUNC-002.md](REQ-FUNC-002.md) | Câmera isométrica ortográfica | Funcional | Essencial | Verificado | baseline implementado |
| `FR-003` | [REQ-FUNC-003.md](REQ-FUNC-003.md) | Modos de operação | Funcional | Essencial | Implementado | baseline implementado |
| `FR-004` | [REQ-FUNC-004.md](REQ-FUNC-004.md) | Geração determinística de terreno | Funcional | Essencial | Verificado | baseline implementado |
| `FR-005` | [REQ-FUNC-005.md](REQ-FUNC-005.md) | Cavernas tridimensionais | Funcional | Desejável | Verificado | baseline implementado |
| `FR-006` | [REQ-FUNC-006.md](REQ-FUNC-006.md) | Chunks e face culling | Funcional | Essencial | Verificado | baseline implementado |
| `FR-007` | [REQ-FUNC-007.md](REQ-FUNC-007.md) | Streaming de chunks | Funcional | Essencial | Verificado | baseline implementado |
| `FR-008` | [REQ-FUNC-008.md](REQ-FUNC-008.md) | Frustum culling | Funcional | Desejável | Verificado | baseline implementado |
| `FR-009` | [REQ-FUNC-009.md](REQ-FUNC-009.md) | Água | Funcional | Desejável | Verificado | baseline implementado |
| `FR-010` | [REQ-FUNC-010.md](REQ-FUNC-010.md) | Texturização de blocos | Funcional | Essencial | Verificado | baseline implementado |
| `FR-011` | [REQ-FUNC-011.md](REQ-FUNC-011.md) | Iluminação e modo subterrâneo | Funcional | Desejável | Implementado | baseline implementado |
| `FR-012` | [REQ-FUNC-012.md](REQ-FUNC-012.md) | Seleção de bloco por cursor | Funcional | Essencial | Verificado | baseline implementado |
| `FR-013` | [REQ-FUNC-013.md](REQ-FUNC-013.md) | Grade tática | Funcional | Essencial | Verificado | baseline implementado |
| `FR-014` | [REQ-FUNC-014.md](REQ-FUNC-014.md) | Destaque de bloco | Funcional | Desejável | Implementado | baseline implementado |
| `FR-015` | [REQ-FUNC-015.md](REQ-FUNC-015.md) | Movimento do token | Funcional | Essencial | Verificado | baseline implementado |
| `FR-016` | [REQ-FUNC-016.md](REQ-FUNC-016.md) | Colisão e gravidade | Funcional | Essencial | Verificado | baseline implementado |
| `FR-017` | [REQ-FUNC-017.md](REQ-FUNC-017.md) | Câmera acompanha o token | Funcional | Essencial | Verificado | baseline implementado |
| `FR-018` | [REQ-FUNC-018.md](REQ-FUNC-018.md) | Overlay de coordenadas | Funcional | Opcional | Implementado | baseline implementado |
| `FR-019` | [REQ-FUNC-019.md](REQ-FUNC-019.md) | Console de chat | Funcional | Essencial | Verificado | baseline implementado |
| `FR-020` | [REQ-FUNC-020.md](REQ-FUNC-020.md) | Comandos de customização e roupas | Funcional | Essencial | Implementado | baseline implementado |
| `FR-021` | [REQ-FUNC-021.md](REQ-FUNC-021.md) | Editor de personagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-022` | [REQ-FUNC-022.md](REQ-FUNC-022.md) | Rosto, olhos, boca e maquiagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-023` | [REQ-FUNC-023.md](REQ-FUNC-023.md) | Proporções do corpo | Funcional | Essencial | Verificado | baseline implementado |
| `FR-024` | [REQ-FUNC-024.md](REQ-FUNC-024.md) | Peças procedurais | Funcional | Desejável | Verificado | baseline implementado |
| `FR-025` | [REQ-FUNC-025.md](REQ-FUNC-025.md) | Raças | Funcional | Desejável | Verificado | baseline implementado |
| `FR-026` | [REQ-FUNC-026.md](REQ-FUNC-026.md) | Cabelo | Funcional | Essencial | Verificado | baseline implementado |
| `FR-027` | [REQ-FUNC-027.md](REQ-FUNC-027.md) | Vestir e encaixar roupas Roblox | Funcional | Essencial | Implementado | baseline implementado |
| `FR-028` | [REQ-FUNC-028.md](REQ-FUNC-028.md) | Ocultação de pele sob a roupa (HSR) | Funcional | Essencial | Verificado | baseline implementado |
| `FR-029` | [REQ-FUNC-029.md](REQ-FUNC-029.md) | Camadas, sapatos e extras | Funcional | Desejável | Implementado com falha conhecida | baseline implementado |
| `FR-030` | [REQ-FUNC-030.md](REQ-FUNC-030.md) | Animação esquelética | Funcional | Essencial | Verificado | baseline implementado |
| `FR-031` | [REQ-FUNC-031.md](REQ-FUNC-031.md) | Salvar e carregar personagem | Funcional | Essencial | Verificado | baseline implementado |
| `FR-032` | [REQ-FUNC-032.md](REQ-FUNC-032.md) | Automação por linha de comando | Funcional | Desejável | Implementado | baseline implementado |
| `FR-033` | [REQ-FUNC-033.md](REQ-FUNC-033.md) | Diagnóstico de versão e sincronização | Funcional | Opcional | Verificado | baseline implementado |
| `FR-034` | [REQ-FUNC-034.md](REQ-FUNC-034.md) | Catálogo e miniaturas do editor | Funcional | Desejável | Implementado | baseline implementado |
| `FR-035` | [REQ-FUNC-035.md](REQ-FUNC-035.md) | Modo editor de mapa e objetos | Funcional | Essencial | Proposto | incremento proposto |
| `FR-036` | [REQ-FUNC-036.md](REQ-FUNC-036.md) | Edição de voxels | Funcional | Essencial | Proposto | incremento proposto |
| `FR-037` | [REQ-FUNC-037.md](REQ-FUNC-037.md) | Cor por voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-038` | [REQ-FUNC-038.md](REQ-FUNC-038.md) | Textura individual por voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-039` | [REQ-FUNC-039.md](REQ-FUNC-039.md) | Tamanho do volume de edição | Funcional | Essencial | Proposto | incremento proposto |
| `FR-040` | [REQ-FUNC-040.md](REQ-FUNC-040.md) | Plataforma renderizada por shader | Funcional | Essencial | Proposto | incremento proposto |
| `FR-041` | [REQ-FUNC-041.md](REQ-FUNC-041.md) | Formato e exportação de objeto voxel | Funcional | Essencial | Proposto | incremento proposto |
| `FR-042` | [REQ-FUNC-042.md](REQ-FUNC-042.md) | Colocar objeto no mundo isométrico | Funcional | Essencial | Proposto | incremento proposto |
| `FR-043` | [REQ-FUNC-043.md](REQ-FUNC-043.md) | Biblioteca de objetos | Funcional | Desejável | Proposto | incremento proposto |
| `FR-044` | [REQ-FUNC-044.md](REQ-FUNC-044.md) | Criar e editar mapa | Funcional | Essencial | Proposto | incremento proposto |
| `FR-045` | [REQ-FUNC-045.md](REQ-FUNC-045.md) | Salvar e carregar mapa | Funcional | Essencial | Proposto | incremento proposto |
| `FR-046` | [REQ-FUNC-046.md](REQ-FUNC-046.md) | Desfazer e refazer | Funcional | Desejável | Proposto | incremento proposto |
| `FR-047` | [REQ-FUNC-047.md](REQ-FUNC-047.md) | Selecionar e transformar objetos | Funcional | Desejável | Proposto | incremento proposto |
| `FR-048` | [REQ-FUNC-048.md](REQ-FUNC-048.md) | Feedback visual do editor | Funcional | Essencial | Proposto | incremento proposto |
| `FR-049` | [REQ-FUNC-049.md](REQ-FUNC-049.md) | Exportar e importar MagicaVoxel (opcional) | Funcional | Opcional | Proposto | incremento proposto |
| `FR-050` | [REQ-FUNC-050.md](REQ-FUNC-050.md) | Geração procedural por regras (opcional) | Funcional | Opcional | Proposto | incremento proposto |

### Interfaces externas (6)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `EI-001` | [REQ-INT-001.md](REQ-INT-001.md) | Teclado e mouse | Funcional | Essencial | Implementado | baseline implementado |
| `EI-002` | [REQ-INT-002.md](REQ-INT-002.md) | Vídeo | Funcional | Essencial | Implementado | baseline implementado |
| `EI-003` | [REQ-INT-003.md](REQ-INT-003.md) | Sistema de arquivos | Funcional | Essencial | Implementado | baseline implementado |
| `EI-004` | [REQ-INT-004.md](REQ-INT-004.md) | GitHub | Funcional | Essencial | Implementado | baseline implementado |
| `EI-005` | [REQ-INT-005.md](REQ-INT-005.md) | Roblox | Funcional | Essencial | Implementado | baseline implementado |
| `EI-006` | [REQ-INT-006.md](REQ-INT-006.md) | Linha de comando | Funcional | Essencial | Implementado | baseline implementado |

### Usabilidade (7)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `UR-001` | [REQ-USA-001.md](REQ-USA-001.md) | Controles de teclado e mouse | Usabilidade | Essencial | Implementado | baseline implementado |
| `UR-002` | [REQ-USA-002.md](REQ-USA-002.md) | Feedback de comandos | Usabilidade | Essencial | Verificado | baseline implementado |
| `UR-003` | [REQ-USA-003.md](REQ-USA-003.md) | Autocompletar e ajuda | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-004` | [REQ-USA-004.md](REQ-USA-004.md) | Idioma e apelidos | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-005` | [REQ-USA-005.md](REQ-USA-005.md) | Editor: seleção, rolagem e arraste | Usabilidade | Desejável | Verificado | baseline implementado |
| `UR-006` | [REQ-USA-006.md](REQ-USA-006.md) | Barra de ferramentas e atalhos | Usabilidade | Essencial | Proposto | incremento proposto |
| `UR-007` | [REQ-USA-007.md](REQ-USA-007.md) | Prévia de cor e textura | Usabilidade | Desejável | Proposto | incremento proposto |

### Desempenho (10)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `PR-001` | [REQ-PERF-001.md](REQ-PERF-001.md) | Upload e liberação amortizados | Performance | Essencial | Verificado | baseline implementado |
| `PR-002` | [REQ-PERF-002.md](REQ-PERF-002.md) | Geração de chunks em segundo plano | Performance | Essencial | Verificado | baseline implementado |
| `PR-003` | [REQ-PERF-003.md](REQ-PERF-003.md) | Montagem do personagem em segundo plano | Performance | Essencial | Verificado | baseline implementado |
| `PR-004` | [REQ-PERF-004.md](REQ-PERF-004.md) | Skinning na GPU | Performance | Desejável | Implementado | baseline implementado |
| `PR-005` | [REQ-PERF-005.md](REQ-PERF-005.md) | Grade em uma chamada e por revisão | Performance | Desejável | Verificado | baseline implementado |
| `PR-006` | [REQ-PERF-006.md](REQ-PERF-006.md) | Limites de raycast e colisão | Performance | Essencial | Verificado | baseline implementado |
| `PR-007` | [REQ-PERF-007.md](REQ-PERF-007.md) | Raio de streaming de 25 colunas | Performance | Essencial | Verificado | baseline implementado |
| `PR-008` | [REQ-PERF-008.md](REQ-PERF-008.md) | Resposta de edição no quadro seguinte | Performance | Essencial | Proposto | incremento proposto |
| `PR-009` | [REQ-PERF-009.md](REQ-PERF-009.md) | Plataforma e objeto em poucas chamadas | Performance | Essencial | Proposto | incremento proposto |
| `PR-010` | [REQ-PERF-010.md](REQ-PERF-010.md) | Colocação multi-chunk sem travar | Performance | Desejável | Proposto | incremento proposto |

### Dados (7)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `DR-001` | [REQ-DATA-001.md](REQ-DATA-001.md) | Save do personagem em JSON | Funcional | Essencial | Verificado | baseline implementado |
| `DR-002` | [REQ-DATA-002.md](REQ-DATA-002.md) | Cache de roupa e sidecars | Funcional | Essencial | Verificado | baseline implementado |
| `DR-003` | [REQ-DATA-003.md](REQ-DATA-003.md) | Assets de roupa por ID | Funcional | Essencial | Verificado | baseline implementado |
| `DR-004` | [REQ-DATA-004.md](REQ-DATA-004.md) | Sem persistência de mundo no modo atual | Funcional | Essencial | Implementado | baseline implementado |
| `DR-005` | [REQ-DATA-005.md](REQ-DATA-005.md) | Miniaturas do catálogo | Funcional | Opcional | Implementado | baseline implementado |
| `DR-006` | [REQ-DATA-006.md](REQ-DATA-006.md) | Formato de objeto voxel | Funcional | Essencial | Proposto | incremento proposto |
| `DR-007` | [REQ-DATA-007.md](REQ-DATA-007.md) | Formato de mapa | Funcional | Essencial | Proposto | incremento proposto |

### Restrições de design (12)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `CR-001` | [REQ-CONS-001.md](REQ-CONS-001.md) | Stack Python e dependências | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-002` | [REQ-CONS-002.md](REQ-CONS-002.md) | OpenGL 3.3 Core e GLSL 330 | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-003` | [REQ-CONS-003.md](REQ-CONS-003.md) | Chunks 16³ e streaming em Y=0 | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-004` | [REQ-CONS-004.md](REQ-CONS-004.md) | Um token por execução | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-005` | [REQ-CONS-005.md](REQ-CONS-005.md) | Sem regras de RPG, IA ou multiplayer | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-006` | [REQ-CONS-006.md](REQ-CONS-006.md) | Vestuário restrito ao sistema Roblox | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-007` | [REQ-CONS-007.md](REQ-CONS-007.md) | Sem áudio | Restrição de Design | Opcional | Implementado | baseline implementado |
| `CR-008` | [REQ-CONS-008.md](REQ-CONS-008.md) | Catálogo de exemplo sem credencial | Restrição de Design | Desejável | Implementado | baseline implementado |
| `CR-009` | [REQ-CONS-009.md](REQ-CONS-009.md) | Licença MIT e assets de terceiros | Restrição de Design | Essencial | Implementado | baseline implementado |
| `CR-010` | [REQ-CONS-010.md](REQ-CONS-010.md) | Modo editor aditivo | Restrição de Design | Essencial | Proposto | incremento proposto |
| `CR-011` | [REQ-CONS-011.md](REQ-CONS-011.md) | Formatos abertos e versionados | Restrição de Design | Essencial | Proposto | incremento proposto |
| `CR-012` | [REQ-CONS-012.md](REQ-CONS-012.md) | Sem ferramenta externa obrigatória | Restrição de Design | Essencial | Proposto | incremento proposto |

### Conformidade (4)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `SR-001` | [REQ-CONF-001.md](REQ-CONF-001.md) | Shaders com #version e GLSL 330 | Conformidade | Essencial | Verificado | baseline implementado |
| `SR-002` | [REQ-CONF-002.md](REQ-CONF-002.md) | Estrutura ISO/IEC/IEEE 29148 | Conformidade | Desejável | Implementado | baseline implementado |
| `SR-003` | [REQ-CONF-003.md](REQ-CONF-003.md) | Licença MIT | Conformidade | Essencial | Implementado | baseline implementado |
| `SR-004` | [REQ-CONF-004.md](REQ-CONF-004.md) | Especificação MagicaVoxel | Conformidade | Opcional | Proposto | incremento proposto |

### Atributos do sistema (12)

| ID | Arquivo | Nome | Tipo | Prioridade | Status | Origem |
|---|---|---|---|---|---|---|
| `AR-001` | [REQ-ATTR-001.md](REQ-ATTR-001.md) | Determinismo de geração e encaixe | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-002` | [REQ-ATTR-002.md](REQ-ATTR-002.md) | Fallback de roupa e HSR | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-003` | [REQ-ATTR-003.md](REQ-ATTR-003.md) | Invalidação de cache v37 | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-004` | [REQ-ATTR-004.md](REQ-ATTR-004.md) | Save atômico | Confiabilidade | Essencial | Verificado | baseline implementado |
| `AR-005` | [REQ-ATTR-005.md](REQ-ATTR-005.md) | Falha de montagem mantém modelo | Confiabilidade | Essencial | Implementado | baseline implementado |
| `AR-006` | [REQ-ATTR-006.md](REQ-ATTR-006.md) | Portabilidade Windows/Linux/WSL | Portabilidade | Essencial | Implementado | baseline implementado |
| `AR-007` | [REQ-ATTR-007.md](REQ-ATTR-007.md) | Sem telemetria e rede limitada | Segurança | Essencial | Implementado | baseline implementado |
| `AR-008` | [REQ-ATTR-008.md](REQ-ATTR-008.md) | Credenciais em .env ignorado | Segurança | Essencial | Implementado | baseline implementado |
| `AR-009` | [REQ-ATTR-009.md](REQ-ATTR-009.md) | Lógica testável sem OpenGL | Manutenibilidade | Essencial | Verificado | baseline implementado |
| `AR-010` | [REQ-ATTR-010.md](REQ-ATTR-010.md) | Round-trip de objeto e mapa | Confiabilidade | Essencial | Proposto | incremento proposto |
| `AR-011` | [REQ-ATTR-011.md](REQ-ATTR-011.md) | Arquivo inválido recusado | Confiabilidade | Essencial | Proposto | incremento proposto |
| `AR-012` | [REQ-ATTR-012.md](REQ-ATTR-012.md) | Trabalho preservado em falha de gravação | Confiabilidade | Desejável | Proposto | incremento proposto |

## Como usar

1. Abra o arquivo do requisito pelo ID (`REQ-FUNC-012.md` para `FR-012`).
2. Leia a ficha: identificação, descrição, rastreabilidade, justificativa, Gherkin e conformidade.
3. Use o Gherkin como base do teste de aceitação e o campo "Casos de Teste Associados" para localizar a suíte existente.

## Manutenção

- Um requisito por arquivo: não junte dois comportamentos no mesmo arquivo.
- Ao mudar um requisito implementado, atualize o texto, o Gherkin e o teste associado.
- Ao promover um requisito proposto, troque `Proposto` por `Implementado` ou `Verificado` e registre o teste.
- O índice acima é a visão de navegação; o `INDICE.csv` é a versão para ferramentas.