"""Testes CPU para unprojection, DDA e interseção ray-AABB."""

import math

import numpy as np
import pytest

from src.camera import IsometricCamera
from src.integration import VoxelGridProvider
from src.interaction import (
    Ray,
    is_pickable_block,
    ray_aabb_intersection,
    raycast_voxels,
    screen_to_ndc,
    screen_to_world_ray,
)
from src.math import mat4_identity, mat4_inverse, mat4_rotate_y, transform_vector, vec3
from src.math.aabb import AABB
from src.world import BlockType, Chunk3D, TerrainGenerator, WorldManager


VIEWPORT = (1280, 720)


def make_provider(blocks: dict[tuple[int, int, int], BlockType]) -> VoxelGridProvider:
    chunks: dict[tuple[int, int, int], Chunk3D] = {}
    for (x, y, z), block_type in blocks.items():
        chunk_position = (
            x // Chunk3D.SIZE,
            y // Chunk3D.SIZE,
            z // Chunk3D.SIZE,
        )
        chunk = chunks.setdefault(chunk_position, Chunk3D(*chunk_position))
        chunk.set_block(x % Chunk3D.SIZE, y % Chunk3D.SIZE, z % Chunk3D.SIZE, block_type)
    return VoxelGridProvider(chunks)


def camera_ray(
    camera: IsometricCamera,
    x: float,
    y: float,
    width: int = VIEWPORT[0],
    height: int = VIEWPORT[1],
    model: np.ndarray | None = None,
) -> Ray:
    return screen_to_world_ray(
        x,
        y,
        width,
        height,
        camera.get_view_matrix(),
        camera.get_projection_matrix(width, height),
        model,
    )


def test_screen_to_ndc_center_and_corners():
    assert screen_to_ndc(640, 360, 1280, 720) == (0.0, 0.0)
    assert screen_to_ndc(0, 0, 1280, 720) == (-1.0, 1.0)
    assert screen_to_ndc(1280, 720, 1280, 720) == (1.0, -1.0)


def test_screen_to_ndc_inverts_mouse_y():
    top = screen_to_ndc(640, 0, 1280, 720)
    bottom = screen_to_ndc(640, 720, 1280, 720)
    assert top[1] == 1.0
    assert bottom[1] == -1.0


def test_screen_to_ndc_rejects_invalid_viewport():
    with pytest.raises(ValueError):
        screen_to_ndc(0, 0, 0, 720)


def test_center_ray_is_normalized_and_points_at_camera_target():
    camera = IsometricCamera(target=vec3(3.0, 4.0, -2.0), ortho_size=8.0)
    ray = camera_ray(camera, 640, 360)
    expected = camera.target - camera._camera_position()
    expected /= np.linalg.norm(expected)
    assert np.isclose(np.linalg.norm(ray.direction), 1.0)
    np.testing.assert_allclose(ray.direction, expected, atol=1e-5)


def test_orthographic_pixels_have_parallel_rays_and_distinct_origins():
    camera = IsometricCamera(ortho_size=10.0)
    left = camera_ray(camera, 100, 360)
    right = camera_ray(camera, 1180, 360)
    np.testing.assert_allclose(left.direction, right.direction, atol=1e-6)
    assert not np.allclose(left.origin, right.origin)


def test_vertical_pixels_follow_inverted_screen_axis():
    camera = IsometricCamera(ortho_size=10.0)
    top = camera_ray(camera, 640, 0)
    bottom = camera_ray(camera, 640, 720)
    inverse_view = mat4_inverse(camera.get_view_matrix())
    world_up = transform_vector(inverse_view, vec3(0.0, 1.0, 0.0))
    assert np.dot(top.origin - bottom.origin, world_up) > 0.0


def test_pan_translates_ray_origin():
    camera = IsometricCamera(ortho_size=8.0)
    before = camera_ray(camera, 640, 360)
    camera.pan(7.0, -3.0)
    after = camera_ray(camera, 640, 360)
    np.testing.assert_allclose(after.origin - before.origin, [7.0, 0.0, -3.0], atol=2e-5)
    np.testing.assert_allclose(after.direction, before.direction, atol=1e-6)


def test_zoom_changes_origin_distribution_but_not_center_or_direction():
    camera = IsometricCamera(ortho_size=10.0)
    center_before = camera_ray(camera, 640, 360)
    edge_before = camera_ray(camera, 1280, 360)
    before_offset = np.linalg.norm(edge_before.origin - center_before.origin)
    camera.zoom_in()
    center_after = camera_ray(camera, 640, 360)
    edge_after = camera_ray(camera, 1280, 360)
    after_offset = np.linalg.norm(edge_after.origin - center_after.origin)
    np.testing.assert_allclose(center_after.origin, center_before.origin, atol=2e-5)
    np.testing.assert_allclose(edge_after.direction, edge_before.direction, atol=1e-6)
    assert after_offset < before_offset


