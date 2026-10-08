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
        assert rows[:, 2].max() > 0.150 + 0.005                                       # and it stands out of it (the flat one, less)
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
    for rows in built.values():                                       # each normal is the one of its triangle
        corners = rows[:, :3].reshape(-1, 3, 3)
        winding = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        solid = np.linalg.norm(winding, axis=1) > 1e-12
        assert ((rows[::3, 3:6] * winding).sum(1)[solid] > 0).all()
    ridge = base[:102]                                                 # the body of the nose comes first: it faces outwards
    inside = np.array([0.0, np.ptp(base[:, 1]) / 2, 0.0])
    assert ((ridge[::3, 3:6] * (ridge[:, :3].reshape(-1, 3, 3).mean(1) - inside)).sum(1) > -1e-9).all()


def test_wide_noses_have_wings_beside_the_tip_and_the_others_have_none():
    from src.clothing import nose
    width = lambda name: np.ptp(nose.build(nose.NOSE_STYLES[name])[:, 0])
    for name in ("botao_largo", "narinas_grandes", "achatado", "batata", "aberto", "botao_arrebitado"):
        shape = nose.NOSE_STYLES[name]
        assert shape.wing_width > 0 and width(name) == pytest.approx(shape.nostril_width + 2 * shape.wing_width)
    assert width("narinas_grandes") > 2 * width("botao")              # much wider than the button nose it comes from
    assert nose.NOSE_STYLES["narinas_grandes"].length < nose.BASE.length
    plain = nose.build(nose.BASE).reshape(-1, 3, 8)[34:50]            # the wings of a nose without them
    areas = np.linalg.norm(np.cross(plain[:, 1, :3] - plain[:, 0, :3], plain[:, 2, :3] - plain[:, 0, :3]), axis=1)
    assert len(plain) == 16 and (areas < 1e-12).all()                 # flat: nothing to see


def test_each_part_of_the_nose_is_adjusted_by_itself():
    from src.clothing import nose
    wide = nose.NOSE_STYLES["narinas_grandes"]
    assert not nose.parametric({"nariz_tamanho": 1.0}) and nose.parametric({"nariz_ponta_largura": 0.3})
    assert nose.adjusted(wide, {}) == wide
    tip = nose.adjusted(wide, {"nariz_ponta_largura": 1.0})
    assert tip.tip_width > wide.tip_width and (tip.bridge_base, tip.nostril_width) == (wide.bridge_base, wide.nostril_width)
    bridge = nose.adjusted(wide, {"nariz_ponte_largura": -1.0, "nariz_ponte_altura": 1.0})
    assert bridge.bridge_base < wide.bridge_base and bridge.bridge_depth == pytest.approx(wide.bridge_depth + 0.006)
    assert (bridge.tip_width, bridge.nostril_width, bridge.wing_width) == (wide.tip_width, wide.nostril_width, wide.wing_width)
    base = nose.adjusted(wide, {"nariz_base_largura": 1.0, "nariz_base_altura": 1.0})
    assert base.nostril_width > wide.nostril_width and base.wing_width > wide.wing_width
    assert base.wing_height > wide.wing_height and base.flare < wide.flare and base.tip_width == wide.tip_width
    assert nose.build(tip).shape == nose.build(wide).shape             # still the same triangles
    wings = lambda shape: nose.build(shape).reshape(-1, 3, 8)[34:50, :, :3].reshape(-1, 3)
    raised = nose.adjusted(wide, {"nariz_narinas_altura": 1.0})
    np.testing.assert_allclose(wings(raised) - wings(wide), [[0.0, nose.WING_LIFT, 0.0]] * 48, atol=1e-12)  # only up
    np.testing.assert_allclose(nose.build(raised)[:102], nose.build(wide)[:102])    # the nose itself stays
    lowered = nose.adjusted(wide, {"nariz_narinas_altura": -1.0})
    assert wings(lowered)[:, 1].min() == pytest.approx(-nose.WING_LIFT)


def test_the_tip_of_the_nose_can_be_pinker_and_the_bridge_keeps_the_skin():
    from src.clothing import nose
    head = np.zeros((8, 11))
    head[:, :3] = [[x, y, z] for x in (-0.11, 0.11) for y in (1.492, 1.809) for z in (-0.10, 0.133)]
    rows, _ = nose.styled_rows(head, "padrao")
    np.testing.assert_array_equal(nose.tip_colours(rows, {}), 1.0)
    pink = nose.tip_colours(rows, {"nariz_ponta_cor": 1.0})
    top, bottom = rows[:, 1] > rows[:, 1].max() - 0.01, rows[:, 1] < rows[:, 1].min() + 0.005
    np.testing.assert_array_equal(pink[top], 1.0)                      # the bridge is the skin as it is
    np.testing.assert_allclose(pink[bottom], [nose.TIP_PINK] * int(bottom.sum()))
    assert (pink[bottom][:, 0] > pink[bottom][:, 1]).all()             # red stays, green and blue drop: pink
    half = nose.tip_colours(rows, {"nariz_ponta_cor": 0.5})
    assert (half[bottom] > pink[bottom] - 1e-12).all() and (half[bottom][:, 1] < 1.0).all()
    assert (nose.tip_colours(rows, {"nariz_ponta_cor": -1.0})[bottom] < 1.0).all()   # the other way: darker


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


