# requirements-voxel-editor — Incremento: editor de mapa e objetos voxel

> **Norma de referência:** ISO/IEC/IEEE 29148:2018
> **Projeto:** Isometricon
> **Baseline:** `requirements.md` (commit `0b5c1fe`)
> **Branch:** `feat/requirements-voxel-editor`
> **Natureza:** requisitos **propostos**; nada desta lista está implementado no baseline
> **Data:** 21/10/2026

> **Versão atômica:** cada requisito deste incremento também está em
> `.context-dsh/requirements/` (`REQ-FUNC-035.md` … `REQ-FUNC-050.md` e afins), com ficha completa
> e Gherkin. Índice em `.context-dsh/requirements/README.md`.

Este documento é um **incremento** de `requirements.md`. Ele não repete os requisitos atuais:
referencia os IDs existentes e adiciona apenas o que falta para o editor de mapa/objetos voxel.
Todos os requisitos novos têm status **Proposto** e IDs que continuam as faixas existentes
(`FR-035` em diante, `PR-008` em diante etc.).

Conforme o pedido, não há stakeholder nem versionamento de documento.

---

## 1. Contexto e objetivo

### 1.1 Pedido que originou o incremento

Texto recebido (21/10/2026):

> “UI trocar cor e textura, shaders renderizar a plataforma, criar objetos voxels poder exportar
> os objetos voxel pro mundo isometrico. Ex.: Cria uma casa em voxel e coloca no isometric.”
>
> “customiza o tamanho do grid, cores dos cubos e texturas individuais”
>
> “a ideia é ser um editor de mapa / objeto que da pra ou criar o mapa ou inputar casas
> construções etc na vibe do jogo Replicube”

Interpretação adotada:

1. Um **modo editor** novo, separado do editor de personagem e do modo terreno atual.
2. Um **editor de objetos voxel** com paleta de cores e texturas por voxel.
3. Uma **plataforma** de edição desenhada por shader (superfície + grade + borda + feedback),
   não apenas o grid de linhas atual.
4. **Exportar** o objeto criado e **colocá-lo no mundo isométrico** (ex.: uma casa).
5. Um **editor de mapa** que aceita objetos prontos e/ou criados no próprio editor.
6. **Tamanho do grid** configurável e **materiais individuais** por cubo.

### 1.2 Pesquisa: o que é o Replicube e o que foi aproveitado

O Replicube é um “programming puzzle game/toy” de 2025, da Walaber Entertainment, sobre escrever
código para replicar objetos 3D feitos de voxels. Ele tem um **editor voxel em modo livre**, no
qual cada voxel tem coordenadas XYZ e um código de cor (16 cores + vazio), exporta os objetos
gerados para o formato **MagicaVoxel** e permite compartilhar criações na comunidade. A linguagem
usada é Lua; o jogo também tem um editor 2D de imagens e leaderboards.

Fontes consultadas:

