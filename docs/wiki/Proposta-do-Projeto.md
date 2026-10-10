# 🎲 Proposta do Projeto: VTT Isométrico (Formato Dual 2x3)

## 1. Visão Geral e Objetivo

**Prazo de Execução:** 30 dias  
**Disciplina:** Computação Gráfica — CEFET-MG  

Desenvolver a fundação de um **Virtual Tabletop (VTT)** com visual de blocos (estilo *Minecraft*). Como a turma tem 6 pessoas e o limite por grupo é de 3, o projeto foi estruturado em **duas aplicações complementares (Equipe A e Equipe B)**. Ambas exigem renderização nativa de baixo nível em OpenGL, garantindo complexidade e carga de Computação Gráfica rigorosamente iguais para os dois lados.

---

## 2. Paradigma de Design

Não programaremos IA de inimigos, cálculo de dano automático ou colisões físicas de ação. O software é um **Auxílio Visual Gráfico**. O computador renderiza o cenário 3D e a movimentação; os jogadores e o Mestre aplicam as regras e rolam os dados físicos na mesa real. A prioridade é a engenharia do motor gráfico e a otimização matemática de blocos.

---

## 3. Divisão das Duas Equipes (3 Membros Cada)

### 🟩 Equipe A: O "Motor do Mundo" (Geração, Otimização e Terreno)
* **Foco:** Criar o ambiente tridimensional de blocos estático, aplicando algoritmos avançados de otimização de CPU e GPU.
* **Tarefas de Computação Gráfica (OpenGL Raiz):**
  * **Arquitetura de Chunks & Perlin Noise:** Estruturar dados lógicos de blocos em matrizes tridimensionais e implementar geração procedural de terreno.
  * **Face Culling & Frustum Culling:** Programar a lógica na CPU para descartar faces encobertas e ignorar Chunks fora da visão da câmera.
  * **Instanced Rendering:** Enviar a malha de um único cubo básico para a placa de vídeo e desenhar milhares de instâncias de blocos em uma única chamada de desenho.
  * **Shaders de Iluminação:** Escrever código GLSL focado no sombreamento direcional das faces do terreno.

### 🟦 Equipe B: O "Motor Interativo" (Grid, Raycasting e UI de VTT)
* **Foco:** Criar a camada de interação do usuário, transformar cliques bidimensionais da tela em coordenadas tridimensionais do tabuleiro e gerenciar as miniaturas.
* **Tarefas de Computação Gráfica (OpenGL Raiz):**
  * **Mouse Picking (Raycasting 3D):** Programar a matemática reversa que pega as coordenadas 2D do clique do mouse na janela e converte em um raio vetorial 3D para descobrir exatamente em qual bloco do grid o Mestre clicou.
  * **Shaders de Destaque e Seleção:** Escrever Shaders específicos em GLSL para desenhar bordas, contornos ou alterar a coloração de blocos quando o cursor do mouse passa por cima (*hover*).
  * **Matrizes de Transformação:** Controlar a escala, rotação e translação das malhas tridimensionais das miniaturas (personagens e bosses) sobre o tabuleiro.
  * **Desacoplamento de UI em OpenGL:** Renderizar caixas de texto e painéis de status sobre o cenário usando texturas geradas dinamicamente ou primitivas do OpenGL.
