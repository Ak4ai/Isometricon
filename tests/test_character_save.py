"""O personagem gravado em disco volta igual."""
from types import SimpleNamespace

from src.clothing import character_save
from src.clothing.customization import AvatarCustomization, BodyType, EyeStyle, HairColor, HairStyle, IrisColor
from src.interactive.skin_commands import SkinCommandHandler


def make_model():
    custom = AvatarCustomization(body_type=BodyType.FEMALE, hair_style=HairStyle.BUZZ_CUT, hair_color=HairColor.PINK,
                                 skin_color_rgb=(0.4, 0.28, 0.22), eye_style=EyeStyle.CLASSIC, iris_color=IrisColor.GREEN,
                                 custom_hair_obj="C:/somewhere/fitted_hair.obj")
    reloads = []
    return SimpleNamespace(customization=custom, top_id=111, bottom_id=None, outer_top_id=222, shoes_id="5,6",
                           hair_id="777", tool_id=None, extra_ids=[12550912577], hair_offset_x=0.01, hair_offset_y=-0.02, hair_offset_z=0.0,
                           hair_scale_x=1.1, hair_scale_y=1.0, hair_scale_z=0.9, async_loading=True,
                           reload=lambda: reloads.append(1), reloads=reloads)


def test_a_saved_character_comes_back_the_same(tmp_path):
    model, path = make_model(), str(tmp_path / "saves" / "personagem.json")
    character_save.save(model, path)
    data = character_save.load(path)
    arguments = character_save.model_arguments(data)
    custom = arguments.pop("customization")
    assert arguments == dict(top_id=111, bottom_id=None, outer_top_id=222, shoes_id="5,6", hair_id="777", tool_id=None,
                             extra_ids=[12550912577])
    assert custom.body_type is BodyType.FEMALE and custom.hair_style is HairStyle.BUZZ_CUT
    assert custom.hair_color is HairColor.PINK and custom.iris_color is IrisColor.GREEN
    assert custom.skin_color_rgb == (0.4, 0.28, 0.22)
    assert (custom.hair_offset_x, custom.hair_scale_z) == (0.01, 0.9)
    assert custom.custom_hair_obj is None  # a path of this body's cache is found again, not saved


def test_a_missing_or_broken_save_is_no_character(tmp_path):
    assert character_save.load(str(tmp_path / "nothing.json")) is None
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    assert character_save.load(str(broken)) is None
    broken.write_text('{"outro": 1}', encoding="utf-8")
    assert character_save.load(str(broken)) is None


def test_the_command_line_can_choose_the_character_instead_of_the_save():
    assert character_save.wanted(["--terrain", "--editor"])
    assert not character_save.wanted(["--terrain", "--novo"])
    assert not character_save.wanted(["--char", "--top", "sweater"])
    assert not character_save.wanted(["--char", "--hair-color=pink"])


def test_skin_salvar_and_carregar_write_and_restore_the_character(tmp_path):
    model = make_model()
    handler = SkinCommandHandler(character_model=model)
    handler.save_path = str(tmp_path / "personagem.json")
    assert handler.execute("/skin carregar")[0] is False  # nothing saved yet
    assert handler.execute("/skin salvar")[0] is True
    model.top_id, model.customization.hair_color = 999, HairColor.BLACK
    assert handler.execute("/skin carregar")[0] is True
    assert model.top_id == 111 and model.customization.hair_color is HairColor.PINK
    assert model.hair_scale_x == 1.1 and model.reloads


def test_skin_extra_wears_and_removes_a_garment_beside_the_others():
    model = make_model()
    model.extra_ids = []
    handler = SkinCommandHandler(character_model=model)
    assert handler.execute("/skin extra 12550912577")[0] and model.extra_ids == [12550912577]
    assert handler.execute("/skin extra 13863832652")[0] and model.extra_ids == [12550912577, 13863832652]
    assert handler.execute("/skin extra 12550912577")[0] and model.extra_ids == [13863832652]   # again: taken off
    assert handler.execute("/skin extra coisa_que_nao_existe")[0] is False
    assert handler.execute("/skin extra none")[0] and model.extra_ids == [] and len(model.reloads) == 4
