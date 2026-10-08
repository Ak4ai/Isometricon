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


def test_longer_legs_raise_the_body_so_the_feet_stay_on_the_ground(skeleton):
    adjust = {"pernas_comprimento": 1.0}
    scales = body_shape.bone_scales(skeleton, adjust)
    lift = body_shape.ground_lift(skeleton, scales)
    assert lift > 0.05 and body_shape.ground_lift(skeleton, {}) == 0.0
    foot = skeleton.index("Foot_L")
    rows = np.zeros((1, 11))
    rows[0, :3] = skeleton.heads[foot]
    matrices = skeleton.pose({}, (0.0, lift, 0.0), scales=scales)
    ankle = skin(rows, np.array([[foot, foot]]), np.array([[1.0, 0.0]]), matrices)[0, :3]
    assert ankle[1] == pytest.approx(skeleton.heads[foot][1], abs=0.01)   # the ankle is as high as before
    hip = skeleton.index("UpperLeg_L")
    rows[0, :3] = skeleton.heads[hip]
    assert skin(rows, np.array([[hip, hip]]), np.array([[1.0, 0.0]]), matrices)[0, 1] > skeleton.heads[hip][1] + 0.05


def test_longer_arms_and_neck_carry_the_hand_and_the_head_further(skeleton):
    hand, head = skeleton.index("Hand_L"), skeleton.index("Head")
    shoulder = skeleton.heads[skeleton.index("UpperArm_L")]
    reach = np.linalg.norm(skeleton.heads[hand] - shoulder)
    longer = posed(skeleton, skeleton.heads[hand], "Hand_L", {"bracos_comprimento": 1.0})
    assert np.linalg.norm(longer - shoulder) == pytest.approx(reach * (1 + body_shape.ARM_LENGTH), rel=0.02)
    assert posed(skeleton, skeleton.heads[head], "Head", {"pescoco": 1.0})[1] > skeleton.heads[head][1] + 0.03


def test_the_waist_narrows_the_trunk_and_leaves_the_hands_beside_it(skeleton):
    torso = skeleton.index("Torso")
    low, high = sorted((skeleton.heads[torso][1], skeleton.tails[torso][1]))
    y = low + body_shape.WAIST_BAND[0] * (high - low)
    axis = skeleton.heads[torso]
    points = np.array([[axis[0] + 0.15, y, axis[2]], [axis[0] + 0.16, y, axis[2]],   # skin and the cloth over it
                       [axis[0] + 0.50, y, axis[2]], [axis[0] + 0.15, y + 0.6, axis[2]]])  # a hand, the shoulders
    out = body_shape.warp(points, skeleton, {"cintura": -1.0})
    assert out[0, 0] - axis[0] == pytest.approx(0.15 * (1 - body_shape.WAIST))
    assert out[1, 0] > out[0, 0]                      # the cloth is still outside the skin
    np.testing.assert_allclose(out[2:], points[2:], atol=1e-6)


def test_clearance_moves_the_cloth_along_one_normal_at_each_seam():
    rows = np.zeros((3, 11))
    rows[:, :3] = [[0, 0, 0], [0, 0, 0], [1, 0, 0]]        # two vertices of a texture seam, and another
    rows[:, 3:6] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    normals = body_shape.smooth_normals(rows)
    np.testing.assert_allclose(normals[0], normals[1])
    np.testing.assert_allclose(normals[0], np.array([1, 1, 0]) / np.sqrt(2))
    np.testing.assert_allclose(normals[2], [0, 0, 1])
    assert body_shape.clearance({"folga": 1.0}) == 0.02 and body_shape.clearance({}) == 0.0
    assert body_shape.clearance({"folga": -1.0}) == -0.003  # closer to the body there is little room


def test_the_nose_sits_on_the_face_of_each_head():
    from src.clothing import nose
    head = np.zeros((8, 11))
    head[:, :3] = [[x, y, z] for x in (-0.11, 0.11) for y in (1.479, 1.795) for z in (-0.10, 0.150)]  # the female head's box
    for style in nose.STYLE_NAMES:
        rows, triangles = nose.styled_rows(head, style)
        assert rows.shape[1] == 11 and triangles.max() < len(rows)
        assert rows[:, 1].min() == pytest.approx(nose.NOSE_BOTTOM - 0.013, abs=1e-6)  # ends above the mouth, as on the old head
        assert 0.150 - 0.004 <= rows[:, 2].min() <= 0.150                             # its base is on this face
        assert rows[:, 2].max() > 0.150 + 0.008                                       # and it stands out of it
        np.testing.assert_array_equal(rows[:, 8:], 1.0)


