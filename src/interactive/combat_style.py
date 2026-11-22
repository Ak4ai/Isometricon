"""O visual do combate no mesmo vocabulário das telas de entrada e de configurações.

Pergaminho (``menu_style.paper``) com borda dourada e cantos de metal, títulos em Georgia e texto em Segoe UI,
tinta verde-escura, o verde do botão "Continuar aventura" para quem está agindo e o dourado dos botões principais.
As cores vivas do registro (feitas para fundo escuro) viram tinta legível no papel com ``ink``.
"""

from __future__ import annotations

import colorsys
from functools import lru_cache
from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter

from src.core.fonts import ui_font
from src.interactive.menu_style import paper

Color = Tuple[int, int, int]

# a paleta das telas (game_menus / menu_style)
INK = (41, 62, 52)            # #293E34
MUTED = (107, 113, 96)        # #6B7160
CARD = (251, 244, 228)        # #FBF4E4
LINE = (207, 197, 171)        # #CFC5AB
BORDER = (186, 163, 115)      # #BAA373
INNER = (212, 197, 164)       # #D4C5A4
METAL = (160, 126, 63)        # #A07E3F
METAL_LIGHT = (196, 162, 93)  # #C4A25D
GOLD = (231, 182, 94)         # #E7B65E
GOLD_BUTTON = (213, 170, 82)  # #D5AA52
GOLD_DARK = (138, 98, 30)     # o dourado como tinta no papel
FOREST = (41, 79, 64)         # #294F40, o botão escuro
CREAM = (251, 244, 228)
BUTTON = (248, 240, 223)      # #F8F0DF
BUTTON_EDGE = (199, 182, 141)  # #C7B68D
BUTTON_SHADOW = (176, 152, 110)  # #B0986E
DISABLED = (236, 228, 210)
DANGER = (145, 70, 52)        # #914634
ALLY_INK = (46, 112, 60)
FOE_INK = (160, 52, 40)
TRACK = (217, 205, 176)

HP_GOOD, HP_MID, HP_LOW = (78, 138, 85), (201, 149, 47), (168, 69, 47)


@lru_cache(maxsize=64)
def font(size: int, heading: bool = False, bold: bool = False):
    return ui_font(size, heading=heading, bold=bold)


def measure(text: str, size: int, heading: bool = False, bold: bool = False) -> int:
    if not text:
        return 0
    return int(round(font(size, heading, bold).getlength(text)))


def text_size(size: int, heading: bool = False) -> int:
    """A altura de uma linha (do topo das maiúsculas à base das descendentes)."""
    f = font(size, heading)
    return f.getbbox("ÁgjpqyÇ")[3] - f.getbbox("ÁgjpqyÇ")[1]


def write(draw: ImageDraw.ImageDraw, xy, text: str, size: int, color, heading: bool = False, bold: bool = False,
          stroke: int = 0, stroke_color=INK) -> int:
    """Escreve com o topo do texto em ``xy[1]`` (não na linha de base); devolve a largura."""
    f = font(size, heading, bold)
    top = f.getbbox("Á")[1]
    fill = color if len(color) == 4 else (*color, 255)
    draw.text((xy[0], xy[1] - top), text, font=f, fill=fill, stroke_width=stroke,
              stroke_fill=stroke_color if len(stroke_color) == 4 else (*stroke_color, 255))
    return int(round(f.getlength(text)))


def fit(text: str, size: int, width: int, heading: bool = False, bold: bool = False) -> str:
    """O texto cortado com reticências para caber em ``width``."""
    if measure(text, size, heading, bold) <= width:
        return text
    while text and measure(text + "…", size, heading, bold) > width:
        text = text[:-1]
    return text + "…"


