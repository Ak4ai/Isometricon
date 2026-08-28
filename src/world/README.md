# 🌍 Módulo de Mundo & Chunks (Equipe A)

Responsável pelo armazenamento, geração e otimização dos dados de blocos do terreno 3D:

## Responsabilidades:
1. **Estrutura de Chunks:**
   - Dimensão padrão de $16 \times 16 \times 16$ blocos (4096 voxels por chunk).
   - Tipagem de bloco compacta (`uint8_t` ou `enum BlockType`).
2. **Geração Procedural de Terreno:**
   - Algoritmo de Ruído Perlin/Simplex 2D/3D com múltiplas oitavas (fractal noise).
   - Camadas de bioma: pedra profunda, terra intermediária e grama no topo.
3. **Face Culling (CPU Meshing):**
   - Itera sobre os blocos e inclui na malha apenas as faces que fazem fronteira com blocos de ar (`AIR`) ou transparentes.
   - Gera vértices contendo `[posição (x, y, z), normal (nx, ny, nz), cor (r, g, b)]`.
