Aqui está a versão completa, detalhada e estruturada exatamente como você pediu, reformulada para o modelo de **duas equipes de 3 pessoas (Equipe A e Equipe B)**, mantendo todas as opções de tecnologia (com destaque para o Java/LWJGL) e garantindo que ambos os grupos mexam igualmente com Computação Gráfica raiz e OpenGL.

Você pode copiar o texto a partir da linha abaixo e enviar para a turma e para o professor.

---

# 🎲 Documento de Arquitetura v4.0: Projeto VTT Isométrico (Formato Dual 2x3)

**Objetivo (Prazo: 30 dias):**
Desenvolver a fundação de um **Virtual Tabletop (VTT)** com visual de blocos (estilo *Minecraft*). Como a turma tem 6 pessoas e o limite por grupo é de 3, o projeto foi estruturado em **duas aplicações complementares (Equipe A e Equipe B)**. Ambas exigem renderização nativa de baixo nível em OpenGL, garantindo complexidade e carga de Computação Gráfica rigorosamente iguais para os dois lados.

**O Paradigma de Design:**
Não programaremos IA de inimigos, cálculo de dano automático ou colisões físicas de ação. O software é um **Auxílio Visual Gráfico**. O computador renderiza o cenário 3D e a movimentação; os jogadores e o Mestre aplicam as regras e rolam os dados físicos na mesa real. A prioridade é a engenharia do motor gráfico e a otimização matemática de blocos.

---

## 🛠️ Opções de Stack Tecnológica (Em discussão)

*Todas as opções abaixo cumprem o requisito da disciplina de "renderização raiz", exigindo programação manual do Pipeline Gráfico, Shaders e Matrizes.*

### 🏆 Recomendação Principal da Equipe: Java + LWJGL

* **A Abordagem:** O LWJGL (Lightweight Java Game Library) atua como uma ponte direta para as funções nativas do OpenGL.
* **A Grande Vantagem:** O LWJGL é o motor base do *Minecraft Java Edition*. Como já temos o costume de lidar com o ecossistema de modificações do jogo, debugar ambientes multi-mods pesados e analisar o código-fonte de projetos focados em blocos (como o Fabric), essa rota reaproveita nosso conhecimento prévio. Encontrar referências para lógica de *chunks*, algoritmos de iluminação e renderização de voxels será muito mais fácil.
* **O Apelo Acadêmico:** Gerenciamento rigoroso de buffers de memória (`ByteBuffers`), compilação de GLSL e matrizes de câmera (via `JOML`) programados 100% do zero.

### Opção B: As Três Vias do Python

O Python garante desenvolvimento ágil e elimina problemas de ambiente de compilação entre os membros.

1. **O Purista (`PyOpenGL`):** Programação OpenGL 100% manual, idêntica ao C++, gerenciando ponteiros de memória e buffers com `NumPy`.
2. **O Arquiteto (`ModernGL`):** Mantém a escrita manual de Shaders e Matrizes, mas encapsula a configuração de buffers em objetos mais limpos, focando na arquitetura do motor.
3. **O Ágil (`Pyglet` + OpenGL):** Usa o Pyglet apenas para gerenciar a janela e a UI do RPG, deixando o desenho do tabuleiro tridimensional a cargo das funções nativas do OpenGL.

### Opção C: O VTT de Navegador (WebGL + JavaScript/TypeScript)

* **A Abordagem:** O OpenGL rodando nativamente no navegador através da tag HTML5 `<canvas>`.
* **A Grande Vantagem:** Divisão perfeita de front-end. Metade da equipe renderiza o 3D puro em WebGL (programando Shaders em GLSL), enquanto a outra metade usa HTML/CSS para criar as telas e fichas de personagem do VTT.

---

## 🏛️ Arquitetura Central e Otimizações Gráficas Comuns

Independente da linguagem escolhida, as duas equipes implementarão três pilares técnicos fundamentais:

