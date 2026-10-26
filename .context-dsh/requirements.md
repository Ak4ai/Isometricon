# requirements — Especificação de Requisitos do Isometricon (estado atual)

> **Norma de referência:** ISO/IEC/IEEE 29148:2018
> **Projeto:** Isometricon — motor gráfico isométrico em voxels e sistema de personagem/roupas
> **Natureza:** documento derivado do código implementado, não de intenção futura
> **Estado de referência:** commit `0b5c1fe` (branch `main`), working tree limpo
> **Data:** 21/10/2026

Conforme pedido, este documento **não registra stakeholders nem versionamento**. Ele descreve
**o que o sistema já faz hoje**, verificado por leitura do código, inspeção da documentação e
execução da suíte de testes. Funcionalidades apenas prometidas em README/wiki e não implementadas
aparecem na seção 2.4 (Limitações) e no Apêndice C (TBD), nunca como requisito.

Legenda de status:

- **Verificado** — comportamento coberto por teste automatizado que passa no commit de referência.
- **Implementado** — comportamento existe no código; a verificação é por inspeção/demonstração
  (em geral porque depende de janela/contexto OpenGL, indisponível no ambiente headless).
- **Implementado com falha conhecida** — existe, mas um teste associado falha no commit de
  referência; a falha está registrada na ficha.

---

## 1. Introdução

### 1.1 Propósito

Este documento especifica os requisitos do Isometricon tal como implementado: uma aplicação
Python que abre uma janela OpenGL 3.3 Core, gera e renderiza um mundo voxel isométrico com
streaming, permite interação por mouse/teclado, e monta, veste e anima um personagem 3D com roupas
em camadas do catálogo Roblox. Serve como linha de base para manutenção, verificação e evolução
acadêmica do projeto.

### 1.2 Escopo

**Dentro do escopo:** a aplicação desktop executada por `python src/main.py`, nos modos de
demonstração, terreno e personagem; o motor de mundo (chunks, terreno, cavernas, streaming,
meshing, culling, água, raycasting, colisão, grid, destaque); a camada de personagem (corpo,
rosto, cabelo, peças procedurais, proporções, roupas Roblox, HSR, animação, save); o console de
comandos; o editor de personagem; e as ferramentas de automação de captura.

**Fora do escopo atual:** regras de RPG (fichas, iniciativa, turnos, dados), seleção persistente
de bloco, click-to-move, múltiplos tokens, salvamento de sessão/mundo, multiplayer, áudio,
física de tecido, suporte a macOS empacotado e formatos de malha Roblox v3/v6.

### 1.3 Referências

| Referência | Título | Fonte |
|---|---|---|
| REF-001 | `docs/INTEGRATION_SPEC.md` — contrato atual entre mundo e interação | repositório |
| REF-002 | `docs/ARCHITECTURE.md` — arquitetura do motor de mundo | repositório |
| REF-003 | `docs/wiki/Sistema-de-Roupas.md` — encaixe, HSR e camadas | repositório |
| REF-004 | `docs/wiki/Animacao-e-Esqueleto.md` — rig, pesos e skinning | repositório |
| REF-005 | `docs/wiki/Bateria-de-Robustez.md` — métricas e limites de defeito | repositório |
| REF-006 | `docs/wiki/Criacao-de-Personagem.md` — editor, opções e ajustes | repositório |
| REF-007 | `docs/wiki/Comandos-do-Chat.md` — comandos e sintaxe | repositório |
| REF-008 | `tests/` — 34 arquivos, 765 casos | repositório |
| REF-009 | `.context-dsh/` — dossiê técnico completo deste repositório | repositório |
| REF-010 | ISO/IEC/IEEE 29148:2018 — Engenharia de sistemas e software | norma |

### 1.4 Termos

| Termo | Definição |
|---|---|
| Voxel | Célula cúbica unitária identificada por um `BlockType` em `uint8`. |
| Chunk | Volume lógico de 16×16×16 voxels (4.096 células). |
| Face culling | Descarte de faces de voxel cuja vizinha é opaca. |
| Frustum culling | Descarte de chunk cuja AABB está inteiramente fora do volume visível. |
| Streaming | Carregar e descarregar chunks conforme a posição do jogador. |
| Token | Miniatura tridimensional que representa o jogador no tabuleiro. |
| Cage | Malha de controle que envolve corpo ou roupa (interna/referência e externa). |
| WrapLayer | Mecanismo do Roblox que deforma a roupa entre as cages. |
| Encaixe (fit) | Reposicionamento da malha da roupa para o corpo do jogo. |
| HSR | Hidden Surface Removal: máscara de pele coberta pela roupa. |
| Camada | Peça externa (jaqueta, casaco) sobre uma peça interna. |
| Ajuste | Parâmetro de proporção ou aparência entre -100 e 100. |
| Cutaway | Segundo passe translúcido que revela o subsolo. |
| Turntable | Rotação automática do personagem no visualizador. |
| Peça procedural | Malha gerada por código (nariz, orelhas, chifres, cauda, asas). |

### 1.5 Abreviações

| Abreviação | Significado |
|---|---|
| SRS | Software Requirements Specification |
| GL | OpenGL |
| FR | Requisito funcional |
| PR | Requisito de desempenho |
| UR | Requisito de usabilidade |
| DR | Requisito de dados |
| CR | Restrição de design |
| SR | Requisito de conformidade |
| AR | Atributo do sistema |
| EI | Interface externa |
| HUD | Heads-up display |
| LBS | Linear blend skinning |

---

## 2. Visão geral do produto

### 2.1 Perspectiva do produto

