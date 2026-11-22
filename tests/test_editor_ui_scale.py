from src.editor.editor_hud import PANEL_HEIGHT, PANEL_WIDTH, fit_panel_scale


def test_panel_scales_down_to_fit_small_windows():
    assert fit_panel_scale(1280, 720) == 1.0
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
