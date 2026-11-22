from PIL import Image

from src.editor.color_wheel import hsv_at, hsv_to_hex, wheel_image


def test_wheel_image_is_transparent_outside_and_colorful_inside():
    image = wheel_image(48)
    assert isinstance(image, Image.Image)
    assert image.size == (48, 48)
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((24, 24))[3] == 255


def test_hsv_hit_testing():
    hue, saturation = hsv_at(80, 41.5, 84)  # à direita do centro
    assert abs(hue) < 0.02
    assert 0.85 < saturation <= 1.0
    center = hsv_at(41.5, 41.5, 84)
    assert center is not None and center[1] < 0.05
    assert hsv_at(0, 0, 84) is None


def test_hsv_to_hex():
    assert hsv_to_hex(0.0, 1.0, 1.0) == "ff0000"
    assert hsv_to_hex(0.0, 0.0, 1.0) == "ffffff"
