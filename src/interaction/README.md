# 🟦 Motor Interativo — Equipe B

Módulo principal da **Equipe B** do projeto *Isometricon*.

Este pacote contém toda a lógica de interação do usuário com o tabuleiro:

## Módulos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `raycasting.py` | Algoritmo de Mouse Picking (2D → Raio 3D → Bloco) |
| `grid_overlay.py` | Renderização do grid quadriculado sobre o terreno |
| `token_manager.py` | Gerenciamento de miniaturas/tokens com matrizes de transformação |
| `ui_renderer.py` | Overlay de UI: fichas de RPG, status e painel de controle |

## Dependências

- `src/integration/` — Pontos de contato com a Equipe A (VoxelGridProvider, HighlightBridge, CameraStateProvider)
- `src/rendering/` — TexturedMesh para renderização dos tokens
- `src/camera/` — IsometricCamera para cálculos de raycasting

## Issues Relacionadas

- [#27 — Raycasting 3D](https://github.com/Ak4ai/Isometricon/issues/27)
- [#28 — Shaders de Destaque](https://github.com/Ak4ai/Isometricon/issues/28)
- [#29 — Grid Overlay](https://github.com/Ak4ai/Isometricon/issues/29)
- [#30 — Sistema de Tokens](https://github.com/Ak4ai/Isometricon/issues/30)
- [#31 — UI Overlay](https://github.com/Ak4ai/Isometricon/issues/31)

## Documentação Completa

Consulte [docs/EQUIPE_B_ARCHITECTURE.md](../../docs/EQUIPE_B_ARCHITECTURE.md) para a especificação técnica detalhada.
