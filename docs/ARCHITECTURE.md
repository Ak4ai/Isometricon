# 🏛️ Documento de Arquitetura do Motor de Mundo (Equipe A)

## 1. Visão Geral do Sistema

O **Motor de Mundo (World Engine)** do *Isometricon* é responsável pela representação espacial, geração procedural e renderização em alta performance do terreno tridimensional em blocos. O sistema foi projetado para operar com **OpenGL 3.3 Core Profile**, utilizando programação de baixo nível para buffers de vértices, compilação de shaders GLSL e operações matriciais.

```
+-------------------------------------------------------------+
|                      Isometricon Core                       |
+-------------------------------------------------------------+
                               |
       +-----------------------+-----------------------+
       |                                               |
       v                                               v
+-----------------------------+       +-------------------------------+
|  Equipe A: Motor do Mundo   |       | Equipe B: Motor Interativo    |
| - Geração Procedural (Noise)|       | - Raycasting 3D (Mouse Pick)  |
| - Chunk Data & Voxel Palettes|      | - Grid Overlay & Miniaturas   |
| - Face & Frustum Culling    | <===> | - UI & Destaques (Hover)      |
| - Instancing & GLSL Shaders |       | - Controle de Turnos / Fichas |
+-----------------------------+       +-------------------------------+
```

---

## 2. Pipeline de Renderização

O fluxo de dados da CPU para a GPU segue o pipeline gráfico moderno:

```
[ Geração de Terreno / Ruído Perlin ]
                 │
                 ▼
[ Estrutura de Chunks (Matriz 3D 16x16x16) ]
                 │
                 ▼
[ Algoritmo de Face Culling na CPU ] ──► (Descarta faces internas)
                 │
                 ▼
[ Construção de Buffers (VAO, VBO, EBO) ]
                 │
                 ▼
[ Teste de Frustum Culling com Câmera Isométrica ]
                 │
                 ▼
[ Chamada de Desenho: glDrawElements / Instanced ]
                 │
                 ▼
[ Vertex Shader: MVP Isométrica + Normais + Cores ]
                 │
                 ▼
[ Rasterização & Teste de Profundidade (Z-Buffer) ]
                 │
                 ▼
[ Fragment Shader: Iluminação Direcional Lambertiana + Ambiente ]
                 │
                 ▼
[ Framebuffer / Janela de Apresentação ]
```

---

## 3. Estruturas de Dados

### 3.1. Voxel & Tipo de Bloco (`BlockType`)
Cada voxel ocupa 1 byte de informação representando seu tipo/material:
```
0 = AIR (Vazio/Transparente)
1 = DIRT (Terra)
2 = GRASS (Grama)
3 = STONE (Pedra)
4 = WATER (Água)
5 = WOOD (Madeira)
6 = LEAVES (Folhas)
```

### 3.2. Chunk (`Chunk3D`)
O mundo é discretizado em blocos lógicos chamados **Chunks** de dimensão $16 \times 16 \times 16$ (ou $16 \times 256 \times 16$).
* **Array Linear:** `uint8_t blocks[16 * 16 * 16] = 4096 bytes (4 KB)`.
* **Indexação Rápida:** $\text{index}(x, y, z) = x + 16 \times (y + 16 \times z)$.
* **Bounding Box (AABB):** `min = (chunkX * 16, chunkY * 16, chunkZ * 16)`, `max = min + 16`.

---

## 4. Otimizações de Computação Gráfica

### 4.1. Algoritmo de Face Culling (CPU-side Meshing)
Para cada bloco não-ar em $(x, y, z)$, inspecionamos seus 6 vizinhos ortogonais:
* **Face Norte (+Z):** Desenhar se `neighbor(x, y, z + 1) == AIR`
* **Face Sul (-Z):** Desenhar se `neighbor(x, y, z - 1) == AIR`
* **Face Topo (+Y):** Desenhar se `neighbor(x, y + 1, z) == AIR`
* **Face Fundo (-Y):** Desenhar se `neighbor(x, y - 1, z) == AIR`
* **Face Leste (+X):** Desenhar se `neighbor(x + 1, y, z) == AIR`
* **Face Oeste (-X):** Desenhar se `neighbor(x - 1, y, z) == AIR`

### 4.2. Câmera Isométrica (True Isometric Projection)
A visualização isométrica padrão é obtida configurando:
1. Rotação em torno do eixo Y de $45^\circ$.
2. Rotação em torno do eixo X de $\theta = \arcsin(\tan(30^\circ)) \approx 35.264^\circ$.
3. Matriz de Projeção Ortográfica com dimensões controladas pelo fator de Zoom.

### 4.3. Iluminação Direcional (GLSL)
O Fragment Shader calcula a intensidade de luz para cada face com base no produto escalar entre a normal da face $\vec{N}$ e o vetor da fonte de luz direcional $\vec{L}$:

$$I = I_{\text{ambient}} + I_{\text{diffuse}} \times \max(\vec{N} \cdot \vec{L}, 0.0)$$