@pytest.mark.parametrize("quarter_turns", [1, 2, 3])
def test_board_rotation_uses_same_model_transform_as_renderer(quarter_turns):
    camera = IsometricCamera(ortho_size=8.0)
    base = camera_ray(camera, 640, 360, model=mat4_identity())
    model = mat4_rotate_y(math.radians(90.0 * quarter_turns))
    rotated = camera_ray(camera, 640, 360, model=model)
    expected = transform_vector(mat4_inverse(model), base.direction)
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(rotated.direction, expected, atol=1e-5)


def test_resize_preserves_ray_at_same_normalized_pixel():
    camera = IsometricCamera(ortho_size=8.0)
    first = camera_ray(camera, 320, 180, 1280, 720)
    resized = camera_ray(camera, 480, 270, 1920, 1080)
    np.testing.assert_allclose(first.origin, resized.origin, atol=2e-5)
    np.testing.assert_allclose(first.direction, resized.direction, atol=1e-6)


@pytest.mark.parametrize(
    "origin,direction,expected_normal,expected_distance,expected_point",
    [
        ((-2.0, 0.5, 0.5), (1, 0, 0), (-1, 0, 0), 2.0, (0, 0.5, 0.5)),
        ((2.0, 0.5, 0.5), (-1, 0, 0), (1, 0, 0), 1.0, (1, 0.5, 0.5)),
        ((0.5, -2.0, 0.5), (0, 1, 0), (0, -1, 0), 2.0, (0.5, 0, 0.5)),
        ((0.5, 2.0, 0.5), (0, -1, 0), (0, 1, 0), 1.0, (0.5, 1, 0.5)),
        ((0.5, 0.5, -2.0), (0, 0, 1), (0, 0, -1), 2.0, (0.5, 0.5, 0)),
        ((0.5, 0.5, 2.0), (0, 0, -1), (0, 0, 1), 1.0, (0.5, 0.5, 1)),
    ],
)
def test_dda_hits_from_each_axis(
    origin,
    direction,
    expected_normal,
    expected_distance,
    expected_point,
):
    hit = raycast_voxels(
        Ray(vec3(*origin), vec3(*direction)),
        make_provider({(0, 0, 0): BlockType.STONE}),
    )
    assert hit is not None
    assert hit.block == (0, 0, 0)
    assert hit.normal == expected_normal
    assert hit.distance == pytest.approx(expected_distance)
    np.testing.assert_allclose(hit.point, expected_point, atol=1e-6)


def test_dda_returns_none_when_ray_misses():
    provider = make_provider({(0, 0, 0): BlockType.STONE})
    assert raycast_voxels(Ray(vec3(-2, 2, 0.5), vec3(1, 0, 0)), provider) is None


def test_dda_returns_first_block_on_path():
    provider = make_provider({
        (0, 0, 0): BlockType.DIRT,
        (3, 0, 0): BlockType.STONE,
    })
    hit = raycast_voxels(Ray(vec3(-2, 0.5, 0.5), vec3(1, 0, 0)), provider)
    assert hit is not None
    assert hit.block == (0, 0, 0)
    assert hit.block_type is BlockType.DIRT


def test_dda_uses_floor_for_negative_coordinates():
    provider = make_provider({(-2, -1, -3): BlockType.STONE})
    hit = raycast_voxels(
        Ray(vec3(-4.5, -0.5, -2.5), vec3(1, 0, 0)),
        provider,
    )
    assert hit is not None
    assert hit.block == (-2, -1, -3)
    assert hit.distance == pytest.approx(2.5)


def test_dda_origin_inside_solid_voxel():
    ray = Ray(vec3(0.25, 0.5, 0.75), vec3(1, 0, 0))
    hit = raycast_voxels(ray, make_provider({(0, 0, 0): BlockType.STONE}))
    assert hit is not None
    assert hit.distance == 0.0
    assert hit.normal == (0, 0, 0)
    np.testing.assert_array_equal(hit.point, ray.origin)


def test_dda_direction_with_zero_components():
    provider = make_provider({(4, 2, -3): BlockType.STONE})
    hit = raycast_voxels(Ray(vec3(0.5, 2.5, -2.5), vec3(1, 0, 0)), provider)
    assert hit is not None
    assert hit.block == (4, 2, -3)


def test_dda_on_voxel_boundary_uses_floor_selected_side():
    provider = make_provider({(1, 0, 0): BlockType.STONE})
    hit = raycast_voxels(Ray(vec3(1.0, -1.0, 0.5), vec3(0, 1, 0)), provider)
    assert hit is not None
    assert hit.block == (1, 0, 0)
    assert hit.distance == pytest.approx(1.0)