def test_each_eye_takes_its_own_colour_and_makeup_changes_only_what_it_names():
    from src.clothing.customization import HeadAtlasBuilder, IrisColor
    builder = HeadAtlasBuilder()
    def atlas(**fields):
        return np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB"), dtype=int)
    same = atlas(iris_color=IrisColor.BLUE)
    odd = atlas(iris_color=IrisColor.BLUE, iris_color_other=IrisColor.GREEN)
    changed = np.nonzero((same != odd).any(axis=2))
    assert len(changed[0]) > 50
    eyes = np.nonzero((same != atlas(iris_color=IrisColor.GREEN)).any(axis=2))[1]    # the columns of both irises
    middle = (eyes.min() + eyes.max()) // 2
    assert changed[1].min() > middle                         # only one eye changed: the other half of the layer
    lips = np.nonzero((same != atlas(iris_color=IrisColor.BLUE, makeup={"batom": "roxo"})).any(axis=2))
    assert len(lips[0]) > 20 and lips[0].min() > changed[0].max()      # lipstick: below the eyes, and nothing else
    lids = np.nonzero((same != atlas(iris_color=IrisColor.BLUE, makeup={"sombra": "azul"})).any(axis=2))
    assert len(lids[0]) > 50 and lids[0].max() < lips[0].min()         # eye shadow: around the eyes, above the mouth
    np.testing.assert_array_equal(same, atlas(iris_color=IrisColor.BLUE, makeup={"batom": "cor_que_nao_existe"}))


def test_skin_olho_and_maquiagem_set_what_the_face_is_drawn_with():
    from src.clothing.customization import IrisColor
    model = SimpleNamespace(customization=AvatarCustomization(iris_color=IrisColor.BLUE), reload=lambda: None)
    handler = SkinCommandHandler(character_model=model)
    custom = model.customization
    assert handler.execute("/skin olho esquerdo verde")[0]
    assert (custom.iris_color, custom.iris_color_other) == (IrisColor.BLUE, IrisColor.GREEN)
    assert handler.execute("/skin olho direito castanho")[0] and custom.iris_color is IrisColor.BROWN
    assert handler.execute("/skin olhos roxo")[0] and custom.iris_color_other is None    # both the same again
    assert handler.execute("/skin olho meio azul")[0] is False
    assert handler.execute("/skin maquiagem batom vermelho")[0] and handler.execute("/skin maquiagem sombra roxo")[0]
    assert custom.makeup == {"batom": "vermelho", "sombra": "roxo"}
    assert handler.execute("/skin maquiagem batom sem")[0] and custom.makeup == {"sombra": "roxo"}
    assert handler.execute("/skin maquiagem blush alternar")[0] and custom.resolved_face_detail == "blush"
    assert handler.execute("/skin maquiagem sardas sim")[0] and custom.resolved_face_detail == "blush_and_freckles"
    assert handler.execute("/skin maquiagem blush alternar")[0] and custom.resolved_face_detail == "freckles"
    assert handler.execute("/skin maquiagem batom fluorescente")[0] is False
    assert handler.execute("/skin maquiagem sem")[0] and custom.makeup == {} and custom.resolved_face_detail == "none"


def test_eye_shapes_come_from_the_eye_the_face_already_has():
    from src.clothing.eye_shapes import EDGE, SHAPE_NAMES, shape_eyes
    base = Image.open("assets/models/textures/layers/eyes/eye_anime_blue.png").convert("RGBA")
    assert shape_eyes(base, "padrao") is base and shape_eyes(base, "formato_que_nao_existe") is base
    box = base.getbbox()
    middle = (box[0] + box[2]) // 2
    left = lambda image: image.crop((0, 0, middle, image.height)).getbbox()
    plain = left(base)
    height = lambda name: left(shape_eyes(base, name))[3] - left(shape_eyes(base, name))[1]
    width = lambda name: left(shape_eyes(base, name))[2] - left(shape_eyes(base, name))[0]
    assert height("arredondado") > plain[3] - plain[1] + 6 and width("arredondado") < plain[2] - plain[0]
    assert height("estreito") < plain[3] - plain[1] - 6 and height("fechado") < plain[3] - plain[1] - 6
    assert height("grande") > plain[3] - plain[1] and width("grande") > plain[2] - plain[0]
    assert width("feminino") > plain[2] - plain[0]                      # the lashes reach further out
    palette = {tuple(p) for p in np.array(base).reshape(-1, 4).tolist()}
    for name in SHAPE_NAMES:
        shaped = shape_eyes(base, name)
        assert shaped.size == base.size
        assert left(shaped)[3] == plain[3]                                  # every shape rests on the same line
        assert {tuple(p) for p in np.array(shaped).reshape(-1, 4).tolist()} <= palette | {(0, 0, 0, 0)}  # no new colours: not blurred
        right = shaped.crop((middle, 0, shaped.width, shaped.height)).getbbox()   # the other eye is reshaped too
        assert right is not None and right[3] == plain[3]
    soft = np.array(shape_eyes(base, "suave"))
    drawn = np.nonzero(soft[:, :, 3] > 0)[0]
    assert drawn.min() >= plain[1] + 8                                      # the spikes above the lid are gone
    lower = soft[plain[3] - 8:plain[3], plain[0]:plain[0] + 26]
    assert not ((lower[:, :, 3] > 0) & (lower[:, :, :3].astype(int).mean(axis=2) < EDGE)).any()  # and the dots under it


