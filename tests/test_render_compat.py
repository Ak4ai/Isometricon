from pathlib import Path

from src.rendering.shader import Shader

ROOT = Path(__file__).resolve().parents[1]


def test_world_shader_uses_arrays_and_has_macos_variant():
    source = (ROOT / "assets" / "shaders" / "world_textured.frag").read_text(encoding="utf-8")
    assert "sampler3D" not in source
    assert "sampler2DArray u_ShadowMask" in source
    assert "COMPAT_SUN_SHADOWS" in source
    assert "u_PointLightCount" in source


def test_shadow_samplers_have_unique_units():
    units = Shader.EXTRA_SAMPLER_UNITS
    values = list(units.values())
    assert len(values) == len(set(values))
    assert units["u_TextureAtlas"] == 0
    assert units["u_ShadowShapeIds"] not in (units["u_TextureAtlas"], units["u_ShadowMask"])


def test_shadow_renderers_upload_array_textures():
    for name in ("sun_shadows.py", "room_reveal.py"):
        source = (ROOT / "src" / "rendering" / name).read_text(encoding="utf-8")
        assert "GL_TEXTURE_2D_ARRAY" in source
        assert "GL_TEXTURE_3D" not in source
