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

## Superfície tática e grid (#29)

`surface.py` concentra as regras reutilizáveis `is_tactical_surface()` e
`is_tactical_column()`: `DIRT`, `GRASS`, `STONE` e `WOOD` sustentam uma célula;
`AIR`, `WATER` e `LEAVES` não. Água acima de um suporte também invalida a coluna.
O renderer em `src/interactive/grid_overlay.py` recebe snapshots dos chunks
carregados e monta segmentos `GL_LINES` em `topo_do_voxel + 1 + 0.002`.
Cada contorno segue a altura de sua própria célula, portanto desníveis não são
unidos por diagonais que cruzariam faces laterais. Água não recebe grade e
invalida o leito submerso antes de gerar geometria.

O `WorldManager` expõe uma revisão monotônica barata e
`get_loaded_chunks_snapshot()`, uma cópia rasa protegida por lock. O snapshot e
o VBO só são obtidos/refeitos quando a revisão muda, e não são sequer
sincronizados enquanto o grid está desligado. Em regiões contíguas de
streaming, alturas, bloqueadores e segmentos compartilhados são calculados em
arrays NumPy; snapshots com ilhas muito distantes usam um caminho esparso para
não alocar a área vazia entre elas. Revisões consecutivas de uma mesma sequência
de streaming são coalescidas e o snapshot só é sincronizado quando não há
solicitações, geração ou resultados pendentes no `WorldManager`. A
renderização usa as mesmas matrizes `Projection`, `View` e `Model` animada do terreno, mantém
o depth test ativo, desativa escrita de profundidade e aplica apenas esse
pequeno offset contra z-fighting. `G` alterna a visibilidade por evento PRESS.
Não há suporte a múltiplos andares ou navegação de cavernas nesta etapa.

## Issues Relacionadas

- [#27 — Raycasting 3D](https://github.com/Ak4ai/Isometricon/issues/27)
- [#28 — Shaders de Destaque](https://github.com/Ak4ai/Isometricon/issues/28)
- [#29 — Grid Overlay](https://github.com/Ak4ai/Isometricon/issues/29)
- [#30 — Sistema de Tokens](https://github.com/Ak4ai/Isometricon/issues/30)
- [#31 — UI Overlay](https://github.com/Ak4ai/Isometricon/issues/31)

## Documentação Completa

Consulte [docs/EQUIPE_B_ARCHITECTURE.md](../../docs/EQUIPE_B_ARCHITECTURE.md) para a especificação técnica detalhada.
