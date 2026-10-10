# 🏛️ Arquitetura do Motor de Mundo (Equipe A)

## 1. Pipeline de Computação Gráfica

O pipeline de renderização do **Isometricon** transforma os dados brutos de voxels em uma cena rasterizada de alto desempenho:

1. **Geração Procedural (Perlin Noise 3D):**
   - Cria o mapa de elevação e cavernas baseado em funções contínuas de ruído.
2. **Armazenamento em Chunks ($16 \times 16 \times 16$):**
   - Discretização do espaço em volumes de 4.096 blocos para culling e rebuild de malha localizado.
3. **Algoritmo de Face Culling (CPU Meshing):**
   - Elimina faces internas checando os 6 vizinhos $(\pm X, \pm Y, \pm Z)$.
4. **Envio para Buffers de GPU:**
   - Criação de Vertex Array Objects (VAO) e Vertex Buffer Objects (VBO) com posição, normais e cor.
5. **Frustum Culling:**
   - Teste de interseção da AABB de cada Chunk com os 6 planos do Frustum Ortográfico.
6. **Execução de Shaders GLSL:**
   - Projeção ortográfica isométrica e iluminação direcional.

---

## 2. Câmera Isométrica com Projeção Ortográfica

A câmera posiciona o observador com os ângulos exatos da projeção isométrica padrão:
* **Rotação no Eixo Y (Yaw):** $45^\circ$
* **Inclinação no Eixo X (Pitch):** $\arcsin(\tan(30^\circ)) \approx 35.264^\circ$
* **Matriz de Projeção Ortográfica:**

$$\mathbf{P}_{\text{ortho}} = \begin{bmatrix} \frac{2}{r - l} & 0 & 0 & -\frac{r + l}{r - l} \\ 0 & \frac{2}{t - b} & 0 & -\frac{t + b}{t - b} \\ 0 & 0 & \frac{-2}{f - n} & -\frac{f + n}{f - n} \\ 0 & 0 & 0 & 1 \end{bmatrix}$$

---

## 3. Algoritmo de Face Culling (Otimização)

Sem otimização, um chunk de $16 \times 16 \times 16$ possui até $4.096 \times 6 = 24.576$ faces (49.152 triângulos).

Com o Face Culling na CPU:
* Se o bloco vizinho em uma face for opaco, a face **não é incluída na malha**.
* Apenas as faces expostas ao ar geram vértices no VBO.
* **Redução típica:** 75% a 85% a menos de vértices na GPU.
