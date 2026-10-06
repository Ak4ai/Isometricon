# 🔗 Contrato de Integração (Equipe A $\leftrightarrow$ Equipe B)

## 1. Visão Geral

Este documento define os pontos de contato entre os dois subprojetos, permitindo que a **Equipe A** (Motor do Mundo) e a **Equipe B** (Motor Interativo) desenvolvam suas partes em paralelo e as unam sem conflitos de arquitetura.

---

## 2. API de Consulta do Mundo (`VoxelGridProvider`)

A Equipe A fornece a seguinte interface para consultas espaciais:

* `getBlockAt(x, y, z)`: Retorna o tipo de bloco em uma posição global.
* `isSolid(x, y, z)`: Retorna `true` se o bloco for sólido (usado pela Equipe B para posicionamento e colisão de miniaturas).
* `getTopSolidBlock(x, z)`: Retorna a maior coordenada Y com bloco sólido na coluna (X, Z).
* `getBlockBoundingBox(x, y, z)`: Retorna o AABB `(min, max)` para o Raycasting 3D da Equipe B.

---

## 3. API de Renderização de Destaque (`HighlightRenderer`)

A Equipe B aciona o destaque do cursor enviando:

* `setHighlightedBlock(x, y, z, color)`: Ativa o efeito de seleção sobre o bloco.
* `clearHighlight()`: Remove o destaque atual.
* `setGridOverlayVisible(bool)`: Exibe/oculta a grade sobre as faces superiores do terreno.

---

## 4. Matrizes de Visualização Compartilhadas

A Equipe A disponibiliza as matrizes da câmera isométrica para conversão de coordenadas de tela (pixel do clique) em raio tridimensional no mundo:

* `mat4 ViewMatrix`
* `mat4 ProjectionMatrix`
* `vec4 Viewport`
