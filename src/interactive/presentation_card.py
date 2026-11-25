"""O cartão de pergaminho de cada slide do modo apresentação, como imagem PIL do tamanho da janela.

Tudo numa TTF com Unicode (Σ, ⊙, λ, ⁱ, ã, ç): a folha da fonte do Minecraft não tem esses símbolos nem os
acentos do português, e misturar as duas fontes nos títulos ficava desigual. Sem OpenGL: o ``main.py`` põe a imagem num ``HudQuad``.
"""
from dataclasses import replace
from functools import lru_cache
import os

from PIL import Image, ImageDraw, ImageFont

from src.interactive.menu_style import panel
from src.interactive.presentation_slides import Slide

FONT_CANDIDATES = (
    "C:/Windows/Fonts/cambria.ttc",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)
BOLD_CANDIDATES = ("C:/Windows/Fonts/cambriab.ttf",)

INK = (46, 58, 52)
MUTED = (112, 104, 86)
ACCENT = (52, 82, 70)
FORMULA_BG = (233, 222, 196)
MARGIN = 32
FOOTER = 64


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    size = max(int(size), 8)
    for path in (BOLD_CANDIDATES if bold else ()) + FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def card_bounds(layout: str, width: int, height: int) -> tuple[int, int, int, int]:
    """Retângulo do cartão: central (capa, encerramento) ou numa coluna à direita, acima do rodapé."""
    if layout == "center":
        w, h = int(width * 0.62), int(height * 0.84)
        x, y = (width - w) // 2, (height - h) // 2
        return x, y, x + w, y + h
    w = max(int(width * 0.44), 260)
    return width - MARGIN - w, MARGIN, width - MARGIN, max(height - FOOTER - 32, MARGIN + 120)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: float) -> list[str]:
    lines, current = [], ""
    for word in text.split(" "):
        trial = word if not current else current + " " + word
        if current and draw.textlength(trial, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    lines.append(current)
    return lines


class _Layout:
    """Desenha (ou só mede, com ``draw=None``) o conteúdo do slide numa coluna de largura ``width``."""

    def __init__(self, slide: Slide, step: int, width: int, body: int, center: bool) -> None:
        self.slide, self.step, self.width, self.body, self.center = slide, step, width, body, center

    def run(self, image: Image.Image | None, x0: int, y0: int) -> int:
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        draw = ImageDraw.Draw(image) if image is not None else None
        body, width = self.body, self.width
        y = y0

        def text_line(line: str, font, color, indent: int = 0) -> None:
            nonlocal y
            for part in _wrap(probe, line, font, width - indent):
                if draw is not None:
                    w = probe.textlength(part, font=font)
                    x = x0 + (width - w) / 2 if self.center else x0 + indent
                    draw.text((x, y), part, font=font, fill=color)
                y += int(font.size * 1.28)

        text_line(self.slide.title, _font(int(body * 1.7), bold=True), INK)
        y += body // 3
        if draw is not None and not self.center:
            draw.line((x0, y, x0 + width, y), fill=(186, 163, 115), width=2)
        y += body // 2

        regular, bold = _font(body), _font(int(body * 1.1), bold=True)
        for block in self.slide.blocks:
            if block.kind == "subtitle":
                y += body // 4
                text_line(block.content[0], bold, ACCENT)
            elif block.kind == "text":
                for line in block.content:
                    text_line(line, regular, INK if not self.center else MUTED)
            elif block.kind == "bullets":
                for line in block.content:
                    font = regular
                    if draw is not None and not self.center:
                        r = max(body // 7, 2)
                        cy = y + font.size * 0.62
                        draw.ellipse((x0 + 4, cy - r, x0 + 4 + 2 * r, cy + r), fill=ACCENT)
                    text_line(line, font, INK, indent=0 if self.center else body)
            elif block.kind == "formula":
                for line in block.content:
                    size = int(body * 1.15)
                    while size > 10 and probe.textlength(line, font=_font(size)) > width - 16:
                        size -= 1
                    font = _font(size)
                    h = int(font.size * 1.5)
                    if draw is not None:
                        draw.rounded_rectangle((x0, y, x0 + width, y + h), 8, fill=FORMULA_BG)
                        w = probe.textlength(line, font=font)
                        draw.text((x0 + (width - w) / 2, y + font.size * 0.2), line, font=font, fill=INK)
                    y += h + body // 3
            elif block.kind == "prompt":
                font = _font(int(body * 0.92))
                lines = _wrap(probe, "“" + block.content[0] + "”", font, width - 2 * body)
                h = len(lines) * int(font.size * 1.28) + body
                if draw is not None:
                    draw.rounded_rectangle((x0, y, x0 + width, y + h), 8, fill=FORMULA_BG)
                    draw.line((x0 + 4, y + 6, x0 + 4, y + h - 6), fill=ACCENT, width=4)
                    for i, part in enumerate(lines):
                        draw.text((x0 + body, y + body // 2 + i * int(font.size * 1.28)), part, font=font, fill=INK)
                y += h + body // 2
            elif block.kind == "pipeline":
                y = self._pipeline(image, draw, probe, block.content, x0, y)
            elif block.kind == "heightmap":
                y = self._heightmap(image, draw, block.content, x0, y)
            y += body // 3
        return y - y0

    def _pipeline(self, image, draw, probe, stages, x0, y) -> int:
        body, width = self.body, self.width
        font = _font(body)
        box_h, gap = int(body * 1.9), int(body * 0.9)
        label_w = int(body * 3.2)
        for i, stage in enumerate(stages):
            lit = i <= self.step
            if draw is not None:
                fill = (122, 156, 112) if lit else (226, 216, 190)
                ink = (255, 255, 255) if lit else (160, 150, 128)
                draw.rounded_rectangle((x0 + label_w, y, x0 + width, y + box_h), 8, fill=fill,
                                       outline=(160, 140, 96), width=2)
                w = probe.textlength(stage, font=font)
                draw.text((x0 + label_w + (width - label_w - w) / 2, y + (box_h - font.size) / 2 - 2), stage,
                          font=font, fill=ink)
                if i < len(stages) - 1:
                    cx = x0 + label_w + (width - label_w) // 2
                    color = ACCENT if i < self.step else (200, 188, 160)
                    draw.line((cx, y + box_h + 2, cx, y + box_h + gap - 4), fill=color, width=3)
                    draw.polygon([(cx - 6, y + box_h + gap - 10), (cx + 6, y + box_h + gap - 10),
                                  (cx, y + box_h + gap - 2)], fill=color)
            y += box_h + gap
        if draw is not None:
            top = y - 5 * (box_h + gap)
            for label, first, count in (("CPU", 0, 3), ("GPU", 3, 2)):
                a = top + first * (box_h + gap)
                b = a + count * (box_h + gap) - gap
                draw.line((x0 + label_w - 14, a, x0 + label_w - 14, b), fill=MUTED, width=2)
                f = _font(int(body * 0.9), bold=True)
                draw.text((x0, (a + b) / 2 - f.size / 2), label, font=f, fill=MUTED)
        return y

    def _heightmap(self, image, draw, labels, x0, y) -> int:
        size = max(min((self.width - 2 * 12) // 3, 140), 48)
        strip = heightmap_strip(1234, size=size)
        if image is not None:
            image.paste(strip, (x0 + (self.width - strip.width) // 2, y))
        return y + strip.height + self.body // 4


@lru_cache(maxsize=6)   # cada cartão tem o tamanho da janela (8 MB em 1920×1080)
def render_card(slide: Slide, step: int, width: int, height: int) -> Image.Image:
    """O cartão do slide sobre fundo transparente, do tamanho da janela (o ``HudQuad`` desenha em 0, 0)."""
    image = Image.new("RGBA", (max(width, 1), max(height, 1)), (0, 0, 0, 0))
    bounds = card_bounds(slide.scene.layout, width, height)
    x, y, r, b = bounds
    pad = max(int((r - x) * 0.07), 18)
    inner_w, inner_h = r - x - 2 * pad, b - y - 2 * pad
    center = slide.scene.layout == "center"
    body = max(int(height / (28 if center else 31)), 12)
    while True:
        layout = _Layout(slide, step, inner_w, body, center)
        used = layout.run(None, 0, 0)
        if used <= inner_h or body <= 10:
            break
        body = max(int(body * 0.9), 10)
    if not center:   # a coluna da direita encolhe até o conteúdo
        b = min(b, y + used + 2 * pad)
    else:            # o central fica do tamanho do conteúdo, no meio da tela
        h = min(used + 2 * pad, b - y)
        y = (height - h) // 2
        b = y + h
    panel(image, (x, y, r, b))
    layout.run(image, x + pad, y + pad)
    return image


def render_footer(index: int, total: int, counters: dict[str, tuple[int, int]], width: int) -> Image.Image:
    """Faixa do rodapé: "7/13" à esquerda e os contadores da cena à direita."""
    font = _font(18)
    image = Image.new("RGBA", (max(width, 1), 40), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    names = {"faces": "faces desenhadas", "chunks": "chunks desenhados"}
    parts = [f"{names.get(k, k)}: {a:,} de {b:,}".replace(",", ".") for k, (a, b) in counters.items()]
    for text, right in ((f"{index + 1}/{total}", False), ("    ".join(parts), True)):
        if not text:
            continue
        w = draw.textlength(text, font=font)
        x = width - MARGIN - w if right else MARGIN
        draw.rounded_rectangle((x - 10, 4, x + w + 10, 36), 8, fill=(20, 28, 24, 170))
        draw.text((x, 9), text, font=font, fill=(242, 232, 209))
    return image


@lru_cache(maxsize=8)
def heightmap_strip(seed: int, octaves: tuple[int, ...] = (1, 2, 3), size: int = 96) -> Image.Image:
    """Mapas de altura do gerador do jogo com 1, 2 e 3 oitavas, lado a lado, com legenda."""
    from src.world.terrain_options import make_generator
    import numpy as np
    base = make_generator(seed, None, vegetation=False)
    cells = 48
    gap = 12
    label_h = 22
    font = _font(15)
    strip = Image.new("RGBA", (len(octaves) * size + (len(octaves) - 1) * gap, size + label_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    xs, zs = np.meshgrid(np.arange(cells) * 3 - 72, np.arange(cells) * 3 - 72)
    for i, count in enumerate(octaves):
        generator = replace(base, octaves=count)
        heights = generator.heights(xs.ravel(), zs.ravel()).reshape(cells, cells)
        sea = generator.sea_level
        tile = Image.new("RGB", (cells, cells))
        pixels = tile.load()
        for z in range(cells):
            for x in range(cells):
                h = int(heights[z, x])
                pixels[x, z] = ((66, 109, 120) if h < sea else (181, 174, 126) if h == sea
                                else (125, 149, 97) if h < sea + 3 else (73, 106, 78) if h < sea + 7
                                else (128, 128, 118))
        left = i * (size + gap)
        strip.paste(tile.resize((size, size), Image.NEAREST), (left, 0))
        label = f"{count} oitava" + ("s" if count > 1 else "")
        w = draw.textlength(label, font=font)
        draw.text((left + (size - w) / 2, size + 3), label, font=font, fill=MUTED)
    return strip
