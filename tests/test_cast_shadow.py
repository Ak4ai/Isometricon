"""A sombra dos personagens: a câmera do sol do mapa de sombra (sem OpenGL)."""
import numpy as np

from src.rendering.cast_shadow import CLIP_TO_TEXTURE, DEPTH, CharacterShadowMap, sun_camera

SUN = (0.55, 0.26, 0.7)


def to_map(point, center=(0.0, 9.0, 0.0)):
    p = CLIP_TO_TEXTURE @ sun_camera(center, SUN) @ np.array([*point, 1.0])
    return p[:3] / p[3]


def test_a_point_and_what_shades_it_fall_on_the_same_texel():
    sun = np.array(SUN) / np.linalg.norm(SUN)
    ground = np.array([1.0, 9.0, -2.0])
    head = ground + sun * 6.0                     # no raio do sol, seis blocos acima do chão
    a, b = to_map(ground), to_map(head)
    assert np.allclose(a[:2], b[:2], atol=1e-5)   # o mesmo lugar do mapa
    assert b[2] < a[2]                            # e a cabeça, mais perto do sol, tapa o chão
    assert np.isclose((a[2] - b[2]) * (DEPTH - 0.5), 6.0, atol=1e-3)   # a diferença, em blocos, é a distância


def test_the_map_covers_the_area_around_the_player():
    for point in ((0.0, 9.0, 0.0), (20.0, 9.0, 0.0), (0.0, 4.0, -20.0)):
        c = to_map(point)
        assert np.all(c >= 0.0) and np.all(c <= 1.0), point
    assert np.any(to_map((60.0, 9.0, 0.0)) > 1.0) or np.any(to_map((60.0, 9.0, 0.0)) < 0.0)


def test_without_characters_nothing_is_drawn_and_the_shadow_is_off():
    class FakeShader:
        def __init__(self):
            self.values = {}

        def set_float(self, name, value):
            self.values[name] = value

    shader = FakeShader()
    shadows = CharacterShadowMap()
    shadows.render(shader, (0.0, 9.0, 0.0), SUN, [])
    shadows.apply(shader)
    assert shadows.fbo == 0 and shader.values["u_CharShadowStrength"] == 0.0
