# 🎲 Bem-vindo à Wiki Oficial do Isometricon

**Isometricon** é uma fundação de **Virtual Tabletop (VTT)** tridimensional em voxels (*estilo Minecraft*) sob uma **perspectiva isométrica ortográfica**, desenvolvida para a disciplina de Computação Gráfica do **CEFET-MG**.

O projeto é dividido em **dois subprojetos complementares** desenvolvidos no mesmo repositório.

---

## 📚 Navegação Rápida

| Página | Descrição |
| :--- | :--- |
| [[Proposta do Projeto\|Proposta-do-Projeto]] | Documento da proposta acadêmica original e divisão das equipes (2×3). |
| [[Arquitetura do Motor A\|Arquitetura-do-Motor]] | Pipeline gráfico, Chunks 3D, Face Culling e algoritmos da Equipe A. |
| [[Motor Interativo — Equipe B\|Motor-Interativo-Equipe-B]] | Raycasting 3D, Grid, Tokens e UI da Equipe B. |
| [[Contrato de Integração\|Contrato-de-Integracao]] | Interfaces entre Equipe A (Mundo) e Equipe B (Interativo). |
| [[Guia de Shaders GLSL\|Guia-de-Shaders]] | Shaders GLSL 330 core, matrizes MVP e iluminação direcional. |
| [[Sistema de Roupas\|Sistema-de-Roupas]] | Roupas do Roblox por cages, HSR e camadas. |
| [[Animação e Esqueleto\|Animacao-e-Esqueleto]] | Rig do jogo, pesos das roupas, descanso e caminhada. |
| [[Bateria de Robustez\|Bateria-de-Robustez]] | Como medir o catálogo inteiro e os resultados. |
| [[Comandos do Chat\|Comandos-do-Chat]] | Todos os comandos /skin. |

---

## 🟩 Equipe A — Motor do Mundo

Responsável pela fundação gráfica de baixo nível:

1. **Janela e Contexto:** Criação de janela e inicialização do contexto OpenGL 3.3 Core com GPU dedicada.
2. **Câmera Isométrica:** Projeção ortográfica com $\text{Yaw} = 45°$, $\text{Pitch} \approx 35.264°$ e rotação suave por lerp.
3. **Texturização de Blocos:** 1110 texturas PNG 16×16, ciclo automático a cada 0.5s, TexturedMesh com layout UV.
4. **Estrutura de Chunks 3D:** Armazenamento volumétrico de voxels em blocos de $16 \times 16 \times 16$.
5. **Face Culling na CPU:** Algoritmo que elimina faces internas, reduzindo > 75% dos vértices enviados à GPU.
6. **Geração Procedural:** Relevo e biomas com Perlin Noise / Simplex Noise.
7. **Shaders de Iluminação:** Sombreamento Lambertiano com luz ambiente e direcional.

**Issues ativas:** [#5](https://github.com/Ak4ai/Isometricon/issues/5), [#6](https://github.com/Ak4ai/Isometricon/issues/6), [#7](https://github.com/Ak4ai/Isometricon/issues/7), [#8](https://github.com/Ak4ai/Isometricon/issues/8)

---

## 🟦 Equipe B — Motor Interativo

Responsável pela camada de interação do usuário:

1. **Raycasting 3D:** Converte cliques 2D em seleção de blocos 3D via unprojection de matrizes.
2. **Grid Overlay:** Linhas GL_LINES sobre o terreno formando o tabuleiro quadriculado.
3. **Shaders de Destaque:** Efeito pulsante hover/seleção com uniforms configuráveis.
4. **Tokens/Miniaturas:** Objetos 3D com matrizes de transformação (T × R × S) e lerp de movimento.
5. **UI Overlay:** Fichas de RPG renderizadas em projeção ortográfica 2D sobre a cena 3D.
6. **Integração A↔B:** Interfaces VoxelGridProvider, HighlightBridge, CameraStateProvider.

**Issues ativas:** [#27](https://github.com/Ak4ai/Isometricon/issues/27), [#28](https://github.com/Ak4ai/Isometricon/issues/28), [#29](https://github.com/Ak4ai/Isometricon/issues/29), [#30](https://github.com/Ak4ai/Isometricon/issues/30), [#31](https://github.com/Ak4ai/Isometricon/issues/31), [#33](https://github.com/Ak4ai/Isometricon/issues/33)

---

## 🔗 Integração Final

Na data da avaliação, os dois motores se unem:
- A **Equipe A** fornece a base visual (mundo de blocos otimizado e texturizado).
- A **Equipe B** adiciona seleção de blocos, movimentação de miniaturas e interface gráfica.
- A ponte é implementada via `src/integration/` com contratos pré-estabelecidos.

Consulte o [[Contrato de Integração|Contrato-de-Integracao]] para a especificação completa.