def test_skin_olhos_takes_a_shape_as_well_as_a_colour_or_a_style():
    from src.clothing.customization import EyeStyle, HeadAtlasBuilder
    model = SimpleNamespace(customization=AvatarCustomization(eye_style=EyeStyle.CLASSIC), reload=lambda: None)
    handler = SkinCommandHandler(character_model=model)
    custom = model.customization
    assert handler.execute("/skin olhos arredondado")[0] and custom.eye_shape == "arredondado"
    assert custom.resolved_eye_style == "anime"                             # the shapes are of the anime eye
    assert handler.execute("/skin olhos formato fechado")[0] and custom.eye_shape == "fechado"
    assert handler.execute("/skin olhos verde")[0] and custom.eye_shape == "fechado"   # the colour leaves the shape
    assert handler.execute("/skin olhos quadrado")[0] is False
    builder = HeadAtlasBuilder()
    closed = np.array(builder.build_atlas(custom).convert("RGB"), dtype=int)
    custom.eye_shape = "padrao"
    assert (closed != np.array(builder.build_atlas(custom).convert("RGB"), dtype=int)).any()


def test_the_eye_models_are_cut_from_the_original_eye():
    from src.clothing.eye_shapes import SHAPE_NAMES, shape_eyes
    base = Image.open("assets/models/textures/layers/eyes/eye_anime_blue.png").convert("RGBA")
    colours = {tuple(p) for p in np.array(base).reshape(-1, 4).tolist() if p[3]}
    blue = lambda layer: (lambda a: (a[:, :, 2] > a[:, :, 0] + 15) & (a[:, :, 3] > 0))(np.array(layer).astype(int))
    centre = lambda mask: np.nonzero(mask[:, :128])[1].mean()
    old = base.getbbox()
    for name in ("serio", "masculino", "afiado", "redondo", "retro", "cansado", "felino"):
        assert name in SHAPE_NAMES
        shaped = shape_eyes(base, name)
        pixels = np.array(shaped)
        assert {tuple(p) for p in pixels.reshape(-1, 4).tolist() if p[3]} <= colours, name   # nothing but the original's pixels
        assert (pixels != np.array(base)).any(), name
        assert abs(centre(blue(shaped)) - centre(blue(base))) <= 8, name                    # the iris where it was: not cross-eyed
        box = shaped.getbbox()
        assert abs(box[3] - old[3]) <= 8 and blue(shaped).sum() > 0.3 * blue(base).sum(), name   # at the same height, the iris showing
    wing = lambda name: np.array(shape_eyes(base, name))[:, :128, 3].any(axis=0).nonzero()[0].min()
    assert wing("masculino") > wing("padrao") and wing("serio") > wing("padrao")          # without the wing of lashes


def test_the_block_nose_with_nostrils_is_the_old_block_and_two_wings():
    from src.clothing import nose
    block, _ = nose.model_rows("bloco")
    winged, triangles = nose.model_rows("bloco_narinas")
    assert "bloco_narinas" in nose.STYLE_NAMES and len(winged) > len(block)
    np.testing.assert_array_equal(winged[:len(block)], block)                      # the block as it was
    wings = winged[len(block):]
    assert triangles.max() == len(winged) - 1
    assert wings[:, 0].min() < block[:, 0].min() and wings[:, 0].max() > block[:, 0].max()   # one on each side
    assert abs(wings[:, 1].min() - block[:, 1].min()) < 1e-9 and wings[:, 1].max() < block[:, 1].max()   # at the tip, not up the bridge


def test_the_computed_nose_shadow_follows_the_nose_in_use():
    from src.clothing.customization import HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    atlas = lambda **fields: np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB"), dtype=int)
    bare = atlas(body_adjust={"nariz_sombra": -1.0})
    dark = lambda image: (bare - image).sum(axis=2) > 6                              # where a shadow darkened the skin
    legacy, plain = dark(atlas()), dark(atlas(nose_shadow="calculada"))
    wide, short = dark(atlas(nose_shadow="calculada", nose_style="narinas_grandes")), dark(atlas(nose_shadow="calculada", nose_style="botao"))
    assert legacy.any() and plain.any() and (legacy != plain).any()
    assert (dark(atlas(nose_style="botao")) == legacy).all()                         # the legacy one is the same for every nose
    rows = lambda mask: np.nonzero(mask.any(axis=1))[0]
    columns = lambda mask: np.nonzero(mask.any(axis=0))[0]
    assert rows(short).min() > rows(plain).min() + 10                                # a short nose: a short shadow
    assert np.ptp(columns(wide)) > np.ptp(columns(plain)) + 6                        # wide nostrils: a wider one
    assert not plain[:, 160:].any() and not plain[:120].any()                        # and it stays by the nose
    wider = dark(atlas(nose_shadow="calculada", body_adjust={"nariz_base_largura": 1.0}))
    assert (wider != plain).any()                                                    # the adjustments of the nose move it too


