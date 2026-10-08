"""A tela de criação de personagem: o que lista, onde clica e o que cada gesto faz (sem OpenGL)."""
from types import SimpleNamespace

import numpy as np

from src.interactive.character_editor import PANEL_WIDTH, CharacterEditor, catalog
from src.interactive.skin_commands import SkinCommandHandler

LEFT, PRESS, RELEASE = 0, 1, 0
ESCAPE, SPACE = 256, 32
SIZE = (1280, 720)


def make_editor(**model):
    sent = []
    handler = SimpleNamespace(character_model=SimpleNamespace(body="female", customization=None, **model), busy_status="",
                              execute=lambda command: (sent.append(command), (True, "feito", (0, 0, 0)))[1])
    editor = CharacterEditor(handler, {"active": False, "yaw": 0.0}, create_gl=False)
    editor.open()
    editor.layout(*SIZE)
    return editor, sent


def centre(rect):
    return (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2


def click(editor, x, y, shift=False):
    used = editor.handle_mouse_button(x, y, LEFT, PRESS, shift)
    editor.handle_mouse_button(x, y, LEFT, RELEASE, shift)
    return used


def touch(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_catalog_sorts_items_by_asset_type_and_pairs_the_shoes(tmp_path):
    clothing, models = tmp_path / "clothing", tmp_path / "models"
    for name in ("Knit_Sweater_111111", "Zip_Jacket_222222", "Baggy_Jeans_333333", "Long_Dress_444444",
                 "Fur_Boots_-_Left_Shoe_Accessory_555555", "Fur_Boots_-_Right_Shoe_Accessory_666666",
                 "Black_Flowy_Pigtails_777777", "Lonely_-_Left_Shoe_Accessory_888888", "Mystery_Thing_999999"):
        touch(clothing / f"{name}.rbxm")
    touch(clothing / "Knit_Sweater_111111.png")
    for asset, asset_type, body in ((111111, 68, "female"), (222222, 67, "male"), (333333, 66, "female"),
                                    (444444, 72, "female"), (555555, 70, "female"), (666666, 71, "female")):
        touch(models / f"character_native_{asset}_{body}.obj", f"# header\n# asset_type {asset_type}\n")
    found = catalog(str(clothing), str(models))
    assert [i.asset_id for i in found["top"]] == ["111111"]
    assert found["top"][0].name == "Knit Sweater" and found["top"][0].image.endswith("Knit_Sweater_111111.png")
    assert [i.asset_id for i in found["jacket"]] == ["222222"]   # fitted on the other body only
    assert [i.asset_id for i in found["bottom"]] == ["333333"]
    assert [i.asset_id for i in found["dress"]] == ["444444"]
    assert [(i.asset_id, i.name) for i in found["shoes"]] == [("555555,666666", "Fur Boots")]  # the lone left shoe is left out
    assert [i.asset_id for i in found["hair"]] == ["777777"]     # never fitted: told by its name
    assert [i.asset_id for i in found["other"]] == ["999999"]


def test_a_click_on_an_option_runs_its_chat_command():
    editor, sent = make_editor()
    option = next(payload for _, kind, payload in editor.layout(*SIZE) if kind == "option" and payload.label == "Masculino")
    rect = next(rect for rect, kind, payload in editor.layout(*SIZE) if payload is option)
    assert click(editor, *centre(rect))
    assert sent == ["/skin corpo masculino"]
    assert editor.message == "feito"


def test_tabs_change_section_and_the_wheel_scrolls_only_over_the_panel():
    editor, _ = make_editor()
    titles = [section.title for section in editor.sections]
    assert titles[:7] == ["Corpo", "Ajustes", "Olhos", "Rosto", "Nariz", "Maquiagem", "Cabelo"] and "Superior" in titles and "Extras" in titles
    labels = lambda: [option.label for group in editor.groups() for option in group.options]   # the whole section, scrolled or not
    for title, expected in (("Rosto", ("Sorriso", "Altura das sobrancelhas")), ("Nariz", ("Narinas grandes", "Bloco", "Largura da ponte")),
                            ("Olhos", ("Azul", "Arredondado", "Altura dos olhos"))):
        rect = next(rect for rect, kind, payload in editor.layout(*SIZE) if kind == "tab" and payload == titles.index(title))
        click(editor, *centre(rect))
        assert editor.active == titles.index(title) and set(expected) <= set(labels())
    assert "Altura das sobrancelhas" not in labels()                                            # the eyebrows are not in with the eyes
    editor.layout(*SIZE)
    assert editor.handle_scroll(PANEL_WIDTH + 50, -1.0) is False  # over the character: the camera zooms
    assert editor.handle_scroll(50, -1.0) is True                 # over the panel: the grid scrolls
    assert editor.scroll > 0
    editor.select_section(0)
    editor.layout(*SIZE)
    assert editor.handle_scroll(50, -1.0) is True and editor.scroll == 0  # a short section has nothing to scroll


def test_a_long_grid_scrolls_and_stops_at_its_end():
    editor, _ = make_editor()
    editor._catalog = {"top": [SimpleNamespace(asset_id=str(k), name=f"Peça {k}", image=None) for k in range(40)]}
    editor.select_section([s.title for s in editor.sections].index("Superior"))
    editor.layout(*SIZE)
    first = [payload.label for _, kind, payload in editor._hits if kind == "option"]
    assert first[0] == "Nenhum" and "Peça 39" not in first
    for _ in range(200):
        editor.handle_scroll(50, -1.0)
    editor.layout(*SIZE)
    last = [payload.label for _, kind, payload in editor._hits if kind == "option"]
    assert "Peça 39" in last and "Nenhum" not in last
    assert editor.scroll == editor._max_scroll()


def test_the_worn_garment_is_marked_as_selected():
    editor, _ = make_editor(top_id=42, bottom_id=None)
    editor._catalog = {"top": [SimpleNamespace(asset_id="42", name="Suéter", image=None)]}
    editor.select_section([s.title for s in editor.sections].index("Superior"))
    chosen = {o.label: o.selected(editor.model) for g in editor.groups() for o in g.options}
    assert chosen == {"Nenhum": False, "Suéter": True}


def test_dragging_beside_the_panel_turns_the_character_and_pauses_the_spin():
    editor, _ = make_editor()
    editor.turntable["active"] = True
    assert editor.handle_mouse_button(800, 300, LEFT, PRESS)
    editor.handle_cursor(900, 300)
    assert editor.turntable["yaw"] > 0
    turned = editor.turntable["yaw"]
    editor.update(1.0)
    assert editor.turntable["yaw"] == turned       # no spinning while it is held
    editor.handle_mouse_button(900, 300, LEFT, RELEASE)
    editor.update(1.0)
    assert editor.turntable["yaw"] != turned       # it spins again once let go
    assert not editor.handle_mouse_button(800, 300, LEFT, PRESS, shift=True)  # Shift + drag stays the camera pan


def test_dragging_up_and_down_tilts_the_camera_within_its_limits():
    editor, _ = make_editor()
    editor.turntable["pitch"] = 30.0
    editor.handle_mouse_button(800, 300, LEFT, PRESS)
    editor.handle_cursor(800, 400)
    assert editor.turntable["pitch"] > 30.0 and editor.turntable["yaw"] == 0.0  # straight down: tilt only
    editor.handle_cursor(800, 5000)
    assert editor.turntable["pitch"] == 80.0
    editor.handle_cursor(800, -5000)
    assert editor.turntable["pitch"] == -20.0
    editor.handle_mouse_button(800, -5000, LEFT, RELEASE)
    editor.handle_cursor(800, 300)
    assert editor.turntable["pitch"] == -20.0  # not held: moving the mouse changes nothing


def test_escape_and_the_done_button_close_the_editor_and_space_toggles_the_spin():
    editor, _ = make_editor()
    assert editor.handle_key(SPACE, PRESS) and editor.turntable["active"] is False
    rect = next(rect for rect, kind, payload in editor.layout(*SIZE) if payload == "done")
    click(editor, *centre(rect))
    assert editor.is_open is False
    assert editor.handle_key(ESCAPE, PRESS) is False  # closed: the key goes on to the game
    editor.open()
    assert editor.handle_key(ESCAPE, PRESS) and editor.is_open is False


def test_the_panel_image_is_drawn_for_every_section():
    editor, _ = make_editor()
    for index in range(len(editor.sections)):
        editor.select_section(index)
        panel = editor.image(*SIZE)
        assert panel.size == (PANEL_WIDTH, SIZE[1])


def test_skin_interface_asks_the_main_loop_to_open_the_editor():
    handler = SkinCommandHandler(character_model=SimpleNamespace())
    ok, feedback, _ = handler.execute("/skin interface")
    assert ok and handler.editor_requested is True
    assert SkinCommandHandler(character_model=None).execute("/skin interface")[0] is False


def test_the_field_takes_the_keyboard_and_enter_wears_the_item():
    editor, sent = make_editor()
    editor.clipboard = lambda: " https://www.roblox.com/catalog/123456/Some-Shirt \n"
    rect = next(rect for rect, kind, _ in editor.layout(*SIZE) if kind == "field")
    assert editor.handle_char(ord("a")) is False            # not typing yet: the key is the game's
    click(editor, *centre(rect))
    assert editor.typing
    for letter in "12x":
        assert editor.handle_char(ord(letter))
    assert editor.handle_key(259, PRESS)                     # Backspace
    assert editor.entry == "12"
    assert editor.handle_key(SPACE, PRESS) and editor.turntable["active"] is True  # typed keys do not act on the game
    editor.handle_key(259, PRESS), editor.handle_key(259, PRESS)
    assert editor.handle_key(86, PRESS, mods=2)              # Ctrl+V
    assert editor.entry == "https://www.roblox.com/catalog/123456/Some-Shirt"
    assert editor.handle_key(257, PRESS)                     # Enter
    assert sent == ["/skin vestir https://www.roblox.com/catalog/123456/Some-Shirt"]
    assert editor.typing is False and editor.entry == ""


def test_escape_leaves_the_field_before_it_closes_the_editor():
    editor, sent = make_editor()
    rect = next(rect for rect, kind, _ in editor.layout(*SIZE) if kind == "field")
    click(editor, *centre(rect))
    editor.handle_char(ord("9"))
    assert editor.handle_key(ESCAPE, PRESS) and editor.is_open and not editor.typing and editor.entry == ""
    assert sent == []
    assert editor.handle_key(ESCAPE, PRESS) and editor.is_open is False


def slider_rect(editor, section, label):
    """The whole tile of a slider, scrolling the grid down until it is all in view."""
    editor.select_section([s.title for s in editor.sections].index(section))
    for _ in range(60):
        for rect, kind, payload in editor.layout(*SIZE):
            if kind == "option" and payload.label == label and rect[3] - rect[1] >= 46:
                return rect
        editor.handle_scroll(50, -1.0)
    raise AssertionError(f"no slider {label!r} in {section!r}")


def test_dragging_a_body_slider_sends_the_adjustment_as_it_moves():
    editor, sent = make_editor()
    x0, y0, x1, y1 = slider_rect(editor, "Ajustes", "Altura")
    y = (y0 + y1) / 2
    editor.handle_mouse_button(x1 - 10, y, LEFT, PRESS)        # the right end of the track
    assert sent[-1] == "/skin ajuste altura 100"
    editor.handle_cursor(x0 + 10, y)                           # dragged to the left end
    assert sent[-1] == "/skin ajuste altura -100"
    editor.handle_cursor((x0 + x1) / 2 + 2, y)                 # near the middle: back to 0
    assert sent[-1] == "/skin ajuste altura 0"
    editor.handle_mouse_button((x0 + x1) / 2, y, LEFT, RELEASE)
    before = len(sent)
    editor.handle_cursor(x1, y)                                # let go: the mouse no longer moves it
    assert len(sent) == before


def test_a_face_slider_redraws_a_few_times_a_second_and_takes_the_last_value(monkeypatch):
    import src.interactive.character_editor as module
    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    editor, sent = make_editor()
    x0, y0, x1, y1 = slider_rect(editor, "Olhos", "Tamanho dos olhos")
    y = (y0 + y1) / 2
    editor.handle_mouse_button(x1 - 10, y, LEFT, PRESS)
    assert sent == ["/skin ajuste olhos_tamanho 100"]
    editor.handle_cursor(x1 - 40, y)                          # right after: the face is not drawn again yet
    assert len(sent) == 1
    clock[0] += 0.2
    editor.handle_cursor(x1 - 60, y)                          # later: it follows the mouse
    assert len(sent) == 2
    editor.handle_cursor(x1 - 80, y)
    editor.handle_mouse_button(x1 - 80, y, LEFT, RELEASE)      # let go: the value it was left at
    assert len(sent) == 3 and sent[-1] != sent[-2]


def test_makeup_and_extra_garments_are_chosen_from_their_sections():
    editor, sent = make_editor(extra_ids=[42])
    editor._catalog = {"bottom": [SimpleNamespace(asset_id="42", name="Polainas", image=None),
                                  SimpleNamespace(asset_id="43", name="Cinto", image=None)]}
    editor.select_section([s.title for s in editor.sections].index("Extras"))
    chosen = {o.label: o.selected(editor.model) for g in editor.groups() for o in g.options}
    assert chosen == {"Nenhuma peça extra": False, "Polainas": True, "Cinto": False}
    cinto = next(o for g in editor.groups() for o in g.options if o.label == "Cinto")
    editor.choose(cinto)
    assert sent[-1] == "/skin extra 43"
    editor.select_section([s.title for s in editor.sections].index("Maquiagem"))
    commands = {o.label: o.command for g in editor.groups() for o in g.options}
    assert commands["Vermelho"] == "/skin maquiagem blush vermelho" and commands["Sem maquiagem"] == "/skin maquiagem sem"
    assert commands["Sem blush"] == "/skin maquiagem blush sem" and commands["Sem sombra"] == "/skin maquiagem sombra sem"
    editor.select_section(0)
    assert "Vitiligo (quantidade)" in [o.label for g in editor.groups() for o in g.options]


def test_the_face_sections_ask_the_camera_for_the_face():
    editor, _ = make_editor()
    titles = [s.title for s in editor.sections]
    focus = {}
    for index, title in enumerate(titles):
        editor.select_section(index)
        focus[title] = editor.focus
    assert focus["Rosto"] == focus["Maquiagem"] == "face"
    assert {t for t, f in focus.items() if f == "face"} == {"Olhos", "Rosto", "Nariz", "Maquiagem"}   # every other section shows the body


def test_the_eyebrows_are_adjusted_apart_from_the_eyes():
    from src.clothing.customization import AvatarCustomization, HeadAtlasBuilder
    builder = HeadAtlasBuilder()
    atlas = lambda **adjust: np.array(builder.build_atlas(AvatarCustomization(body_adjust=adjust)).convert("RGB"), dtype=int)
    plain = atlas()
    brows, eyes = (slice(95, 122), slice(0, 256)), (slice(125, 185), slice(0, 256))   # the face of the atlas: eyebrows over eyes
    moved_eyes = atlas(olhos_distancia=1.0)
    assert (moved_eyes[eyes] != plain[eyes]).any() and (moved_eyes[brows] == plain[brows]).all()
    for name in ("sobrancelha_tamanho", "sobrancelha_altura", "sobrancelha_distancia"):
        moved = atlas(**{name: 1.0})
        assert (moved[:125, :256] != plain[:125, :256]).any(), name                    # the eyebrows change
        assert (moved[135:185, :256] == plain[135:185, :256]).all(), name             # and the eyes stay where they were