def test_dda_respects_max_distance_inclusively():
    ray = Ray(vec3(0.5, 0.5, 0.5), vec3(1, 0, 0))
    provider = make_provider({(3, 0, 0): BlockType.STONE})
    assert raycast_voxels(ray, provider, max_distance=2.49) is None
    hit = raycast_voxels(ray, provider, max_distance=2.5)
    assert hit is not None
    assert hit.distance == pytest.approx(2.5)


@pytest.mark.parametrize("block_type", [BlockType.WATER, BlockType.LEAVES, BlockType.STONE])
def test_pick_policy_hits_every_non_air_block(block_type):
    assert is_pickable_block(block_type)
    provider = make_provider({(0, 0, 0): block_type})
    hit = raycast_voxels(Ray(vec3(-1, 0.5, 0.5), vec3(1, 0, 0)), provider)
    assert hit is not None
    assert hit.block_type is block_type


def test_pick_policy_ignores_air():
    assert not is_pickable_block(BlockType.AIR)
    provider = make_provider({(0, 0, 0): BlockType.AIR})
    assert raycast_voxels(Ray(vec3(-1, 0.5, 0.5), vec3(1, 0, 0)), provider) is None


def test_dda_custom_hit_rule_can_ignore_transparent_blocks():
    provider = make_provider({
        (0, 0, 0): BlockType.WATER,
        (1, 0, 0): BlockType.STONE,
    })
    hit = raycast_voxels(
        Ray(vec3(-1, 0.5, 0.5), vec3(1, 0, 0)),
        provider,
        hit_test=lambda block: block is BlockType.STONE,
    )
    assert hit is not None
    assert hit.block == (1, 0, 0)


def test_ray_rejects_zero_direction():
    with pytest.raises(ValueError):
        Ray(vec3(), vec3())


def test_dynamic_voxel_provider_delegates_world_lookup():
    calls = []

    def lookup(x, y, z):
        calls.append((x, y, z))
        return BlockType.LEAVES

    provider = VoxelGridProvider(block_lookup=lookup)
    assert provider.get_block_at(-1, 2, 3) is BlockType.LEAVES
    assert calls == [(-1, 2, 3)]


def test_raycast_integrates_world_manager_and_generated_terrain():
    generator = TerrainGenerator(seed=27, enable_caves=False)
    manager = WorldManager(
        generator=generator,
        render_distance=1,
        create_gl_meshes=False,
        async_loading=False,
    )
    try:
        manager.load_initial_region(0.0, 0.0)
        surface_y = generator.get_height(0, 0)
        expected_y = max(surface_y, generator.sea_level)
        provider = VoxelGridProvider(block_lookup=manager.neighbor_at)
        hit = raycast_voxels(
            Ray(vec3(0.5, surface_y + 10.0, 0.5), vec3(0, -1, 0)),
            provider,
        )
        assert hit is not None
        assert hit.block == (0, expected_y, 0)
        assert hit.block_type is not BlockType.AIR
        assert hit.normal == (0, 1, 0)
    finally:
        manager.delete()


@pytest.mark.parametrize(
    "origin,direction,expected",
    [
        ((-2, 0.5, 0.5), (1, 0, 0), 2.0),
        ((0.5, 0.5, 0.5), (1, 0, 0), 0.0),
        ((2, 0.5, 0.5), (-1, 0, 0), 1.0),
        ((-2, 2, 0.5), (1, 0, 0), None),
        ((2, 0.5, 0.5), (1, 0, 0), None),
    ],
)
def test_ray_aabb_slab_cases(origin, direction, expected):
    bounds = AABB(vec3(0, 0, 0), vec3(1, 1, 1))
    distance = ray_aabb_intersection(Ray(vec3(*origin), vec3(*direction)), bounds)
    if expected is None:
        assert distance is None
    else:
        assert distance == pytest.approx(expected)


def test_ray_aabb_respects_max_distance():
    ray = Ray(vec3(-2, 0.5, 0.5), vec3(1, 0, 0))
    bounds = AABB(vec3(0, 0, 0), vec3(1, 1, 1))
    assert ray_aabb_intersection(ray, bounds, max_distance=1.99) is None
    assert ray_aabb_intersection(ray, bounds, max_distance=2.0) == pytest.approx(2.0)


def test_ray_aabb_supports_negative_coordinates():
    ray = Ray(vec3(-5.0, -1.5, -2.5), vec3(1, 0, 0))
    bounds = AABB(vec3(-3, -2, -3), vec3(-2, -1, -2))
    assert ray_aabb_intersection(ray, bounds) == pytest.approx(2.0)
