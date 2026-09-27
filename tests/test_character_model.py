"""Testes unitários para o módulo CharacterModel e montagem do personagem 3D."""

import os
import numpy as np
import pytest

from src.clothing.character_model import (
    CharacterModel,
    CharacterPart,
    MODELS_DIR,
    CLOTHING_DIR,
    find_clothing_texture,
    parse_character_cli_args,
    parse_clean_obj_groups,
    parse_obj_as_mesh,
    SKIN_PRESETS,
    OUTFIT_PRESETS,
)
from src.clothing.customization import (
    AvatarCustomization,
    HeadType,
    MouthStyle,
    EyeStyle,
    IrisColor,
    HairColor,
    HairStyle,
)


def test_parse_character_cli_args_defaults():
    customization, top_id, bottom_id, tool_id, auto_spin = parse_character_cli_args([])
    assert customization.head_type == HeadType.ROUNDED
    assert customization.resolved_mouth_style == "anime_original"
    assert customization.resolved_eye_style == "anime"
    assert top_id == OUTFIT_PRESETS["sweater"]
    assert bottom_id == 109837605892174
    assert tool_id is None
    assert auto_spin is True


def test_parse_character_cli_args_custom():
    args = [
        "--head", "blocky",
        "--mouth", "cat",
        "--eyes", "anime_wink",
        "--iris", "green",
        "--hair-color", "blonde",
        "--hair", "bald",
        "--skin", "dark",
        "--top", "boxy",
        "--tool", "katana",
        "--no-spin",
    ]
    customization, top_id, bottom_id, tool_id, auto_spin = parse_character_cli_args(args)
    assert customization.head_type == HeadType.BLOCKY
    assert customization.mouth_style == MouthStyle.CAT
    assert customization.eye_style == EyeStyle.ANIME_WINK
    assert customization.iris_color == IrisColor.GREEN
    assert customization.hair_color == HairColor.BLONDE
    assert customization.hair_style == HairStyle.BALD
    assert customization.skin_color_rgb == SKIN_PRESETS["dark"]
    assert top_id == OUTFIT_PRESETS["boxy"]
    assert tool_id == 12187348
    assert auto_spin is False


def test_find_clothing_texture():
    sweater_tex = find_clothing_texture(9240757332)
    assert sweater_tex is not None
    assert os.path.exists(sweater_tex)
    assert "9240757332" in sweater_tex

    jeans_tex = find_clothing_texture(109837605892174)
    assert jeans_tex is not None
    assert os.path.exists(jeans_tex)
    assert "109837605892174" in jeans_tex


def test_parse_clean_obj_groups_rounded_head():
    head_path = os.path.join(MODELS_DIR, "character_head_rounded.obj")
    res = parse_clean_obj_groups(head_path, [""])
    assert res is not None
    v_arr, i_arr = res
    # 11 floats per vertex: Pos(3), Normal(3), UV(2), Col(3)
    assert len(v_arr) % 11 == 0
    assert len(i_arr) > 0
    # Must have smooth normals computed
    normals = v_arr.reshape(-1, 11)[:, 3:6]
    norm_lengths = np.linalg.norm(normals, axis=1)
    assert np.allclose(norm_lengths, 1.0, atol=1e-3)


def test_parse_clean_obj_groups_hair_fitted():
    hair_path = os.path.join(CLOTHING_DIR, "Hair_fitted_116773763268018.obj")
    res = parse_clean_obj_groups(hair_path, [""])
    assert res is not None
    v_arr, i_arr = res
    assert len(v_arr) % 11 == 0
    assert len(i_arr) > 0


def test_parse_obj_as_mesh_sweater():
    sweater_obj = os.path.join(MODELS_DIR, "character_native_9240757332.obj")
    res = parse_obj_as_mesh(sweater_obj)
    assert res is not None
    v_arr, i_arr = res
    assert len(v_arr) % 11 == 0
    assert len(i_arr) > 0


