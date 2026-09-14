# Contrato de Integração Atual (Motor do Mundo ↔ Motor Interativo)

## Visão geral

O Isometricon executa o Motor do Mundo e o Motor Interativo no mesmo processo e
no mesmo loop de frame. O contrato de dados entre as camadas é
`src.integration.VoxelGridProvider`; não há bridges de câmera ou de destaque.

```
WorldManager ──neighbor_at──► VoxelGridProvider ──► raycast_voxels
       │                                                    │
       ├── chunks carregados ──► GridOverlayRenderer        ▼
       └── terreno renderizado ◄── BlockHighlightRenderer / PlayerToken

IsometricCamera ──► View, Projection, Model, viewport ──► raycasting e renderizadores
```

## Consulta de terreno: `VoxelGridProvider`

```python
from src.integration import VoxelGridProvider

provider = VoxelGridProvider(block_lookup=world_manager.neighbor_at)
```

O provider recebe e retorna coordenadas globais `(x, y, z)`. Para testes ou
mundos estáticos, pode receber um mapeamento de `Chunk3D`; para o mundo em
produção, `block_lookup=WorldManager.neighbor_at` consulta somente os chunks
atualmente carregados.

| Método | Contrato |
|---|---|
| `get_block_at(x, y, z)` | Retorna `BlockType`; regiões/chunks ausentes retornam `AIR`. |
| `is_solid(x, y, z)` | Retorna se a célula está ocupada, isto é, se é diferente de `AIR`. |
| `get_top_solid_block(x, z)` | Retorna o maior Y não-`AIR` na coluna carregada, ou `-1` se ela não existir. No streaming atual, a busca cobre a coluna vertical carregada `y=0` (0–15). |
| `get_block_bounding_box(x, y, z)` | Retorna a AABB unitária `[x,x+1] × [y,y+1] × [z,z+1]`. |

As conversões para chunk/local usam divisão inteira e módulo, preservando
coordenadas negativas. As consultas não iniciam carregamento, não aguardam a
worker e não alteram o estado de streaming. O mundo é streamado e não possui
bounds globais fixos.

### Ocupação não é superfície tática

Para o provider e o raycasting padrão, todo bloco diferente de `AIR` é
ocupado/atingível, incluindo `WATER` e `LEAVES`. A política de uma célula
capaz de sustentar tokens e grade está em `src.interaction.surface`:
`DIRT`, `GRASS`, `STONE` e `WOOD` são superfícies táticas; água e folhas não.

## Estado de câmera e frame

No frame, `src.main` calcula diretamente:

```python
projection = camera.get_projection_matrix(window.width, window.height)
view = camera.get_view_matrix()
model = camera.get_animated_model_matrix()
mouse_x, mouse_y = window.get_cursor_pos_framebuffer()
```

Esses valores são passados diretamente a `screen_to_world_ray`,
`WorldManager.render`, `GridOverlayRenderer.render` e
`BlockHighlightRenderer.render`. O `Model` rotaciona o tabuleiro em torno do
`camera.target` usado pela `View` no mesmo frame, mantendo o foco invariável
durante toda a animação Q/E. O raycasting usa a inversa de
`Projection @ View @ Model`, mantendo o espaço lógico de voxels consistente
durante pan, zoom, resize e rotação Q/E. Uma `CameraStateProvider` duplicaria
esse estado sem adicionar um limite arquitetural útil.

O WASD usa os vetores forward/right transformados pela inversa de
`board_rotation`. Assim, o controle acompanha a orientação visual discreta sem
depender da interpolação em `current_rotation`.

## Highlight e grid

O loop principal calcula o hover por raycast e chama
`BlockHighlightRenderer.render` diretamente quando há um hit. Sem hit, nenhum
destaque é desenhado; durante pan, o hover é suspenso. O grid é controlado por
`GridOverlayRenderer` e sua visibilidade é alternada diretamente pela tecla
`G`; sua malha é atualizada a partir do snapshot e da revisão dos chunks
carregados.

Portanto, `HighlightBridge` não faz parte do contrato atual. Seleção
persistente, alcance de movimento e click-to-move são funcionalidades futuras
e não são inferidas da existência de raycasting, token ou highlight de hover.

## Ordem por frame

1. Processar entrada, atualizar token, câmera e streaming.
2. Obter View, Projection, Model, viewport e cursor em pixels de framebuffer.
3. Fazer raycast contra o `VoxelGridProvider` dos chunks carregados.
4. Renderizar o mundo.
5. Renderizar grid, destaques e token com as mesmas matrizes.
6. Apresentar o framebuffer.

## Verificação

Os testes de integração cobrem provider estático, limites de chunk,
coordenadas negativas, AABB, consulta dinâmica via `WorldManager` e unload de
chunks. Os testes de raycasting cobrem unprojection, DDA e o provider dinâmico.
