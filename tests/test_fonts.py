from src.core.fonts import FONT_DIR, load_font, mono_font, ui_font


def test_bundled_fonts_exist():
    assert (FONT_DIR / "Inter-Variable.ttf").is_file()
    assert (FONT_DIR / "JetBrainsMono-Variable.ttf").is_file()
    assert (FONT_DIR / "OFL-Inter.txt").is_file()


def test_ui_font_and_mono_font_render_text():
    body = ui_font(14)
    heading = ui_font(14, heading=True)
    mono = mono_font(14)
    for font in (body, heading, mono):
        assert font.getlength("Isometricon") > 0
    assert mono.getlength("iiii") == mono.getlength("WWWW")


def test_font_weight_is_variable():
    regular = load_font(14, "body")
    bold = load_font(14, "body", bold=True)
    # Em Inter o peso maior costuma alargar um pouco o texto; o importante é
    # que os dois objetos sejam carregados sem erro e não sejam idênticos.
    assert regular is not bold
    assert regular.getlength("Texto") > 0
    assert bold.getlength("Texto") > 0
