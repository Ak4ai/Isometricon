# 📚 Central de Documentação do Isometricon

Bem-vindo à documentação oficial do motor de **Virtual Tabletop (VTT)** 3D em voxels **Isometricon**, desenvolvido para a disciplina de Computação Gráfica do **CEFET-MG**.

---

## 🧭 Guias e Especificações Técnicas

<div align="center">

| Documento | Foco Principal | Público-Alvo |
| :--- | :--- | :--- |
| [📋 **Proposta Acadêmica**](../proposta.md) | Escopo geral, prazos (30 dias) e modelo dual 2x3. | Professor & Equipes |
| [🏛️ **Arquitetura do Motor**](ARCHITECTURE.md) | Estrutura de Chunks 3D, Face Culling na CPU e Pipeline OpenGL. | Equipe A (Mundo) |
| [🔗 **Contrato de Integração**](INTEGRATION_SPEC.md) | Interfaces `VoxelGridProvider`, Raycasting 3D e Matrizes de Câmera. | Equipe A & Equipe B |
| [🎨 **Guia de Shaders GLSL**](SHADERS.md) | Shaders GLSL 330 core, modelo de iluminação Lambertiana e Destaques. | Equipe A & Equipe B |

</div>

---

## 📂 Módulos do Código Fonte (`src/`)

* [📐 **`src/camera/`**](../src/camera/README.md) — Câmera Isométrica (Projeção Ortográfica, Matrizes View & Projection).
* [🌍 **`src/world/`**](../src/world/README.md) — Gerenciamento de Chunks ($16 \times 16 \times 16$), Face Culling na CPU e Ruído Procedural.
* [🎨 **`src/rendering/`**](../src/rendering/README.md) — Buffers de GPU (VAO/VBO/EBO), Frustum Culling e Shaders.
* [🧮 **`src/math/`**](../src/math/README.md) — Álgebra Linear (Vetores, Matrizes $4\times4$, Bounding Boxes AABB).
* [🔌 **`src/integration/`**](../src/integration/README.md) — Pontos de extensão e pontes de comunicação com a Equipe B.

---

## 🎨 Arquivos de Shaders (`assets/shaders/`)

* [`world.vert`](../assets/shaders/world.vert) & [`world.frag`](../assets/shaders/world.frag) — Shaders de terreno com iluminação direcional difusa.
* [`highlight.vert`](../assets/shaders/highlight.vert) & [`highlight.frag`](../assets/shaders/highlight.frag) — Shaders de seleção e contorno para interação.
