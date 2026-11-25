"""Cartão do modo apresentação: imagem PIL do tamanho da janela, legível em qualquer tamanho."""
from PIL import Image

from src.interactive import presentation_card as card
from src.interactive.presentation_slides import SLIDES


def _inside(bounds):
    x, y, r, b = bounds
    return (x + r) // 2, y + 40


def test_bounds_center_e_right():
    x, y, r, b = card.card_bounds("center", 1000, 800)
    assert abs((x + r) / 2 - 500) <= 1 and abs((y + b) / 2 - 400) <= 1
    assert card.card_bounds("right", 1000, 800)[2] == 1000 - 32


def test_cartao_tem_tamanho_da_janela():
    for slide in SLIDES:
        image = card.render_card(slide, 0, 1280, 720)
        assert image.size == (1280, 720) and image.mode == "RGBA"
        point = (640, 360) if slide.scene.layout == "center" else _inside(card.card_bounds("right", 1280, 720))
        assert image.getpixel(point)[3] == 255


def test_cartao_janela_pequena():
    image = card.render_card(SLIDES[7], 0, 640, 360)
    assert image.size == (640, 360)
    assert image.getpixel((2, 2))[3] == 0


def test_pipeline_muda_com_passo():
    a = card.render_card(SLIDES[3], 0, 1280, 720)
    b = card.render_card(SLIDES[3], 4, 1280, 720)
    assert a.tobytes() != b.tobytes()


def test_heightmap_oitavas_diferem():
    strip = card.heightmap_strip(1234)
    assert strip.width >= 3 * 96
    w = strip.width // 3
    parts = [strip.crop((i * w, 0, i * w + 90, 90)).tobytes() for i in range(3)]
    assert len(set(parts)) == 3


def test_rodape_zero_de_zero():
    image = card.render_footer(0, 13, {"faces": (0, 0)}, 800)
    assert isinstance(image, Image.Image) and image.width == 800


def test_sem_fontes_do_windows(monkeypatch):
    monkeypatch.setattr(card, "FONT_CANDIDATES", ("nao/existe.ttf",))
    card._font.cache_clear()
    card.render_card.cache_clear()
    try:
        image = card.render_card(SLIDES[5], 0, 1024, 600)
        assert image.size == (1024, 600)
    finally:
        card._font.cache_clear()
        card.render_card.cache_clear()
