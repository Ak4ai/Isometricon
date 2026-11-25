import pytest

from src.editor.editor_hud import PANEL_HEIGHT, PANEL_WIDTH, fit_panel_scale


def test_panel_scales_down_to_fit_small_windows():
    scale = fit_panel_scale(1280, 720)
    assert scale < 1.0
    assert PANEL_HEIGHT * scale == pytest.approx(696)
    scale = fit_panel_scale(640, 480)
    assert 0.45 <= scale < 1.0
    assert PANEL_WIDTH * scale <= 640
    assert PANEL_HEIGHT * scale <= 480


def test_panel_scale_has_a_floor():
    assert fit_panel_scale(200, 150) == 0.45


def test_scaled_click_coordinates_convert_back_to_logical_panel():
    from src.editor.editor_hud import EditorHud
    hud = EditorHud.__new__(EditorHud)
    hud._scale = 0.5
    hud._panel_origin = (12.0, 12.0)
    # um alvo lógico em (100, 120) deve ser encontrado na tela em 12 + 50, 12 + 60
    assert hud.local_point(62.0, 72.0) == (100.0, 120.0)
    assert hud.local_point(12.0, 12.0) == (0.0, 0.0)
    assert hud.local_point(0.0, 0.0) is None


def test_editor_canvas_is_left_of_the_solid_sidebar():
    from src.editor.editor_hud import EditorHud
    hud = EditorHud.__new__(EditorHud)
    x, y, width, height = hud.canvas_rect(1280, 720)
    assert x == 12 and y == 12
    assert width > 500 and height == 696
    # o painel ocupa a direita; o canvas termina antes dele
    assert x + width < 1280


def test_editor_canvas_fits_small_window():
    from src.editor.editor_hud import EditorHud
    hud = EditorHud.__new__(EditorHud)
    x, y, width, height = hud.canvas_rect(640, 480)
    assert x > 0 and y > 0 and width > 0 and height > 0
    assert x + width < 640


def test_sidebar_matches_canvas_height_and_has_large_vertical_tool_buttons():
    from PIL import Image

    from src.editor.editor_hud import EditorHud, TOOLS, VALUE_BOX, WHEEL_BOX, WHEEL_SIZE

    hud = EditorHud.__new__(EditorHud)
    assert PANEL_HEIGHT * hud._fit_scale(1280, 720) == pytest.approx(696)

    hud._key = None
    hud.set_state("Editor", [], swatch=(255, 255, 255),
                  grid_size=(20, 18, 16), grid_spacing=2, light_enabled=True)
    tool_buttons = [hud._buttons[key] for key, _ in TOOLS]
    assert all(button[2] - button[0] == PANEL_WIDTH - 28 for button in tool_buttons)
    assert all(button[3] - button[1] >= 46 for button in tool_buttons)
    assert [button[1] for button in tool_buttons] == sorted(button[1] for button in tool_buttons)
    assert hud._wheel_box == WHEEL_BOX
    assert hud.hit_wheel(VALUE_BOX[0] + 10, VALUE_BOX[1] + 5)[0] == "value"
    previous_key = hud._key

    hud.set_state("Editor", [], swatch=(255, 255, 255),
                  grid_size=(20, 18, 16), grid_spacing=2, light_enabled=False)
    assert hud._key != previous_key

    thumb = Image.new("RGBA", (104, 104), (80, 90, 100, 255))
    hud.set_state("Editor", [], active_tab="textures", textures=[(0, "stone", thumb)],
                  filters=("Todas",), grid_size=(20, 18, 16), grid_spacing=2,
                  light_enabled=False)
    assert hud.hit_texture(42, 586) == 0
    assert hud.hit_search(30, 510)
    assert hud.hit_filter(30, 540) == "Todas"
    assert WHEEL_SIZE > 84