O Isometricon é uma aplicação desktop autônoma. Não há servidor, banco de dados relacional nem
serviço de sessão. O processo principal abre uma janela GLFW, cria um contexto OpenGL 3.3 Core,
carrega assets do diretório `assets/` e executa um laço de renderização e entrada. A montagem do
personagem roda em thread separada e troca de malhas no laço principal.

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Aplicação Isometricon                          │
│                                                                      │
│  Entrada (teclado/mouse) ──► main.py ──► cena                        │
│                                │                                     │
│                                ├─ câmera, renderizadores, HUD        │
│                                ├─ mundo: gerador, streaming, mesher  │
│                                ├─ interação: raycast, grid, token    │
│                                └─ personagem: montagem, roupas,      │
│                                   animação, save                     │
│                                                                      │
│  Saída: janela OpenGL, texto no console, saves/, PNG de captura      │
└──────────────────────────────────────────────────────────────────────┘
```

#### 2.1.1 Interfaces de sistema

| Interface | Descrição |
|---|---|
| Sistema operacional | Janela GLFW, eventos de teclado/mouse, framebuffer. |
| Sistema de arquivos | Leitura de assets; escrita de caches, save e capturas. |
| GPU/driver | OpenGL 3.3 Core e GLSL 330. |
| Rede (opcional) | API pública do GitHub para checar sincronização; entrega de assets do Roblox. |

#### 2.1.2 Interfaces de usuário

| Interface | Descrição |
|---|---|
| Janela 3D | Cena isométrica, overlays 2D e título com versão/FPS/status. |
| Console de chat | Caixa de entrada, mensagens, sugestões e histórico. |
| Tela de criação | Painel de 408 px com 15 seções e o personagem à direita. |
| HUD de coordenadas | Texto `X: Y: Z:` em pixels. |
| Captura de tela | Arquivo PNG quando solicitado por linha de comando. |

#### 2.1.3 Interfaces de hardware

| Interface | Requisito |
|---|---|
| Display | Janela redimensionável (padrão 1280×720). |
| GPU | OpenGL 3.3 Core; MSAA 4× solicitado. |
| Teclado | Eventos GLFW para comandos e texto. |
| Mouse | Botões, roda e posição; posição convertida para pixels do framebuffer em HiDPI. |

#### 2.1.4 Interfaces de software

| Produto | Uso |
|---|---|
| Python 3.10 ou superior (recomendado 3.12) | Execução. |
| PyOpenGL 3.1.7+ | Chamadas OpenGL. |
| GLFW 2.7.0+ | Janela e entrada. |
| NumPy 1.26.0+ | Vetores, matrizes e malhas. |
| Pillow 10.0.0+ | Texturas, atlas, HUD e atlas do rosto. |
| lz4 4.4.5+ | Descompressão de `.rbxm`. |
| DracoPy 2.0.0+ | Decodificação de malhas Draco do Roblox. |
| SciPy 1.12.0+ | Processamento de imagem: componentes conexos das máscaras de íris e de olhos. |
| pytest 8.0.0+ | Verificação automatizada. |

#### 2.1.5 Interfaces de comunicação

| Interface | Protocolo | Uso |
|---|---|---|
| GitHub API | HTTPS/JSON | Comparar commit local com `origin/main` e exibir status. |
| Roblox asset delivery | HTTPS | Baixar malha, textura, cage e HSR de itens do catálogo. |
| Blender MCP (ferramenta) | TCP/JSON, porta 9876 | Apenas em script de importação, fora do runtime do jogo. |

#### 2.1.6 Restrições de memória

| Item | Valor |
|---|---|
| Chunk | 4.096 células `uint8` (4 KB de voxels). |
| Vértice de malha | 11 floats (44 bytes); skin acrescenta 8 floats. |
| Cache em memória do personagem | Até 64 entradas por memo, com despejo FIFO. |
| Chunks carregados | 25 colunas (raio 2) na configuração padrão. |

#### 2.1.7 Operações

| Operação | Como ocorre |
|---|---|
| Inicialização | `python src/main.py [flags]`. |
| Operação interativa | Laço contínuo até fechar a janela ou atingir `--frames`. |
| Seleção de modo | `--terrain`, `--char`; sem flag, demonstração do cubo. |
| Troca de personagem | Comandos `/skin`, editor ou flags de linha de comando. |
| Persistência | Save manual/automático do personagem em JSON. |
| Recuperação | Modelo anterior permanece visível se a montagem falhar; cache inválido é refeito. |

#### 2.1.8 Adaptação de site

| Item | Comportamento |
|---|---|
| Resolução | A projeção ortográfica acompanha o aspecto da janela. |
| HiDPI | Cursor convertido de janela para framebuffer antes do picking. |
| WSL | Backend PyOpenGL forçado para GLX quando detectado WSL. |
| Diretório de trabalho | Caminhos resolvidos a partir da raiz do repositório. |

#### 2.1.9 Interfaces com serviços

O sistema consulta a API do GitHub em thread daemon, com timeout de 4 segundos, e trata falha
como estado `offline`. O download de itens do Roblox é opcional: o repositório inclui 32 itens de
exemplo e o jogo funciona sem credencial para esse catálogo.

### 2.2 Funções do produto

1. Abrir janela e contexto OpenGL, manter laço de quadro e encerrar recursos.
2. Renderizar cena isométrica com câmera ortográfica controlável.
3. Gerar terreno e cavernas determinísticos e armazená-los em chunks.
4. Construir malhas com face culling e desenhar com frustum culling.
5. Transmitir chunks ao redor do jogador, incluindo água e subsolo.
6. Interagir com o tabuleiro: hover, clique, grade e destaque.
7. Mover um token com colisão, gravidade e animação.
8. Exibir HUD de chat e overlay de coordenadas.
9. Interpretar comandos de customização e de roupas.
10. Abrir editor visual de personagem com catálogo e miniaturas.
11. Montar corpo, rosto, cabelo e peças procedurais.
12. Vestir, encaixar e empilhar roupas do catálogo Roblox.
13. Ocultar a pele coberta e permitir correção manual.
14. Animar o personagem com esqueleto e pesos de roupa.
15. Salvar e restaurar o personagem.
16. Automatizar capturas e execução de comandos por linha de comando.

### 2.3 Características do usuário

| Grupo | Característica |
|---|---|
| Operador do jogo | Familiaridade com teclado/mouse e com o gênero voxel; usa os modos terreno e personagem. |
| Criador de personagem | Usa o editor e o chat; espera ver o resultado imediato das escolhas. |
| Avaliador técnico | Executa a suíte de testes, inspeciona shaders e mede o comportamento do motor. |

### 2.4 Limitações

| Limitação | Consequência |
|---|---|
| Sem regras de RPG | Não há fichas, iniciativa, turnos, dados, dano ou condições. |
| Sem seleção persistente | O clique esquerdo apenas registra o bloco atingido no console. |
| Um único token | Não há lista de miniaturas nem posicionamento de vários personagens. |
| Mundo não persistido | Fechar o jogo perde o terreno e a posição. |
| Streaming só em Y=0 | O mundo carregado é uma fatia de 16 blocos de altura; chunks Y<0 existem só onde cavernas os criaram. |
| Sem multiplayer | Não há rede de sessão nem sincronização entre clientes. |
| Roupas restritas ao Roblox | Não há simulação de tecido para geometria arbitrária. |
| Defeitos de roupa conhecidos | Seis peças do catálogo falham em pelo menos um corpo. |
| Sem áudio | Não há subsistema de som. |
| Empacotamento | `scripts/build.py` cobre Windows e Linux; macOS cai no ramo Windows. |
| Formatos de malha | FileMesh v3 e v6 não são suportados. |
| Necessidade de credencial para itens novos | Sem `ROBLOSECURITY`, o download de itens fora do catálogo de exemplo responde 401. |

### 2.5 Suposições e dependências

| Suposição | Impacto se falsa |
|---|---|
| O ambiente oferece OpenGL 3.3 Core. | A aplicação não inicia. |
| As dependências de `requirements.txt` estão instaladas. | Importação falha antes de abrir a janela. |
| Os assets do repositório estão presentes. | Personagem e roupas de exemplo não montam. |
| O usuário tem permissão de leitura/escrita na raiz do projeto. | Caches, save e capturas falham. |
| A rede está disponível quando se baixa item novo. | Apenas o catálogo local fica disponível. |
| O commit local está no repositório Git. | O diagnóstico de versão mostra `unknown`. |

### 2.6 Distribuição de requisitos

| Elemento | Requisitos |
|---|---|
| `src/core`, `src/main.py` | FR-001, FR-002, FR-003, FR-032, FR-033, EI-001, EI-002 |
| `src/world`, `src/rendering` | FR-004 a FR-011 |
| `src/interaction`, `src/interactive` | FR-012 a FR-019, FR-034 |
| `src/interactive/skin_commands.py` | FR-020 |
| `src/interactive/character_editor.py` | FR-021 |
| `src/clothing` | FR-022 a FR-031 |
| `tests/` | Verificação de FR-002, FR-004 a FR-016, FR-019 a FR-031, FR-033 |

### 2.7 Requisitos especificados

Os requisitos abaixo usam o formato de ficha do template, sem os campos de stakeholder e versão.
Cada requisito é singular, verificável e rastreável a código e, quando existe, a teste.

Campos do template não aplicáveis a este levantamento reverso: **stakeholder**, **versão**,
**requisito pai/filho** e **casos de uso**. A rastreabilidade é feita por arquivo e por teste, e a
justificativa do conjunto está na seção 5.2; observações específicas aparecem na própria ficha
quando mudam o entendimento do requisito.

---

## 3. Requisitos específicos

### 3.1 Interfaces externas

| ID | Interface | Entrada | Saída | Formato/faixa | Status |
|---|---|---|---|---|---|
| EI-001 | Teclado e mouse | Eventos GLFW (tecla, botão, roda, posição) | Estado interno | Códigos GLFW; posição em pixels. | Implementado |
| EI-002 | Vídeo | — | Framebuffer da janela | RGBA; 1280×720 padrão; redimensionável. | Implementado |
| EI-003 | Sistema de arquivos | Assets, caches, save, argumentos | Caches, save, PNG | OBJ, PNG, RBXM, NPZ, NPY, JSON. | Implementado |
| EI-004 | GitHub | Requisição HTTPS | Commit remoto e mensagem | JSON; timeout 4 s. | Implementado |
| EI-005 | Roblox | ID de asset, cookie opcional | Malha, textura, cage, HSR | Binário proprietário; HTTPS. | Implementado |
| EI-006 | Linha de comando | Flags e valores | Configuração da execução | Pares `--flag valor` ou `--flag=valor` (ver 3.2). | Implementado |

### 3.2 Requisitos funcionais

#### FR-001 — Janela e contexto OpenGL

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Implementado |
| Requisito | O sistema deve abrir uma janela redimensionável com contexto OpenGL 3.3 Core, habilitar teste de profundidade, descarte de faces traseiras e limpeza de cor/profundidade por quadro. |
| Condições | Driver com OpenGL 3.3 Core; execução de `python src/main.py`. |
| Verificação | Inspeção de `src/core/window.py` e `src/main.py`; demonstração; `test_platform` verifica a escolha de backend. |
| Critério de aceitação | A janela abre, o título exibe versão e FPS, e o redimensionamento atualiza o viewport sem erro. |
| Rastreabilidade | `src/core/window.py`; `src/main.py` (`setup_opengl_state`); `tests/test_platform.py`. |

#### FR-002 — Câmera isométrica ortográfica

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve manter uma câmera ortográfica com yaw de 45°, pitch de aproximadamente 35,264°, zoom limitado entre 0,25 e 100, pan no plano XZ e rotação do tabuleiro em passos de 90° com transição interpolada em torno do foco. |
| Condições | Modo terreno, personagem ou demonstração; eventos de tecla, roda e arraste. |
| Verificação | Teste automatizado (`tests/test_camera.py`, 38 casos). |
| Critério de aceitação | Quatro rotações de 90° retornam ao ângulo inicial; o foco permanece fixo durante a animação; o pan desloca o alvo apenas em X/Z. |
| Rastreabilidade | `src/camera/camera.py`; `tests/test_camera.py`. |

#### FR-003 — Modos de operação

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Implementado |
| Requisito | O sistema deve oferecer três modos de execução selecionáveis por argumento: demonstração de cubo texturizado (padrão), terreno voxel (`--terrain`) e visualizador de personagem (`--char` ou `--character`). |
| Condições | Um modo por execução; flags adicionais podem alterar o comportamento dentro do modo. |
| Verificação | Inspeção de `src/main.py`; demonstração dos três comandos. |
| Critério de aceitação | Sem flags, a janela mostra um cubo; com `--terrain`, mostra terreno e token; com `--char`, mostra o personagem e o turntable. |
| Rastreabilidade | `src/main.py` (ramos `terrain_demo`, `char_demo`, padrão). |

#### FR-004 — Geração determinística de terreno

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve gerar o terreno a partir de uma seed inteira, com altura contínua por coluna, camadas de pedra, terra e grama, água até o nível do mar e resultado independente da ordem de geração e do processo. |
| Condições | `TerrainGenerator(seed=...)`, com parâmetros padrão ou configurados; `enable_caves` opcional. |
| Verificação | Teste automatizado (`tests/test_terrain.py`, 14 casos), incluindo reprodutibilidade entre processos. |
| Critério de aceitação | A mesma seed produz as mesmas alturas e blocos; seeds diferentes produzem relevos diferentes; as faixas de camada respeitam `dirt_depth` e `sea_level`. |
| Rastreabilidade | `src/world/terrain.py`; `tests/test_terrain.py`. |

```gherkin
Funcionalidade: Terreno determinístico
  Cenário: Mesma seed, mesmo mundo
    Dado um gerador com seed 1234
    Quando eu gero a mesma região duas vezes
    Então as alturas e os blocos das duas regiões são idênticos