def test_parse_obj_as_mesh_hidden_arm():
    # An arm with '# Arm hidden' should return None
    arm_path = os.path.join(MODELS_DIR, "character_native_arm_left.obj")
    res = parse_obj_as_mesh(arm_path)
    assert res is None


def test_character_model_init_without_gl():
    cust = AvatarCustomization(head_type=HeadType.ROUNDED, mouth_style=MouthStyle.CAT)
    model = CharacterModel(customization=cust, create_mesh=False)
    assert model.customization.mouth_style == MouthStyle.CAT
    assert len(model.parts) == 0
    model.delete()


def test_slice_mesh_between_y():
    from src.clothing.character_model import slice_mesh_between_y
    clean_male = os.path.join(MODELS_DIR, "character_clean.obj")
    res = parse_clean_obj_groups(clean_male, ["Export_torso", "Export_pelve"])
    assert res is not None
    v_arr, i_arr = res
    v_mat = v_arr.reshape(-1, 11)
    faces = i_arr.reshape(-1, 3)

    y_min = 0.920
    y_max = 1.400
    sv, sf = slice_mesh_between_y(v_mat, faces, y_min=y_min, y_max=y_max)
    assert len(sv) > 0
    assert len(sf) > 0
    assert float(sv[:, 1].min()) >= y_min - 1e-4
    assert float(sv[:, 1].max()) <= y_max + 1e-4


def test_character_model_male_default_hem():
    from src.clothing.customization import AvatarCustomization, BodyType
    cust = AvatarCustomization(body_type=BodyType.MALE)
    model = CharacterModel(customization=cust, create_mesh=False)
    assert model.top_hem_offset == pytest.approx(-0.02)
    model.delete()


def test_character_model_waist_radius():
    model = CharacterModel(create_mesh=False)
    assert model.waist_radius_offset == 0.0
    model.set_waist_radius(-0.02)
    assert model.waist_radius_offset == pytest.approx(-0.02)
    model.set_waist_radius(0.02)
    assert model.waist_radius_offset == pytest.approx(0.02)
    model.reset_waist_radius()
    assert model.waist_radius_offset == 0.0

    # reset_waist_adjustments should also reset waist_radius_offset
    model.set_waist_radius(-0.015)
    model.reset_waist_adjustments()
    assert model.waist_radius_offset == 0.0
    model.delete()


def test_character_model_waist_chamfer():
    model = CharacterModel(create_mesh=False)
    assert model.waist_chamfer == pytest.approx(0.015)
    model.set_waist_chamfer(0.025)
    assert model.waist_chamfer == pytest.approx(0.025)
    model.set_waist_chamfer(0.0)
    assert model.waist_chamfer == pytest.approx(0.0)
    model.reset_waist_chamfer()
    assert model.waist_chamfer == pytest.approx(0.015)

    # reset_waist_adjustments should restore chamfer to 0.015
    model.set_waist_chamfer(0.035)
    model.reset_waist_adjustments()
    assert model.waist_chamfer == pytest.approx(0.015)
    model.delete()


def test_bevel_torso_corners():
    from src.clothing.character_model import bevel_torso_corners, parse_clean_obj_groups, MODELS_DIR
    import os
    clean_obj = os.path.join(MODELS_DIR, "character_clean.obj")
    trunk_data = parse_clean_obj_groups(clean_obj, ["Export_torso", "Export_pelve"])
    assert trunk_data is not None
    v_arr, i_arr = trunk_data
    v_mat = v_arr.reshape(-1, 11).copy()
    faces = i_arr.reshape(-1, 3).copy()

    # Zero chamfer returns identical faces
    v_0, f_0 = bevel_torso_corners(v_mat, faces, chamfer_m=0.0)
    assert len(f_0) == len(faces)

    # 1.5cm chamfer adds 24 faces (12 chamfer quads across 12 corner segments)
    v_bev, f_bev = bevel_torso_corners(v_mat, faces, chamfer_m=0.015)
    assert len(f_bev) > len(faces)
    assert len(v_bev) == len(v_mat)
    # Check that corner vertices were separated along X and Z
    assert np.any(np.abs(v_bev[:, [0, 2]] - v_mat[:, [0, 2]]) > 1e-4)


