# 🧮 Módulo Matemático (Matrizes & Vetores)

Fornece operações de álgebra linear essenciais para o pipeline de Computação Gráfica:

## Componentes:
1. **`Vector3` / `Vector4`:**
   - Adição, subtração, multiplicação por escalar.
   - Produto escalar (`dot product`), produto vetorial (`cross product`), normalização e distância.
2. **`Matrix4` (Matrizes $4 \times 4$ Homogêneas):**
   - Matriz Identidade, Translação, Rotação (Euler e Quaternions) e Escala.
   - Matriz de Visão (`LookAt`).
   - Matriz de Projeção Ortográfica (`Orthographic`).
   - Multiplicação de matrizes e inversão de matriz.
3. **`AABB` (Axis-Aligned Bounding Box):**
   - Representação por `min` e `max` vec3.
   - Teste de interseção Raio-AABB e Frustum-AABB.