```

#### FR-005 — Cavernas tridimensionais

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Verificado |
| Requisito | O sistema deve escavar cavernas determinísticas em formato de túneis e salões, criar entradas de superfície quando sorteado e preservar blocos de água durante a escavação. |
| Condições | `TerrainGenerator(enable_caves=True)`; colunas geradas. |
| Verificação | Teste automatizado (`tests/test_caves.py`, 11 casos). |
| Critério de aceitação | Duas gerações com a mesma seed produzem as mesmas cavernas; nenhum bloco de água é removido; cavernas profundas podem criar chunks em Y negativo. |
| Rastreabilidade | `src/world/caves.py`; `src/world/terrain.py`; `tests/test_caves.py`. |

#### FR-006 — Chunks e face culling

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve armazenar voxels em chunks de 16×16×16 com identificadores `uint8`, validar coordenadas locais e gerar malha apenas para faces expostas, consultando vizinhos de chunks adjacentes. |
| Condições | Construção de malha por `ChunkMesher.build`, com ou sem callback de vizinhança. |
| Verificação | Teste automatizado (`tests/test_world.py` 17 casos; `tests/test_mesher.py` 15 casos). |
| Critério de aceitação | Um chunk vazio não gera vértices; um cubo 2×2×2 gera 24 faces; blocos adjacentes não geram faces internas; água e folhas não ocultam faces. |
| Rastreabilidade | `src/world/chunk.py`; `src/world/mesher.py`; `tests/test_world.py`; `tests/test_mesher.py`. |

#### FR-007 — Streaming de chunks

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve carregar e descarregar chunks ao redor da posição do jogador em um raio de duas colunas, priorizar chunks próximos e tratar regiões ausentes como ar sem iniciar carregamento em consultas. |
| Condições | Modo terreno; deslocamento do token entre colunas de chunk. |
| Verificação | Teste automatizado (`tests/test_interactive.py`, casos de streaming e revisões; `tests/test_integration.py`). |
| Critério de aceitação | Ao cruzar uma fronteira de chunk, colunas fora do raio são descarregadas e as novas entram na fila; consultas ao provedor não bloqueiam a thread principal. |
| Rastreabilidade | `src/world/manager.py`; `src/integration/voxel_grid.py`; `tests/test_interactive.py`. |

#### FR-008 — Frustum culling

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Verificado |
| Requisito | O sistema deve deixar de desenhar chunks cujos oito cantos ficam fora de um mesmo plano do frustum, mantendo visível o chunk que contém o foco da câmera. |
| Condições | Renderização do mundo com matriz de projeção e visão válidas. |
| Verificação | Teste automatizado (`tests/test_interactive.py`, casos de frustum culling). |
| Critério de aceitação | Um chunk distante do foco é descartado quando fora do frustum; o chunk do foco permanece desenhado. |
| Rastreabilidade | `src/world/manager.py` (`render`); `tests/test_interactive.py`. |

#### FR-009 — Água

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Verificado |
| Requisito | O sistema deve propagar água entre células de ar dentro dos chunks carregados, reduzindo o nível a cada avanço, e refletir a altura parcial da água na malha renderizada. |
| Condições | Chunks carregados com água e células de ar vizinhas; modo terreno. |
| Verificação | Teste automatizado (`tests/test_interactive.py`, três casos de água e o teste de altura reduzida). |
| Critério de aceitação | A água desce antes de espalhar; o volume permanece finito no teste; a superfície renderizada fica abaixo do topo do voxel quando o nível é menor que 1. |
| Rastreabilidade | `src/world/manager.py` (`_simulate_water`); `src/world/mesher.py` (`water_levels`); `tests/test_interactive.py`. |

#### FR-010 — Texturização de blocos

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve texturizar os tipos de bloco com um atlas de 12 tiles de 16×16 pixels, aplicar coordenadas UV por tipo e face e modular a cor do vértice pelo tom do material. |
| Condições | Renderização do mundo; atlas carregado de `assets/textures/blocks`. |
| Verificação | Teste automatizado (`tests/test_atlas.py`; `tests/test_mesher.py`, casos de UV e cor). |
| Critério de aceitação | Tipos distintos recebem tiles distintos; grama usa topo/lateral/baixo diferentes; o filtro é nearest e a borda é clampeada. |
| Rastreabilidade | `src/rendering/atlas.py`; `src/world/mesher.py`; `tests/test_atlas.py`. |

#### FR-011 — Iluminação e modo subterrâneo

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Implementado |
| Requisito | O sistema deve aplicar iluminação ambiente e direcional às superfícies e, quando o jogador está abaixo da superfície, desenhar o terreno acima dele em um segundo passe translúcido com atenuação por altura. |
| Condições | Renderização do terreno; `get_top_solid_block` disponível no provedor. |
| Verificação | Inspeção de `assets/shaders/world_textured.frag` e de `src/main.py`; demonstração em `--terrain` cavando até o subsolo. |
| Critério de aceitação | O terreno acima do jogador fica translúcido no subsolo e opaco na superfície; a miniatura do personagem não herda o cutaway. |
| Rastreabilidade | `assets/shaders/world_textured.frag`; `src/main.py`; `src/integration/voxel_grid.py`. |

#### FR-012 — Seleção de bloco por cursor

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve converter a posição do cursor em um raio no espaço do mundo, percorrer os voxels até 256 unidades e identificar o primeiro bloco diferente de ar, informando bloco, tipo, face e distância. |
| Condições | Modo terreno; cursor dentro da janela; fora de gesto de pan. |
| Verificação | Teste automatizado (`tests/test_raycast.py`, 28 casos). |
| Critério de aceitação | O centro da tela aponta para o alvo da câmera; coordenadas negativas usam `floor`; água e folhas são atingíveis; o clique registra o resultado no terminal. |
| Rastreabilidade | `src/interaction/raycast.py`; `src/main.py`; `tests/test_raycast.py`. |

```gherkin
Funcionalidade: Seleção de bloco
  Cenário: Hover sobre um bloco
    Dado que o cursor está sobre um bloco carregado
    Quando o quadro é renderizado
    Então o bloco sob o cursor recebe o destaque amarelo
