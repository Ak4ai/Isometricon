"""Cartões do modo apresentação: posição, tamanho em tela cheia e janela pequena, gráficos ao vivo."""
from PIL import Image

from src.interactive import presentation_card as card
from src.interactive.presentation_slides import SLIDES, Block, Panel

FULL_HD = (1920, 1080)


def _area(pieces):
    return [(x, y, x + im.width, y + im.height) for x, y, im in pieces]


def test_todos_os_slides_em_tela_cheia():
    for slide in SLIDES:
        pieces = card.render_slide(slide, 0, *FULL_HD, {"faces": (10, 60), "chunks": (3, 9)})
        assert len(pieces) == len(slide.panels)
        for x0, y0, x1, y1 in _area(pieces):
            # a imagem inclui a margem da sombra; o cartão em si fica dentro da tela
            assert x0 + card.SHADOW >= 0 and y0 + card.SHADOW >= 0, slide.title
            assert x1 - card.SHADOW <= FULL_HD[0] and y1 - card.SHADOW <= FULL_HD[1], slide.title


def test_cartoes_do_mesmo_slide_nao_se_sobrepoem():
    for slide in SLIDES:
        rects = [(x + card.SHADOW, y + card.SHADOW, x + im.width - card.SHADOW, y + im.height - card.SHADOW)
                 for x, y, im in card.render_slide(slide, 0, *FULL_HD, {"faces": (1, 2), "chunks": (1, 2)})]
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                overlap = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                assert not overlap, slide.title


def test_cartoes_sao_opacos_por_dentro():
    # nenhum gráfico ou imagem pode furar o pergaminho (a cena do jogo apareceria pelo buraco)
    for slide in SLIDES:
        for _, _, im in card.render_slide(slide, 0, *FULL_HD, {"faces": (1, 2), "chunks": (1, 2)}):
            m = card.SHADOW + 8
            for x in range(m, im.width - m, 7):
                for y in range(m, im.height - m, 7):
                    assert im.getpixel((x, y))[3] == 255, (slide.title, x, y)


def test_janela_pequena_nao_quebra():
    for slide in SLIDES:
        image = card.compose(slide, 0, 640, 360, {"faces": (0, 0), "chunks": (0, 0)})
        assert image.size == (640, 360)


def test_cartao_encolhe_ate_o_conteudo_e_respeita_o_anchor():
    small = Panel((0.5, 0.5, 0.4, 0.45), (Block("text", ("curto",)),), "T", anchor="bottom")
    x, y, im = card.render_panel(small, 0, *FULL_HD)
    assert im.height - 2 * card.SHADOW < 0.45 * FULL_HD[1] / 2
    assert y + im.height - card.SHADOW == int(0.95 * FULL_HD[1])


def test_pipeline_muda_com_passo_e_fica_em_linha_na_faixa():
    slide = SLIDES[3]
    a = card.compose(slide, 0, *FULL_HD)
    b = card.compose(slide, 4, *FULL_HD)
    assert a.tobytes() != b.tobytes()
    _, _, piece = card.render_slide(slide, 0, *FULL_HD)[0]
    assert piece.width > piece.height       # as cinco caixas lado a lado


def _slide(title):
    return next(s for s in SLIDES if s.title == title)


def test_grafico_de_faces_muda_com_os_numeros():
    slide = _slide("Mundo: malha e texturas")
    live_panels = [p for p in slide.panels if p.live]
    assert live_panels
    one = card.render_slide(slide, 0, *FULL_HD, {"faces": (100, 600)})
    two = card.render_slide(slide, 0, *FULL_HD, {"faces": (300, 600)})
    i = slide.panels.index(live_panels[0])
    assert one[i][2].tobytes() != two[i][2].tobytes()
    j = 1 - i
    assert one[j][2] is two[j][2]           # o cartão sem gráfico vem do cache, não é refeito


def test_grafico_sem_dados():
    image = card.compose(_slide("Otimizações"), 0, *FULL_HD, {"chunks": (0, 0)})
    assert image.size == FULL_HD


def test_regua_do_vertice():
    panel = next(p for s in SLIDES for p in s.panels if any(b.kind == "vertex" for b in p.blocks))
    _, _, image = card.render_panel(panel, 0, *FULL_HD)
    assert image.width > 300


def test_heightmap_oitavas_diferem():
    strip = card.heightmap_strip(1234)
    assert strip.width >= 3 * 96
    w = strip.width // 3
    parts = [strip.crop((i * w, 0, i * w + 90, 90)).tobytes() for i in range(3)]
    assert len(set(parts)) == 3


def test_rodape():
    assert isinstance(card.render_footer(6, 13, 1920), Image.Image)


def test_sem_fontes_do_windows(monkeypatch):
    monkeypatch.setattr(card, "FONT_CANDIDATES", ("nao/existe.ttf",))
    monkeypatch.setattr(card, "BOLD_CANDIDATES", ())
    card._font.cache_clear()
    card.render_panel.cache_clear()
    try:
        image = card.compose(_slide("Mundo: modelagem"), 0, 1024, 600)
        assert image.size == (1024, 600)
    finally:
        card._font.cache_clear()
        card.render_panel.cache_clear()


def test_etiquetas_quebram_linha_e_cabem_no_cartao():
    many = Panel((0.6, 0.1, 0.3, 0.8), (Block("tags", tuple(f"Recurso {i}" for i in range(14))),), "T")
    one = Panel((0.6, 0.1, 0.3, 0.8), (Block("tags", ("Recurso 0",)),), "T")
    _, _, tall = card.render_panel(many, 0, *FULL_HD)
    _, _, short = card.render_panel(one, 0, *FULL_HD)
    assert tall.height > short.height and tall.width == short.width