- [Página oficial do Replicube](http://www.walaber.com/replicube)
- [Replicube na Steam](https://store.steampowered.com/app/3401490/Replicube/)
- [Press kit do Replicube](http://www.walaber.com/replicube-press-kit)
- [Famitsu — matéria sobre o Replicube](https://www.famitsu.com/article/202505/41415)

O que este incremento **aproveita** da referência:

| Ideia do Replicube | Como entra aqui |
|---|---|
| Modo livre de edição voxel | FR-035, FR-036 |
| Paleta pequena de cores + vazio | FR-037 |
| Exportação para ferramenta externa | FR-041, FR-049 (MagicaVoxel, opcional) |
| Feedback visual imediato | FR-040, FR-048 |
| Criação procedural por regras/código | FR-050 (opcional, não é o núcleo) |

O que **não** entra: puzzles, leaderboards, fórum/comunidade online, runtime Lua, editor 2D de
imagens e formato `.vox` como formato nativo obrigatório. O Isometricon é um editor de tabuleiro
isométrico, não um jogo de programação.

Diferença central em relação ao Replicube: lá o voxel tem **cor**; aqui ele precisa aceitar
**cor e textura**, e o objeto precisa ser **inserido num mundo isométrico existente**, com grade
tática, colisão e streaming (FR-006, FR-007, FR-013, FR-016).

### 1.3 Escopo

**Dentro do escopo deste incremento:**

- modo editor de mapa/objetos;
- edição de voxels (colocar, remover, pintar);
- paleta de cores e biblioteca de texturas por voxel;
- dimensões configuráveis do volume de edição;
- plataforma renderizada por shader;
- formato de objeto voxel e exportação;
- colocação de objetos no mundo (posição, rotação, encaixe, prévia);
- biblioteca de objetos;
- criação, salvamento e carregamento de mapa;
- desfazer/refazer, seleção e transformação de objetos;
- feedback visual do editor;
- interoperabilidade opcional com MagicaVoxel;
- geração procedural opcional por regras.

**Fora do escopo:**

- regras de RPG (fichas, turnos, dados) — continua fora (CR-005);
- multiplayer e compartilhamento online;
- edição de personagem/roupas — continua em FR-021 a FR-031;
- animação dentro do editor;
- importação de modelos 3D que não sejam voxels;
- editor 2D de imagens;
- script Lua embutido.

---

## 2. Relação com os requisitos atuais

### 2.1 Requisitos existentes reutilizados

| Requisito atual | Como o incremento usa |
|---|---|
| FR-001 (janela/GL) | O editor roda na mesma janela e contexto. |
| FR-002 (câmera) | A plataforma e os objetos usam a câmera isométrica existente. |
| FR-003 (modos) | Novo modo de execução, ao lado de `--terrain` e `--char`. |
| FR-006 (chunks/mesher) | A geometria do objeto é convertida em malha pelo mesmo pipeline. |
| FR-007 (streaming) | Objetos colocados precisam entrar/sair com os chunks. |
| FR-010 (atlas) | A biblioteca de texturas parte do atlas atual e o estende. |
| FR-011 (iluminação) | Objetos e plataforma recebem a mesma iluminação. |
| FR-012 (picking) | Seleção de voxels/objetos usa o raycast atual. |
| FR-013 (grade tática) | A grade tática continua existindo; a plataforma é uma superfície adicional. |
| FR-016 (colisão) | Objetos colocados passam a bloquear/ sustentar o token. |
| FR-019/FR-021 (chat/editor) | Padrões de UI, mouse e comandos são reaproveitados. |
| FR-031 (save) | O padrão de gravação atômica é reaproveitado. |
| FR-034 (catálogo) | O padrão de catálogo com miniaturas é reaproveitado para objetos. |
| FR-028 (HSR undo) | O padrão de desfazer/refazer existente inspira FR-046. |

### 2.2 Conflitos e extensões conscientes

| Requisito atual | Efeito do incremento |
|---|---|
| DR-004 (“não persistir o mundo”) | Continua valendo para o modo terreno; o modo editor introduz mapa persistente (FR-045). A implementação deve declarar se o modo terreno também passa a abrir mapas. |
| FR-010 / atlas de 12 tiles | O atlas atual é fixo por `BlockType`. FR-037/FR-038 exigem materiais por voxel; o atlas pode ser estendido ou complementado por uma tabela de materiais, sem quebrar os 12 tiles existentes. |
| FR-006 / chunk `uint8` | O chunk atual guarda só o tipo. Objetos com cor/textura exigem dados adicionais; a extensão deve preservar o comportamento de terreno descrito em FR-004 a FR-009. |
| CR-003 (“streaming só em Y=0”) | Objetos podem ocupar vários chunks e alturas; FR-042 exige que a colocação atualize todos os chunks afetados. |
| CR-004 (um token) | Não muda; o editor não adiciona tokens. |
| CR-005 (sem regras de RPG) | Não muda; o editor é ferramenta de autoria. |
| FR-013 (grade de linhas) | A plataforma (FR-040) é uma superfície shader; a grade tática continua sendo a política de células de `surface.py`. |

---

## 3. Análise de lacunas

| Capacidade | Hoje | Lacuna para o pedido |
|---|---|---|
| Editar voxels | Só o terreno é gerado; não há ferramenta de colocação/remoção. | FR-036 |
| Cor por voxel | Cor vem do `BlockType`/atlas; não há cor arbitrária por célula. | FR-037 |
| Textura por voxel | Atlas fixo de 12 tiles por tipo/face. | FR-038 |
| Tamanho do grid | `Chunk3D.SIZE = 16` fixo; grade tática é derivada do mundo. | FR-039 |
| Plataforma | Apenas `GL_LINES` da grade tática. | FR-040 |
| Objeto voxel | Não existe estrutura de objeto, formato nem exportação. | FR-041 |
| Colocar construção | Não existe placement, prévia nem biblioteca. | FR-042, FR-043 |
| Mapa | Terreno é procedural e não persistido. | FR-044, FR-045 |
| Histórico de edição | Só o HSR tem desfazer/refazer. | FR-046 |
| Seleção/transformação | Só hover/clique que imprime bloco. | FR-047 |
| UI de editor de mapa | Existe só o editor de personagem. | FR-049, UR-006 |

---

## 4. Requisitos funcionais propostos

> Todos com status **Proposto**. A verificação será por testes a criar e demonstração; nenhum
> teste desta seção existe no baseline.

### FR-035 — Modo editor de mapa e objetos

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O sistema deve oferecer um modo de execução dedicado ao editor de mapa e objetos, selecionável por linha de comando e por ação de interface do usuário, no qual o usuário cria, abre e salva um projeto de mapa sem iniciar a partida. |
| Condições | Aplicação iniciada; modo editor solicitado; projeto novo ou existente. |
| Verificação | Teste de integração (a criar) para entrada/saída do modo; demonstração. |
| Critério de aceitação | O modo editor abre com plataforma, painel e barra de ferramentas; ao sair, o modo anterior continua funcional; nenhum comando do editor altera o personagem. |
| Depende de | FR-003, FR-019, FR-021, FR-031 |
| Impacto | `src/main.py` (novo modo), novo pacote de editor, UI própria; o editor de personagem permanece separado. |

### FR-036 — Edição de voxels

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve permitir colocar, remover e pintar voxels em um volume de edição, com ferramenta ativa, tamanho de pincel de 1 a 8 voxels e indicação visual da célula sob o cursor. |
| Condições | Modo editor; plataforma visível; ferramenta de construção, remoção ou pintura selecionada. |
| Verificação | Teste unitário do modelo de edição (a criar); teste de integração de colocação/remoção; demonstração. |
| Critério de aceitação | Colocar cria um voxel na célula indicada; remover esvazia a célula; pintar altera apenas a célula atingida; o pincel maior afeta o bloco de células ao redor do centro; arrastar aplica a ferramenta de forma contínua. |
| Depende de | FR-006, FR-012, FR-040 |
| Impacto | Novo modelo de edição; raycast atual para a célula; malha do objeto atualizada por edição. |

### FR-037 — Cor por voxel

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve permitir atribuir a cada voxel uma cor escolhida de uma paleta com pelo menos 16 cores nomeadas, além de cor livre em formato hexadecimal, e recoloriar voxels existentes sem alterar sua geometria. |
| Condições | Ferramenta de pintura ou de atributo de cor ativa; paleta aberta; voxel existente ou novo. |
| Verificação | Teste unitário de paleta e de atribuição (a criar); demonstração visual. |
| Critério de aceitação | A cor escolhida aparece no voxel no mesmo quadro; trocar de cor não move o voxel; a paleta guarda as cores usadas recentemente; cor inválida é rejeitada com mensagem. |
| Depende de | FR-036, FR-038, FR-040 |
| Impacto | Novo atributo de material por voxel; renderização e serialização. |

### FR-038 — Textura individual por voxel

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve permitir atribuir a cada voxel uma textura de uma biblioteca de texturas, de modo que dois voxels da mesma cor possam exibir texturas diferentes e que a textura escolhida seja preservada ao exportar e ao colocar o objeto no mundo. |
| Condições | Ferramenta de textura ativa; biblioteca carregada; voxel existente ou novo. |
| Verificação | Teste unitário de atribuição e serialização (a criar); demonstração. |
| Critério de aceitação | Texturas distintas aparecem em voxels vizinhos; a textura sobrevive ao salvar, exportar e importar; voxel sem textura usa a cor sólida; textura ausente cai em uma textura padrão visível. |
| Depende de | FR-010, FR-036, FR-037 |
| Impacto | Atlas/tabela de materiais; mesher precisa emitir UV e material por voxel; textura adicional no shader. |

### FR-039 — Tamanho do volume de edição

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve permitir definir as dimensões X, Y e Z do volume de edição dentro de limites declarados, exibir o volume delimitado na plataforma e preservar os voxels existentes que couberem no novo tamanho. |
| Condições | Projeto novo ou existente; painel de configurações do grid aberto. |
| Verificação | Teste unitário de redimensionamento (a criar); demonstração. |
| Critério de aceitação | Alterar as dimensões atualiza a plataforma e os limites; voxels dentro do novo volume permanecem; voxels fora são informados e não são apagados sem confirmação; dimensão inválida é rejeitada. |
| Depende de | FR-013, FR-040, FR-045 |
| Impacto | Modelo de projeto com dimensões próprias; não confundir com `Chunk3D.SIZE = 16`. |

### FR-040 — Plataforma renderizada por shader

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve renderizar a plataforma de edição por um passe GLSL dedicado, com superfície, grade de espaçamento configurável, borda do volume, realce da célula sob o cursor e transparência, em vez de depender apenas das linhas de grade atuais. |
| Condições | Modo editor; câmera isométrica; volume de edição definido. |
| Verificação | Inspeção do shader e do passe de renderização; demonstração visual; teste de que a grade acompanha zoom/pan/rotação. |
| Critério de aceitação | A plataforma aparece como superfície contínua sob os voxels; a grade acompanha a câmera sem desalinhar; a célula sob o cursor é realçada; a borda delimita o volume; a plataforma respeita profundidade em relação aos objetos. |
| Depende de | FR-002, FR-010, FR-011, FR-013 |
| Impacto | Novo par de shaders (`platform.vert/frag`) e um renderizador de plataforma; a grade tática existente pode continuar como camada separada. |

### FR-041 — Formato e exportação de objeto voxel

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O sistema deve salvar e exportar um objeto voxel em um formato aberto e documentado que preserve dimensões, voxels vazios, cor, textura e metadados do objeto, com gravação atômica e recusa de arquivos inválidos. |
| Condições | Objeto em edição; comando de salvar ou exportar; caminho de destino. |
| Verificação | Teste de round-trip (a criar); teste de arquivo corrompido; inspeção do formato documentado. |
| Critério de aceitação | Salvar e reabrir reproduz o mesmo objeto; exportar e importar reproduz dimensões, cores e texturas; arquivo inválido é rejeitado sem apagar o objeto em memória; o formato tem identificador e versão. |
| Depende de | FR-036, FR-037, FR-038, DR-006 |
| Impacto | Novo módulo de serialização de objeto; formato JSON (legível) e, se necessário, carga binária opcional. |

### FR-042 — Colocar objeto no mundo isométrico

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O sistema deve permitir escolher um objeto voxel e colocá-lo no mundo isométrico em uma posição da grade, com prévia visual, encaixe na superfície, rotação em passos de 90° e confirmação ou cancelamento antes de efetivar. |
| Condições | Mundo carregado; objeto disponível na biblioteca ou recém-criado; ferramenta de colocação ativa. |
| Verificação | Teste de integração (a criar): colocar uma casa, confirmar, salvar e reabrir; demonstração. |
| Critério de aceitação | A prévia acompanha o cursor e indica posição válida ou inválida; confirmar grava o objeto no mapa; cancelar não altera o mapa; a rotação muda o objeto em 90°; a colocação atualiza todos os chunks afetados; o token passa a colidir com os voxels colocados. |
| Depende de | FR-007, FR-012, FR-013, FR-016, FR-041 |
| Impacto | Objetos podem ocupar vários chunks; é preciso remalhar os chunks afetados e atualizar colisão/grid. |

### FR-043 — Biblioteca de objetos

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Proposto |
| Requisito | O editor deve listar os objetos disponíveis com nome, miniatura e categoria, permitir importar um objeto de arquivo, duplicar e excluir objetos, e manter a lista atualizada após salvar um objeto novo. |
| Condições | Modo editor; diretório de objetos acessível. |
| Verificação | Teste unitário do catálogo (a criar); demonstração. |
| Critério de aceitação | Objeto novo aparece na lista sem reiniciar; miniatura ausente é gerada ou substituída por marcador; importar arquivo válido adiciona o objeto; excluir pede confirmação. |
| Depende de | FR-034, FR-041 |
| Impacto | Reaproveita o padrão de catálogo/miniaturas do editor de personagem; novo diretório de objetos. |

### FR-044 — Criar e editar mapa

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve permitir criar um mapa novo, definir suas dimensões e seu terreno base, posicionar objetos e construir voxels diretamente no mapa, e remover objetos ou construções existentes. |
| Condições | Modo editor; projeto de mapa aberto. |
| Verificação | Teste de integração (a criar); demonstração com uma casa e um trecho de terreno. |
| Critério de aceitação | Um mapa novo abre vazio ou com terreno base; colocar/remover objetos altera apenas o mapa; construir voxels no mapa é possível; remover um objeto restaura os voxels anteriores do terreno. |
| Depende de | FR-035, FR-036, FR-042, FR-045 |
| Impacto | Modelo de mapa separado do gerador procedural; decisão sobre como representar terreno editado. |

### FR-045 — Salvar e carregar mapa

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve salvar e carregar um mapa em arquivo próprio, com versão, dimensões, terreno base e lista de objetos com posição e rotação, usando gravação atômica e validação na leitura. |
| Condições | Projeto de mapa aberto; comando de salvar/carregar; caminho de arquivo. |
| Verificação | Teste de round-trip (a criar); teste de arquivo corrompido; demonstração. |
| Critério de aceitação | Salvar e reabrir reproduz o mapa; o mapa carregado pode ser jogado no modo terreno; arquivo de versão desconhecida é recusado com mensagem; interrupção da gravação não deixa arquivo parcial. |
| Depende de | FR-031 (padrão atômico), FR-044, DR-007 |
| Impacto | Novo formato de mapa; possível reutilização do `WorldManager` para carregar chunks prontos. |

### FR-046 — Desfazer e refazer

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Proposto |
| Requisito | O editor deve manter um histórico de pelo menos 50 operações de edição e permitir desfazer e refazer por atalho de teclado e por botões visíveis. |
| Condições | Modo editor; pelo menos uma operação realizada. |
| Verificação | Teste unitário de histórico (a criar); demonstração. |
| Critério de aceitação | Desfazer reverte a última operação; refazer reaplica; uma nova operação após desfazer descarta o ramo refeito; o histórico inclui colocação, remoção, pintura, cor, textura, tamanho do grid e transformação de objeto. |
| Depende de | FR-036, FR-037, FR-038, FR-047 |
| Impacto | Padrão semelhante ao histórico de HSR (FR-028), mas para operações de mapa. |

### FR-047 — Selecionar e transformar objetos

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Proposto |
| Requisito | O editor deve permitir selecionar um objeto colocado por clique, exibir sua caixa delimitadora e movê-lo, rotacioná-lo em 90°, duplicá-lo e excluí-lo, mantendo o resultado no mapa salvo. |
| Condições | Modo editor; objeto colocado no mapa. |
| Verificação | Teste de integração (a criar); demonstração. |
| Critério de aceitação | O objeto selecionado é destacado; mover atualiza a posição; rotacionar gira o objeto; duplicar cria uma cópia independente; excluir remove o objeto e libera as células; todas as operações entram no histórico. |
| Depende de | FR-012, FR-042, FR-046 |
| Impacto | Seleção de objeto por AABB/raycast; transformação e persistência. |

### FR-048 — Feedback visual do editor

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Proposto |
| Requisito | O editor deve exibir, durante a edição, a célula sob o cursor, a posição em coordenadas, a ferramenta ativa, o material ativo, os limites do volume e a validade da colocação de um objeto, com distinção visual entre prévia válida e inválida. |
| Condições | Modo editor; cursor sobre a plataforma ou sobre um objeto. |
| Verificação | Demonstração; teste de estado da prévia (a criar). |
| Critério de aceitação | O cursor mostra a célula e as coordenadas; a ferramenta e o material ativos são visíveis no painel; a prévia válida e a inválida têm cores distintas; a colocação fora dos limites é recusada com indicação. |
| Depende de | FR-014, FR-040, UR-006 |
| Impacto | Reaproveita highlight/HUD; nova camada de prévia. |

### FR-049 — Exportar e importar MagicaVoxel (opcional)

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Opcional |
| Status | Proposto |
| Requisito | O sistema deve poder exportar um objeto voxel para o formato MagicaVoxel `.vox` e importar um arquivo `.vox`, preservando dimensões, posições e cores da paleta suportada. |
| Condições | Objeto voxel válido; arquivo `.vox` acessível; funcionalidade habilitada. |
| Verificação | Teste de round-trip com arquivo de referência (a criar); demonstração. |
| Critério de aceitação | Um objeto exportado abre em ferramenta compatível com MagicaVoxel; a importação reproduz dimensões e cores; texturas (não suportadas pelo `.vox`) são substituídas por cor sólida e o usuário é avisado. |
| Depende de | FR-041 |
| Impacto | Implementação do formato aberto MagicaVoxel; sem dependência de runtime externo. |

### FR-050 — Geração procedural por regras (opcional)

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Opcional |
| Status | Proposto |
| Requisito | O editor deve permitir gerar voxels de um objeto a partir de regras declarativas simples por coordenada, com prévia antes de aplicar, inspirado no modo de criação por código do Replicube, sem exigir runtime de linguagem externa. |
| Condições | Modo editor; funcionalidade habilitada; expressão/regra válida. |
| Verificação | Teste unitário do interpretador de regras (a criar); demonstração. |
| Critério de aceitação | Uma regra que associa cor a uma condição de X, Y e Z produz o objeto esperado; erro de sintaxe é mostrado sem alterar o objeto; a prévia pode ser aplicada ou descartada; o resultado vira um objeto normal, editável e exportável. |
| Depende de | FR-036, FR-037, FR-041 |
| Impacto | Pequeno interpretador de expressões; não é o núcleo do incremento e pode ser cortado sem afetar os demais requisitos. |

---

## 5. Requisitos não funcionais propostos

### 5.1 Desempenho

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| PR-008 | Uma operação de colocação, remoção ou pintura em um objeto de até 32³ voxels deve aparecer na tela no quadro seguinte à ação. | Essencial | Proposto | Teste de tempo (a criar); demonstração. |
| PR-009 | A plataforma deve ser desenhada em uma única chamada de desenho e os voxels do objeto devem ser desenhados em malha agrupada, sem uma chamada por voxel. | Essencial | Proposto | Inspeção de draw calls; teste com captura de contadores (a criar). |
| PR-010 | A colocação de um objeto que ocupa vários chunks deve atualizar apenas os chunks afetados e não bloquear o laço de renderização por mais de um quadro. | Desejável | Proposto | Teste de integração e medição (a criar). |

### 5.2 Usabilidade

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| UR-006 | O editor deve oferecer barra de ferramentas com ferramenta ativa, paleta de cores, biblioteca de texturas, controle de dimensões do grid e comandos de salvar, exportar e desfazer, acessíveis por mouse e por atalho de teclado. | Essencial | Proposto | Inspeção de UI; teste de interação (a criar). |
| UR-007 | A escolha de cor e de textura deve mostrar prévia do material no voxel antes de aplicar e indicar o material ativo no painel. | Desejável | Proposto | Teste de UI (a criar); demonstração. |

### 5.3 Dados

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| DR-006 | O formato de objeto voxel deve conter identificador, versão, dimensões X/Y/Z, tabela de materiais (cor e textura) e a lista de voxels não vazios com coordenada e índice de material. | Essencial | Proposto | Inspeção do formato; teste de round-trip. |
| DR-007 | O formato de mapa deve conter identificador, versão, dimensões, configuração do terreno base e a lista de objetos com identificador, posição e rotação. | Essencial | Proposto | Inspeção do formato; teste de round-trip. |

### 5.4 Restrições de design

| ID | Restrição | Prioridade | Status | Verificação |
|---|---|---|---|---|
| CR-010 | O modo editor deve ser aditivo: os modos atuais (`--terrain`, `--char` e demonstração), os requisitos FR-001 a FR-034 e o editor de personagem devem continuar funcionando sem alteração de comportamento. | Essencial | Proposto | Execução da suíte atual; teste de regressão (a criar). |
| CR-011 | Os formatos de objeto e de mapa devem ser abertos, documentados e versionados, sem depender de serviço ou formato proprietário para o funcionamento básico. | Essencial | Proposto | Inspeção da documentação e dos arquivos. |
| CR-012 | O editor não deve exigir ferramenta externa para criar, salvar, abrir e colocar objetos; a interoperabilidade com MagicaVoxel é opcional. | Essencial | Proposto | Demonstração em ambiente limpo. |

### 5.5 Atributos do sistema

| ID | Requisito | Tipo | Prioridade | Status | Verificação |
|---|---|---|---|---|---|
| AR-010 | Exportar e importar um objeto ou mapa deve reproduzir o estado original (round-trip), desconsiderando apenas perdas documentadas como a textura no `.vox`. | Confiabilidade | Essencial | Proposto | Teste de round-trip (a criar). |
| AR-011 | Arquivo de objeto ou mapa inválido, truncado ou de versão desconhecida deve ser recusado com mensagem, sem encerrar a aplicação e sem sobrescrever o projeto aberto. | Confiabilidade | Essencial | Proposto | Teste com arquivos corrompidos (a criar). |
| AR-012 | O editor deve preservar o trabalho em caso de falha de gravação, mantendo o projeto em memória e permitindo nova tentativa. | Confiabilidade | Desejável | Proposto | Teste de falha de I/O (a criar). |
| SR-004 | Quando FR-049 for implementado, o formato `.vox` deve seguir a especificação pública do MagicaVoxel e a paleta suportada deve ser documentada. | Conformidade | Opcional | Proposto | Teste com arquivo de referência. |

---

## 6. Impacto técnico previsto

> Esta seção orienta a implementação; não é requisito. Nomes de arquivos são sugestões.

| Área | O que muda |
|---|---|
| `src/world/chunk.py` / `src/world/block.py` | Necessidade de material por voxel além do `BlockType` (paleta + textura) ou de uma estrutura de objeto separada que seja “assada” nos chunks ao colocar. |
| `src/world/mesher.py` | Emitir UV/cor/material por voxel, não só por tipo/face; preservar o caminho atual para o terreno. |
| `src/rendering/atlas.py` | Atlas/tabela de materiais extensível; os 12 tiles atuais continuam válidos. |
| `assets/shaders/` | Novo par para a plataforma; extensão do shader do mundo para material por voxel. |
| `src/main.py` | Novo modo (`--map-editor` ou equivalente), entrada/saída do editor, atualização do frame. |
| Novo pacote `src/editor/` | Modelo de projeto, ferramentas, histórico, paleta, biblioteca, serialização, UI. |
| `src/interactive/character_editor.py` | Referência de UI e entrada; não deve ser acoplado ao editor de mapa. |
| `src/interactive/grid_overlay.py` | Continua como grade tática; a plataforma é um renderizador separado. |
| `src/world/manager.py` | Colocação de objetos grandes, remalha de chunks afetados, carregamento de mapa. |
| `assets/` | Novo diretório de objetos, texturas de plataforma e possivelmente texturas de material. |
| `tests/` | Novos testes de objeto, mapa, edição, histórico, round-trip e shader da plataforma. |

### 6.1 Decisão em aberto: onde mora o material por voxel

| Opção | Vantagens | Riscos |
|---|---|---|
| A. Estender o chunk com uma camada de material (paleta + textura) | Objetos e terreno usam o mesmo pipeline; colocação é “assar” voxels no mundo. | Aumenta memória por chunk; migração de caches; precisa preservar os testes atuais. |
| B. Objeto como malha própria, separada dos chunks | Não altera o chunk atual; objects podem ser instanciados e movidos. | Colisão, grade tática e edição por voxel ficam mais complexas; mistura de pipelines. |
| C. Híbrido: objeto editável em estrutura própria; ao confirmar, gera malha e/ou voxels nos chunks | Mantém o editor simples e o mundo atual. | Duplica representação; remalha e remoção precisam de cuidado. |

A escolha deve ser registrada em ADR ou na documentação de arquitetura antes da implementação.
Este incremento exige o comportamento, não a opção.

---

## 7. Plano de verificação

### 7.1 Testes a criar

| Área | Teste mínimo |
|---|---|
| Objeto | Criar, editar, salvar, reabrir, exportar, importar, arquivo inválido. |
| Material | Cor e textura por voxel; independência entre cor e textura; fallback. |
| Grid | Redimensionar preservando conteúdo; limites; voxels fora. |
| Plataforma | Shader compila; grade acompanha câmera; uma chamada de desenho. |
| Colocação | Prévia, confirmação, cancelamento, rotação, múltiplos chunks, colisão. |
| Mapa | Criar, salvar, reabrir, jogar; objeto removido restaura terreno. |
| Histórico | 50 operações; desfazer/refazer; ramo descartado. |
| Regressão | Suíte atual continua com o mesmo resultado; modos atuais inalterados. |

### 7.2 Critérios de aceitação de alto nível

1. Criar uma casa de até 32×32×32 no editor, com paredes de cores e texturas diferentes.
2. Salvar o objeto, fechar e reabrir o editor: a casa está idêntica.
3. Colocar a casa no mapa, rotacionada, sobre o terreno; o token colide com ela.
4. Salvar o mapa, fechar e reabrir: a casa está na mesma posição e rotação.
5. Exportar a casa para `.vox` e abrir em ferramenta compatível (FR-049).
6. A plataforma é desenhada com superfície e grade alinhadas à câmera.
7. Desfazer e refazer uma sequência de 50 edições.
8. Rodar a suíte atual e obter o mesmo resultado do baseline (fora as duas falhas já conhecidas).

---

## 8. Riscos e questões abertas

| # | Risco/questão | Impacto | Mitigação sugerida |
|---|---|---|---|
| 1 | Material por voxel aumenta memória e quebra o chunk `uint8` atual. | Alto | ADR antes de implementar; opção híbrida; orçamento de memória por objeto. |
| 2 | Texturas por voxel podem estourar o atlas e o número de draw calls. | Alto | Atlas/tabela de materiais com limite; materiais agrupados por textura; teste de draw calls. |
| 3 | Objetos grandes ocupam vários chunks e exigem remalha cara. | Médio | Limite inicial (ex.: 64³); remalha só dos chunks afetados; fila fora do quadro. |
| 4 | Editar terreno existente e depois remover objeto: restaurar o original não é trivial. | Médio | Guardar cópia do terreno sob o objeto ou limitar remoção a objetos colocados. |
| 5 | Colisão e grade tática precisam reconhecer materiais personalizados. | Médio | Definir opacidade/solidez por material; manter `surface.py` como política única. |
| 6 | `.vox` não tem textura e tem paleta limitada. | Baixo | Importar/exportar cor sólida e avisar da perda. |
| 7 | Interpretador de regras (FR-050) vira uma linguagem e cresce sem limite. | Baixo | Manter opcional e mínimo; cortar se o prazo apertar. |
| 8 | UI do editor competir com o editor de personagem e o chat. | Médio | Modo separado; atalhos consistentes; não misturar painéis. |
| 9 | Formato de mapa sem versionamento quebra saves futuros. | Médio | Campo de versão e validação desde a primeira versão. |
| 10 | Escopo acadêmico e tempo de implementação. | Alto | Priorizar FR-035 a FR-042; deixar FR-043, FR-046, FR-047, FR-049 e FR-050 para incrementos seguintes. |

### 8.1 Corte mínimo recomendado (MVP)

Se o prazo for curto, o incremento entrega valor com:

**FR-035, FR-036, FR-037, FR-038, FR-039, FR-040, FR-041, FR-042, FR-044, FR-045, PR-008,
PR-009, UR-006, DR-006, DR-007, CR-010, CR-011, CR-012, AR-010, AR-011.**

Ficam para depois: FR-043 (biblioteca), FR-046 (undo), FR-047 (transformar objetos), FR-048
(feedback avançado), FR-049 (.vox), FR-050 (procedural).

---

## 9. Matriz de rastreabilidade do incremento

| Novo requisito | Requisitos atuais | Código atual impactado |
|---|---|---|
| FR-035 | FR-003, FR-019, FR-021, FR-031 | `src/main.py`; novo pacote de editor |
| FR-036 | FR-006, FR-012, FR-040 | `src/world/mesher.py`; `src/interaction/raycast.py` |
| FR-037 | FR-036, FR-038 | `src/world/block.py`; `src/world/mesher.py`; shader |
| FR-038 | FR-010, FR-036, FR-037 | `src/rendering/atlas.py`; `src/world/mesher.py`; shader |
| FR-039 | FR-013, FR-040, FR-045 | novo modelo de projeto; `grid_overlay.py` como referência |
| FR-040 | FR-002, FR-010, FR-011, FR-013 | `assets/shaders/`; novo renderizador de plataforma |
| FR-041 | FR-036 a FR-038; DR-006 | novo módulo de serialização |
| FR-042 | FR-007, FR-012, FR-013, FR-016, FR-041 | `src/world/manager.py`; `src/physics/voxel_collision.py` |
| FR-043 | FR-034, FR-041 | padrão de catálogo do editor de personagem |
| FR-044 | FR-035, FR-036, FR-042, FR-045 | modelo de mapa; `WorldManager` |
| FR-045 | FR-031, FR-044; DR-007 | `src/clothing/character_save.py` como referência de escrita atômica |
| FR-046 | FR-028 (padrão de undo) | novo histórico de edição |
| FR-047 | FR-012, FR-042, FR-046 | raycast/AABB; modelo de objeto |
| FR-048 | FR-014, FR-040, FR-049 | `highlight.py`; HUD |
| FR-049 | FR-041; SR-004 | novo codec `.vox` |
| FR-050 | FR-036, FR-037, FR-041 | novo interpretador de regras |
| PR-008 a PR-010 | PR-001, PR-002, PR-005 | `WorldManager`; mesher |
| UR-006/UR-007 | FR-019, FR-021, UR-001 a UR-005 | UI do editor |
| DR-006/DR-007 | DR-001, DR-004 | novos formatos |
| CR-010 a CR-012 | CR-001 a CR-009 | arquitetura |
| AR-010 a AR-012; SR-004 | AR-001 a AR-009 | serialização e validação |

---

## 10. Definição de pronto do incremento

O incremento estará pronto quando:

1. O modo editor abrir e fechar sem afetar os modos atuais.
2. For possível criar um objeto voxel com cor e textura por voxel e grid dimensionável.
3. A plataforma for renderizada por shader com grade e realce alinhados à câmera.
4. O objeto puder ser salvo, reaberto, exportado e colocado no mundo como construção.
5. Um mapa com pelo menos uma casa puder ser salvo, reaberto e jogado.
6. Os testes novos passarem e a suíte atual mantiver o resultado do baseline (descontadas as
   duas falhas conhecidas de `test_layer_clearance.py`).
7. Os formatos de objeto e mapa estiverem documentados e versionados.

---

## Apêndice A — Decisões que este incremento NÃO toma

- Não define a linguagem/forma final das regras de FR-050.
- Não decide entre camada de material no chunk e objeto como malha própria (seção 6.1).
- Não define limite final de dimensões nem de número de objetos por mapa.
- Não define se o modo terreno passará a carregar mapas editados.
- Não define se texturas serão por voxel ou por face (o requisito mínimo é por voxel).
- Não define a paleta final de cores nem o conjunto inicial de texturas.

## Apêndice B — Fontes da referência Replicube

| Fonte | Uso |
|---|---|
| [Site oficial](http://www.walaber.com/replicube) | Descrição, modo livre, exportação para MagicaVoxel. |
| [Steam](https://store.steampowered.com/app/3401490/Replicube/) | Descrição, editor, exportação, plataformas. |
| [Press kit](http://www.walaber.com/replicube-press-kit) | Ficha do produto, linguagem Lua, público. |
| [Famitsu](https://www.famitsu.com/article/202505/41415) | 16 cores + vazio, coordenadas XYZ, modo livre, Lua. |
| [Especificação MagicaVoxel](https://github.com/ephtracy/voxel-model) | Referência para FR-049/SR-004 (formato `.vox`). |
