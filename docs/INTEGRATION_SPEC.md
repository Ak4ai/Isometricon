# 🔌 Especificação Completa do Contrato de Integração (Equipe A ↔ Equipe B)

<div align="center">

[![Equipe A](https://img.shields.io/badge/Equipe%20A-Motor%20do%20Mundo-228B22?style=flat-square)](ARCHITECTURE.md)
[![Equipe B](https://img.shields.io/badge/Equipe%20B-Motor%20Interativo-0066CC?style=flat-square)](EQUIPE_B_ARCHITECTURE.md)

</div>

---

## 1. Visão Geral

Para garantir total independência de desenvolvimento durante os 30 dias e uma integração final simples e sem atritos, definem-se os seguintes contratos de dados e serviços entre a **Equipe A (Motor do Mundo)** e a **Equipe B (Motor Interativo)**.

O módulo de ponte está em `src/integration/` e é mantido pela **Equipe A**, mas consumido pela **Equipe B**.

---

## 2. Diagrama de Comunicação

```
┌───────────────────────────────────┐     ┌───────────────────────────────────┐
│      EQUIPE A (Motor do Mundo)    │     │   EQUIPE B (Motor Interativo)     │
│                                   │     │                                   │
│  IsometricCamera ──────────────────────►  CameraStateProvider              │
│                                   │     │       (view, proj, viewport)      │
│                                   │     │              │                    │
│  VoxelWorld / Chunks ──────────────────►  VoxelGridProvider                │
│                                   │     │  (getBlockAt, isSolid, getTop)   │
│                                   │     │              │                    │
│  HighlightRenderer ◄───────────────────── HighlightBridge                  │
│  (shader ativado pela Equipe A)   │     │  (setHighlight, clearHighlight)   │
│                                   │     │              │                    │
│  GridOverlay ◄─────────────────────────── setGridOverlayVisible            │
└───────────────────────────────────┘     └───────────────────────────────────┘
```

---

## 3. Contrato 1 — Acesso a Dados do Terreno (`VoxelGridProvider`)

A Equipe A expõe métodos de consulta rápida para que a Equipe B possa realizar Raycasting 3D e validar posicionamento de miniaturas.

### Interface Python

```python
# src/integration/voxel_provider.py

class VoxelGridProvider:
    """
    Interface de consulta espacial do VoxelGrid para uso da Equipe B.
    Implementada pela Equipe A, consumida pela Equipe B.
    """

    def get_block_at(self, world_x: int, world_y: int, world_z: int) -> int:
        """
        Retorna o tipo do bloco (BlockType) na coordenada do mundo.
        Retorna 0 (AIR) para coordenadas fora dos limites do mundo.
        """
        ...

    def is_solid(self, world_x: int, world_y: int, world_z: int) -> bool:
        """
        Retorna True se o bloco em (x, y, z) é sólido (não-ar).
        Usado pela Equipe B para validar movimento de tokens.
        """
        ...

    def get_top_solid_block(self, world_x: int, world_z: int) -> int:
        """
        Retorna a coordenada Y do bloco sólido mais alto na coluna (x, z).
        Usado para posicionar tokens sobre o terreno.
        """
        ...

    def get_block_bounding_box(self, world_x: int, world_y: int, world_z: int) -> AABB:
        """
        Retorna a AABB (Axis-Aligned Bounding Box) do bloco em (x, y, z).
        Usado pelo algoritmo de ray-AABB intersection.
        """
        ...

    def get_world_bounds(self) -> tuple[int, int, int]:
        """
        Retorna (width, height, depth) do mundo em blocos.
        """
        ...
```

### Tipos de Bloco (`BlockType`)

| ID | Nome | Sólido |
|:--- |:--- |:---: |
| `0` | `AIR` | ❌ |
| `1` | `DIRT` | ✅ |
| `2` | `GRASS` | ✅ |
| `3` | `STONE` | ✅ |
| `4` | `WATER` | ❌ |
| `5` | `WOOD` | ✅ |
| `6` | `LEAVES` | ❌ |

---

## 4. Contrato 2 — Estado da Câmera (`CameraStateProvider`)

Para que a Equipe B consiga converter coordenadas de tela $(x_{mouse}, y_{mouse})$ em um raio 3D, a Equipe A expõe as matrizes ativas da câmera isométrica por frame.

### Interface Python

```python
# src/integration/camera_provider.py

class CameraStateProvider:
    """
    Exporta estado atual da câmera isométrica para uso do raycasting da Equipe B.
    Deve ser atualizada a cada frame antes do loop de renderização da Equipe B.
    """

    def get_view_matrix(self) -> np.ndarray:
        """Retorna a matriz View 4x4 (float32) da câmera isométrica."""
        ...

    def get_projection_matrix(self) -> np.ndarray:
        """Retorna a matriz Projection 4x4 ortográfica (float32)."""
        ...

    def get_viewport(self) -> tuple[int, int, int, int]:
        """Retorna (x, y, width, height) da viewport OpenGL atual."""
        ...

    def get_camera_target(self) -> np.ndarray:
        """Retorna o ponto de foco da câmera (vec3) no espaço do mundo."""
        ...
```

### Matemática do Raycasting (Projeção Ortográfica)

Para projeção ortográfica, pixels diferentes produzem origens diferentes e
direções paralelas. O raycast desprojeta os dois planos de recorte. Como o
renderer gira o tabuleiro com uma matriz Model animada, usa-se a mesma matriz
na composição $\mathbf{Q}=\mathbf{P}\mathbf{V}\mathbf{M}$:

$$x_{NDC} = \frac{2 \cdot x_{mouse}}{W} - 1, \qquad y_{NDC} = 1 - \frac{2 \cdot y_{mouse}}{H}$$

$$\mathbf{p}_{near}=\operatorname{dehom}\left(\mathbf{Q}^{-1}
(x_{NDC},y_{NDC},-1,1)^T\right)$$

$$\mathbf{p}_{far}=\operatorname{dehom}\left(\mathbf{Q}^{-1}
(x_{NDC},y_{NDC},1,1)^T\right)$$

$$\mathbf{o}=\mathbf{p}_{near}$$

$$\mathbf{d}=\operatorname{normalize}(\mathbf{p}_{far}-\mathbf{p}_{near})$$

O resultado fica no espaço lógico dos voxels, coerente com as coordenadas
globais do `VoxelGridProvider` durante pan, zoom, resize e rotação Q/E.

---

## 5. Contrato 3 — Renderização de Destaque (`HighlightBridge`)

Quando a Equipe B detectar a interseção do raio do mouse com um bloco $(x, y, z)$, ela aciona a renderização de destaque via esta interface.

### Interface Python

```python
# src/integration/highlight_bridge.py

class HighlightBridge:
    """
    Permite que a Equipe B ative/desative efeitos visuais de seleção
    nos shaders de destaque implementados pela Equipe A/B.
    """

    def set_highlighted_block(self,
                               world_x: int, world_y: int, world_z: int,
                               color: np.ndarray) -> None:
        """
        Define o bloco atualmente sob foco do cursor (hover).
        color: vec4 (r, g, b, a) com valores em [0.0, 1.0]
        """
        ...

    def set_selected_block(self,
                            world_x: int, world_y: int, world_z: int,
                            color: np.ndarray) -> None:
        """Define o bloco selecionado (clique confirmado)."""
        ...

    def set_movement_range(self, cells: list[tuple[int, int, int]],
                            color: np.ndarray) -> None:
        """
        Define a lista de células alcançáveis no turno atual.
        Exibidas com cor diferente para indicar alcance de movimento.
        """
        ...

    def clear_highlight(self) -> None:
        """Remove todos os destaques ativos."""
        ...

    def set_grid_overlay_visible(self, visible: bool) -> None:
        """Ativa ou desativa a renderização do grid quadriculado."""
        ...
```

---

## 6. Protocolo de Sincronização por Frame

A ordem de execução por frame quando ambas as equipes estão integradas:

```
┌─── LOOP PRINCIPAL ─────────────────────────────────────────────────────────┐
│                                                                            │
│  1. [Input]    Coletar eventos de mouse e teclado                          │
│                                                                            │
│  2. [Equipe B] Raycasting → detectar bloco sob cursor                      │
│                                                                            │
│  3. [Bridge]   HighlightBridge.set_highlighted_block(x, y, z, color)      │
│                                                                            │
│  4. [Equipe A] Renderizar mundo (chunks, terreno, shaders de iluminação)   │
│                                                                            │
│  5. [Equipe B] Renderizar overlays (highlight, grid, tokens, UI)           │
│                ↑ Deve vir DEPOIS da Equipe A para sobrepor corretamente    │
│                                                                            │
│  6. [Swap]     Apresentar framebuffer final                                │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Opção de Integração via Sockets TCP (Avançado)

Para integração de **processos separados** (cada equipe com seu próprio executável), as equipes podem usar TCP/IP local:

```
┌─────────────────────┐   TCP localhost:9999   ┌─────────────────────┐
│   Equipe A          │ ──────────────────────► │   Equipe B          │
│   (Servidor)        │ ◄────────────────────── │   (Cliente)         │
│   Porta: 9999       │                         │                     │
└─────────────────────┘                         └─────────────────────┘

Mensagens JSON:
  A → B: { "type": "world_state", "chunks": [...], "camera": {...} }
  B → A: { "type": "highlight",   "block": [x, y, z], "color": [...] }
  B → A: { "type": "token_move",  "token_id": "...", "target": [x, y, z] }
```

### Protocolo de Mensagens

| Direção | Tipo | Payload | Frequência |
|:--- |:--- |:--- |:--- |
| A → B | `camera_state` | `view[16], proj[16], viewport[4]` | Por frame |
| A → B | `world_ready` | `bounds[3], chunk_list` | Uma vez |
| B → A | `highlight_set` | `x, y, z, color[4]` | Por evento |
| B → A | `highlight_clear` | — | Por evento |
| B → A | `grid_toggle` | `visible: bool` | Por evento |

---

## 8. Checklist de Integração

### Equipe A entrega para Equipe B:
- [ ] `VoxelGridProvider` funcional com mundo gerado
- [ ] `CameraStateProvider` atualizado por frame
- [ ] `HighlightBridge` ativa shader de destaque
- [ ] Documentação de coordenadas do mundo (sistema de eixos)

### Equipe B entrega para Equipe A:
- [ ] Shaders `highlight.vert/frag` compiláveis
- [ ] Shaders `grid.vert/frag` compiláveis
- [ ] Interface de teste para demonstrar raycasting

### Critério de Integração Final:
- [ ] Clicar no terreno da Equipe A destaca o bloco com shader da Equipe B
- [ ] Token da Equipe B se move pelo terreno gerado pela Equipe A
- [ ] Grid da Equipe B acompanha a câmera da Equipe A

---

*Documento de contrato mantido em conjunto pelas **Equipes A e B** | CEFET-MG — Computação Gráfica*
