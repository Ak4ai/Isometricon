import pytest

from src.rendering import hud_quad


@pytest.mark.parametrize(("width", "height"), [(0, 0), (0, 720), (1280, 0)])
def test_draw_skips_nonpositive_viewports_before_using_opengl(monkeypatch, width, height):
    quad = hud_quad.HudQuad.__new__(hud_quad.HudQuad)
    quad.size = (16, 16)
    monkeypatch.setattr(
        hud_quad.gl,
        "glEnable",
        lambda *_: pytest.fail("A viewport without area must not issue OpenGL calls."),
    )

    quad.draw(0, 0, width, height, size=(16, 16))
