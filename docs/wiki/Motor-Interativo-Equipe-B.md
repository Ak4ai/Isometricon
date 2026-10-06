# 🟦 Motor Interativo — Equipe B

## Visão Geral

O **Motor Interativo** é o subprojeto da **Equipe B** do *Isometricon*. Enquanto a **Equipe A** gera e renderiza o mundo de blocos, a **Equipe B** é responsável pela camada de interação do usuário:

- 🎯 Detectar qual bloco o mestre clicou (Raycasting 3D)
- 🔲 Exibir o grid quadriculado do tabuleiro
- 🧙 Gerenciar miniaturas de personagens e monstros
- 🖼️ Renderizar fichas de RPG como overlay sobre a cena 3D

---

## 📁 Estrutura do Código

```
src/
├── interaction/           ← 🟦 EQUIPE B - Motor Interativo
│   ├── __init__.py
│   ├── raycasting.py      → Mouse Picking: Clique 2D → Bloco 3D
│   ├── grid_overlay.py    → Grid quadriculado sobre o terreno
│   ├── token_manager.py   → Miniaturas de personagens com matrizes
│   └── ui_renderer.py     → Overlay de fichas de RPG em OpenGL
└── integration/           ← 🔗 Ponte Equipe A ↔ Equipe B
    ├── voxel_provider.py  → VoxelGridProvider
    ├── highlight_bridge.py→ HighlightBridge
    └── camera_provider.py → CameraStateProvider

assets/shaders/
    ├── highlight.vert/.frag  → 🟦 Shader de destaque/hover
    ├── grid.vert/.frag       → 🟦 Shader de grid overlay
    └── ui.vert/.frag         → 🟦 Shader 2D ortográfico de UI
```

---

## 🔬 Módulos de Computação Gráfica

### 1. 🎯 Raycasting 3D (Mouse Picking)

