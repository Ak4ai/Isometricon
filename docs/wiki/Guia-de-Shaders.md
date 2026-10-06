# 🎨 Guia de Shaders GLSL (OpenGL 3.3 Core)

## 1. Shaders de Terreno (`world.vert` e `world.frag`)

### 1.1. Vertex Shader
* **Responsabilidade:** Multiplicação da matriz de transformação $\mathbf{P} \times \mathbf{V} \times \mathbf{M}$, repasse de normais de faces e suporte a instanciamento.

### 1.2. Fragment Shader
* **Responsabilidade:** Cálculo de iluminação ambiente e difusa direcional (modelo Lambertiano):

$$I_{\text{total}} = (I_{\text{ambient}} + I_{\text{diffuse}} \times \max(\vec{N} \cdot \vec{L}, 0.0)) \times \text{CorBase}$$

---

## 2. Shaders de Destaque / Hover (`highlight.vert` e `highlight.frag`)

* **Responsabilidade:** Renderização da caixa de seleção translúcida com leve expansão escalar (1.002) para mitigar artefatos de Z-fighting com o bloco subjacente.