```

#### FR-013 — Grade tática

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve desenhar uma grade de linhas sobre a superfície de células suportadas por terra, grama, pedra ou madeira, não criar célula sobre água ou folhas e alternar a visibilidade com a tecla G. |
| Condições | Modo terreno; chunks carregados; grade visível. |
| Verificação | Teste automatizado (`tests/test_grid_overlay.py`, 15 casos). |
| Critério de aceitação | Células planas compartilham a aresta; degraus mantêm cada contorno na própria altura; água invalida a célula do leito; a grade é desenhada em uma chamada de linhas. |
| Rastreabilidade | `src/interaction/surface.py`; `src/interactive/grid_overlay.py`; `tests/test_grid_overlay.py`. |

#### FR-014 — Destaque de bloco

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Implementado |
| Requisito | O sistema deve destacar o bloco sob o cursor e o bloco sob o token com cor distinta e intensidade pulsante, usando mistura aditiva e sem escrever no buffer de profundidade. |
| Condições | Modo terreno; hover com interseção ou token apoiado. |
| Verificação | Inspeção de `src/interactive/highlight.py` e do shader; demonstração. |
| Critério de aceitação | O bloco sob o token recebe destaque branco; o bloco sob o cursor recebe destaque amarelo; o destaque desaparece quando não há interseção. |
| Rastreabilidade | `src/interactive/highlight.py`; `assets/shaders/highlight.*`; `src/main.py`. |

#### FR-015 — Movimento do token

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve mover o token no plano horizontal com as teclas WASD, orientar o token na direção do deslocamento e animar caminhada enquanto houver movimento e repouso quando parar. |
| Condições | Modo terreno; teclas WASD pressionadas; token com ou sem avatar. |
| Verificação | Teste automatizado (`tests/test_interactive.py`, casos de inicialização, movimento, yaw e caminhada; `tests/test_token_avatar.py`). |
| Critério de aceitação | O movimento diagonal é normalizado; o yaw aponta para a direção do movimento; o avatar caminha enquanto o token se move e repousa ao parar; sem avatar, o token modular é exibido. |
| Rastreabilidade | `src/interactive/token_system.py`; `tests/test_interactive.py`; `tests/test_token_avatar.py`. |

#### FR-016 — Colisão e gravidade

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve impedir que o token atravesse blocos sólidos, aplicar gravidade com velocidade máxima de queda, permitir subir um bloco quando o token já está apoiado e tratar água como não sólida. |
| Condições | Movimento horizontal ou queda; provedor de blocos disponível. |
| Verificação | Teste automatizado (`tests/test_voxel_collision.py`, 7 casos; `tests/test_interactive.py`, água e degrau). |
| Critério de aceitação | O token para diante de parede, pousa sobre o bloco mais alto, não atravessa o piso virtual e não é bloqueado por água. |
| Rastreabilidade | `src/physics/voxel_collision.py`; `src/interactive/token_system.py`; `tests/test_voxel_collision.py`. |

#### FR-017 — Câmera acompanha o token

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve deslocar suavemente o foco da câmera para a posição do token quando não há gesto de pan em andamento. |
| Condições | Modo terreno; token em movimento; pan inativo. |
| Verificação | Teste automatizado (`tests/test_camera.py`, caso de acompanhamento; `tests/test_interactive.py`, WASD relativo à tela). |
| Critério de aceitação | O alvo da câmera converge para a posição do token; durante o pan, o alvo não é sobrescrito. |
| Rastreabilidade | `src/main.py`; `src/camera/camera.py` (`follow_target`); `tests/test_camera.py`. |

#### FR-018 — Overlay de coordenadas

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Opcional |
| Status | Implementado |
| Requisito | O sistema deve exibir em pixels as coordenadas X, Y e Z da posição do token em sobreposição à cena 3D. |
| Condições | Modo terreno; token existente. |
| Verificação | Inspeção de `src/interactive/coordinate_overlay.py`; demonstração. |
| Critério de aceitação | O texto acompanha a posição do token e usa apenas dígitos, sinais e separador decimal. |
| Rastreabilidade | `src/interactive/coordinate_overlay.py`; `assets/shaders/coordinate_overlay.*`; `src/main.py`. |

#### FR-019 — Console de chat

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve oferecer um console de texto aberto por T ou barra, com edição de linha, histórico, autocompletar por Tab, colagem, mensagens coloridas e indicador de carregamento. |
| Condições | Janela ativa; console aberto ou fechado; modelo de personagem opcional. |
| Verificação | Teste automatizado (`tests/test_chat_console.py`, 20 casos). |
| Critério de aceitação | Tab completa e cicla opções; Enter executa; Esc fecha; colagem insere o texto; mensagens de erro e sucesso têm cores distintas; o indicador aparece durante importação. |
| Rastreabilidade | `src/interactive/chat_console.py`; `src/interactive/skin_commands.py`; `tests/test_chat_console.py`. |

#### FR-020 — Comandos de customização e roupas

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Implementado |
| Requisito | O sistema deve interpretar 32 comandos sob `/skin` e 3 comandos raiz, aceitando nomes em português e inglês, e executar troca de corpo, aparência, roupas, raças, peças 3D, ajustes, editor e persistência. |
| Condições | Console aberto; modelo de personagem pode estar ausente para comandos de aparência. |
| Verificação | Teste automatizado da tabela, dos apelidos e de comandos representativos (`tests/test_chat_console.py`, `tests/test_body_shape.py`, `tests/test_character_save.py`, `tests/test_skin_brush.py`); os demais comandos por inspeção. |
| Critério de aceitação | Cada comando tem uso e nome único; apelidos em inglês executam o mesmo efeito; `/ajuda` lista grupos e detalha um comando; comando inválido retorna erro colorido. |
| Rastreabilidade | `src/interactive/skin_commands.py`; `tests/test_chat_console.py`; `tests/test_body_shape.py`; `tests/test_character_save.py`. |

```gherkin
Funcionalidade: Comando de customização
  Cenário: Trocar a cor dos olhos
    Dado que o personagem está montado
    Quando eu executo "/skin olhos verde"
    Então os dois olhos passam a usar a cor verde