def test_the_block_noses_take_the_adjustments_of_the_parts():
    from src.clothing import nose
    plain, _ = nose.model_rows("bloco")
    lower = plain[:, 1] < (plain[:, 1].min() + plain[:, 1].max()) / 2
    front = plain[:, 2] > nose.BLOCK_FRONT
    width = lambda rows, mask: np.ptp(rows[mask, 0])
    rows = lambda **adjust: nose.model_rows("bloco", adjust)[0]
    tip, base, bridge = rows(nariz_ponta_largura=1.0), rows(nariz_base_largura=1.0), rows(nariz_ponte_largura=1.0)
    assert width(tip, lower & front) > width(plain, lower & front) * 1.4 and width(tip, ~lower) == width(plain, ~lower)
    assert width(base, lower & ~front) > width(plain, lower & ~front) * 1.4 and width(base, lower & front) == width(plain, lower & front)
    assert width(bridge, ~lower) > width(plain, ~lower) * 1.4 and width(bridge, lower) == width(plain, lower)
    assert rows(nariz_ponte_altura=1.0)[~lower, 2].max() > plain[~lower, 2].max() + 0.004
    assert rows(nariz_base_altura=1.0)[lower, 1].max() > plain[lower, 1].max() + 0.004
    assert all(len(rows(**{name: 1.0})) == len(plain) for name in nose.PARAMETRIC)   # reshaped in place, the same vertices
    winged = lambda **adjust: nose.model_rows("bloco_narinas", adjust)[0][len(plain):]
    assert winged(nariz_narinas_altura=1.0)[:, 1].min() > winged()[:, 1].min() + 0.005
    assert np.ptp(winged(nariz_base_largura=1.0)[:, 0]) > np.ptp(winged()[:, 0])
    assert np.ptp(winged(nariz_ponta_largura=1.0)[:, 0]) > np.ptp(winged()[:, 0])    # the wings stay against the wider tip


def test_the_computed_nose_shadow_fades_up_the_nose_and_stays_off_it():
    from src.clothing import nose
    from src.clothing.customization import HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    atlas = lambda **fields: np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB"), dtype=int)
    shade = (atlas(body_adjust={"nariz_sombra": -1.0}) - atlas(nose_shadow="calculada")).sum(axis=2)
    rows8, _ = nose.model_rows("padrao")
    flat = nose.face_pixels(rows8[:, :3])
    top, bottom = int(flat[:, 1].min()), int(flat[:, 1].max())
    assert shade[top - 4:top + 6].max() <= 3                                         # nothing at the top of the bridge
    quarter = (bottom - top) // 4
    assert shade[top:top + quarter].max() < shade[bottom - quarter:bottom + 4].max()   # and it grows down the nose
    middle = int(round(flat[:, 0].mean()))
    assert shade[bottom - 12:bottom - 3, middle - 2:middle + 3].max() == 0             # none under the nose itself
    u, v = int(nose.PLAIN_UV[0] * 512), int(nose.PLAIN_UV[1] * 512)
    assert shade[v - 1:v + 2, u - 1:u + 2].max() == 0                                  # nor where the nose takes its colour
    plain = nose.styled_rows(np.zeros((3, 11)), "batata", plain=True)[0]
    assert np.allclose(plain[:, 6:8], nose.PLAIN_UV) and not np.allclose(nose.styled_rows(np.zeros((3, 11)), "batata")[0][:, 6:8], nose.PLAIN_UV)


def test_the_tip_comes_out_on_its_own_without_the_nostrils():
    from dataclasses import replace
    from src.clothing import nose
    shape = nose.NOSE_STYLES["batata"]
    out = nose.adjusted(shape, {"nariz_ponta_projecao": 1.0})
    assert out.tip_depth > shape.tip_depth + 0.008 and out == replace(shape, tip_depth=out.tip_depth)   # nothing else: not the wings
    assert nose.adjusted(shape, {"nariz_ponta_projecao": -1.0}).tip_depth < shape.tip_depth
    assert "nariz_ponta_projecao" in body_shape.NOSE and "nariz_ponta_projecao" in nose.PARAMETRIC
    plain, _ = nose.model_rows("bloco_narinas")
    far, _ = nose.model_rows("bloco_narinas", {"nariz_ponta_projecao": 1.0})
    block = len(nose.ROWS)
    assert far[:block, 2].max() > plain[:block, 2].max() + 0.008                   # the block's tip
    np.testing.assert_allclose(far[block:], plain[block:], atol=1e-9)              # its wings as they were
    top = plain[:block, 1] > plain[:block, 1].max() - 0.001
    np.testing.assert_allclose(far[:block][top], plain[:block][top], atol=1e-9)    # and the top of the bridge


