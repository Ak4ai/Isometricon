"""Animation must preserve the visible skin chosen by HSR, including near cloth."""
from types import SimpleNamespace

import numpy as np
import pytest

from src.clothing.character_animation import CharacterAnimator


class MemoryMesh:
    def __init__(self, points):
        self.rows = np.zeros((3, 11), dtype=np.float32)
        self.rows[:, :3] = points
        self.rows[:, 5] = 1
        self.indices = np.array([0, 1, 2], dtype=np.uint32)

    def read_vertices(self):
        return self.rows.copy()

    def read_indices(self):
        return self.indices.copy()

    def update_vertices(self, rows):
        self.rows = rows.copy()

    def update_buffers(self, rows, indices):
        self.rows = rows.reshape(-1, 11).copy()
        self.indices = indices.copy()

    def delete(self):
        self.indices = np.zeros(0, dtype=np.uint32)


@pytest.mark.parametrize('body', ['female', 'male'])
def test_animation_does_not_delete_skin_even_when_cloth_crosses_a_bone_ray(body):
    # A visible triangle in front of cloth: the old bone-ray test deleted this
    # whole triangle for every pose, even though HSR had left it visible.
    skin_mesh = MemoryMesh([[-.02, 1.1, .2], [.02, 1.1, .2], [0, 1.14, .2]])
    cloth_mesh = MemoryMesh([[-.2, .9, .15], [.2, .9, .15], [0, 1.4, .15]])
    parts = [SimpleNamespace(name='trunk_skin', mesh=skin_mesh, transform=None, source_obj=None),
             SimpleNamespace(name='top', mesh=cloth_mesh, transform=None, source_obj='missing.obj')]
    model = SimpleNamespace(body=body, parts=parts.copy())
    animator = CharacterAnimator(model, walking=False)
    animator.update(0)
    animator.walking = True
    for phase in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        animator.walk_time = phase
        animator.update(0)
        assert len(model.parts) == 2
        for part in parts:
            np.testing.assert_array_equal(part.mesh.read_indices(), [0, 1, 2])
            assert np.isfinite(part.mesh.read_vertices()).all()


@pytest.mark.parametrize('body', ['female', 'male'])
def test_torso_mesh_cannot_bind_to_a_nearby_arm(body):
    from src.clothing.skeleton import Skeleton, rotation_z, skin
    skeleton = Skeleton.load(body)
    arm = skeleton.index('UpperArm_L')
    # Deliberately near the arm cage: anatomical ownership must win over proximity.
    point = skeleton.heads[arm] + .2 * (skeleton.tails[arm] - skeleton.heads[arm])
    mesh = MemoryMesh(point + np.array([[0, 0, 0], [.01, 0, 0], [0, 0, .01]]))
    part = SimpleNamespace(name='trunk_skin', mesh=mesh, transform=None, source_obj=None)
    animator = CharacterAnimator(SimpleNamespace(body=body, parts=[part]))
    animator._bind()
    _, rows, indices, weights = animator._bindings[0]
    posed = skin(rows, indices, weights, skeleton.pose({'UpperArm_L': rotation_z(.7)}))
    np.testing.assert_allclose(posed, rows, atol=1e-7)


@pytest.mark.parametrize("body", ["female", "male"])
def test_a_skirt_is_not_split_between_the_legs(body):
    """Cloth labelled half with each leg, all round both, gets weights without a jump along the garment."""
    from src.clothing.skeleton import Skeleton

    animator = CharacterAnimator.__new__(CharacterAnimator)
    animator.skeleton = skeleton = Skeleton.load(body)
    hip = skeleton.heads[skeleton.index("UpperLeg_L")]
    turns, levels = 24, 12
    angle = np.arange(turns) * 2 * np.pi / turns
    points = np.array([[0.25 * np.cos(a), hip[1] + 0.08 - 0.05 * k, hip[2] + 0.25 * np.sin(a)]
                       for k in range(levels) for a in angle])
    faces = np.array([[k * turns + i, k * turns + (i + 1) % turns, (k + 1) * turns + i]
                      for k in range(levels - 1) for i in range(turns)]
                     + [[k * turns + (i + 1) % turns, (k + 1) * turns + (i + 1) % turns, (k + 1) * turns + i]
                        for k in range(levels - 1) for i in range(turns)])
    bones = np.where(points[:, 1] > hip[1], skeleton.index("Pelvis"),
                     np.where(points[:, 0] > 0, skeleton.index("UpperLeg_L"), skeleton.index("UpperLeg_R")))
    indices, weights = animator._cloth_weights(points, faces, bones, bones)
    dense = np.zeros((len(points), len(skeleton.names)))
    np.add.at(dense, (np.repeat(np.arange(len(points)), indices.shape[1]), indices.ravel()), weights.ravel())
    np.testing.assert_allclose(dense.sum(1), 1.0)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    assert np.abs(dense[edges[:, 0]] - dense[edges[:, 1]]).max() < 0.5
    side = points[:, 0] > 0.2  # the cloth beside the left leg goes with it
    assert dense[side & (points[:, 1] < hip[1] - 0.3), skeleton.index("UpperLeg_L")].min() > 0.5



@pytest.mark.parametrize('body', ['female', 'male'])
def test_arms_swing_less_only_when_the_clothes_tear(body):
    skin_mesh = MemoryMesh([[-.02, 1.1, .2], [.02, 1.1, .2], [0, 1.14, .2]])
    model = SimpleNamespace(body=body, parts=[SimpleNamespace(name='trunk_skin', mesh=skin_mesh,
                                                              transform=None, source_obj=None)])
    animator = CharacterAnimator(model, walking=False)
    animator.update(0)
    assert animator.arm_swing == 1.0  # nothing worn, nothing to tear

    def swing(amount):
        animator.arm_swing = amount
        upper = animator.walk_pose(0.0)[0]['UpperArm_L'] @ np.linalg.inv(animator.rest['UpperArm_L'])
        return np.arccos(np.clip((np.trace(upper[:3, :3]) - 1) / 2, -1.0, 1.0))

    assert 0.0 < swing(0.35) < swing(1.0)


def test_torn_area_counts_only_triangles_stretched_well_past_their_size():
    from src.clothing.character_animation import _torn_area
    rows = np.array([[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0]], dtype=np.float64)
    faces = np.array([[0, 1, 2]])
    assert _torn_area(rows, rows, faces) == 0.0
    assert _torn_area(rows, rows * [2.0, 1.0, 1.0], faces) == 0.0  # twice as long: not torn
    torn = rows * [4.0, 1.0, 1.0]
    assert _torn_area(rows, torn, faces) == pytest.approx(0.5 * 0.4 * 0.1)