```

#### FR-021 — Editor de personagem

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve abrir uma tela de criação com 15 seções, opções em grade, abas, rolagem, controles deslizantes, seletores de cor, campo para ID de item e botões de girar e concluir. |
| Condições | `/skin interface`, `--editor` ou botão do editor; personagem montado. |
| Verificação | Teste automatizado (`tests/test_character_editor.py`, 21 casos). |
| Critério de aceitação | Clicar numa opção executa o comando correspondente; a roda rola a grade apenas sobre o painel; o item em uso aparece contornado; Esc e Concluir fecham e gravam o personagem. |
| Rastreabilidade | `src/interactive/character_editor.py`; `src/main.py`; `tests/test_character_editor.py`. |

#### FR-022 — Rosto, olhos, boca e maquiagem

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve compor a textura do rosto a partir de pele, cabelo 2D, olhos com 18 formatos, sobrancelhas, boca, maquiagem, contorno, sardas, sombra do nariz e presas, permitindo cor independente por olho. |
| Condições | Corpo e cabeça escolhidos; atlas de rosto gerado. |
| Verificação | Teste automatizado (`tests/test_customization.py`; `tests/test_body_shape.py`, casos de rosto/maquiagem/olhos; `tests/test_character_model.py`). |
| Critério de aceitação | Cada olho aceita cor própria; formatos de olho preservam cílios e globo; batom, sombra e blush respondem aos controles; maquiagem não altera geometria. |
| Rastreabilidade | `src/clothing/customization.py`; `src/clothing/eye_shapes.py`; `src/clothing/character_model.py`; `tests/test_customization.py`. |

#### FR-023 — Proporções do corpo

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve aplicar 78 ajustes de -100 a 100 sobre altura, cabeça, pescoço, ombros, peito, cintura, pelve, quadril, glúteos, braços, mãos, pernas, pés, olhos, sobrancelhas, nariz, pele, sombra, bordas de roupa, maquiagem, orelhas, chifres, cauda e asas. |
| Condições | Personagem montado; ajuste alterado por comando ou editor. |
| Verificação | Teste automatizado (`tests/test_body_shape.py`, 62 casos). |
| Critério de aceitação | Com os 78 ajustes em zero, o corpo fica como modelado; alongar pernas levanta o corpo e mantém os pés no chão; peito, cintura e glúteos movem pele e tecido juntos; folga atua apenas no tecido. |
| Rastreabilidade | `src/clothing/body_shape.py`; `src/clothing/skeleton.py`; `src/clothing/character_animation.py`; `tests/test_body_shape.py`. |

#### FR-024 — Peças procedurais

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Verificado |
| Requisito | O sistema deve gerar orelhas (17 modelos), chifres (11), caudas (11) e asas (5), com cor e ajustes próprios, compartilhando a topologia entre modelos do mesmo tipo. |
| Condições | Seção Rosto ou Corpo; estilo diferente de "sem"; personagem montado. |
| Verificação | Teste automatizado (`tests/test_body_shape.py`, casos de modelos, cores e ajustes; `tests/test_character_animation.py`). |
| Critério de aceitação | Todos os modelos de um tipo têm os mesmos triângulos; trocar de modelo só move vértices; asas e cauda saem das costas; a fada tem asa translúcida. |
| Rastreabilidade | `src/clothing/ears.py`; `horns.py`; `tails.py`; `wings.py`; `tests/test_body_shape.py`. |

#### FR-025 — Raças

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Verificado |
| Requisito | O sistema deve aplicar 17 presets de raça sobre o corpo escolhido, alterando pele, orelhas, olhos, nariz, boca, chifres, cauda, asas e proporções. |
| Condições | Seção Corpo ou comando `/skin raca`; corpo feminino ou masculino. |
| Verificação | Teste automatizado (`tests/test_body_shape.py`, casos de raça por comando e cartões). |
| Critério de aceitação | A raça altera apenas as chaves de `RACE_ADJUSTMENTS`; maquiagem, cabelo, roupas e corpo são preservados; trocar de raça remove a boca de vampiro. |
| Rastreabilidade | `src/clothing/races.py`; `src/interactive/skin_commands.py`; `tests/test_body_shape.py`. |

#### FR-026 — Cabelo

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve vestir o cabelo padrão, cabelos do catálogo Roblox encaixados na cabeça e cabelos feitos à mão, com cor, posição, escala e degradê de opacidade. |
| Condições | Corpo escolhido; cabelo selecionado por comando, ID ou estilo. |
| Verificação | Teste automatizado (`tests/test_hair_fit.py`; `tests/test_character_model.py`; `tests/test_body_shape.py`, casos de cabelo). |
| Critério de aceitação | O cabelo padrão é usado quando nenhum é escolhido; cabelos do catálogo assentam na cabeça de cada corpo; nudred e raspado são vestidos sem download; o degradê deixa a pele aparecer. |
| Rastreabilidade | `src/clothing/hair_fit.py`; `src/clothing/character_model.py`; `tests/test_hair_fit.py`. |

#### FR-027 — Vestir e encaixar roupas Roblox

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Implementado |
| Requisito | O sistema deve obter uma roupa do catálogo por ID, decodificar sua malha e textura, encaixá-la no corpo escolhido por meio das cages e reutilizar o resultado em cache. |
| Condições | Item presente em `assets/models/clothing` ou rede e credencial disponíveis; corpo feminino ou masculino. |
| Verificação | Teste automatizado do encaixe e do cache (`tests/test_clothing_engine.py`; `tests/test_clothing_uv_cage_mapping.py`; `tests/test_wrap_layer_fit.py`; `tests/test_radial_prism_fit.py`); o download em rede e a conferência do catálogo nos dois corpos são documentados, não exercitados pela suíte (`docs/wiki/Scripts-do-Projeto.md`). |
| Critério de aceitação | A peça veste no corpo sem alterar a topologia da malha; a mesma roupa veste nos dois corpos; o cache é reutilizado em montagens seguintes; peça sem cage usa o caminho alternativo. |
| Rastreabilidade | `src/clothing/wear_engine.py`; `wrap_layer_fit.py`; `radial_prism_fit.py`; `tests/test_clothing_engine.py`. |

```gherkin
Funcionalidade: Vestir roupa
  Cenário: Vestir um suéter do catálogo
    Dado um personagem montado e o item 9240757332 disponível
    Quando eu executo "/skin vestir 9240757332"
    Então o suéter aparece vestido e o cache da peça é gravado
```

#### FR-028 — Ocultação de pele sob a roupa (HSR)

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve ocultar a pele coberta pelas roupas usando a máscara HSR do Roblox, com alternativa geométrica quando a máscara não existe, e permitir correção manual por espelhamento e pintura de pontos. |
| Condições | Roupas com sidecar de HSR ou malha encaixada disponível; seção Ajuste fino para edição. |
| Verificação | Teste automatizado (`tests/test_hsr.py`, 12 casos; `tests/test_skin_brush.py`, 19 casos). |
| Critério de aceitação | A pele sob a roupa não é desenhada; a pele sob aberturas permanece visível; pintar um ponto esconde ou mostra apenas o que ele decide; desfazer/refazer restaura o estado anterior. |
| Rastreabilidade | `src/clothing/hsr.py`; `src/clothing/character_model.py`; `src/interactive/skin_brush.py`; `tests/test_hsr.py`; `tests/test_skin_brush.py`. |

#### FR-029 — Camadas, sapatos e extras

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Implementado com falha conhecida |
| Requisito | O sistema deve empilhar peças de roupa, puxar a peça interna para baixo da externa, tratar calçados com sola rígida e elevar o corpo para apoiar na sola, e aceitar peças extras simultâneas. |
| Condições | Duas ou mais peças vestidas; calçado presente ou ausente; peça extra selecionada. |
| Verificação | Teste automatizado (`tests/test_layer_clearance.py`, `tests/test_rigid_footwear.py`, `tests/test_body_shape.py`). |
| Critério de aceitação | A jaqueta permanece por fora da camisa; o cós que fura a barra é puxado para dentro; o corpo sobe sobre a sola; extras não deslocam as peças principais. |
| Rastreabilidade | `src/clothing/layer_clearance.py`; `src/clothing/character_model.py`; `src/clothing/character_animation.py`; `tests/test_layer_clearance.py`. |
| Observação | No commit de referência, 2 casos de `tests/test_layer_clearance.py` falham por tolerância de borda (0,21 vs 0,20 e 4/192 vértices). A funcionalidade existe; a verificação não está verde. |

#### FR-030 — Animação esquelética

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve animar o personagem com um rig de 16 ossos, pose de repouso, caminhada com balanço de braços ajustado ao rasgo da roupa e skinning de até quatro ossos por vértice. |
| Condições | Personagem montado; andando ou parado; editor pode solicitar braços a 90°. |
| Verificação | Teste automatizado (`tests/test_skeleton.py`, 13 casos; `tests/test_character_animation.py`, 8 casos). |
| Critério de aceitação | O rig tem 16 ossos com pais antes dos filhos; ombros não movem o tronco; joelho e cotovelo misturam pesos; a caminhada move quadril, joelhos, tornozelos e braços; o balanço reduz apenas quando a roupa rasga acima de 1500 cm². |
| Rastreabilidade | `src/clothing/skeleton.py`; `character_animation.py`; `src/rendering/mesh.py`; `assets/shaders/world_textured.vert`; `tests/test_skeleton.py`. |

#### FR-031 — Salvar e carregar personagem

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Essencial |
| Status | Verificado |
| Requisito | O sistema deve gravar o personagem em `saves/personagem.json` com aparência, peças vestidas e posicionamento do cabelo, e restaurá-lo na abertura quando não houver flag de personagem. |
| Condições | Fechamento do editor, `/skin salvar`, `/skin carregar` ou abertura do jogo. |
| Verificação | Teste automatizado (`tests/test_character_save.py`, 5 casos). |
| Critério de aceitação | O save é escrito de forma atômica; um save ausente ou corrompido não impede a abertura; o personagem restaurado é igual ao salvo; `--novo` ignora o save. |
| Rastreabilidade | `src/clothing/character_save.py`; `src/main.py`; `src/interactive/skin_commands.py`; `tests/test_character_save.py`. |

```gherkin
Funcionalidade: Persistência do personagem
  Cenário: Reabrir o jogo
    Dado que salvei um personagem com corpo feminino e suéter
    Quando eu abro o jogo sem flags de personagem
    Então o mesmo corpo e o mesmo suéter são restaurados