def test_nose_styles_share_their_triangles_and_differ_where_their_names_say():
    from src.clothing import nose
    built = {name: nose.build(shape) for name, shape in nose.NOSE_STYLES.items()}
    base = built["padrao"]
    assert all(rows.shape == base.shape for rows in built.values())   # one topology: a style is changed in place
    width = lambda rows: np.ptp(rows[:, 0])
    assert np.ptp(base[:, 1]) == pytest.approx(0.070) and base[:, 2].max() == pytest.approx(0.015)  # the old nose's measures
    assert built["projetado"][:, 2].max() > base[:, 2].max() + 0.005
    assert width(built["narinas_largas"]) > width(base) + 0.008 and width(built["fino"]) < width(base)
    tip = lambda rows: rows[rows[:, 2] > rows[:, 2].max() - 1e-9]
    assert np.ptp(tip(built["ponta_larga"])[:, 0]) > np.ptp(tip(base)[:, 0]) + 0.005
    from dataclasses import replace
    middle = lambda rows: rows[np.abs(rows[:, 1] - 0.035) < 0.012][:, 2].max()   # the ridge half-way up, same length
    curved_out, curved_in = nose.build(replace(nose.BASE, curve=1.0)), nose.build(replace(nose.BASE, curve=-1.0))
    assert middle(curved_out) > middle(base) + 0.003 and middle(curved_in) < middle(base) - 0.003
    assert nose.NOSE_STYLES["aquilino"].curve > 0 > nose.NOSE_STYLES["arrebitado"].curve
    assert np.ptp(built["botao"][:, 1]) < 0.05 < 0.08 < np.ptp(built["longo"][:, 1])
    for rows in built.values():                                       # every face looks out of the nose
        inside = np.array([0.0, np.ptp(rows[:, 1]) / 2, 0.0])
        centres = rows[:, :3].reshape(-1, 3, 3).mean(1)
        assert ((rows[::3, 3:6] * (centres - inside)).sum(1) > -1e-9).all()


def test_nose_adjustments_grow_it_out_of_the_face_not_into_it():
    from src.clothing import nose
    points = nose.ROWS[:, :3]
    assert not body_shape.nose_adjusted({"nariz_sombra": 1.0}) and body_shape.nose_adjusted({"nariz_altura": 0.2})
    out = body_shape.nose_shape(points, {"nariz_projecao": 1.0})
    assert out[:, 2].min() == pytest.approx(points[:, 2].min())                        # still on the face
    assert np.ptp(out[:, 2]) == pytest.approx(np.ptp(points[:, 2]) * (1 + body_shape.NOSE_DEPTH))
    wide = body_shape.nose_shape(points, {"nariz_largura": 1.0})
    assert np.ptp(wide[:, 0]) == pytest.approx(np.ptp(points[:, 0]) * (1 + body_shape.NOSE_WIDTH))
    assert np.ptp(wide[:, 1]) == pytest.approx(np.ptp(points[:, 1]))
    high = body_shape.nose_shape(points, {"nariz_altura": 1.0})
    np.testing.assert_allclose(high - points, [[0.0, body_shape.NOSE_LIFT, 0.0]] * len(points), atol=1e-12)


def test_the_nose_shadow_is_painted_between_the_eyes_and_follows_its_slider():
    from src.clothing.customization import HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    spot = (128, 170)  # the middle of the shadow in the 512 px atlas
    def skin_at(**fields):
        return np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB").getpixel(spot), dtype=int)
    bare = skin_at(has_3d_nose=False)
    assert (skin_at() < bare).all()                                                    # a little darker with the nose
    assert (skin_at(body_adjust={"nariz_sombra": 1.0}) < skin_at()).all()              # darker still
    np.testing.assert_array_equal(skin_at(body_adjust={"nariz_sombra": -1.0}), bare)   # and none at all


def test_skin_nariz_shows_and_hides_the_nose():
    reloads = []
    model = SimpleNamespace(customization=AvatarCustomization(), reload=lambda: reloads.append(1))
    handler = SkinCommandHandler(character_model=model)
    assert model.customization.should_render_3d_nose
    assert handler.execute("/skin nariz nao")[0] and not model.customization.should_render_3d_nose
    assert handler.execute("/skin nariz sim")[0] and model.customization.should_render_3d_nose and len(reloads) == 2
    assert handler.execute("/skin nariz talvez")[0] is False
    assert handler.execute("/skin ajuste nariz_projecao 60")[0] and len(reloads) == 2  # the mesh is reshaped, not rebuilt
    assert handler.execute("/skin nariz aquilino")[0] and model.customization.nose_style == "aquilino"
    assert handler.execute("/skin nariz arrebitado")[0] and len(reloads) == 2            # another shape of the same mesh
    assert handler.execute("/skin nariz bloco")[0] and len(reloads) == 3                 # the old mesh: rebuilt
    assert handler.execute("/skin nariz nao")[0] and handler.execute("/skin nariz fino")[0]
    assert model.customization.should_render_3d_nose and len(reloads) == 5               # a style puts the nose back
