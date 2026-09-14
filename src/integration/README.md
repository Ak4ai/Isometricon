# 🔌 Módulo de Integração

Ponto de contato entre o Motor do Mundo (Equipe A) e o Motor Interativo
(Equipe B).

## VoxelGridProvider

A implementação Python está disponível em:

    from src.integration import VoxelGridProvider

O provider abstrai a organização dos voxels em chunks e expõe consultas
usando coordenadas globais `(x, y, z)`.

Para mundos estáticos, ele recebe um mapeamento de chunks. Para o mundo com
streaming, `block_lookup=world_manager.neighbor_at` mantém as consultas ligadas
aos chunks atualmente carregados. Uma região ausente continua retornando
`AIR`; nenhuma consulta carrega chunks nem aguarda o worker assíncrono.

`get_top_solid_block(x, z)` percorre somente a coluna vertical atualmente
usada pelo `WorldManager` (chunk `y=0`) e também retorna `-1` quando a coluna
não está carregada. O mundo streamado não possui bounds globais fixos.

### Consultas

    get_block_at(x, y, z)
    is_solid(x, y, z)
    get_top_solid_block(x, z)
    get_block_bounding_box(x, y, z)

Também estão disponíveis aliases camelCase compatíveis com a
INTEGRATION_SPEC.md:

    getBlockAt(...)
    isSolid(...)
    getTopSolidBlock(...)
    getBlockBoundingBox(...)

### Coordenadas

As coordenadas fornecidas à interface são sempre coordenadas globais.

A conversão para chunk/local é feita internamente e suporta coordenadas
negativas.

### Semântica de ocupação e superfície

`is_solid()` significa "bloco ocupado": qualquer valor diferente de `AIR`,
inclusive `WATER` e `LEAVES`. A superfície tática válida para tokens e grade
é uma política separada de `src.interaction.surface`.

### Integração de frame

O estado de câmera/frame é passado diretamente pelo loop principal ao
raycasting e aos renderizadores. Hover/highlight e visibilidade da grade são
controlados diretamente por `BlockHighlightRenderer` e `GridOverlayRenderer`;
não há `CameraStateProvider` nem `HighlightBridge` no contrato atual.

### AABB

Cada voxel ocupa:

    [x, x+1] × [y, y+1] × [z, z+1]

O provider apenas fornece a geometria da AABB. Algoritmos de raycasting
e interseção permanecem responsabilidade da camada interativa.
