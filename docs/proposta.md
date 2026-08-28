# 🎲 Documento de Arquitetura: Projeto VTT Isométrico (Formato Dual 2x3)

**Objetivo (Prazo: 30 dias):**
Desenvolver a fundação de um **Virtual Tabletop (VTT)** com visual de blocos (estilo *Minecraft*). Como a turma tem 6 pessoas e o limite por grupo é de 3, o projeto foi estruturado em **duas aplicações complementares (Equipe A e Equipe B)**. Ambas exigem renderização nativa de baixo nível em OpenGL, garantindo complexidade e carga de Computação Gráfica rigorosamente iguais para os dois lados.

**O Paradigma de Design:**
Não programaremos IA de inimigos, cálculo de dano automático ou colisões físicas de ação. O software é um **Auxílio Visual Gráfico**. O computador renderiza o cenário 3D e a movimentação; os jogadores e o Mestre aplicam as regras e rolam os dados físicos na mesa real. A prioridade é a engenharia do motor gráfico e a otimização matemática de blocos.

---

## 🛠️ Opções de Stack Tecnológica (Em discussão)

*Todas as opções abaixo cumprem o requisito da disciplina de "renderização raiz", exigindo programação manual do Pipeline Gráfico, Shaders e Matrizes.*

### 🏆 Recomendação Principal da Equipe: Java + LWJGL
* **A Abordagem:** O LWJGL (Lightweight Java Game Library) atua como uma ponte direta para as funções nativas do OpenGL.
* **A Grande Vantagem:** O LWJGL é o motor base do *Minecraft Java Edition*. Reaproveita referências para lógica de *chunks*, algoritmos de iluminação e renderização de voxels.
* **O Apelo Acadêmico:** Gerenciamento rigoroso de buffers de memória (`ByteBuffers`), compilação de GLSL e matrizes de câmera (via `JOML`) programados 100% do zero.

### Opção B: As Três Vias do Python
1. **O Purista (`PyOpenGL`):** Programação OpenGL 100% manual, gerenciando ponteiros de memória e buffers com `NumPy`.
2. **O Arquiteto (`ModernGL`):** Mantém a escrita manual de Shaders e Matrizes com encapsulamento de buffers limpo.
3. **O Ágil (`Pyglet` + OpenGL):** Janela com Pyglet e desenho 3D nativo em OpenGL.

### Opção C: O VTT de Navegador (WebGL + JavaScript/TypeScript)
* OpenGL nativo no navegador via HTML5 `<canvas>`.

---

## 🏛️ Arquitetura Central e Otimizações Gráficas Comuns

1. **A Lente Isométrica (Câmera Ortográfica):** Cenário em 3D real (X, Y, Z) com matriz de **Projeção Ortográfica** e Z-buffer nativo.
2. **Shaders em GLSL Obrigatórios:** Vertex Shaders e Fragment Shaders para iluminação direcional e projeção de matrizes (MVP).
3. **Otimizações de Geometria e Câmera:** *Face Culling* na CPU e *Frustum Culling* na câmera.

---

## 👥 Divisão das Duas Equipes (3 Membros Cada)

### 🟩 Equipe A: O "Motor do Mundo" (Geração, Otimização e Terreno)
* **Tarefas de CG:** Chunks 3D, Perlin Noise procedural, Face Culling na CPU, Frustum Culling, Instanced Rendering e Shaders de Iluminação.

### 🟦 Equipe B: O "Motor Interativo" (Grid, Raycasting e UI de VTT)
* **Tarefas de CG:** Mouse Picking (Raycasting 3D), Shaders de Destaque/Hover, Matrizes de Transformação de Miniaturas e UI em OpenGL.

---

## 🔗 A Integração Final (O VTT Completo)

1. A **Equipe A** fornece a base visual pesada (o mundo de blocos otimizado).
2. A **Equipe B** roda integrada ou sobreposta a esse mundo, permitindo selecionar blocos, movimentar miniaturas e abrir as fichas de RPG.
