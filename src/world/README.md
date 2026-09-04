# 🌍 Módulo de Mundo & Chunks (Equipe A)

Responsável pelo armazenamento, geração e otimização dos dados de blocos do terreno 3D:

## Responsabilidades:
1. **Estrutura de Chunks:**
   - Dimensão padrão de $16 \times 16 \times 16$ blocos (4096 voxels por chunk).
   - Tipagem de bloco compacta (`uint8_t` ou `enum BlockType`).
2. **Geração Procedural de Terreno:**
   - Value noise 2D suave com múltiplas oitavas normalizadas.
   - Camadas de pedra, terra e grama; água nas depressões abaixo do nível do mar.
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
A representação AABB contém somente dados; raycasting permanece fora deste módulo.

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
para eliminar. Sistemas globais e otimizações adicionais permanecem para etapas futuras.


## Terreno procedural (Issue #7)

`TerrainGenerator` é uma configuração imutável e um gerador CPU, sem OpenGL,
GLFW ou estado aleatório global. `Chunk3D` continua apenas armazenamento;
`ChunkMesher` continua responsável pela geometria visível.

```python
from src.world import Chunk3D, ChunkMesher, TerrainGenerator

generator = TerrainGenerator(seed=1234)
height = generator.get_height(20, -15)  # Y inteiro do último voxel sólido
chunk = Chunk3D(0, 0, 0)
generator.populate_chunk(chunk)        # substitui todos os voxels, retorna None
mesh_data = ChunkMesher().build(chunk)

# Coleção finita de coordenadas (chunk_x, chunk_y, chunk_z), inclusive negativas.
region = generator.generate_region(
    (x, y, z) for x in (-1, 0) for y in (-1, 0, 1) for z in (-1, 0)
)
# dict[(chunk_x, chunk_y, chunk_z), Chunk3D]; duplicatas são ignoradas.
```

### Formulação e escolha do algoritmo

Value noise interpola quatro valores pseudoaleatórios em uma malha 2D.
É mais simples que Perlin/Simplex e suficiente para um relevo de colinas e
vales sem cavernas. Não foi adicionada biblioteca externa: NumPy já faz parte
do projeto; `hashlib.blake2b` e as operações matemáticas vêm da biblioteca padrão.
BLAKE2b é usado somente como uma função estável de dispersão de coordenadas,
não como uma funcionalidade de segurança.

Cada vértice inteiro `(i,j)` recebe um valor em `[-1,1]`, derivado do digest
BLAKE2b de 8 bytes de `"seed:i:j"` em ASCII, interpretado como inteiro big-endian:

$$
v(i,j)=2\frac{\operatorname{digest}(seed,i,j)}{2^{64}-1}-1.
$$

Para `(x,z)`, tome `i=floor(x)`, `j=floor(z)`, inclusive no domínio negativo.
Os pesos de interpolação são `u=s(x-i)` e `v=s(z-j)`, com

$$
s(t)=6t^5-15t^4+10t^3.
$$

Interpolamos primeiro os pares horizontais, depois os resultados em Z.
A interpolação quintica tem primeira e segunda derivadas nulas nos extremos,
produzindo ruído contínuo e suave entre células da malha.

Para `k=octaves`, `p=persistence` e `l=lacunarity`:

$$
A_0=1,\quad A_{i+1}=pA_i,\qquad
f_0=frequency,\quad f_{i+1}=lf_i,
$$
$$
N(x,z)=\frac{\sum_{i=0}^{k-1}A_i\,noise(f_i x,f_i z)}
                 {\sum_{i=0}^{k-1}A_i},
\qquad h(x,z)=base\_height+\lfloor amplitude\cdot N(x,z)\rfloor.
$$

A normalização mantém `N` em `[-1,1]` independentemente da quantidade de
oitavas; um clamp corrige possíveis resíduos numéricos. A altura pertence a
`[base_height + floor(-amplitude), base_height + floor(amplitude)]`.
A quantização por `floor` cria degraus de voxels, não uma superfície contínua.
`get_height` retorna o Y da célula sólida; seu topo geométrico é `h+1`.

### Parâmetros e defaults

