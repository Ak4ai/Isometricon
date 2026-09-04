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
   - Gera vértices contendo `[posição (x, y, z), normal (nx, ny, nz), UV (u, v), cor (r, g, b)]`.

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
Não há geração procedural, raycasting ou renderização
de chunks nesta implementação. A representação AABB contém somente dados.

## Meshing CPU (Issue #6)

`ChunkMesher` transforma `Chunk3D` em `ChunkMeshData`, sem importar OpenGL,
criar VAO/VBO/EBO ou modificar voxels. O renderer continua responsável pela GPU.

```python
from src.world import BlockType, Chunk3D, ChunkMesher

chunk = Chunk3D(-1, 0, 0)
chunk.blocks[:2, :2, :2] = BlockType.STONE
mesh_data = ChunkMesher().build(chunk)
assert mesh_data.face_count == 24

# Somente no renderer, com contexto OpenGL ativo:
# mesh = TexturedMesh(mesh_data.vertices, mesh_data.indices)
# u_Model deve incluir a translação chunk.local_to_world(0, 0, 0).
```

O algoritmo visita os voxels e ignora AIR. Para cada outro bloco, examina
os seis vizinhos (+X, -X, +Y, -Y, +Z, -Z) e emite a face se o vizinho não
ocluir completamente. Consulta `get_block()` apenas após conferir limites,
sem índices negativos ou wrap do ndarray.

A política central `is_opaque(tipo)` em `block.py` considera **DIRT, GRASS,
STONE e WOOD** oclusores. **AIR, WATER e LEAVES** não ocluem. Existência
(`tipo != AIR`), solidez para colisão (ainda futura) e oclusão são conceitos
diferentes. WATER/LEAVES geram quads; entre dois deles, mesmo do mesmo tipo,
as faces de contato são preservadas. Em contato com STONE, apenas a face
do bloco transparente voltada para STONE é descartada. Essa política
conservadora não implementa blending, ordenação de transparência, materiais
ou associação de BlockType a arquivos de textura. O shader atual já faz
alpha discard; sua configuração permanece responsabilidade do renderer.

**Bordas:** por padrão, o exterior é AIR. Opcionalmente,
`build(chunk, neighbor_at=consulta)` aceita uma função `(world_x, world_y,
world_z) -> BlockType | int`, chamada somente para vizinhos externos.
Coordenadas podem ser negativas. A função deve devolver AIR para regiões
desconhecidas; IDs inválidos e erros da consulta são propagados. O chamador
fica responsável por reconstruir as malhas afetadas após mudanças dos
vizinhos. Isso permite culling entre chunks sem antecipar WorldManager ou
o contrato global VoxelGridProvider.

**Formato de saída:**

- `vertices`: ndarray C-contíguo `float32`, shape `(vertex_count, 11)`.
  Ordem **Pos3 + Normal3 + UV2 + Color3**, stride 44 bytes, atributos 0/1/2/3
  e offsets 0/12/24/32 bytes, compatíveis com `TexturedMesh` e
  `world_textured.vert/.frag`. A descrição antiga Pos+Normal+Color da issue
  não substitui o pipeline texturizado atual.
- `indices`: ndarray C-contíguo `uint32`, shape `(index_count,)`.
- Cada face: 4 vértices e 6 índices CCW vistos do exterior, normais axiais
  constantes. Os vértices não são compartilhados entre faces com normais/UVs
  diferentes. `face_count`, `vertex_count` e `index_count` são propriedades.
- Posições locais: a célula `(x,y,z)` ocupa `[x,x+1] × [y,y+1] × [z,z+1]`;
  a origem mundial é aplicada pelo renderer em `u_Model`, preservando AABB
  e as conversões da Issue #5. Não há deslocamento de meio voxel.
- UVs cobrem `[0,1]²` em cada face, com a mesma orientação do cubo do main.
  Uma mesma textura é reutilizada em todas as faces; não há atlas/material
  novo. A cor RGB é `get_block_color(tipo)` e modula a textura como no shader.
- Chunk vazio retorna shapes `(0,11)` e `(0,)`, sem vértices renderizáveis.

**Complexidade:** O(n) para n voxels, com no máximo seis consultas de
vizinhança por voxel não AIR (assumindo callback O(1)). A montagem usa uma
descrição temporária por face e aloca os arrays no tamanho exato, sem objetos
por vértice. Memória temporária e saída O(f), com f ≤ 6n. Não há greedy meshing.

Contagens: um bloco = 6 faces; dois adjacentes = 10; linha de N = 4N+2;
cubo 2³ = 24; chunk opaco 16³ = 1536 (6144 vértices, 9216 índices), contra
24576 faces de cubos completos: **93,75% de redução**, com exterior AIR.
O percentual depende da ocupação; blocos isolados não oferecem faces internas
para eliminar. Geração procedural (#7), integração visual de chunks e
sistemas globais permanecem para etapas futuras.
