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
