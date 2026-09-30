"""Game rig: bone weights that keep seams joined, and linear blend skinning."""
import numpy as np
import pytest

from src.clothing.skeleton import Skeleton, rotation_x, skin, walk_rotations


@pytest.fixture(params=["female", "male"])
def skeleton(request):
    return Skeleton.load(request.param)


def test_rig_has_the_sixteen_bones_parents_first(skeleton):
    assert len(skeleton.names) == 16
    for bone, parent in enumerate(skeleton.parents):
        assert parent < bone
    for side in "LR":
        hand = skeleton.index(f"Hand_{side}")
        assert skeleton.names[skeleton.parents[hand]] == f"LowerArm_{side}"


def test_seam_vertices_get_the_same_weights_from_both_bones(skeleton):
    knee = skeleton.index("LowerLeg_L")
    thigh = skeleton.index("UpperLeg_L")
    point = skeleton.heads[knee][None] + [[0.02, 0.0, 0.0]]
    from_thigh = skeleton.weights(point, np.array([thigh]))
    from_shin = skeleton.weights(point, np.array([knee]))
    as_dict = lambda iw: {int(i): float(w) for i, w in zip(iw[0][0], iw[1][0]) if w > 0}
    assert as_dict(from_thigh) == pytest.approx(as_dict(from_shin))
    assert set(as_dict(from_thigh)) == {knee, thigh}


def test_rest_pose_leaves_vertices_in_place(skeleton):
    rows = np.zeros((3, 11))
    rows[:, :3] = skeleton.heads[:3] + 0.01
    rows[:, 3:6] = [0.0, 1.0, 0.0]
    indices, weights = skeleton.weights(rows[:, :3], np.array([0, 1, 2]))
    np.testing.assert_allclose(skin(rows, indices, weights, skeleton.pose({})), rows, atol=1e-9)


def test_bent_knee_moves_the_foot_and_not_the_hip(skeleton):
    knee = skeleton.index("LowerLeg_L")
    foot = skeleton.index("Foot_L")
    rows = np.zeros((2, 11))
    rows[0, :3] = skeleton.tails[foot]
    rows[1, :3] = skeleton.heads[skeleton.index("UpperLeg_L")]
    bones = np.array([foot, skeleton.index("UpperLeg_L")])
    indices, weights = skeleton.weights(rows[:, :3], bones)
    posed = skin(rows, indices, weights, skeleton.pose({"LowerLeg_L": rotation_x(np.radians(45))}))
    assert np.linalg.norm(posed[0, :3] - rows[0, :3]) > 0.1
    np.testing.assert_allclose(posed[1, :3], rows[1, :3], atol=1e-9)
    # Positive pitch swings the foot backward (-z), as the world token's walk does.
    assert posed[0, 2] < rows[0, 2]


def test_walk_cycle_poses_every_limb():
    rotations, root = walk_rotations(0.7)
    for bone in ("UpperLeg_L", "LowerLeg_R", "UpperArm_L", "LowerArm_R", "Torso", "Head"):
        assert bone in rotations
    assert root[1] >= 0


def test_rest_pose_hangs_the_arms_close_to_the_body(skeleton):
    from src.clothing.skeleton import REST_ARM_ANGLE, rest_rotations
    matrices = skeleton.pose(rest_rotations(skeleton))
    for side in "LR":
        hand = skeleton.index(f"Hand_{side}")
        shoulder = skeleton.heads[skeleton.index(f"UpperArm_{side}")]
        wrist = (matrices[hand] @ np.r_[skeleton.heads[hand], 1.0])[:3]
        arm = wrist - shoulder
        assert np.degrees(np.arctan2(abs(arm[0]), -arm[1])) == pytest.approx(np.degrees(REST_ARM_ANGLE), abs=1.0)


def test_rest_arms_clear_the_hips_on_each_body():
    from src.clothing.character_animation import CharacterAnimator
    from src.clothing.skeleton import REST_ARM_ANGLE

    class Model:
        def __init__(self, body):
            self.body = body

    angles = {}
    for body in ("female", "male"):
        animator = CharacterAnimator(Model(body))
        animator.skeleton = Skeleton.load(body)
        angles[body] = animator._rest_arm_angle(*animator._body_cage())
    assert angles["male"] == pytest.approx(REST_ARM_ANGLE)
    assert angles["female"] > angles["male"]  # wider hips push the hands out