def test_the_shading_of_the_chin_is_turned_down_or_up_without_touching_the_face():
    rows = np.zeros((6, 11), dtype=np.float32)
    rows[:, 8:11] = 1.0
    rows[:, 1] = [0.00, 0.02, 0.02, 0.20, 0.25, 0.25]                                # two levels: the chin, the face
    rows[:, 3:6] = [[0, -0.7, 0.71], [0.6, -0.3, 0.74], [0, 0, -1], [0, 0.1, 0.995], [0.1, 0.1, 0.99], [1, 0, 0]]
    assert body_shape.face_shading(rows, {}) is rows
    flat = body_shape.face_shading(rows, {"rosto_sombra": -1.0})
    lit = rows[3:5, 3:6].mean(axis=0) / np.linalg.norm(rows[3:5, 3:6].mean(axis=0))
    np.testing.assert_allclose(flat[:2, 3:6], [lit, lit], atol=1e-6)                 # the chin lit as the front of the face
    np.testing.assert_array_equal(flat[2:], rows[2:])                                # the back of the chin and the face as they were
    half = body_shape.face_shading(rows, {"rosto_sombra": -0.5})
    assert rows[0, 4] < half[0, 4] < flat[0, 4]
    dark = body_shape.face_shading(rows, {"rosto_sombra": 1.0})
    assert (dark[:2, 8:11] < 0.8).all() and (dark[2:, 8:11] == 1.0).all() and (dark[:, 3:6] == rows[:, 3:6]).all()
    assert "rosto_sombra" in body_shape.ADJUSTMENTS and "rosto_sombra" in body_shape.REDRAWS_FACE


def test_contour_makeup_and_the_chin_band_are_drawn_on_the_face():
    from src.clothing.customization import CHIN_BAND, HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    atlas = lambda **fields: np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB"), dtype=int)
    plain = atlas()
    soft, strong = atlas(makeup={"contorno": "suave"}), atlas(makeup={"contorno": "marcado"})
    darker = lambda image: (plain - image).sum(axis=2)
    assert darker(soft).max() > 10 and darker(strong).max() > darker(soft).max()      # shade, stronger when marked
    assert darker(strong).min() < 0                                                   # and light on the cheekbones
    left, right = darker(strong)[150:240, 10:110].sum(), darker(strong)[150:240, 147:247].sum()
    assert abs(left - right) < 0.1 * abs(left)                                        # on both sides of the face
    assert (strong[125:185, 40:80] == plain[125:185, 40:80]).mean() > 0.5             # under the eyes, which are drawn over it
    y0, y1, x0, x1 = CHIN_BAND
    skin = np.array(AvatarCustomization().skin_rgb_255)
    assert (plain[y0:y1, x0:x1] != skin).any()                                        # the band is a darker skin
    none = atlas(body_adjust={"rosto_sombra": -1.0})
    assert np.abs(none[y0 + 2:y1 - 12, x0 + 20:x1 - 20] - skin).max() <= 1            # down to the skin itself
    more = atlas(body_adjust={"rosto_sombra": 1.0})
    assert (more[y0 + 2:y1 - 12, x0 + 20:x1 - 20] < plain[y0 + 2:y1 - 12, x0 + 20:x1 - 20]).all()
    assert (none[:y0] == plain[:y0]).all() and (more[:y0] == plain[:y0]).all()        # nothing else changes


def test_contour_is_chosen_by_command():
    model = SimpleNamespace(customization=AvatarCustomization(), reload=lambda: None, refresh_face=lambda: True)
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin maquiagem contorno marcado")[0] and model.customization.makeup == {"contorno": "marcado"}
    assert handler.execute("/skin maquiagem batom rosa")[0] and model.customization.makeup == {"contorno": "marcado", "batom": "rosa"}
    assert handler.execute("/skin maquiagem contorno sem")[0] and model.customization.makeup == {"batom": "rosa"}
    assert not handler.execute("/skin maquiagem contorno forte")[0]


def test_the_female_face_has_no_shading_under_it_unless_it_is_asked_for():
    from src.clothing.customization import BodyType
    woman, man = AvatarCustomization(body_type=BodyType.FEMALE), AvatarCustomization(body_type=BodyType.MALE)
    assert woman.face_adjust("rosto_sombra") == -1.0 and man.face_adjust("rosto_sombra") == 0.0
    assert woman.body_adjust == {} and woman.resolved_body_adjust == {"rosto_sombra": -1.0} and man.resolved_body_adjust == {}
    assert woman.get_cache_key() != man.get_cache_key()
    model = SimpleNamespace(customization=woman, reload=lambda: None, refresh_face=lambda: True)
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin ajuste rosto_sombra 0")[0]
    assert woman.body_adjust == {"rosto_sombra": 0.0} and woman.face_adjust("rosto_sombra") == 0.0   # a zero asked for is kept
    assert handler.execute("/skin ajuste peito 40")[0] and woman.face_adjust("rosto_sombra") == 0.0
    assert handler.execute("/skin ajuste reset")[0] and woman.face_adjust("rosto_sombra") == -1.0      # back to the body's default


