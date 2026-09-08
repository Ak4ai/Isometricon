# 🔌 Módulo de Integração (Team B Bridge)

Ponto de contato entre o Motor do Mundo (Equipe A) e o Motor Interativo
(Equipe B).

## VoxelGridProvider

A implementação Python está disponível em:

    from src.integration import VoxelGridProvider

O provider abstrai a organização dos voxels em chunks e expõe consultas
usando coordenadas globais `(x, y, z)`.

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

### AABB

Cada voxel ocupa:

    [x, x+1] × [y, y+1] × [z, z+1]

O provider apenas fornece a geometria da AABB. Algoritmos de raycasting
e interseção permanecem responsabilidade da camada interativa.
