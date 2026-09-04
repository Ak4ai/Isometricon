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

## Fundação lógica (Issue #5)

`from src.world import BlockType, Chunk3D, get_block_color`

- `BlockType` é um `IntEnum` com IDs AIR=0 até LEAVES=6.
  `get_block_color(tipo)` e `BLOCK_COLORS` oferecem RGB em [0, 1],
  compatível com os atributos de cor de Mesh/TexturedMesh. Cores não definem
  opacidade, colisão nem associação com assets.
- `Chunk3D(chunk_x=0, chunk_y=0, chunk_z=0, blocks=None)` cria 16³ células AIR.
  `blocks` é um ndarray uint8 de 4096 bytes (sem contar metadados Python/NumPy).
  O acesso é `blocks[x, y, z]`, em ordem Fortran: X varia mais rápido,
  preservando `x + 16 * (y + 16 * z)` de ARCHITECTURE.md.
- `get_block(x, y, z)` retorna BlockType; `set_block(x, y, z, tipo)`
  valida e modifica uma célula em O(1). Índices fora de [0, 16) geram
  IndexError; coordenadas não inteiras ou booleanas geram TypeError.
  IDs desconhecidos geram ValueError. A edição direta de `blocks` deve
  preservar shape, dtype e IDs; prefira os métodos para acesso validado.
- O array opcional deve ter shape (16, 16, 16), dtype inteiro e IDs válidos.
  A conversão para uint8 ocorre somente após validação e sempre cria uma
  cópia independente. Floats, booleanos e objetos são rejeitados.
- `local_to_world(x, y, z)` aplica `chunk * SIZE + local`.
  `world_to_local(x, y, z)` faz a inversa e rejeita células de outro chunk.
  Para selecionar chunks futuramente, use `world // SIZE` e
  `world % SIZE` por eixo, inclusive em coordenadas negativas.
- `get_bounding_box()` retorna `src.math.aabb.AABB`, com `min` e `max`
  em vec3 NumPy float32, seguindo a precisão geométrica do módulo matemático.
  A posse das células é [min, max), e max = min + SIZE. Coordenadas lógicas
  permanecem inteiras. O cubo de demonstração centrado em main.py precisará
  ser posicionado no centro da célula pela futura renderização.

O contrato VoxelGridProvider permanece futuro: consultas globais, solidez,
topo de coluna e AABB por bloco serão compostas sobre esta fundação.
Não há geração procedural, meshing, face culling, raycasting ou renderização
de chunks nesta implementação. A representação AABB contém somente dados.