def test_makeup_takes_any_colour_and_its_tone_is_moved_by_the_controls():
    from src.clothing.customization import MAKEUP_COLORS, parse_makeup_colour, shift_colour
    assert parse_makeup_colour("rosa") == MAKEUP_COLORS["rosa"] and parse_makeup_colour("#20C0a0") == (32, 192, 160)
    assert parse_makeup_colour("200,40,55") == (200, 40, 55) and len(MAKEUP_COLORS) >= 16
    assert all(parse_makeup_colour(bad) is None for bad in ("", "fluorescente", "#12", "300,0,0", "1,2"))
    red = (200, 40, 55)
    assert shift_colour(red) == red
    turned = shift_colour(red, hue=0.5)
    assert turned[1] > turned[0] or turned[2] > turned[0]                                # a quarter of the wheel away: no longer red
    assert max(shift_colour(red, saturation=-1.0)) - min(shift_colour(red, saturation=-1.0)) == 0   # grey
    assert sum(shift_colour(red, brightness=1.0)) > sum(red) > sum(shift_colour(red, brightness=-0.5))
    custom = AvatarCustomization(makeup={"batom": "vermelho", "blush": "#ff8899"}, body_adjust={"batom_brilho": -0.5})
    assert custom.makeup_color("batom") == shift_colour(red, brightness=-0.5) and custom.makeup_color("blush") == (255, 136, 153)
    assert custom.makeup_color("sombra") is None
    assert {"blush_intensidade", "blush_tamanho", "blush_esfumado", "blush_altura", "blush_matiz", "sombra_esfumado",
            "batom_saturacao"} <= set(body_shape.ADJUSTMENTS) & body_shape.REDRAWS_FACE
    assert "batom_intensidade" not in body_shape.ADJUSTMENTS


def test_blush_and_eye_shadow_are_drawn_soft_and_follow_their_controls():
    from src.clothing.customization import BLUSH_AT, HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    atlas = lambda **fields: np.array(builder.build_atlas(AvatarCustomization(**fields)).convert("RGB"), dtype=int)
    plain = atlas()
    changed = lambda image: np.abs(image - plain).sum(axis=2)
    x, y = int(BLUSH_AT[0]), int(BLUSH_AT[1])
    blush = changed(atlas(makeup={"blush": "rosa"}))
    assert blush[y, x] > 20 and blush[y, 256 - x] > 20 and blush[60, 128] == 0             # on both cheeks, nowhere else
    assert 0 < blush[y, x + 30] < blush[y, x + 15] < blush[y, x]                           # fading out, with no hard edge
    spread = lambda image: int((image > 6).sum())
    strong = changed(atlas(makeup={"blush": "rosa"}, body_adjust={"blush_intensidade": 1.0}))
    large = changed(atlas(makeup={"blush": "rosa"}, body_adjust={"blush_tamanho": 1.0}))
    soft = changed(atlas(makeup={"blush": "rosa"}, body_adjust={"blush_esfumado": 1.0}))
    high = changed(atlas(makeup={"blush": "rosa"}, body_adjust={"blush_altura": 1.0}))
    assert strong[y, x] > blush[y, x] and spread(large) > spread(blush) and soft[y, x] < blush[y, x]
    assert np.nonzero(high.sum(axis=1))[0].mean() < np.nonzero(blush.sum(axis=1))[0].mean()
    green = atlas(makeup={"blush": "#20c0a0"})
    assert green[y, x, 1] > green[y, x, 0]                                                  # any colour
    shadow = changed(atlas(makeup={"sombra": "roxo"}))
    rows = np.nonzero(shadow[:, :128].sum(axis=1))[0]
    assert shadow.any() and rows.min() > 100 and rows.max() < 190                           # over the eyelid, under the eyebrow's top
    bigger = changed(atlas(makeup={"sombra": "roxo"}, body_adjust={"sombra_tamanho": 1.0}))
    stronger = changed(atlas(makeup={"sombra": "roxo"}, body_adjust={"sombra_intensidade": 1.0}))
    softer = changed(atlas(makeup={"sombra": "roxo"}, body_adjust={"sombra_esfumado": 1.0}))
    assert spread(bigger) > spread(shadow) and stronger.max() > shadow.max() and spread(softer) > spread(shadow)


def test_blush_is_chosen_by_colour_and_takes_the_place_of_the_old_layer():
    model = SimpleNamespace(customization=AvatarCustomization(), reload=lambda: None, refresh_face=lambda: True)
    handler, custom = SkinCommandHandler(character_model=model), model.customization
    assert handler.execute("/skin maquiagem blush alternar")[0] and handler.execute("/skin maquiagem sardas sim")[0]
    assert custom.resolved_face_detail == "blush_and_freckles"
    assert handler.execute("/skin maquiagem blush coral")[0]
    assert custom.makeup == {"blush": "coral"} and custom.resolved_face_detail == "freckles"   # not two blushes
    assert handler.execute("/skin maquiagem sombra #20C0A0")[0] and custom.makeup["sombra"] == "#20c0a0"
    assert handler.execute("/skin maquiagem batom 200, 40, 55")[0] and custom.makeup["batom"] == "200,40,55"
    assert not handler.execute("/skin maquiagem blush fluorescente")[0]
    assert handler.execute("/skin maquiagem blush sem")[0] and "blush" not in custom.makeup