1. **A Lente Isométrica (Câmera Ortográfica):** O cenário será programado em 3D real (X, Y, Z) aplicando uma matriz de **Projeção Ortográfica** na câmera. O *Z-buffer* da placa de vídeo fará todo o trabalho de sobreposição.
2. **Shaders em GLSL Obrigatórios:** Ambas as equipes escreverão seus próprios *Vertex Shaders* e *Fragment Shaders* para iluminação direcional e projeção de matrizes (MVP).
3. **Otimizações de Geometria e Câmera:** Aplicação de *Face Culling* (descartar blocos internos) e *Frustum Culling* (ignorar o que está fora da visão da câmera).

---

## 👥 Divisão das Duas Equipes (3 Membros Cada)

### 🟩 Equipe A: O "Motor do Mundo" (Geração, Otimização e Terreno)

*Foco do Subprojeto: Criar o ambiente tridimensional de blocos estático, aplicando algoritmos avançados de otimização de CPU e GPU.*

* **O que o software faz:** Abre a janela OpenGL, gerencia a câmera isométrica, processa um gerador procedural de terreno e renderiza o mapa de blocos otimizado.
* **Tarefas de Computação Gráfica (OpenGL Raiz):**
* **Arquitetura de Chunks & Perlin Noise:** Estruturar dados lógicos de blocos em matrizes tridimensionais e implementar geração procedural de terreno.
* **Face Culling & Frustum Culling:** Programar a lógica na CPU para descartar faces encobertas e ignorar Chunks fora da visão da câmera.
* **Instanced Rendering:** Enviar a malha de um único cubo básico para a placa de vídeo e desenhar milhares de instâncias de blocos em uma única chamada de desenho.
* **Shaders de Iluminação:** Escrever código GLSL focado no sombreamento direcional das faces do terreno.



### 🟦 Equipe B: O "Motor Interativo" (Grid, Raycasting e UI de VTT)

*Foco do Subprojeto: Criar a camada de interação do usuário, transformar cliques bidimensionais da tela em coordenadas tridimensionais do tabuleiro e gerenciar as miniaturas.*

* **O que o software faz:** Renderiza o tabuleiro quadriculado (grid), as miniaturas dos personagens/bosses, gerencia a movimentação baseada em grade e exibe as janelas de interface (fichas de RPG e instruções de dados para a mesa real).
* **Tarefas de Computação Gráfica (OpenGL Raiz):**
* **Mouse Picking (Raycasting 3D):** Programar a matemática reversa que pega as coordenadas 2D do clique do mouse na janela e converte em um raio vetorial 3D para descobrir exatamente em qual bloco do grid o Mestre clicou.
* **Shaders de Destaque e Seleção:** Escrever Shaders específicos em GLSL para desenhar bordas, contornos ou alterar a coloração de blocos quando o cursor do mouse passa por cima (*hover*).
* **Matrizes de Transformação:** Controlar a escala, rotação e translação das malhas tridimensionais das miniaturas (personagens e bosses) sobre o tabuleiro.
* **Desacoplamento de UI em OpenGL:** Renderizar caixas de texto e painéis de status sobre o cenário usando texturas geradas dinamicamente ou primitivas do OpenGL.



---

## 🔗 A Integração Final (O VTT Completo)

Na data da avaliação, as duas entregas se unem para formar o sistema completo:

1. A **Equipe A** fornece a base visual pesada (o mundo de blocos otimizado).
2. A **Equipe B** roda integrada ou sobreposta a esse mundo, permitindo selecionar blocos, movimentar miniaturas e abrir as fichas de RPG.
3. *(Opcional de Integração)*: As equipes podem conectar os dois sistemas via **Sockets locais (TCP)**, onde a Equipe B envia comandos de movimento e clique que atualizam dinamicamente a renderização na janela da Equipe A.

---

## 🚀 Metas Opcionais (Stretch Goals / Para ambos os grupos)

* **Greedy Meshing:** Algoritmo que funde faces de blocos da mesma cor em um polígono gigante, cortando a carga gráfica em até 80% (inspirado em mods de otimização).
* **Voxel LOD (Efeito Distant Horizons):** Renderizar Chunks distantes com menor resolução (fundindo 8 blocos em 1 bloco genérico), simulando visão infinita.
* **Multiplayer de Mesa (Sockets):** Sincronização Cliente/Servidor trafegando apenas eventos de clique e coordenadas das miniaturas (X, Z).