def test_character_model_head_z_offset():
    from src.clothing.customization import AvatarCustomization, BodyType

    # Male defaults to 0.0
    cust_male = AvatarCustomization(body_type=BodyType.MALE)
    model_m = CharacterModel(customization=cust_male, create_mesh=False)
    assert model_m.head_z_offset == pytest.approx(0.0)

    # Female defaults to 0.0 (anatomical posture baked into clean A-pose mesh)
    cust_fem = AvatarCustomization(body_type=BodyType.FEMALE)
    model_f = CharacterModel(customization=cust_fem, create_mesh=False)
    assert model_f.head_z_offset == pytest.approx(0.0)

    # Custom initial offset
    model_custom = CharacterModel(customization=cust_fem, head_z_offset=-0.030, create_mesh=False)
    assert model_custom.head_z_offset == pytest.approx(-0.030)

    # Set and reset methods
    model_f.set_head_z_offset(-0.050)
    assert model_f.head_z_offset == pytest.approx(-0.050)
    model_f.set_head_z_offset(0.0)
    assert model_f.head_z_offset == pytest.approx(0.0)

    model_f.reset_head_z_offset()
    assert model_f.head_z_offset == pytest.approx(0.0)

    model_m.set_head_z_offset(-0.020)
    assert model_m.head_z_offset == pytest.approx(-0.020)
    model_m.reset_head_z_offset()
    assert model_m.head_z_offset == pytest.approx(0.0)

    model_m.delete()
    model_f.delete()
    model_custom.delete()


def test_character_model_hair_offset_and_scale():
    from src.clothing.customization import AvatarCustomization, BodyType

    cust = AvatarCustomization(body_type=BodyType.MALE)
    model = CharacterModel(
        customization=cust,
        hair_offset_x=0.01,
        hair_offset_y=-0.02,
        hair_offset_z=0.03,
        hair_scale_x=1.1,
        hair_scale_y=1.2,
        hair_scale_z=1.05,
        create_mesh=False,
    )
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.01
    assert pytest.approx(model.hair_offset_y, 0.001) == -0.02
    assert pytest.approx(model.hair_offset_z, 0.001) == 0.03
    assert pytest.approx(model.hair_scale_x, 0.001) == 1.10
    assert pytest.approx(model.hair_scale_y, 0.001) == 1.20
    assert pytest.approx(model.hair_scale_z, 0.001) == 1.05

    # Test setter methods
    model.set_hair_offset(x=0.02, y=0.00, z=-0.01)
    assert pytest.approx(model.hair_offset_x, 0.001) == 0.02
    assert pytest.approx(model.hair_offset_y, 0.001) == 0.00
    assert pytest.approx(model.hair_offset_z, 0.001) == -0.01
    assert model.customization.hair_offset_x == model.hair_offset_x

    # Test uniform and per-axis scale
    model.set_hair_scale(1.15)
    assert pytest.approx(model.hair_scale_x, 0.001) == 1.15
    assert pytest.approx(model.hair_scale_y, 0.001) == 1.15
    assert pytest.approx(model.hair_scale_z, 0.001) == 1.15

    model.set_hair_scale(x=1.05, z=1.25)
    assert pytest.approx(model.hair_scale_x, 0.001) == 1.05
    assert pytest.approx(model.hair_scale_y, 0.001) == 1.15
    assert pytest.approx(model.hair_scale_z, 0.001) == 1.25

    # Test resets
    model.reset_hair_position()
    assert model.hair_offset_x == 0.0
    assert model.hair_offset_y == 0.0
    assert model.hair_offset_z == 0.0

    model.reset_hair_scale()
    assert model.hair_scale_x == 1.0
    assert model.hair_scale_y == 1.0
    assert model.hair_scale_z == 1.0

    model.delete()