def head_box():
    """A head as rows of 11 floats: a box 0.2 m wide and deep, 0.3 m tall, standing on y = 1.5."""
    corners = np.array([[x, y, z] for x in (-0.1, 0.1) for y in (1.5, 1.8) for z in (-0.1, 0.1)])
    rows = np.zeros((len(corners), 11))
    rows[:, :3] = corners
    return rows


def test_every_ear_model_has_the_same_triangles_and_its_own_shape():
    from src.clothing import ears
    assert ears.STYLE_NAMES[:7] == ("sem", "humana", "redonda", "elfo", "elfo_asa", "morcego", "barbatana")
    assert ears.styled_rows(head_box(), "sem") is None and ears.styled_rows(head_box(), "de_gato") is None
    made = {name: ears.styled_rows(head_box(), name, skin=(0.9, 0.7, 0.6)) for name in ears.EAR_STYLES}
    shapes = {rows.shape for rows, _ in made.values()}
    assert len(shapes) == 1                                                             # moved in place from one model to another
    for name, (rows, triangles) in made.items():
        assert triangles.max() == len(rows) - 1 and np.isfinite(rows).all()
        right, left = rows[:len(rows) // 2], rows[len(rows) // 2:]
        if ears.EAR_STYLES[name].other is None:
            np.testing.assert_allclose(left[:, 0], -right[:, 0], atol=1e-6)             # one on each side, mirrored
            np.testing.assert_allclose(left[:, 1:3], right[:, 1:3], atol=1e-6)
        np.testing.assert_allclose(np.linalg.norm(rows[:, 3:6], axis=1), 1.0, atol=1e-5)
        if ears.EAR_STYLES[name].mount == "side" and ears.EAR_STYLES[name].other is None:
            assert right[:, 0].max() > 0.1 and right[:, 0].min() < 0.1                  # out of the head, its root inside it
        if ears.EAR_STYLES[name].coat == "skin":
            assert (rows[:, 8:11] <= np.array([0.9, 0.7, 0.6]) + 1e-6).all() and rows[:, 8].max() > 0.89   # the skin's colour, darker in the hollow
    span = lambda name, axis: float(np.ptp(made[name][0][:len(made[name][0]) // 2, axis]))
    top = lambda name: float(made[name][0][:, 1].max())
    assert span("elfo", 0) > 2 * span("humana", 0)                                      # the elf's stands out to the side
    assert top("morcego") > top("elfo_asa") > top("elfo")                               # the bat's goes up, the wing up and back
    assert span("redonda", 1) > span("humana", 1) and span("barbatana", 0) > span("humana", 0)
    bigger = ears.styled_rows(head_box(), "elfo", {"orelha_tamanho": 1.0})[0]
    higher = ears.styled_rows(head_box(), "elfo", {"orelha_altura": 1.0})[0]
    open_ = ears.styled_rows(head_box(), "humana", {"orelha_abertura": 1.0})[0]
    plain = made["elfo"][0]
    assert np.ptp(bigger[:, 0]) > np.ptp(ears.styled_rows(head_box(), "elfo")[0][:, 0])
    assert abs(higher[:, 1].mean() - ears.styled_rows(head_box(), "elfo")[0][:, 1].mean() - ears.LIFT) < 1e-5
    assert open_[:, 0].max() > ears.styled_rows(head_box(), "humana")[0][:, 0].max()
    assert set(ears.ADJUSTMENTS) == set(body_shape.EARS) <= set(body_shape.ADJUSTMENTS) and plain is not None


def test_ears_are_chosen_by_command_and_rebuilt_only_to_appear_or_go():
    reloads = []
    model = SimpleNamespace(customization=AvatarCustomization(), reload=lambda: reloads.append(1), refresh_face=lambda: True)
    handler, custom = SkinCommandHandler(character_model=model), model.customization
    assert custom.ear_style == "sem"
    assert handler.execute("/skin orelha elfo")[0] and custom.ear_style == "elfo" and len(reloads) == 1   # they appear: built
    assert handler.execute("/skin orelha morcego")[0] and custom.ear_style == "morcego" and len(reloads) == 1   # another model: moved in place
    assert not handler.execute("/skin orelha de_gato")[0] and custom.ear_style == "morcego"
    assert handler.execute("/skin orelha sem")[0] and custom.ear_style == "sem" and len(reloads) == 2


def test_a_race_is_a_choice_of_what_the_customization_already_has():
    from src.clothing import ears, nose, races
    assert {"humano", "elfo", "anao", "demonio", "tritao", "marciano"} <= set(races.RACES) and len(races.RACES) >= 8
    for name, race in races.RACES.items():
        assert race.ears in ears.STYLE_NAMES and (race.nose is None or race.nose in nose.STYLE_NAMES), name
        assert set(race.adjust) <= races.RACE_ADJUSTMENTS and all(-100 <= v <= 100 for v in race.adjust.values()), name
        assert all(0 <= c <= 255 for c in race.skin), name
    from src.clothing.customization import BodyType
    custom = AvatarCustomization(body_type=BodyType.FEMALE, body_adjust={"peito": 0.4, "blusa_barra": 0.3, "blush_tamanho": 0.5},
                                 makeup={"batom": "rosa"})
    races.apply(custom, "anao")
    assert custom.race == "anao" and custom.ear_style == "redonda" and custom.nose_style == "batata" and custom.has_3d_nose
    assert custom.body_adjust["altura"] == -0.9 and custom.body_adjust["ombros"] == 0.7
    assert "peito" in custom.body_adjust and custom.body_adjust["peito"] == 0.3            # the race's own, over what was there
    assert custom.body_adjust["blusa_barra"] == 0.3 and custom.body_adjust["blush_tamanho"] == 0.5   # what no race decides stays
    assert custom.makeup == {"batom": "rosa"} and custom.is_female                           # and the body chosen
    races.apply(custom, "marciano")
    assert custom.has_3d_nose is False and custom.ear_style == "sem" and "peito" not in custom.body_adjust
    assert custom.body_adjust["cabeca"] == 0.85 and custom.body_adjust["blusa_barra"] == 0.3
    races.apply(custom, "humano")
    assert custom.has_3d_nose and custom.ear_style == "humana" and custom.body_adjust == {"blusa_barra": 0.3, "blush_tamanho": 0.5}
    assert all(abs(a - b / 255.0) < 1e-9 for a, b in zip(custom.skin_color_rgb, races.RACES["humano"].skin))


def test_a_race_is_chosen_by_command_and_from_cards_in_the_body_section(tmp_path, monkeypatch):
    from src.interactive import character_editor
    from src.interactive.character_editor import CharacterEditor
    reloads = []
    model = SimpleNamespace(customization=AvatarCustomization(), body="female", reload=lambda: reloads.append(1))
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin raca elfo")[0] and model.customization.race == "elfo" and len(reloads) == 1
    assert not handler.execute("/skin raca gnomo_do_pantano")[0] and model.customization.race == "elfo"
    monkeypatch.setattr(character_editor, "RACE_THUMBS", str(tmp_path))
    (tmp_path / "elfo_female.png").write_bytes(b"")
    fake = SimpleNamespace(character_model=model, busy_status="", execute=lambda command: (True, "", (0, 0, 0)))
    editor = CharacterEditor(fake, {"active": False, "yaw": 0.0}, create_gl=False)
    editor.open()
    group = next(g for g in editor.groups() if g.title.startswith("Raça"))
    titles = [g.title for g in editor.groups()]
    assert titles.index(group.title) == titles.index("Corpo") + 1                            # right under female and male
    cards = {option.label: option for option in group.options}
    assert cards["Elfo"].kind == "card" and cards["Elfo"].command == "/skin raca elfo" and cards["Elfo"].selected(model)
    assert cards["Elfo"].image == str(tmp_path / "elfo_female.png") and cards["Anão"].image == ""   # drawn, and not yet
    assert not cards["Anão"].selected(model) and {"Demônio", "Tritão", "Marciano", "Humano"} <= set(cards)


def test_animal_ears_stand_on_top_of_the_head_in_the_colour_of_the_hair():
    from src.clothing import ears
    wanted = {"gato", "cachorro", "cachorro_caido", "lobo", "raposa", "coelho", "coelho_uma_caida", "coelho_caidas", "dragao", "reptil"}
    assert wanted <= set(ears.STYLE_NAMES)
    hair, skin = (0.5, 0.3, 0.2), (0.9, 0.7, 0.6)
    made = {name: ears.styled_rows(head_box(), name, skin=skin, hair=hair)[0] for name in wanted}
    right = lambda name: made[name][:len(made[name]) // 2]
    left = lambda name: made[name][len(made[name]) // 2:]
    top = 1.8                                                                           # of head_box
    for name in ("gato", "cachorro", "lobo", "raposa", "coelho"):
        assert right(name)[:, 1].min() > top - 0.04 and right(name)[:, 1].max() > top + 0.05, name   # on top, standing up
        assert abs(right(name)[:, 0]).max() < 0.2, name
        colours = right(name)[:, 8:11]
        assert np.allclose(colours.max(axis=0), np.maximum(hair, colours.max(axis=0))) and (colours[:, 0] >= 0.5 * 0.9).all(), name
        assert colours[:, 0].max() > hair[0] + 0.1                                      # pink inside
    assert right("coelho")[:, 1].max() > right("raposa")[:, 1].max() > right("lobo")[:, 1].max() > right("gato")[:, 1].max()
    for name in ("cachorro_caido", "coelho_caidas"):
        assert right(name)[:, 1].min() < top - 0.08 and right(name)[:, 1].max() < top + 0.02, name   # hanging down the side
        assert right(name)[:, 0].min() > 0.05, name
    one = made["coelho_uma_caida"]
    assert right("coelho_uma_caida")[:, 1].max() > top + 0.1 and left("coelho_uma_caida")[:, 1].max() < top + 0.02   # one up, one down
    assert one.shape == made["coelho"].shape
    for name in ("dragao", "reptil"):
        tones = np.unique(np.round(right(name)[:, 8], 3))
        assert len(tones) >= 3 and right(name)[:, 8].max() <= skin[0] + 1e-6, name      # scales: lighter and darker, of the skin
    assert np.ptp(right("dragao")[:, 0]) > 3 * np.ptp(right("reptil")[:, 0])