```

#### FR-032 — Automação por linha de comando

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Implementado |
| Requisito | O sistema deve aceitar comandos iniciais, limite de quadros, captura de framebuffer em PNG, roteiro de mouse e flags de seed, editor e pincel para execuções automatizadas. |
| Condições | Flags `--cmd`, `--frames`, `--screenshot`, `--mouse`, `--seed`, `--editor`, `--pincel`, entre outras. |
| Verificação | Inspeção de `src/main.py`; demonstração com `--frames 10 --screenshot`. |
| Critério de aceitação | O comando inicial é executado antes do laço; a captura é gravada ao atingir o limite de quadros; o roteiro de mouse produz os mesmos eventos do mouse real; `--frames` desliga o autosave. |
| Rastreabilidade | `src/main.py`; `src/core/version.py`; `README.md`. |

#### FR-033 — Diagnóstico de versão e sincronização

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Opcional |
| Status | Verificado |
| Requisito | O sistema deve exibir a versão base, o commit, a branch e o estado de alterações locais, e comparar o commit local com o remoto em segundo plano, mostrando o resultado no console e no título da janela. |
| Condições | Repositório Git presente; rede disponível para comparar com o remoto. |
| Verificação | Teste automatizado (`tests/test_version.py`, 2 casos); inspeção de `src/core/version.py`. |
| Critério de aceitação | O título mostra versão, status e FPS; sem rede, o status é `offline`; com alterações locais, o status é `modified`; commit igual ao remoto é `synced`. |
| Rastreabilidade | `src/core/version.py`; `src/main.py`; `tests/test_version.py`. |

#### FR-034 — Catálogo e miniaturas do editor

| Campo | Valor |
|---|---|
| Tipo | Funcional |
| Prioridade | Desejável |
| Status | Implementado |
| Requisito | O sistema deve listar os itens do catálogo por seção, emparelhar sapatos esquerdo e direito em um item, marcar peças com defeito conhecido e gerar miniaturas ausentes em processo separado. |
| Condições | Editor aberto; itens em `assets/models/clothing`; texturas ou miniaturas disponíveis. |
| Verificação | Teste automatizado (`tests/test_character_editor.py`, catálogo e seleção; `tests/test_body_shape.py`, cartões de raça); inspeção de `scripts/render_catalog_thumbnails.py`. |
| Critério de aceitação | O item em uso aparece contornado; sapatos só aparecem quando as duas metades existem; peça defeituosa mostra aviso; sem miniatura, o cartão mostra a textura ou um X. |
| Rastreabilidade | `src/interactive/character_editor.py`; `scripts/render_catalog_thumbnails.py`; `src/clothing/known_defects.py`; `tests/test_character_editor.py`. |

### 3.3 Requisitos de usabilidade

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| UR-001 | O sistema deve oferecer controles de teclado e mouse documentados para câmera, pan, zoom, rotação, grade, chat, movimento e editor, sem exigir configuração prévia. | Essencial | Implementado | Inspeção de `README.md` e `src/main.py`; demonstração. |
| UR-002 | O sistema deve informar o resultado de cada comando no console, com cor distinta para sucesso e erro, e indicar carregamento no chat e no título da janela. | Essencial | Verificado | `tests/test_chat_console.py` (spinner e fluxo); inspeção. |
| UR-003 | O sistema deve completar comandos e opções com Tab e oferecer ajuda por grupo e por comando individual. | Desejável | Verificado | `tests/test_chat_console.py` (autocomplete e ajuda). |
| UR-004 | O sistema deve apresentar a interface em português e aceitar apelidos em inglês para os comandos. | Desejável | Verificado | `tests/test_chat_console.py` (comandos PT/EN). |
| UR-005 | O editor deve indicar visualmente a opção em uso, permitir rolagem por roda sobre o painel e girar ou inclinar o personagem por arraste. | Desejável | Verificado | `tests/test_character_editor.py` (seleção, rolagem, arraste, abas). |

### 3.4 Requisitos de desempenho

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| PR-001 | O sistema deve enviar à GPU no máximo uma malha de chunk por quadro e liberar no máximo uma malha antiga por quadro. | Essencial | Verificado | `test_world_manager_pending_deletions_amortization`; inspeção de `WorldManager.update`. |
| PR-002 | O sistema deve gerar e montar chunks em thread separada, sem bloquear o laço de renderização, e publicar cada resultado por fila. | Essencial | Verificado | `test_world_manager_result_queue_safe_without_gl`; `test_world_manager_reports_each_pending_streaming_stage`. |
| PR-003 | O sistema deve montar o personagem em thread separada e trocar as malhas no laço principal, mantendo o modelo anterior enquanto a montagem ocorre. | Essencial | Verificado | `test_async_model_defers_reloads_to_poll`; `test_character_model_init_without_gl`. |
| PR-004 | O sistema deve aplicar skinning na GPU com até quatro ossos por vértice e 16 matrizes de osso por personagem. | Desejável | Implementado | Inspeção de `src/rendering/mesh.py`, `assets/shaders/world_textured.vert`; `test_chunk_mesh_textured_upload_and_draw` quando há GL. |
| PR-005 | O sistema deve reconstruir a malha da grade apenas quando a revisão dos chunks mudar e desenhá-la em uma única chamada de linhas. | Desejável | Verificado | `test_visibility_toggle_skips_snapshot_sync_when_hidden_without_gl_context`; inspeção de `grid_overlay.py`. |
| PR-006 | O sistema deve limitar o alcance do raycast a 256 unidades e subdividir deslocamentos de colisão para impedir atravessar blocos. | Essencial | Verificado | `tests/test_raycast.py`; `tests/test_voxel_collision.py` (tunneling). |
| PR-007 | O sistema deve limitar o conjunto padrão a 25 colunas de chunks (raio 2) e descarregar colunas fora desse raio. | Essencial | Verificado | `test_world_manager_chunk_streaming_logic`; inspeção de `WorldManager`. |

### 3.5 Requisitos lógicos de dados

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| DR-001 | O save do personagem deve ser um JSON com `versao`, `aparencia` (39 campos), `veste` (7 slots) e `cabelo` (6 valores), gravado de forma atômica. | Essencial | Verificado | `tests/test_character_save.py`; inspeção de `character_save.py`. |
| DR-002 | O cache de roupa deve ser um OBJ com cabeçalho `# Isometricon Universal Fitted Clothing v37` e `# asset_type N`, acompanhado de `_hsr.npz` e `_parts.npy`. | Essencial | Verificado | `test_fitted_asset_type_reads_the_header`; `tests/test_hsr.py`; inspeção de `wear_engine.py`. |
| DR-003 | Os assets de roupa devem ser localizados por ID no nome do arquivo, em `assets/models/clothing`, com malha, textura e `.rbxm`. | Essencial | Verificado | `test_find_clothing_texture`; `tests/test_character_editor.py` (catálogo). |
| DR-004 | O sistema não deve persistir o mundo nem a posição do token; apenas o personagem é salvo. | Essencial | Implementado | Inspeção de `src/main.py` e `src/world/manager.py` (sem rotina de save de mundo). |
| DR-005 | As miniaturas devem ser gravadas em `assets/models/clothing/thumbs/<id>.png` e `thumbs/racas/<raça>_<corpo>.png`, e regeneradas quando ausentes. | Opcional | Implementado | Inspeção de `scripts/render_catalog_thumbnails.py` e `character_editor.py`. |

