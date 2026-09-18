"""Colisão contínua simples contra voxels sólidos do mundo."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

import numpy as np

from src.world import BlockType


class VoxelLookup(Protocol):
    """Contrato mínimo usado pelo sistema de colisão."""

    def get_block_at(self, world_x: int, world_y: int, world_z: int) -> BlockType:
        ...


@dataclass(frozen=True)
class VoxelCollisionConfig:
    """Parâmetros físicos da miniatura."""

    radius: float = 0.28
    height: float = 0.98
    gravity: float = -24.0
    max_fall_speed: float = 32.0
    step_height: float = 1.02
    skin: float = 0.001
    world_floor_y: int = -64

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError("radius deve ser positivo.")
        if self.height <= 0.0:
            raise ValueError("height deve ser positivo.")
        if self.gravity >= 0.0:
            raise ValueError("gravity deve ser negativo.")
        if self.max_fall_speed <= 0.0:
            raise ValueError("max_fall_speed deve ser positivo.")
        if self.step_height < 0.0:
            raise ValueError("step_height não pode ser negativo.")
        if self.skin < 0.0:
            raise ValueError("skin não pode ser negativo.")
        if isinstance(self.world_floor_y, bool) or not isinstance(self.world_floor_y, int):
            raise TypeError("world_floor_y deve ser um inteiro.")


@dataclass(frozen=True)
class CollisionResult:
    position: np.ndarray
    vertical_velocity: float
    grounded: bool
    ground_block: tuple[int, int, int] | None
    collided_x: bool
    collided_z: bool
    collided_vertical: bool


class VoxelCollisionController:
    """Resolve movimento X/Z e gravidade contra voxels não-AIR.

    A posição do personagem representa o ponto no nível dos pés. Assim, ao
    estar sobre um bloco em Y, a posição vertical é Y + 1.
    """

    _EPSILON = 1e-6

    def __init__(
        self,
        provider: VoxelLookup,
        config: VoxelCollisionConfig | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or VoxelCollisionConfig()

    def _is_solid(self, x: int, y: int, z: int) -> bool:
        if y <= self.config.world_floor_y:
            return True
        try:
            block = BlockType(self.provider.get_block_at(x, y, z))
        except (TypeError, ValueError):
            return False
        return block is not BlockType.AIR

    def _candidate_ranges(
        self,
        position: np.ndarray,
    ) -> tuple[range, range, range]:
        radius = self.config.radius
        height = self.config.height
        skin = self.config.skin

        min_x = math.floor(float(position[0]) - radius)
        max_x = math.floor(float(position[0]) + radius - skin)
        min_y = math.floor(float(position[1]) - skin)
        max_y = math.floor(float(position[1]) + height - skin)
        min_z = math.floor(float(position[2]) - radius)
        max_z = math.floor(float(position[2]) + radius - skin)

        return (
            range(min_x, max_x + 1),
            range(min_y, max_y + 1),
            range(min_z, max_z + 1),
        )

    def _overlaps_block(
        self,
        position: np.ndarray,
        block: tuple[int, int, int],
    ) -> bool:
        x, y, z = block
        r = self.config.radius
        h = self.config.height
        eps = self.config.skin + self._EPSILON

        body_min = np.array(
            [position[0] - r, position[1], position[2] - r],
            dtype=np.float64,
        )
        body_max = np.array(
            [position[0] + r, position[1] + h, position[2] + r],
            dtype=np.float64,
        )
        block_min = np.array([x, y, z], dtype=np.float64)
        block_max = block_min + 1.0

        return bool(
            np.all(body_min < block_max - eps)
            and np.all(body_max > block_min + eps)
        )

    def _colliding_blocks(self, position: np.ndarray) -> list[tuple[int, int, int]]:
        ranges = self._candidate_ranges(position)
        collisions: list[tuple[int, int, int]] = []

        for x in ranges[0]:
            for y in ranges[1]:
                for z in ranges[2]:
                    block = (x, y, z)
                    if self._is_solid(x, y, z) and self._overlaps_block(position, block):
                        collisions.append(block)

        return collisions

    def _horizontal_colliding_blocks(
        self,
        position: np.ndarray,
        grounded: bool,
    ) -> list[tuple[int, int, int]]:
        """Retorna voxels que bloqueiam deslocamento horizontal.

        Quando o personagem está no ar, um voxel cujo topo coincide exatamente
        com o nível dos pés ainda funciona como uma parede para o deslocamento
        lateral. Quando já estamos apoiados, esse mesmo contato é tratado como
        chão, permitindo caminhar sobre a superfície.
        """
        collisions = self._colliding_blocks(position)
        if grounded:
            return collisions

        radius = self.config.radius
        skin = self.config.skin
        feet_y = float(position[1])

        x_min = math.floor(float(position[0]) - radius)
        x_max = math.floor(float(position[0]) + radius - skin)
        z_min = math.floor(float(position[2]) - radius)
        z_max = math.floor(float(position[2]) + radius - skin)
        support_y = math.floor(feet_y - skin)

        blocked = set(collisions)
        for x in range(x_min, x_max + 1):
            for z in range(z_min, z_max + 1):
                if not self._is_solid(x, support_y, z):
                    continue
                block_top = float(support_y + 1)
                if abs(block_top - feet_y) <= 0.05:
                    blocked.add((x, support_y, z))

        return list(blocked)

    def _has_support(
        self,
        position: np.ndarray,
    ) -> tuple[int, int, int] | None:
        """Encontra o bloco imediatamente abaixo dos pés."""
        x_min = math.floor(float(position[0]) - self.config.radius)
        x_max = math.floor(float(position[0]) + self.config.radius - self.config.skin)
        z_min = math.floor(float(position[2]) - self.config.radius)
        z_max = math.floor(float(position[2]) + self.config.radius - self.config.skin)
        support_y = math.floor(float(position[1]) - self.config.skin)

        best: tuple[int, int, int] | None = None
        best_top = -math.inf

        for x in range(x_min, x_max + 1):
            for z in range(z_min, z_max + 1):
                if not self._is_solid(x, support_y, z):
                    continue
                top = support_y + 1
                if top <= float(position[1]) + 0.05 and top > best_top:
                    best = (x, support_y, z)
                    best_top = top

        return best

    def _is_free(self, position: np.ndarray) -> bool:
        return not self._colliding_blocks(position)

    def _resolve_horizontal_axis(
        self,
        position: np.ndarray,
        delta: float,
        axis: int,
        grounded: bool,
    ) -> tuple[np.ndarray, bool, bool]:
        """Move em um único eixo sem atravessar voxels, permitindo degraus."""
        if abs(delta) <= self._EPSILON:
            return position, False, grounded

        # Divide deslocamentos grandes em passos pequenos para evitar tunneling.
        # Isso também torna a rotina robusta para testes que usam um delta maior
        # que uma unidade de voxel em um único frame.
        max_substep = max(self.config.radius * 0.5, 0.1)
        steps = max(1, int(math.ceil(abs(delta) / max_substep)))
        sub_delta = delta / float(steps)
        collided = False

        for _ in range(steps):
            candidate = position.copy()
            candidate[axis] += sub_delta
            collisions = self._horizontal_colliding_blocks(
                candidate,
                grounded,
            )

            if not collisions:
                position = candidate
                continue

            collided = True

            # Subir um degrau é permitido apenas quando o personagem já estava
            # apoiado. O teste é feito na posição atual + o pequeno avanço,
            # portanto o degrau não pode atravessar uma parede de forma mágica.
            if grounded and self.config.step_height > 0.0:
                stepped = candidate.copy()
                stepped[1] += self.config.step_height
                if self._is_free(stepped):
                    position = stepped
                    grounded = False
                    continue

            # Colisão real: encosta a cápsula aproximada (cilindro vertical)
            # na face do voxel e interrompe o movimento deste eixo.
            resolved_axis = float(position[axis])
            radius = self.config.radius
            skin = self.config.skin

            for bx, by, bz in collisions:
                if axis == 0:
                    block_plane = float(bx)
                    block_far = block_plane + 1.0
                    if sub_delta > 0.0:
                        resolved_axis = min(
                            resolved_axis,
                            block_plane - radius - skin,
                        )
                    else:
                        resolved_axis = max(
                            resolved_axis,
                            block_far + radius + skin,
                        )
                elif axis == 2:
                    block_plane = float(bz)
                    block_far = block_plane + 1.0
                    if sub_delta > 0.0:
                        resolved_axis = min(
                            resolved_axis,
                            block_plane - radius - skin,
                        )
                    else:
                        resolved_axis = max(
                            resolved_axis,
                            block_far + radius + skin,
                        )
                else:
                    raise ValueError("axis horizontal deve ser 0 ou 2")

            position[axis] = resolved_axis
            break

        return position, collided, grounded

    def move(
        self,
        position: np.ndarray,
        horizontal_delta: np.ndarray,
        dt: float,
        vertical_velocity: float,
    ) -> CollisionResult:
        """Aplica movimento, colisão horizontal e gravidade em um frame."""
        if dt < 0.0 or not math.isfinite(float(dt)):
            raise ValueError("dt deve ser finito e não negativo.")

        # Use precisão dupla while accumulating substeps. Repeated float32
        # additions otherwise shorten diagonal movement enough to fail at the
        # movement scale used by the token.
        pos = np.asarray(position, dtype=np.float64).copy()
        delta = np.asarray(horizontal_delta, dtype=np.float64)
        if delta.shape != (3,):
            raise ValueError("horizontal_delta deve ser um vetor 3D.")
        delta = delta.copy()
        delta[1] = 0.0

        grounded_block = self._has_support(pos)
        grounded = grounded_block is not None

        pos, collided_x, grounded = self._resolve_horizontal_axis(
            pos,
            float(delta[0]),
            0,
            grounded,
        )
        pos, collided_z, grounded = self._resolve_horizontal_axis(
            pos,
            float(delta[2]),
            2,
            grounded,
        )

        vy = float(vertical_velocity)
        vy += self.config.gravity * float(dt)
        vy = max(vy, -self.config.max_fall_speed)

        vertical_delta = vy * float(dt)
        candidate = pos.copy()
        candidate[1] += vertical_delta

        floor_feet_y = float(self.config.world_floor_y + 1)
        if candidate[1] <= floor_feet_y:
            pos[1] = floor_feet_y
            vy = 0.0
            grounded = True
            grounded_block = (
                math.floor(float(pos[0])),
                self.config.world_floor_y,
                math.floor(float(pos[2])),
            )
            return CollisionResult(
                position=pos.astype(np.float32),
                vertical_velocity=vy,
                grounded=grounded,
                ground_block=grounded_block,
                collided_x=collided_x,
                collided_z=collided_z,
                collided_vertical=True,
            )

        vertical_collisions = self._colliding_blocks(candidate)
        collided_vertical = bool(vertical_collisions)

        if vertical_collisions:
            if vy < 0.0:
                # Ao cair, escolhe o topo mais alto que interceptou o corpo.
                landing_y = max(by + 1.0 for _, by, _ in vertical_collisions)
                pos[1] = float(landing_y)
                vy = 0.0
                grounded = True
                grounded_block = self._has_support(pos)
            elif vy > 0.0:
                # Não há salto hoje, mas a resolução evita atravessar tetos se a
                # movimentação vertical for usada futuramente.
                ceiling_y = min(by for _, by, _ in vertical_collisions)
                pos[1] = float(ceiling_y) - self.config.height
                vy = 0.0
                grounded = False
                grounded_block = None
            else:
                grounded = self._has_support(pos) is not None
        else:
            pos[1] = candidate[1]
            grounded_block = self._has_support(pos)
            grounded = grounded_block is not None

        if grounded_block is None and grounded:
            grounded = False

        return CollisionResult(
            position=pos.astype(np.float32),
            vertical_velocity=vy,
            grounded=grounded,
            ground_block=grounded_block,
            collided_x=collided_x,
            collided_z=collided_z,
            collided_vertical=collided_vertical,
        )