| Parâmetro | Default | Efeito |
|---|---:|---|
| `seed` | `0` | Identidade do mapa; aceita inteiros zero e negativos. |
| `base_height` | `8` | Deslocamento vertical em blocos. |
| `amplitude` | `6.0` | Limite da variação vertical; zero produz terreno plano. |
| `frequency` | `1/24` | Frequência em células de ruído por bloco; menor produz colinas mais largas. |
| `octaves` | `3` | Quantidade de escalas de detalhe somadas. |
| `persistence` | `0.5` | Multiplicador do peso por oitava; menor reduz detalhes finos. |
| `lacunarity` | `2.0` | Multiplicador da frequência por oitava. |
| `dirt_depth` | `3` | Número de células de terra imediatamente abaixo da superfície. |
| `sea_level` | `7` | Y da última célula de água nas colunas submersas. |

Os defaults limitam a superfície a `[2,14]`: relevos visíveis no chunk de
16 células, com espaço acima e água nas regiões baixas. Isso é uma conveniência
de demonstração, não um limite do mundo. Alturas e nível do mar podem atravessar
quaisquer chunks Y. Valores inteiros seguem a validação de coordenadas de
`Chunk3D`. Os demais valores devem ser reais finitos: amplitude >= 0,
frequency > 0, octaves >= 1, persistence em [0,1], lacunarity >= 1,
dirt_depth >= 0. Configurações cuja frequência de oitavas transborda são rejeitadas.

### Camadas e nível do mar

Para `h=get_height(world_x,world_z)` e `d=dirt_depth`:

- `world_y < h-d`: STONE.
- `h-d <= world_y < h`: DIRT.
- `world_y == h`: GRASS se `h >= sea_level`; DIRT se submerso.
- `h < world_y <= sea_level`: WATER.
- `world_y > max(h,sea_level)`: AIR.

Água preenche depressões até um nível constante; não há simulação de fluidos,
rios ou garantia de que cada depressão seja um lago fechado. Não há grama
submersa nem novos tipos de blocos. O terreno sólido estende-se para baixo;
não se adiciona bedrock ou piso artificial em Y=0.

### Continuidade, determinismo e custo

`populate_chunk` usa `chunk.local_to_world(x,0,z)` e calcula a altura uma única
vez por coluna. A origem Y retornada converte as faixas globais em fatias locais,
preservando a identidade do array, shape 16³, dtype uint8, ordem Fortran e AABB.
Uma segunda chamada substitui inclusive blocos antigos acima do relevo.

X=15 e X=16 (ou X=-1 e X=0) são amostras consecutivas da mesma função global;
o mesmo vale para Z. Nenhum ruído é reiniciado na fronteira. Chunks Y apenas
recortam intervalos diferentes da mesma coluna. Mesma seed, configuração e
coordenadas reproduzem exatamente o mapa, independentemente da ordem de geração
e do `PYTHONHASHSEED`. Alterações futuras do algoritmo podem mudar mapas; não
há promessa de compatibilidade de saves entre versões. Coordenadas de ruído
usam floats, portanto o gerador não promete precisão ilimitada a distâncias extremas.

Custo por chunk: `O(SIZE² * octaves + SIZE³)`. Preenchimento por fatias NumPy,
sem calcular ruído por voxel, sem tabelas pesadas ou caches globais.
`generate_region` compõe chamadas de preenchimento e não é um WorldManager.

### Integração e demonstração

Fluxo: **seed → ruído → altura global → camadas → Chunk3D → ChunkMesher → renderer**.
Para remover faces compartilhadas, `ChunkMesher.build(chunk, neighbor_at)` recebe
uma consulta aos chunks gerados, retornando AIR para posições desconhecidas.
Vértices permanecem locais; a translação do chunk é aplicada no renderer.

```bash
python src/main.py --terrain
```

A opção mostra quatro chunks em X/Z `(-1,0)`, Y=0, seed 1234. A escala visual
0.2 e a translação são matrizes do renderer, sem modificar dados ou AABBs.
Usa `TexturedMesh`, shaders existentes, cores dos BlockTypes e o asset neutro
`white_concrete.png` para toda a malha. Não há mapeamento de material/atlas novo.
A água aparece azul e opaca nesta demonstração: blending e ordenação de
transparências continuam futuros, assim como a otimização de faces entre águas.
Sem `--terrain`, permanece a demonstração original do cubo e suas texturas.
Os controles existentes de rotação, zoom e pan continuam disponíveis.

`tests/test_terrain.py` cobre determinismo (inclusive processos independentes),
seeds diferentes/zero/negativas, limites, continuidade X/Z, camadas e água,
chunks Y positivos/negativos, armazenamento/AABB, ordem, preenchimento repetido,
validação da API e geometria/índices do mesher sem contexto gráfico.

Fora desta etapa: WorldManager/streaming, save/load, cavernas, biomas, vegetação,
estruturas, greedy meshing, frustum culling, materiais avançados e Equipe B.
