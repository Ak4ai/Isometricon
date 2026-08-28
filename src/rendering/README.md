# 🎨 Módulo de Renderização (OpenGL Core)

Gerencia a comunicação de baixo nível com a GPU, buffers e Shaders:

## Responsabilidades:
1. **Gerenciamento de Buffers:**
   - Criação e alocação de `VAO` (Vertex Array Object), `VBO` (Vertex Buffer Object) e `EBO` (Element Buffer Object).
   - Suporte a buffers estáticos por Chunk ou buffers dinâmicos instanciados (`glDrawElementsInstanced`).
2. **Compilação e Linkagem de Shaders:**
   - Leitura de arquivos `.vert` e `.frag` em `assets/shaders/`.
   - Tratamento de erros de compilação de shader e uniforms caching.
3. **Frustum Culling:**
   - Teste de interseção entre os 6 planos do Frustum Ortográfico e a Bounding Box (AABB) de cada Chunk.
