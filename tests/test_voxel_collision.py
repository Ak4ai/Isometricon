import numpy as np

from src.physics import VoxelCollisionConfig, VoxelCollisionController
from src.world import BlockType


class DictWorld:
    def __init__(self, blocks: set[tuple[int, int, int]]) -> None:
        self.blocks = blocks

    def get_block_at(self, x: int, y: int, z: int) -> BlockType:
        return BlockType.STONE if (x, y, z) in self.blocks else BlockType.AIR


def simulate(
    controller: VoxelCollisionController,
    position: np.ndarray,
    frames: int = 120,
    dt: float = 1.0 / 60.0,
    velocity: float = 0.0,
):
    result = None
    for _ in range(frames):
        result = controller.move(
            position,
            np.zeros(3, dtype=np.float32),
            dt,
            velocity,
        )
        position[:] = result.position
        velocity = result.vertical_velocity
    return result


def test_player_falls_through_open_cave_to_lower_floor():
    blocks = set()
    for x in range(-2, 3):
        for z in range(-2, 3):
            blocks.add((x, -3, z))

    # A área acima do piso é AIR: a miniatura deve poder descer.
    world = DictWorld(blocks)
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 8.0, 0.5], dtype=np.float32)

    result = simulate(controller, position)

    assert result is not None
    assert result.grounded
    assert np.isclose(result.position[1], -2.0, atol=1e-5)
    assert result.ground_block == (0, -3, 0)


def test_player_stops_at_virtual_world_floor_when_cave_is_open():
    world = DictWorld(set())
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 8.0, 0.5], dtype=np.float32)

    result = simulate(controller, position, frames=240)

    assert result.grounded
    assert np.isclose(result.position[1], -63.0, atol=1e-5)
    assert result.ground_block == (0, -64, 0)


def test_large_frame_delta_cannot_tunnel_through_virtual_floor():
    world = DictWorld(set())
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 8.0, 0.5], dtype=np.float32)

    result = controller.move(position, np.zeros(3), 10.0, -32.0)

    assert result.grounded
    assert np.isclose(result.position[1], -63.0, atol=1e-5)


def test_player_stops_on_surface_block():
    world = DictWorld({(0, 4, 0)})
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 7.0, 0.5], dtype=np.float32)

    result = simulate(controller, position)

    assert result is not None
    assert result.grounded
    assert np.isclose(result.position[1], 5.0, atol=1e-5)
    assert result.ground_block == (0, 4, 0)


def test_water_does_not_block_vertical_movement():
    water = {(0, y, 0) for y in range(1, 4)}
    stone = {(0, 0, 0)}

    class WaterWorld:
        def get_block_at(self, x: int, y: int, z: int) -> BlockType:
            if (x, y, z) in water:
                return BlockType.WATER
            if (x, y, z) in stone:
                return BlockType.STONE
            return BlockType.AIR

    world = WaterWorld()
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 8.0, 0.5], dtype=np.float32)

    result = simulate(controller, position, frames=120)

    assert result.grounded
    assert np.isclose(result.position[1], 1.0, atol=1e-5)


def test_horizontal_collision_blocks_wall():
    world = DictWorld({(1, 0, 0)})
    config = VoxelCollisionConfig(gravity=-24.0)
    controller = VoxelCollisionController(world, config)
    position = np.array([0.5, 1.0, 0.5], dtype=np.float32)

    result = controller.move(
        position,
        np.array([2.0, 0.0, 0.0], dtype=np.float32),
        1.0 / 60.0,
        0.0,
    )

    assert result.collided_x
    assert result.position[0] < 1.0


def test_player_can_step_up_one_block():
    # Piso em Y=0 e degrau em X=1/Y=1.
    blocks = {(0, 0, 0), (1, 0, 0), (1, 1, 0)}
    world = DictWorld(blocks)
    controller = VoxelCollisionController(world)
    position = np.array([0.5, 1.0, 0.5], dtype=np.float32)

    # Primeiro frame estabelece suporte; segundo tenta avançar sobre o degrau.
    controller.move(
        position,
        np.zeros(3, dtype=np.float32),
        1.0 / 60.0,
        0.0,
    )
    result = controller.move(
        position,
        np.array([0.9, 0.0, 0.0], dtype=np.float32),
        1.0 / 60.0,
        0.0,
    )

    assert result.position[0] > 1.0
