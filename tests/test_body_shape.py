"""Ajustes de proporção: agem igual sobre tudo o que um osso carrega e não desfazem o encaixe."""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from src.clothing import body_shape, character_save
from src.clothing.customization import AvatarCustomization, place_face_layer
from src.clothing.skeleton import Skeleton, skin
from src.interactive.skin_commands import SkinCommandHandler


@pytest.fixture(params=["female", "male"])
def skeleton(request):
    return Skeleton.load(request.param)


def posed(skeleton, point, bone, adjust):
    """A vertex carried whole by one bone, in the rest pose with the adjustments."""
    rows = np.zeros((1, 11))
    rows[0, :3] = point
    index = skeleton.index(bone)
    matrices = skeleton.pose({}, scales=body_shape.bone_scales(skeleton, adjust), height=body_shape.height(adjust))
    return skin(rows, np.array([[index, index]]), np.array([[1.0, 0.0]]), matrices)[0, :3]


def test_no_adjustment_leaves_the_body_as_it_was(skeleton):
    assert body_shape.bone_scales(skeleton, {}) == {} and body_shape.height(None) == 1.0
    point = skeleton.tails[skeleton.index("Head")]
    np.testing.assert_allclose(posed(skeleton, point, "Head", {}), point, atol=1e-9)


def test_the_head_grows_about_the_neck_and_height_scales_from_the_ground(skeleton):
    head = skeleton.index("Head")
    neck, top = skeleton.heads[head], skeleton.tails[head]
    bigger = posed(skeleton, top, "Head", {"cabeca": 1.0})
    assert np.linalg.norm(bigger - neck) == pytest.approx((1 + body_shape.HEAD) * np.linalg.norm(top - neck))
    np.testing.assert_allclose(posed(skeleton, neck, "Head", {"cabeca": 1.0}), neck, atol=1e-9)  # the joint stays
    taller = posed(skeleton, top, "Head", {"altura": 1.0})
    np.testing.assert_allclose(taller, top * (1 + body_shape.HEIGHT), atol=1e-9)


def test_wider_shoulders_carry_the_arms_out_without_making_them_thicker(skeleton):
    arm = skeleton.index("UpperArm_L")
    joint = skeleton.heads[arm]
    beside = joint + np.array([0.0, 0.0, 0.05])  # a point of the arm, 5 cm in front of its joint
    wide = {"ombros": 1.0}
    moved_joint, moved_point = posed(skeleton, joint, "UpperArm_L", wide), posed(skeleton, beside, "UpperArm_L", wide)
    assert moved_joint[0] > joint[0] + 0.01                               # the shoulder is further out
    np.testing.assert_allclose(moved_point - moved_joint, beside - joint, atol=1e-9)  # the arm itself is the same


def test_thicker_arms_keep_their_length(skeleton):
    arm = skeleton.index("LowerArm_L")
    head, tail = skeleton.heads[arm], skeleton.tails[arm]
    np.testing.assert_allclose(posed(skeleton, tail, "LowerArm_L", {"bracos": 1.0}), tail, atol=1e-9)
    side = np.cross(tail - head, [0.0, 0.0, 1.0])
    side = head + 0.04 * side / np.linalg.norm(side)
    thick = posed(skeleton, side, "LowerArm_L", {"bracos": 1.0})
    assert np.linalg.norm(thick - head) == pytest.approx(0.04 * (1 + body_shape.ARMS))


def test_chest_and_buttocks_move_what_is_near_them_and_nothing_else(skeleton):
    torso = skeleton.index("Torso")
    low, high = sorted((skeleton.heads[torso][1], skeleton.tails[torso][1]))
    y = low + body_shape.CHEST[0] * (high - low)
    front = np.array([body_shape.CHEST[1], y, 0.12])
    surface = np.array([front, [-body_shape.CHEST[1], y, 0.12]])
    points = np.array([front, front + [0.0, 0.0, 0.01], [0.0, 0.1, 0.0], [0.0, y, -0.3]])  # skin, cloth over it, a foot, the back
    assert not body_shape.warps({}) and body_shape.warps({"peito": 0.5})
    np.testing.assert_array_equal(body_shape.warp(points, skeleton, {}, surface), points)
    out = body_shape.warp(points, skeleton, {"peito": 1.0}, surface)
    # the chest comes out by the bulge of its own side, plus a little of the other side's
    assert body_shape.BULGE <= out[0, 2] - points[0, 2] <= 1.15 * body_shape.BULGE
    assert out[1, 2] - points[1, 2] == pytest.approx(out[0, 2] - points[0, 2], abs=1e-12)  # the cloth over it, exactly as much
    np.testing.assert_allclose(out[2:], points[2:], atol=1e-4)                     # far from it, and behind the body, nothing moves
    back = body_shape.warp(points, skeleton, {"bunda": 1.0}, surface)
    assert (back[:, 2] <= points[:, 2] + 1e-12).all()                              # the buttocks go backwards


def test_face_layers_are_scaled_lifted_and_spread_side_by_side():
    layer = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    layer.paste((0, 0, 0, 255), (40, 100, 80, 120))    # left eye
    layer.paste((0, 0, 0, 255), (150, 100, 190, 120))  # right eye
    assert place_face_layer(layer) is layer
    box = place_face_layer(layer, scale=1.5).getbbox()
    assert box[2] - box[0] > 150 and box[3] - box[1] == pytest.approx(30, abs=2)
    assert place_face_layer(layer, lift=10).getbbox()[1] == 90
    spread = place_face_layer(layer, spread=6).getbbox()
    assert (spread[0], spread[2]) == (34, 196)


def test_skin_ajuste_sets_and_resets_the_adjustments_and_redraws_the_face_only_for_the_face(tmp_path):
    reloads = []
    model = SimpleNamespace(customization=AvatarCustomization(), reload=lambda: reloads.append(1))
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin ajuste altura 50")[0] and model.customization.body_adjust == {"altura": 0.5}
    assert handler.execute("/skin ajuste ombros -250")[0] and model.customization.body_adjust["ombros"] == -1.0
    assert reloads == []                                    # the body is posed by the skeleton: nothing to rebuild
    assert handler.execute("/skin ajuste nariz 10")[0] is False
    assert handler.execute("/skin ajuste olhos_tamanho 40")[0] and reloads == [1]
    assert handler.execute("/skin ajuste altura 0")[0] and "altura" not in model.customization.body_adjust
    assert handler.execute("/skin ajuste reset")[0] and model.customization.body_adjust == {} and reloads == [1, 1]
    assert handler.execute("/skin sobrancelha grossa")[0] and model.customization.resolved_eyebrow_style == "thick"


def test_the_adjustments_are_saved_with_the_character(tmp_path):
    custom = AvatarCustomization(body_adjust={"peito": 0.6, "olhos_altura": -0.3})
    model = SimpleNamespace(customization=custom, top_id=None, bottom_id=None, outer_top_id=None, shoes_id=None,
                            hair_id=None, tool_id=None)
    path = str(tmp_path / "personagem.json")
    character_save.save(model, path)
    assert character_save.customization_from(character_save.load(path)).body_adjust == {"peito": 0.6, "olhos_altura": -0.3}