**Issue:** [#27](https://github.com/Ak4ai/Isometricon/issues/27) | **Milestone:** [Fase 1](https://github.com/Ak4ai/Isometricon/milestone/5)

Converte o clique 2D do mouse em um raio vetorial 3D no espaço do mundo para determinar qual bloco foi selecionado.

**Algoritmo (Unprojection):**

```
1. Converter pixel (x, y) → NDC [-1, 1]:
   xNDC = (2 * mouseX / width) - 1
   yNDC = 1 - (2 * mouseY / height)

2. Desprojetar: NDC → Eye Space:
   rayEye = inverse(Projection) * vec4(xNDC, yNDC, -1, 1)

3. Desprojetar: Eye Space → World Space:
   rayWorld = inverse(View) * vec4(rayEye.xy, -1, 0)
   rayDir = normalize(rayWorld.xyz)

4. Ray-AABB Intersection (Slab Method):
   Testa interseção com AABB de cada bloco candidato
```

**Fórmula:**
$$\vec{d} = \text{normalize}\left(\mathbf{V}^{-1} \times \mathbf{P}^{-1} \times (x_{\text{ndc}}, y_{\text{ndc}}, 1, 0)\right)$$

---

### 2. ✨ Shaders de Destaque (Hover & Seleção)

**Issue:** [#28](https://github.com/Ak4ai/Isometricon/issues/28) | **Milestone:** [Fase 1](https://github.com/Ak4ai/Isometricon/milestone/5)

Shaders GLSL 330 que renderizam efeitos visuais sobre blocos com hover ou selecionados.

**`highlight.frag` — Efeito pulsante:**
```glsl
uniform vec4  u_HighlightColor;  // ex: (1.0, 0.8, 0.0, 0.5) = amarelo
uniform float u_Pulse;           // sin(time) passado pelo loop

void main() {
    float intensity = 0.6 + 0.4 * u_Pulse;
    FragColor = vec4(u_HighlightColor.rgb, u_HighlightColor.a * intensity);
}
```

**Blending:**
```python
gl.glEnable(gl.GL_BLEND)
gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
```

---

### 3. 🔲 Grid Overlay

**Issue:** [#29](https://github.com/Ak4ai/Isometricon/issues/29) | **Milestone:** [Fase 1](https://github.com/Ak4ai/Isometricon/milestone/5)

Renderiza a grade quadriculada do tabuleiro como linhas `GL_LINES` sobre o terreno.

**Geração do VBO:**
```python
def build_grid_mesh(width, depth, y_offset=0.01):
    lines = []
    for x in range(width + 1):
        lines += [x, y_offset, 0,   x, y_offset, depth]
    for z in range(depth + 1):
        lines += [0, y_offset, z,   width, y_offset, z]
    return np.array(lines, dtype=np.float32)
```

Toggle com tecla **G**.

---

### 4. 🧙 Sistema de Tokens/Miniaturas

**Issue:** [#30](https://github.com/Ak4ai/Isometricon/issues/30) | **Milestone:** [Fase 2](https://github.com/Ak4ai/Isometricon/milestone/6)

Objetos 3D posicionados sobre os blocos do terreno representando personagens e monstros.

**Matriz de Modelo por Token:**
$$\mathbf{M} = \mathbf{T}(x+0.5,\, y+1.0,\, z+0.5) \times \mathbf{R}(\text{yaw}) \times \mathbf{S}(0.8)$$

**Movimentação suave:** Interpolação linear (lerp) entre posições discretas da grade.

---

### 5. 🖼️ UI Overlay (Fichas de RPG)

**Issue:** [#31](https://github.com/Ak4ai/Isometricon/issues/31) | **Milestone:** [Fase 2](https://github.com/Ak4ai/Isometricon/milestone/6)

Renderiza painéis de status e fichas de personagem diretamente na tela usando projeção ortográfica 2D.

**Estratégia:**
```python
# Desabilitar depth test para UI
gl.glDisable(gl.GL_DEPTH_TEST)
proj_2d = mat4_ortho(0, width, 0, height, -1, 1)
ui_shader.set_mat4("u_Projection", proj_2d)
# ... renderizar painéis ...
gl.glEnable(gl.GL_DEPTH_TEST)  # Restaurar
```

---

### 6. 🔌 Módulo de Integração com Motor A

**Issue:** [#33](https://github.com/Ak4ai/Isometricon/issues/33) | **Milestone:** [Fase 3](https://github.com/Ak4ai/Isometricon/milestone/7)

Implementa as interfaces do contrato `docs/INTEGRATION_SPEC.md`:

| Interface | Finalidade |
|-----------|------------|
| `VoxelGridProvider` | Consulta tipo de bloco, colisão, altura máxima |
| `HighlightBridge` | Ativa shader de destaque em coordenada específica |
| `CameraStateProvider` | Fornece View e Projection atualizadas por frame |

---

## 📅 Milestones

| Milestone | Período | Issues |
|-----------|---------|--------|
| [🟦 Fase 1 — Fundação Interativa](https://github.com/Ak4ai/Isometricon/milestone/5) | até 15/09 | #27, #28, #29 |
| [🟦 Fase 2 — Miniaturas e Transformações](https://github.com/Ak4ai/Isometricon/milestone/6) | até 22/09 | #30, #31 |
| [🟦 Fase 3 — UI e Integração Final](https://github.com/Ak4ai/Isometricon/milestone/7) | até 30/09 | #33 |

---

## 🤝 Contrato com a Equipe A

A integração é desacoplada via módulo `src/integration/`. Consulte o [[Contrato de Integração|Contrato-de-Integracao]] para a especificação completa.

---

## 🔗 Links

- [Repositório Principal](https://github.com/Ak4ai/Isometricon)
- [docs/EQUIPE_B_ARCHITECTURE.md](https://github.com/Ak4ai/Isometricon/blob/main/docs/EQUIPE_B_ARCHITECTURE.md)
- [Todas as Issues da Equipe B](https://github.com/Ak4ai/Isometricon/issues?q=label%3A%22🟦+equipe-b%22)
