"""Pacote do Motor Interativo (Equipe B).

Contém os módulos de interação com o tabuleiro:
- raycasting: Mouse Picking 3D
- grid_overlay: Renderização do grid quadriculado
- token_manager: Miniaturas de personagens e monstros
- ui_renderer: Interface de fichas de RPG em OpenGL
"""

from src.interaction.raycast import (
    DEFAULT_MAX_DISTANCE,
    Ray,
    RayHit,
    is_pickable_block,
    ray_aabb_intersection,
    raycast_voxels,
    screen_to_ndc,
    screen_to_world_ray,
)

__all__ = [
    "DEFAULT_MAX_DISTANCE",
    "Ray",
    "RayHit",
    "screen_to_ndc",
    "screen_to_world_ray",
    "raycast_voxels",
    "ray_aabb_intersection",
    "is_pickable_block",
]
