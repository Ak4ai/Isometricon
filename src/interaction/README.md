# 🟦 Motor Interativo — Equipe B

Módulo principal da **Equipe B** do projeto *Isometricon*.

Este pacote contém toda a lógica de interação do usuário com o tabuleiro:

## Módulos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `raycast.py` | Unprojection ortográfica e 3D DDA (2D → raio → voxel) |
| `grid_overlay.py` | Renderização do grid quadriculado sobre o terreno |
| `token_manager.py` | Gerenciamento de miniaturas/tokens com matrizes de transformação |
| `ui_renderer.py` | Overlay de UI: fichas de RPG, status e painel de controle |

## Dependências

- `src/integration/` — Pontos de contato com a Equipe A (VoxelGridProvider, HighlightBridge, CameraStateProvider)
- `src/rendering/` — TexturedMesh para renderização dos tokens
- `src/camera/` — IsometricCamera para cálculos de raycasting

## API de Raycasting

```python
from src.interaction import screen_to_world_ray, raycast_voxels

ray = screen_to_world_ray(
    mouse_x, mouse_y, framebuffer_width, framebuffer_height,
    view_matrix, projection_matrix, animated_board_model,
)
hit = raycast_voxels(ray, voxel_provider, max_distance=256.0)
```

`Ray` contém `origin` e `direction` normalizada. `RayHit` contém `block`,
`point`, `distance`, `normal` e `block_type`. O código é CPU puro e consulta o
mundo somente por `VoxelGridProvider.get_block_at()`; chunks ausentes continuam
com a semântica `AIR`, sem iniciar ou aguardar streaming.

Para o terreno, todo bloco diferente de `AIR` é atingível. Isso inclui `WATER`
e `LEAVES`, independentemente da política de opacidade usada pelo mesher.
Durante o pan por Shift + botão esquerdo ou botão do meio, o hover é suspenso e
volta no mesmo frame em que o drag termina.

## Issues Relacionadas

- [#27 — Raycasting 3D](https://github.com/Ak4ai/Isometricon/issues/27)
- [#28 — Shaders de Destaque](https://github.com/Ak4ai/Isometricon/issues/28)
- [#29 — Grid Overlay](https://github.com/Ak4ai/Isometricon/issues/29)
- [#30 — Sistema de Tokens](https://github.com/Ak4ai/Isometricon/issues/30)
- [#31 — UI Overlay](https://github.com/Ak4ai/Isometricon/issues/31)

## Documentação Completa

Consulte [docs/EQUIPE_B_ARCHITECTURE.md](../../docs/EQUIPE_B_ARCHITECTURE.md) para a especificação técnica detalhada.