def ink(color: Sequence[int]) -> Color:
    """Uma cor viva (pensada para fundo escuro) como tinta legível no pergaminho: mesmo matiz, mais escura."""
    r, g, b = (c / 255.0 for c in color[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.18:                     # cinzas e brancos: tinta da tela ou o cinza esverdeado das legendas
        return INK if v > 0.75 else MUTED
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * 1.05 + 0.1), 0.5 if 0.1 < h < 0.5 else 0.6)
    return int(r * 255), int(g * 255), int(b * 255)


def hp_color(ratio: float) -> Color:
    return HP_GOOD if ratio > 0.5 else (HP_MID if ratio > 0.25 else HP_LOW)


# ------------------------------------------------------------------------------------------------ superfícies

def _shadow(size, box, radius: int, blur: int, alpha: int) -> Image.Image:
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle(box, radius, fill=(4, 18, 14, alpha))
    return shade.filter(ImageFilter.GaussianBlur(blur))


def card(width: int, height: int, radius: int = 10, dark: bool = False, corners: bool = True,
         outline: Optional[Color] = None, shadow: bool = True) -> Tuple[Image.Image, int]:
    """Um cartão de pergaminho (ou verde, ``dark``) com sombra; devolve a imagem e a margem da sombra."""
    pad = 8 if shadow else 0
    image = Image.new("RGBA", (width + 2 * pad, height + 2 * pad + (4 if shadow else 0)), (0, 0, 0, 0))
    if shadow:
        image.alpha_composite(_shadow(image.size, (pad - 1, pad + 4, pad + width, pad + height + 4), radius, 5, 120))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=255)
    if dark:
        surface = Image.new("RGBA", (width, height), (*FOREST, 255))
    else:
        sheet = paper(640, 480) if width <= 640 and height <= 480 else paper(width, height)   # um papel só, recortado
        surface = sheet.crop((0, 0, width, height))
    image.paste(surface, (pad, pad), mask)
    d = ImageDraw.Draw(image)
    x0, y0, x1, y1 = pad, pad, pad + width - 1, pad + height - 1
    d.rounded_rectangle((x0, y0, x1, y1), radius, outline=(*(outline or (METAL if dark else BORDER)), 255),
                        width=2)
    if corners and width > 60 and height > 44:
        d.rounded_rectangle((x0 + 5, y0 + 5, x1 - 5, y1 - 5), max(2, radius - 4),
                            outline=(*((70, 105, 88) if dark else INNER), 255))
        arm = 10 if min(width, height) < 120 else 14
        for cx, cy, dx, dy in ((x0 + 10, y0 + 10, 1, 1), (x1 - 10, y0 + 10, -1, 1), (x0 + 10, y1 - 10, 1, -1),
                               (x1 - 10, y1 - 10, -1, -1)):
            d.line((cx, cy + arm * dy, cx, cy, cx + arm * dx, cy), fill=(*METAL, 255), width=2)
            d.polygon([(cx + 4 * dx, cy + 7 * dy), (cx + 7 * dx, cy + 4 * dy), (cx + 10 * dx, cy + 7 * dy),
                       (cx + 7 * dx, cy + 10 * dy)], fill=(*METAL_LIGHT, 255))
    return image, pad


