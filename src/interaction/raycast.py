"""Mouse picking CPU para o mundo voxel do Isometricon.

O módulo converte pixels em um raio no espaço lógico dos voxels e percorre a
grade com 3D DDA. Não depende de GLFW nem de OpenGL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from src.math import mat4_identity, mat4_inverse
from src.math.aabb import AABB
from src.world import BlockType


DEFAULT_MAX_DISTANCE = 256.0
_DIRECTION_EPSILON = 1e-12


class VoxelLookup(Protocol):
    """Contrato mínimo consumido pelo DDA."""

    def get_block_at(self, world_x: int, world_y: int, world_z: int) -> BlockType:
        ...


@dataclass(frozen=True, eq=False)
class Ray:
    """Raio no espaço lógico do mundo, com direção normalizada."""

    origin: NDArray[np.float32]
    direction: NDArray[np.float32]

    def __post_init__(self) -> None:
        origin = np.asarray(self.origin, dtype=np.float32)
        direction = np.asarray(self.direction, dtype=np.float32)
        if origin.shape != (3,) or direction.shape != (3,):
            raise ValueError("origin e direction devem ser vetores 3D.")
        if not np.isfinite(origin).all() or not np.isfinite(direction).all():
            raise ValueError("origin e direction devem conter valores finitos.")
        length = float(np.linalg.norm(direction))
        if length <= _DIRECTION_EPSILON:
            raise ValueError("direction deve ser um vetor não nulo.")
        object.__setattr__(self, "origin", origin.copy())
        object.__setattr__(self, "direction", (direction / length).astype(np.float32))


@dataclass(frozen=True, eq=False)
class RayHit:
    """Primeiro voxel atingido por um raio."""

    block: tuple[int, int, int]
    point: NDArray[np.float32]
    distance: float
    normal: tuple[int, int, int]
    block_type: BlockType


def screen_to_ndc(
    mouse_x: float,
    mouse_y: float,
    viewport_width: int,
    viewport_height: int,
) -> tuple[float, float]:
    """Converte pixel com origem no topo esquerdo para NDC em ``[-1, 1]``."""

    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("viewport_width e viewport_height devem ser positivos.")
    x_ndc = 2.0 * float(mouse_x) / float(viewport_width) - 1.0
    y_ndc = 1.0 - 2.0 * float(mouse_y) / float(viewport_height)
    return x_ndc, y_ndc


def screen_to_world_ray(
    mouse_x: float,
    mouse_y: float,
    viewport_width: int,
    viewport_height: int,
    view_matrix: np.ndarray,
    projection_matrix: np.ndarray,
    model_matrix: np.ndarray | None = None,
) -> Ray:
    """Desprojeta os pontos near/far do pixel e cria um raio ortográfico.

    ``model_matrix`` deve ser a mesma transformação base usada para desenhar o
    tabuleiro. Incluí-la na inversa de ``P @ V @ M`` mantém o resultado no
    espaço lógico dos voxels durante a rotação animada Q/E.
    """

    x_ndc, y_ndc = screen_to_ndc(
        mouse_x,
        mouse_y,
        viewport_width,
        viewport_height,
    )
    model = mat4_identity() if model_matrix is None else np.asarray(model_matrix)
    inverse_mvp = mat4_inverse(
        np.asarray(projection_matrix, dtype=np.float32)
        @ np.asarray(view_matrix, dtype=np.float32)
        @ np.asarray(model, dtype=np.float32)
    )

    near_h = inverse_mvp @ np.array([x_ndc, y_ndc, -1.0, 1.0], dtype=np.float32)
    far_h = inverse_mvp @ np.array([x_ndc, y_ndc, 1.0, 1.0], dtype=np.float32)
    if abs(float(near_h[3])) <= _DIRECTION_EPSILON or abs(float(far_h[3])) <= _DIRECTION_EPSILON:
        raise ValueError("A desprojeção produziu uma coordenada homogênea inválida.")

    near_world = (near_h[:3] / near_h[3]).astype(np.float32)
    far_world = (far_h[:3] / far_h[3]).astype(np.float32)
    return Ray(near_world, far_world - near_world)


def is_pickable_block(block_type: BlockType | int) -> bool:
    """Política de picking do terreno: WATER e LEAVES contam; AIR não."""

    return BlockType(block_type) is not BlockType.AIR


def raycast_voxels(
    ray: Ray,
    provider: VoxelLookup,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    hit_test: Callable[[BlockType], bool] = is_pickable_block,
) -> RayHit | None:
    """Retorna o primeiro voxel aceito por ``hit_test`` usando 3D DDA.

    Células ausentes seguem a semântica do provider. A célula inicial é obtida
    com ``floor``, inclusive para coordenadas negativas e origens em bordas.
    """

    max_distance = float(max_distance)
    if not math.isfinite(max_distance) or max_distance < 0.0:
        raise ValueError("max_distance deve ser finito e não negativo.")

    voxel = [math.floor(float(component)) for component in ray.origin]

    def make_hit(
        distance: float,
        normal: tuple[int, int, int],
        block_type: BlockType,
    ) -> RayHit:
        point = ray.origin + ray.direction * np.float32(distance)
        return RayHit(tuple(voxel), point.astype(np.float32), distance, normal, block_type)

    block_type = BlockType(provider.get_block_at(*voxel))
    if hit_test(block_type):
        return make_hit(0.0, (0, 0, 0), block_type)

    step = [0, 0, 0]
    t_max = [math.inf, math.inf, math.inf]
    t_delta = [math.inf, math.inf, math.inf]
    for axis in range(3):
        direction = float(ray.direction[axis])
        origin = float(ray.origin[axis])
        if abs(direction) <= _DIRECTION_EPSILON:
            continue
        if direction > 0.0:
            step[axis] = 1
            boundary = voxel[axis] + 1
        else:
            step[axis] = -1
            boundary = voxel[axis]
        t_max[axis] = max(0.0, (boundary - origin) / direction)
        t_delta[axis] = abs(1.0 / direction)

    while True:
        # Ordem X, Y, Z resolve empates de aresta/canto de forma determinística.
        axis = min(range(3), key=t_max.__getitem__)
        distance = t_max[axis]
        if distance > max_distance or not math.isfinite(distance):
            return None

        voxel[axis] += step[axis]
        normal_values = [0, 0, 0]
        normal_values[axis] = -step[axis]
        normal = tuple(normal_values)

        block_type = BlockType(provider.get_block_at(*voxel))
        if hit_test(block_type):
            return make_hit(distance, normal, block_type)
        t_max[axis] += t_delta[axis]


def ray_aabb_intersection(
    ray: Ray,
    bounds: AABB,
    max_distance: float = math.inf,
) -> float | None:
    """Retorna a distância de entrada do raio em uma AABB pelo slab method."""

    max_distance = float(max_distance)
    if math.isnan(max_distance) or max_distance < 0.0:
        raise ValueError("max_distance deve ser não negativo.")
    minimum = np.asarray(bounds.min, dtype=np.float64)
    maximum = np.asarray(bounds.max, dtype=np.float64)
    if minimum.shape != (3,) or maximum.shape != (3,) or np.any(minimum > maximum):
        raise ValueError("AABB inválida.")

    t_enter = 0.0
    t_exit = max_distance
    for axis in range(3):
        origin = float(ray.origin[axis])
        direction = float(ray.direction[axis])
        if abs(direction) <= _DIRECTION_EPSILON:
            if origin < minimum[axis] or origin > maximum[axis]:
                return None
            continue
        first = (minimum[axis] - origin) / direction
        second = (maximum[axis] - origin) / direction
        if first > second:
            first, second = second, first
        t_enter = max(t_enter, first)
        t_exit = min(t_exit, second)
        if t_enter > t_exit:
            return None
    return t_enter if t_exit >= 0.0 and t_enter <= max_distance else None