### 3.6 Restrições de design

| ID | Restrição | Prioridade | Status | Verificação |
|---|---|---|---|---|
| CR-001 | A aplicação deve ser escrita em Python 3.10 ou superior, usando PyOpenGL, GLFW, NumPy, Pillow, lz4, DracoPy e SciPy, sem motor gráfico de terceiros. | Essencial | Implementado | `requirements.txt`; imports; inspeção. |
| CR-002 | A renderização deve usar OpenGL 3.3 Core e shaders GLSL 330, sem pipeline fixo. | Essencial | Implementado | `src/core/window.py`; `assets/shaders`; inspeção. |
| CR-003 | O mundo deve ser discreto em chunks de 16×16×16 e transmitido apenas na coluna vertical Y=0. | Essencial | Implementado | `src/world/chunk.py`; `src/world/manager.py`; inspeção. |
| CR-004 | Deve existir um único token de jogador por execução. | Essencial | Implementado | `src/main.py`; `src/interactive/token_system.py`; inspeção. |
| CR-005 | O sistema não deve implementar regras de RPG, IA de inimigos, cálculo de dano, rolagem de dados ou multiplayer. | Essencial | Implementado | Ausência de módulos; inspeção. |
| CR-006 | O vestuário deve se limitar ao sistema de camadas do Roblox, com encaixe por cages em dois corpos de topologia compartilhada, sem simulação de tecido arbitrária. | Essencial | Implementado | `src/clothing`; `assets/models/*cages*`; inspeção. |
| CR-007 | O sistema não deve possuir subsistema de áudio. | Opcional | Implementado | Ausência de imports de áudio; inspeção. |
| CR-008 | O catálogo de exemplo deve funcionar sem credencial do Roblox; itens fora dele exigem download autenticado. | Desejável | Implementado | `docs/wiki/Scripts-do-Projeto.md`; `fetch_asset`; inspeção. |
| CR-009 | O código deve ser distribuído sob licença MIT; os assets de terceiros mantêm seus próprios termos. | Essencial | Implementado | `LICENSE`; `README.md`; inspeção. |

### 3.7 Conformidade com padrões

| ID | Requisito | Prioridade | Status | Verificação |
|---|---|---|---|---|
| SR-001 | Cada arquivo de shader deve começar com a diretiva `#version` e usar GLSL 330 core. | Essencial | Verificado | Etapa de CI `.github/workflows/ci.yml`; inspeção dos 12 arquivos. |
| SR-002 | A documentação de requisitos deve seguir a estrutura da ISO/IEC/IEEE 29148:2018, seções 1 a 5. | Desejável | Implementado | Este documento; template em `.context-dsh/templates/TEMPLATE_SRS.md`. |
| SR-003 | O projeto deve manter a licença MIT para o código-fonte. | Essencial | Implementado | `LICENSE`. |

### 3.8 Atributos do sistema

| ID | Requisito | Tipo | Prioridade | Status | Verificação |
|---|---|---|---|---|---|
| AR-001 | A geração de terreno, cavernas e encaixes deve ser determinística para as mesmas entradas e seed. | Confiabilidade | Essencial | Verificado | `tests/test_terrain.py`; `tests/test_caves.py`; `tests/test_wrap_layer_fit.py`. |
| AR-002 | Uma roupa sem cage, sem HSR ou com dados incompatíveis deve cair em um caminho alternativo sem impedir a montagem do personagem. | Confiabilidade | Essencial | Verificado | `tests/test_clothing_engine.py`; `tests/test_hsr.py`; inspeção de `wear_engine.py`. |
| AR-003 | Um cache de roupa com versão diferente de `v37` deve ser considerado inválido e refeito. | Confiabilidade | Essencial | Verificado | `test_fitted_asset_type_reads_the_header`; `is_valid_v2_obj`; inspeção. |
| AR-004 | A gravação do save deve ser atômica, de modo que uma interrupção não deixe JSON parcial. | Confiabilidade | Essencial | Verificado | `tests/test_character_save.py`; inspeção de `character_save.py`. |
| AR-005 | Uma falha durante a montagem em background deve manter o modelo anterior em uso e registrar a mensagem, sem encerrar a aplicação. | Confiabilidade | Essencial | Implementado | Inspeção de `CharacterModel.poll`; demonstração. |
| AR-006 | A aplicação deve operar em Windows e Linux, incluindo WSL com backend GLX. | Portabilidade | Essencial | Implementado | `src/_platform.py`; `tests/test_platform.py`; CI em `ubuntu-latest` e build em `windows-latest`. |
| AR-007 | A aplicação não deve coletar telemetria nem enviar dados do usuário; as únicas requisições de rede são a checagem de commit no GitHub e o download de assets do Roblox. | Segurança | Essencial | Implementado | Inspeção de `src/core/version.py`, `scripts/import_roblox_clothing.py`; busca por `urllib`. |
| AR-008 | Credenciais do Roblox devem ser lidas de um arquivo `.env` local ignorado pelo Git, não gravadas no repositório. | Segurança | Essencial | Implementado | `.gitignore`; `scripts/import_roblox_clothing.py`; inspeção. |
| AR-009 | A lógica de mundo, matemática, raycast e colisão deve ser importável e testável sem contexto OpenGL. | Manutenibilidade | Essencial | Verificado | `test_cpu_meshing_imports_without_opengl_or_glfw`; `test_voxel_provider_chunks_are_usable_without_graphics_context`; `tests/test_math.py`. |

---

## 4. Verificação

### 4.1 Métodos empregados

| Método | Uso |
|---|---|
| Teste automatizado | Comportamentos de câmera, matemática, terreno, cavernas, chunks, mesher, raycast, colisão, streaming, grid, chat, comandos, ajustes, roupas, HSR, animação, save e versão. |
| Inspeção | Requisitos que dependem de janela/contexto OpenGL, shaders, interfaces e restrições de design. |
| Demonstração | Modos de execução, cutaway, destaque, overlay, automação por flags e editor. |
| Análise | Contagens e limites (chunks, memória, alcance, números de comando). |
| Simulação | Não aplicável no estado atual. |

### 4.2 Como reproduzir a verificação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Resultado no commit de referência: **765 casos coletados, 762 aprovados, 2 reprovados, 1 pulado**.
Os dois reprovados são `test_a_jacket_stays_outside_even_when_the_pants_mostly_poke_through` e
`test_covered_vertices_are_those_under_the_outer_cloth`, ambos em `tests/test_layer_clearance.py`
(FR-029), por tolerância de borda. O caso pulado depende de roupas já encaixadas, que são cache
local.

### 4.3 Cobertura de status

| Grupo | Verificado | Implementado | Falha conhecida | Total |
|---|---:|---:|---:|---:|
| Funcionais (FR) | 24 | 9 | 1 | 34 |
| Interfaces externas (EI) | 0 | 6 | 0 | 6 |
| Usabilidade (UR) | 4 | 1 | 0 | 5 |
| Desempenho (PR) | 6 | 1 | 0 | 7 |
| Dados (DR) | 4 | 1 | 0 | 5 |
| Restrições (CR) | 0 | 9 | 0 | 9 |
| Conformidade (SR) | 1 | 2 | 0 | 3 |
| Atributos (AR) | 5 | 4 | 0 | 9 |
| **Total** | **44** | **33** | **1** | **78** |

### 4.4 Matriz de rastreabilidade requisito → teste