def button(draw: ImageDraw.ImageDraw, box, enabled: bool = True, primary: bool = False, radius: int = 7) -> None:
    """Um botão em relevo como os das telas (sombra embaixo, brilho em cima, filete dourado à esquerda)."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle((x0, y0 + 3, x1, y1 + 3), radius, fill=(*(BUTTON_SHADOW if enabled else LINE), 255))
    fill = GOLD_BUTTON if primary else (BUTTON if enabled else DISABLED)
    draw.rounded_rectangle((x0, y0, x1, y1), radius, fill=(*fill, 255),
                           outline=(*((161, 122, 52) if primary else BUTTON_EDGE), 255), width=1)
    if enabled:
        draw.line((x0 + 8, y0 + 2, x1 - 8, y0 + 2), fill=(248, 222, 165, 255) if primary else (255, 252, 243, 255))


def bar(draw: ImageDraw.ImageDraw, box, ratio: float, color: Optional[Color] = None, temp_ratio: float = 0.0,
        track: Color = TRACK) -> None:
    """A barra de vida arredondada (a vida temporária é um filete dourado por cima)."""
    x0, y0, x1, y1 = box
    r = (y1 - y0) // 2
    draw.rounded_rectangle(box, r, fill=(*track, 255))
    ratio = max(0.0, min(1.0, ratio))
    if ratio > 0:
        right = x0 + max(2 * r, int(round((x1 - x0) * ratio)))
        draw.rounded_rectangle((x0, y0, right, y1), r, fill=(*(color or hp_color(ratio)), 255))
    temp = max(0.0, min(1.0, temp_ratio))
    if temp > 0:
        draw.rounded_rectangle((x0, y0, x0 + max(2 * r, int((x1 - x0) * temp)), y0 + max(2, r - 1)), r,
                               fill=(*GOLD, 255))


def badge(draw: ImageDraw.ImageDraw, x: int, y: int, key: str, enabled: bool = True, size: int = 22) -> None:
    """A tecla da opção: um quadrado dourado com o número."""
    draw.rounded_rectangle((x, y, x + size, y + size), 5, fill=(*(GOLD if enabled else LINE), 255),
                           outline=(*((161, 122, 52) if enabled else BUTTON_EDGE), 255))
    fs = max(9, round(size * 0.6))
    w = measure(key, fs, bold=True)
    write(draw, (x + (size - w) / 2, y + (size - fs * 0.72) / 2 - 1), key, fs, INK if enabled else MUTED, bold=True)


# ------------------------------------------------------------------------------------------------ ícones das ações

def action_icon(draw: ImageDraw.ImageDraw, kind: str, x: float, y: float, size: float = 28,
                enabled: bool = True) -> None:
    """O ícone de uma ação do combate, no traço dos ícones das telas (``menu_style.icon``), num quadrado de
    ``size`` com o canto em (x, y). Apagado (cinza) quando a ação não pode agora."""
    line_c = (*(INK if enabled else (150, 150, 135)), 255)

    def tone(color):
        return (*(color if enabled else (205, 200, 185)), 255)

    def P(a, b):
        return (x + a * size, y + b * size)

    def pts(values):
        return [P(a, b) for a, b in values]

    def line(values, width=2):
        draw.line(pts(values), fill=line_c, width=width, joint="curve")

    def flask(liquid, plus=False):
        draw.ellipse((*P(.2, .38), *P(.8, .95)), fill=tone(liquid), outline=line_c, width=2)
        draw.rectangle((*P(.4, .12), *P(.6, .42)), fill=tone(CARD), outline=line_c, width=2)
        draw.rectangle((*P(.35, .06), *P(.65, .14)), fill=tone(METAL_LIGHT), outline=line_c)
        draw.ellipse((*P(.3, .52), *P(.42, .64)), fill=(255, 255, 255, 150 if enabled else 60))
        if plus:
            line([(.5, .58), (.5, .84)], 2)
            line([(.37, .71), (.63, .71)], 2)

    def shield(fill, cross=False):
        outline = [(.5, .06), (.88, .2), (.82, .6), (.5, .94), (.18, .6), (.12, .2)]
        draw.polygon(pts(outline), fill=tone(fill), outline=line_c)
        draw.line(pts(outline + [outline[0]]), fill=line_c, width=2, joint="curve")
        if cross:
            line([(.5, .24), (.5, .74)], 3)
            line([(.32, .42), (.68, .42)], 3)
        else:
            line([(.5, .16), (.5, .82)], 1)

    def blade(x0, y0, x1, y1, guard=.14):
        draw.line((*P(x0, y0), *P(x1, y1)), fill=tone((214, 218, 222)), width=max(3, int(size * .12)))
        draw.line((*P(x0, y0), *P(x1, y1)), fill=line_c, width=1)
        dx, dy = x1 - x0, y1 - y0
        gx, gy = x0 + dx * .22, y0 + dy * .22
        line([(gx - guard, gy - guard), (gx + guard, gy + guard)], 3)
        line([(x0, y0), (x0 - dx * .12, y0 - dy * .12)], 3)

    if kind == "atacar":
        blade(.2, .8, .86, .14)
    elif kind == "skills":
        star = [(.5, .04), (.62, .38), (.96, .5), (.62, .62), (.5, .96), (.38, .62), (.04, .5), (.38, .38)]
        draw.polygon(pts(star), fill=tone(GOLD), outline=line_c)
        draw.ellipse((*P(.72, .08), *P(.86, .22)), fill=tone(GOLD))
    elif kind == "items":
        draw.rounded_rectangle((*P(.14, .32), *P(.86, .92)), max(2, int(size * .12)), fill=tone((176, 122, 72)),
                               outline=line_c, width=2)
        line([(.34, .32), (.34, .14), (.66, .14), (.66, .32)], 2)
        draw.rectangle((*P(.42, .5), *P(.58, .62)), fill=tone(METAL_LIGHT), outline=line_c)
    elif kind == "defender":
        shield((118, 146, 119))
    elif kind == "disparada":
        for dx in (0.0, .3):
            line([(.12 + dx, .2), (.42 + dx, .5), (.12 + dx, .8)], 3)
        line([(.0, .5), (.08, .5)], 2)
    elif kind == "fugir":
        line([(.6, .1), (.18, .1), (.18, .9), (.6, .9)], 2)
        line([(.42, .5), (.94, .5)], 2)
        line([(.76, .32), (.94, .5), (.76, .68)], 2)
    elif kind == "voltar":
        line([(.85, .7), (.85, .4), (.2, .4)], 2)
        line([(.38, .2), (.16, .4), (.38, .6)], 2)
    elif kind == "golpe_pesado":
        line([(.2, .9), (.62, .38)], 3)
        draw.polygon(pts([(.44, .2), (.72, .06), (.94, .34), (.8, .5)]), fill=tone((150, 156, 160)), outline=line_c)
    elif kind == "ataque_furtivo":
        blade(.3, .76, .74, .2, guard=.1)
        draw.chord((*P(.02, .02), *P(.42, .42)), 60, 300, fill=tone((90, 96, 140)))
    elif kind == "escudo_divino":
        shield(GOLD, cross=True)
    elif kind == "foco_espiritual":
        draw.ellipse((*P(.06, .26), *P(.94, .74)), fill=tone(CARD), outline=line_c, width=2)
        draw.ellipse((*P(.34, .3), *P(.66, .7)), fill=tone((90, 140, 170)), outline=line_c)
        draw.ellipse((*P(.45, .42), *P(.55, .58)), fill=line_c)
    elif kind == "pocao_cura":
        flask((196, 70, 60))
    elif kind == "pocao_regeneracao":
        flask((90, 160, 90), plus=True)
    elif kind == "maca_dourada":
        draw.ellipse((*P(.14, .28), *P(.86, .94)), fill=tone(GOLD), outline=line_c, width=2)
        line([(.5, .3), (.56, .1)], 2)
        draw.ellipse((*P(.56, .06), *P(.82, .22)), fill=tone((90, 150, 80)), outline=line_c)
    else:
        diamond(draw, x + size / 2, y + size / 2, size * .3, GOLD if enabled else LINE)


def diamond(draw: ImageDraw.ImageDraw, x: float, y: float, r: float = 4, color: Color = GOLD) -> None:
    draw.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=(*color, 255))


def rule(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float, color: Color = (184, 148, 79)) -> None:
    """O filete com losango das telas (``ISOMETRICON · SINTA-SE EM CASA``)."""
    draw.line((x0, y, x1 - 8, y), fill=(*color, 255), width=1)
    diamond(draw, x1 - 3, y, 3)
