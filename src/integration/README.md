# 🔌 Módulo de Integração (Team B Bridge)

Ponto de contato e exportação de estado para o **Motor Interativo (Equipe B)**:

## Componentes:
1. **`VoxelGridProvider`:**
   - Interface de consulta de blocos e colisão de miniaturas.
2. **`RaycastTarget`:**
   - Fornece AABBs e dados de geometria para o algoritmo de Raycasting / Mouse Picking da Equipe B.
3. **`HighlightBridge`:**
   - Permite que a Equipe B passe as coordenadas $(X, Y, Z)$ e cor de seleção para ativar os shaders de destaque.