| Requisito | Arquivo(s) de teste |
|---|---|
| FR-001 | `test_platform.py`; `test_rendering.py` (quando há GL) |
| FR-002 | `test_camera.py` |
| FR-004 | `test_terrain.py` |
| FR-005 | `test_caves.py`; `test_terrain.py` |
| FR-006 | `test_world.py`; `test_mesher.py` |
| FR-007, FR-008, FR-009, FR-017 | `test_interactive.py`; `test_integration.py` |
| FR-010 | `test_atlas.py`; `test_mesher.py` |
| FR-012 | `test_raycast.py` |
| FR-013 | `test_grid_overlay.py` |
| FR-015, FR-016 | `test_interactive.py`; `test_token_avatar.py`; `test_voxel_collision.py` |
| FR-019, FR-020 | `test_chat_console.py`; `test_body_shape.py`; `test_character_save.py` |
| FR-021, FR-034 | `test_character_editor.py` |
| FR-022 | `test_customization.py`; `test_body_shape.py`; `test_character_model.py` |
| FR-023, FR-024, FR-025 | `test_body_shape.py` |
| FR-026 | `test_hair_fit.py`; `test_character_model.py` |
| FR-027 | `test_clothing_engine.py`; `test_clothing_uv_cage_mapping.py`; `test_wrap_layer_fit.py`; `test_radial_prism_fit.py` |
| FR-028 | `test_hsr.py`; `test_skin_brush.py` |
| FR-029 | `test_layer_clearance.py`; `test_rigid_footwear.py`; `test_body_shape.py` |
| FR-030 | `test_skeleton.py`; `test_character_animation.py` |
| FR-031 | `test_character_save.py` |
| FR-033 | `test_version.py` |
| PR-001, PR-002, PR-007 | `test_interactive.py` |
| PR-003 | `test_character_model.py` |
| PR-005 | `test_grid_overlay.py`; `test_interactive.py` |
| PR-006 | `test_raycast.py`; `test_voxel_collision.py` |
| DR-001 | `test_character_save.py` |
| DR-002, AR-003 | `test_clothing_engine.py`; `test_hsr.py`; `test_wrap_layer_fit.py` |
| DR-003 | `test_character_model.py`; `test_character_editor.py` |
| AR-001 | `test_terrain.py`; `test_caves.py` |
| AR-002 | `test_clothing_engine.py`; `test_hsr.py` |
| AR-009 | `test_mesher.py`; `test_math.py`; `test_integration.py` |

---

## 5. Informações de suporte

### 5.1 Formatos de entrada e saída

| Item | Formato |
|---|---|
| Malha de corpo/cage | OBJ com grupos `Export_*`; eixos do jogo. |
| Roupa do catálogo | OBJ de origem, PNG de textura, RBXM com `WrapLayer` e `HSRAssetId`. |
| Cache de roupa | OBJ com cabeçalho de versão, NPZ de máscara e NPY de partes. |
| Personagem salvo | JSON versão 1. |
| Captura | PNG RGBA do framebuffer. |
| Textura de bloco | PNG 16×16. |
| Shader | GLSL 330 core, arquivo `.vert`/`.frag`. |

### 5.2 Problemas que o software resolve e justificativa

O projeto demonstra, em código próprio, um pipeline gráfico isométrico completo (câmera, buffers,
shaders, culling, streaming) e um pipeline de vestuário que adapta roupas de terceiros a dois
corpos com topologia compartilhada, incluindo ocultação de pele e camadas. É um auxílio visual
para mesa de RPG, não um sistema de regras.

Justificativa por família de requisitos:

| Família | Por que existe |
|---|---|
| FR-001 a FR-003 | Sem janela, contexto e modos não há aplicação executável nem forma de demonstrar o motor. |
| FR-004 a FR-011 | O produto é um tabuleiro voxel: precisa de terreno, chunks, malha, streaming e leitura visual. |
| FR-012 a FR-018 | O uso de mesa exige apontar e mover no tabuleiro, com grade e feedback visual. |
| FR-019 a FR-021 | O chat e o editor são a interface de operação e de criação do personagem. |
| FR-022 a FR-026 | A customização é o núcleo da identificação do jogador com o avatar. |
| FR-027 a FR-029 | Vestir roupas de terceiros sem clipping é o diferencial técnico do projeto. |
| FR-030 | Sem animação o personagem não se integra ao tabuleiro em movimento. |
| FR-031 | Sem persistência o trabalho de criação se perde a cada execução. |
| FR-032 a FR-034 | Automação, diagnóstico e catálogo tornam o sistema verificável e operável. |
| PR, DR, CR, SR, AR | Garantem que o comportamento anterior é reproduzível, verificável e restrito ao escopo acadêmico. |

### 5.3 Empacotamento

O código é executado a partir do repositório. `scripts/build.py` empacota com PyInstaller para
Windows (portable e instalador) e Linux (tar.gz), copiando `assets/` inteira. O workflow de
release publica os artefatos em uma release draft. macOS não tem caminho de build próprio.

---

## Apêndice A — Índice de requisitos

| Faixa | Conteúdo |
|---|---|
| EI-001 a EI-006 | Interfaces externas |
| FR-001 a FR-034 | Requisitos funcionais |
| UR-001 a UR-005 | Usabilidade |
| PR-001 a PR-007 | Desempenho |
| DR-001 a DR-005 | Dados |
| CR-001 a CR-009 | Restrições de design |
| SR-001 a SR-003 | Conformidade |
| AR-001 a AR-009 | Atributos do sistema |

## Apêndice B — Modelos de análise

### B.1 Fluxo por quadro

```
eventos → atualizar câmera/chat/modelo → atualizar cena (token, streaming, editor)
        → calcular matrizes → raycast/hover → renderizar mundo
        → grid → highlight → token/personagem → HUD → apresentar
```

### B.2 Fluxo de montagem do personagem

```
customização + slots
   → cabelo/rosto → cabeça/nariz/orelhas/chifres
   → top/calça (encaixe + cache) → camadas → sapatos/extras
   → HSR (máscara → recorte da pele)
   → animador (rig, pesos, pose)
   → draw (u_Bones + texturas)
```

### B.3 Fluxo de aquisição de roupa

```
ID → arquivo local? → não → download (RBXM/malha/textura) → decode
   → cache de roupa válido? → não → WrapLayer → prisma radial → HSR → OBJ+NPZ+NPY
   → montagem no personagem
```

## Apêndice C — TBD e itens não implementados

| ID | Item | Situação |
|---|---|---|
| TBD-001 | Fichas de RPG, iniciativa e turnos | Não implementado; apenas documentado como intenção no README/wiki. |
| TBD-002 | Seleção persistente de bloco e click-to-move | Não implementado; o clique apenas registra o bloco. |
| TBD-003 | Múltiplos tokens e montagem de vários personagens | Não implementado. |
| TBD-004 | Salvamento de mundo/sessão | Não implementado. |
| TBD-005 | Multiplayer por sockets | Não implementado. |
| TBD-006 | Suporte a FileMesh v3 e v6 | Não implementado; o decodificador rejeita formatos desconhecidos. |
| TBD-007 | Empacotamento para macOS | Não implementado; `build.py` cai no ramo Windows. |
| TBD-008 | Correção das tampas em leque e costuras de UV do encaixe | Pesquisado e revertido; ver wiki. |
| TBD-009 | Cache com hash de cage/asset | Não implementado; validade é apenas a string `v37`. |
| TBD-010 | Testes de interface com contexto OpenGL no CI | Não implementado; `test_rendering` é pulado sem display. |
| TBD-011 | Correção das duas falhas de `test_layer_clearance.py` | Pendente; funcionalidade existe. |

## Apêndice D — Incremento proposto: editor de mapa e objetos voxel

Este documento descreve apenas o **estado implementado**. O incremento de requisitos para o
editor de mapa/objetos voxel (troca de cor e textura por voxel, plataforma renderizada por
shader, dimensões de grid configuráveis, exportação de objetos e colocação de construções no
mundo isométrico) está em:

- [`requirements-voxel-editor.md`](requirements-voxel-editor.md) — requisitos `FR-035` a `FR-050`,
  `PR-008` a `PR-010`, `UR-006` a `UR-007`, `DR-006` a `DR-007`, `CR-010` a `CR-012`,
  `AR-010` a `AR-012` e `SR-004`, todos com status **Proposto**.

O incremento é **aditivo**: não altera o status nem o texto dos requisitos deste documento.
A única extensão consciente é a persistência de mapa (`FR-045`), que convive com `DR-004`
(“sem persistência de mundo”) porque `DR-004` continua valendo para o modo terreno atual.
