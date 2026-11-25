"""Os cartões de pergaminho de cada slide do modo apresentação, como imagens PIL posicionadas na tela.

Cada ``Panel`` do slide vira uma imagem própria (com a sombra em volta) e a posição dela na tela; o ``main.py``
põe cada uma num ``HudQuad``. Assim só o cartão de um gráfico ao vivo é refeito quando os números mudam.

Tudo numa TTF com Unicode (Σ, ⊙, λ, ⁱ, ã, ç): a folha da fonte do Minecraft não tem esses símbolos nem os
acentos do português. Sem OpenGL: testável à parte.
"""
from dataclasses import replace
from functools import lru_cache
import os

from PIL import Image, ImageDraw, ImageFont

from src.interactive.menu_style import panel as draw_panel
from src.interactive.presentation_slides import Panel, Slide

FONT_CANDIDATES = (
    "C:/Windows/Fonts/cambria.ttc",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)
BOLD_CANDIDATES = ("C:/Windows/Fonts/cambriab.ttf",)
MONO_CANDIDATES = ("C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

INK = (46, 58, 52)
MUTED = (112, 104, 86)
ACCENT = (52, 82, 70)
FORMULA_BG = (233, 222, 196)
SHADOW = 28            # margem da imagem em volta do cartão, para a sombra do pergaminho
SEGMENTS = (("posição", 3, (122, 156, 112)), ("normal", 3, (96, 140, 170)),
            ("UV", 2, (196, 160, 92)), ("cor", 3, (176, 112, 96)))

Live = tuple[tuple[str, tuple[int, int]], ...]   # ("faces", (desenhadas, possíveis)), ordenado


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


@lru_cache(maxsize=16)
def _mono(size: int) -> ImageFont.ImageFont:
    """A fonte dos trechos de código (o JSON dos blocos); sem ela, a do texto."""
    for path in MONO_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, max(int(size), 8))
            except OSError:
                continue
    return _font(size)


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


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


class _Layout:
    """Desenha (ou só mede, com ``image=None``) o conteúdo de um cartão numa coluna de largura ``width``."""

    def __init__(self, panel: Panel, step: int, width: int, body: int, live: dict) -> None:
        self.panel, self.step, self.width, self.body, self.live = panel, step, width, body, live
        self.center = panel.align == "center"

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

        if self.panel.title:
            size = int(body * (1.7 if self.panel.big else 1.25))
            text_line(self.panel.title, _font(size, bold=True), INK if self.panel.big else ACCENT)
            y += body // 4
            if draw is not None and not self.center:
                draw.line((x0, y, x0 + width, y), fill=(186, 163, 115), width=2)
            y += body // 2

        regular, bold = _font(body), _font(int(body * 1.1), bold=True)
        for block in self.panel.blocks:
            kind = block.kind
            if kind == "subtitle":
                y += body // 4
                text_line(block.content[0], bold, ACCENT)
            elif kind == "text":
                for line in block.content:
                    text_line(line, regular, INK if not self.center else MUTED)
            elif kind == "bullets":
                for line in block.content:
                    if draw is not None and not self.center:
                        r = max(body // 7, 2)
                        cy = y + regular.size * 0.62
                        draw.ellipse((x0 + 4, cy - r, x0 + 4 + 2 * r, cy + r), fill=ACCENT)
                    text_line(line, regular, INK, indent=0 if self.center else body)
            elif kind == "formula":
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
            elif kind == "prompt":
                font = _font(int(body * 0.92))
                lines = _wrap(probe, "“" + block.content[0] + "”", font, width - 2 * body)
                h = len(lines) * int(font.size * 1.28) + body
                if draw is not None:
                    draw.rounded_rectangle((x0, y, x0 + width, y + h), 8, fill=FORMULA_BG)
                    draw.line((x0 + 4, y + 6, x0 + 4, y + h - 6), fill=ACCENT, width=4)
                    for i, part in enumerate(lines):
                        draw.text((x0 + body, y + body // 2 + i * int(font.size * 1.28)), part, font=font, fill=INK)
                y += h + body // 2
            elif kind == "code":
                size = int(body * 0.8)
                while size > 9 and max(probe.textlength(l, font=_mono(size)) for l in block.content) > width - body:
                    size -= 1
                font = _mono(size)
                step = int(font.size * 1.3)
                h = len(block.content) * step + body // 2
                if draw is not None:
                    draw.rounded_rectangle((x0, y, x0 + width, y + h), 8, fill=FORMULA_BG)
                    for i, line in enumerate(block.content):
                        draw.text((x0 + body // 2, y + body // 4 + i * step), line, font=font, fill=INK)
                y += h + body // 4
            elif kind == "places":
                y = self._places(draw, probe, block.content, x0, y)
            elif kind == "tags":
                y = self._tags(draw, probe, block.content, x0, y + body // 4)
            elif kind == "pipeline":
                y = self._pipeline(draw, probe, block.content, x0, y)
            elif kind == "heightmap":
                y = self._heightmap(image, x0, y)
            elif kind == "bars":
                y = self._bars(draw, probe, block.content[0], x0, y)
            elif kind == "vertex":
                text_line(block.content[0], regular, INK) if block.content else None
                y = self._vertex(draw, probe, x0, y + body // 4)
            y += body // 3
        return y - y0

    # ------------------------------------------------------------------ etiquetas
    def _tags(self, draw, probe, tags, x0, y) -> int:
        """Os recursos de CG da parte do slide como etiquetas, quebrando linha quando não cabem."""
        font = _font(int(self.body * 0.82), bold=True)
        pad_x, gap = int(self.body * 0.5), int(self.body * 0.35)
        h = int(font.size * 1.55)
        x = x0
        for tag in tags:
            w = probe.textlength(tag, font=font) + 2 * pad_x
            if x > x0 and x + w > x0 + self.width:
                x = x0
                y += h + gap
            if draw is not None:
                draw.rounded_rectangle((x, y, x + w, y + h), h // 2, fill=(52, 82, 70))
                draw.text((x + pad_x, y + (h - font.size) / 2 - 1), tag, font=font, fill=(242, 232, 209))
            x += w + gap
        return y + h + gap

    def _places(self, draw, probe, places, x0, y) -> int:
        """Os lugares do slide, um por passo: o da vez cheio, os outros só com a borda."""
        font = _font(int(self.body * 0.95), bold=True)
        h, gap = int(font.size * 1.9), int(self.body * 0.4)
        for i, name in enumerate(places):
            here = i == self.step
            label = ("▶ " if here else "") + name
            if draw is not None:
                draw.rounded_rectangle((x0, y, x0 + self.width, y + h), 8,
                                       fill=(122, 156, 112) if here else (226, 216, 190),
                                       outline=(160, 140, 96), width=2)
                draw.text((x0 + self.body * 0.7, y + (h - font.size) / 2 - 1), label, font=font,
                          fill=(255, 255, 255) if here else (130, 120, 100))
            y += h + gap
        return y

    # ------------------------------------------------------------------ pipeline
    def _pipeline(self, draw, probe, stages, x0, y) -> int:
        if self.width >= self.body * 40:
            return self._pipeline_row(draw, probe, stages, x0, y)
        body, width = self.body, self.width
        font = _font(body)
        box_h, gap = int(body * 1.9), int(body * 0.9)
        label_w = int(body * 3.2)
        for i, stage in enumerate(stages):
            if draw is not None:
                self._stage(draw, probe, stage, i, (x0 + label_w, y, x0 + width, y + box_h), font)
                if i < len(stages) - 1:
                    cx = x0 + label_w + (width - label_w) // 2
                    self._arrow(draw, (cx, y + box_h + 2), (cx, y + box_h + gap - 2), i < self.step)
            y += box_h + gap
        if draw is not None:
            top = y - len(stages) * (box_h + gap)
            for label, first, count in (("CPU", 0, 3), ("GPU", 3, 2)):
                a = top + first * (box_h + gap)
                b = a + count * (box_h + gap) - gap
                draw.line((x0 + label_w - 14, a, x0 + label_w - 14, b), fill=MUTED, width=2)
                f = _font(int(body * 0.9), bold=True)
                draw.text((x0, (a + b) / 2 - f.size / 2), label, font=f, fill=MUTED)
        return y

    def _pipeline_row(self, draw, probe, stages, x0, y) -> int:
        """As etapas lado a lado (faixa larga), com as chaves CPU e GPU embaixo."""
        body, width = self.body, self.width
        gap = int(body * 2.2)
        box_w = (width - gap * (len(stages) - 1)) / len(stages)
        font = _font(int(body * 0.95))
        lines = max(len(_wrap(probe, s, font, box_w - body)) for s in stages)
        box_h = int(lines * font.size * 1.28 + body * 1.2)
        for i, stage in enumerate(stages):
            left = x0 + i * (box_w + gap)
            if draw is not None:
                self._stage(draw, probe, stage, i, (left, y, left + box_w, y + box_h), font)
                if i < len(stages) - 1:
                    self._arrow(draw, (left + box_w + 4, y + box_h / 2), (left + box_w + gap - 4, y + box_h / 2),
                                i < self.step)
        y += box_h + body // 2
        if draw is not None:
            f = _font(int(body * 0.9), bold=True)
            for label, first, count in (("CPU", 0, 3), ("GPU", 3, 2)):
                a = x0 + first * (box_w + gap)
                b = a + count * (box_w + gap) - gap
                draw.line((a, y, a, y + 8, b, y + 8, b, y), fill=MUTED, width=2)
                w = probe.textlength(label, font=f)
                draw.text(((a + b) / 2 - w / 2, y + 12), label, font=f, fill=MUTED)
        return y + 12 + int(body * 1.3)

    def _stage(self, draw, probe, stage, i, rect, font) -> None:
        lit = i <= self.step
        draw.rounded_rectangle(rect, 8, fill=(122, 156, 112) if lit else (226, 216, 190),
                               outline=(160, 140, 96), width=2)
        ink = (255, 255, 255) if lit else (160, 150, 128)
        x0, y0, x1, y1 = rect
        lines = _wrap(probe, stage, font, x1 - x0 - self.body)
        step = int(font.size * 1.28)
        top = y0 + (y1 - y0 - len(lines) * step) / 2
        for k, part in enumerate(lines):
            w = probe.textlength(part, font=font)
            draw.text((x0 + (x1 - x0 - w) / 2, top + k * step), part, font=font, fill=ink)

    @staticmethod
    def _arrow(draw, start, end, lit) -> None:
        color = ACCENT if lit else (200, 188, 160)
        (ax, ay), (bx, by) = start, end
        draw.line((ax, ay, bx, by), fill=color, width=3)
        if ax == bx:   # para baixo
            draw.polygon([(bx - 6, by - 8), (bx + 6, by - 8), (bx, by)], fill=color)
        else:          # para a direita
            draw.polygon([(bx - 8, by - 6), (bx - 8, by + 6), (bx, by)], fill=color)

    # ------------------------------------------------------------------ gráficos
    def _heightmap(self, image, x0, y) -> int:
        size = max(min((self.width - 2 * 12) // 3, 180), 48)
        strip = heightmap_strip(1234, size=size)
        if image is not None:
            image.alpha_composite(strip, (x0 + (self.width - strip.width) // 2, y))   # paste furava o cartão
        return y + strip.height + self.body // 4

    def _bars(self, draw, probe, what, x0, y) -> int:
        """Barras horizontais ao vivo: faces possíveis × desenhadas, ou chunks carregados × desenhados."""
        body, width = self.body, self.width
        drawn, total = self.live.get(what, (0, 0))
        if what == "faces":
            rows = (("possíveis (6 por cubo)", total, (186, 163, 115)), ("desenhadas", drawn, (122, 156, 112)))
            note = "descartadas na CPU"
        else:
            rows = (("carregados", total, (186, 163, 115)), ("desenhados", drawn, (122, 156, 112)))
            note = "fora do frustum neste quadro"
        font = _font(int(body * 0.85))
        bar_h = int(body * 1.3)
        top = max(total, drawn, 1)
        for label, value, color in rows:
            if draw is not None:
                draw.text((x0, y), label, font=font, fill=MUTED)
            y += int(font.size * 1.3)
            if draw is not None:
                draw.rounded_rectangle((x0, y, x0 + width, y + bar_h), 6, fill=(226, 216, 190))
                length = int(width * value / top)
                if length > 4:
                    draw.rounded_rectangle((x0, y, x0 + length, y + bar_h), 6, fill=color)
                text = _number(value)
                w = probe.textlength(text, font=font)
                inside = length > w + 16
                draw.text((x0 + length - w - 8 if inside else x0 + length + 8, y + (bar_h - font.size) / 2 - 1),
                          text, font=font, fill=(255, 255, 255) if inside else INK)
            y += bar_h + body // 3
        if draw is not None:
            share = f"{100.0 * (1.0 - drawn / total):.0f}% {note}" if total else "carregando o mundo…"
            draw.text((x0, y), share, font=_font(int(body * 1.05), bold=True), fill=ACCENT)
        return y + int(body * 1.4)

    def _vertex(self, draw, probe, x0, y) -> int:
        """Os 11 floats de um vértice como uma régua de 44 bytes, com o deslocamento de cada atributo."""
        body, width = self.body, self.width
        bar_h = int(body * 1.8)
        font = _font(int(body * 0.85))
        unit = width / 11.0
        offset = 0
        for name, floats, color in SEGMENTS:
            a, b = x0 + offset * unit, x0 + (offset + floats) * unit
            if draw is not None:
                draw.rectangle((a, y, b - 2, y + bar_h), fill=color)
                for k in range(1, floats):   # um traço por float
                    draw.line((a + k * unit, y + bar_h - 6, a + k * unit, y + bar_h), fill=(255, 255, 255))
                label = f"{name} ({floats})"
                if probe.textlength(label, font=font) > b - a - 8:
                    label = name
                w = probe.textlength(label, font=font)
                draw.text((a + (b - a - w) / 2, y + (bar_h - font.size) / 2 - 2), label, font=font,
                          fill=(255, 255, 255))
                tick = f"{offset * 4}"
                draw.line((a, y + bar_h, a, y + bar_h + 6), fill=MUTED, width=2)
                draw.text((a + 2, y + bar_h + 6), tick, font=_font(int(body * 0.7)), fill=MUTED)
            offset += floats
        if draw is not None:
            end = x0 + width - 2
            draw.line((end, y + bar_h, end, y + bar_h + 6), fill=MUTED, width=2)
            text = "44 B"
            w = probe.textlength(text, font=_font(int(body * 0.7)))
            draw.text((end - w, y + bar_h + 6), text, font=_font(int(body * 0.7)), fill=MUTED)
        return y + bar_h + 6 + int(body * 1.1)


def body_size(height: int) -> int:
    """Corpo do texto proporcional à altura da tela (~34 px em 1080p, legível no projetor)."""
    return max(int(height / 32), 12)


def panel_rect(panel: Panel, width: int, height: int, used: int) -> tuple[int, int, int, int]:
    """Onde o cartão fica: a caixa do ``Panel`` encolhida até ``used`` pixels de altura, presa pelo ``anchor``."""
    bx, by, bw, bh = panel.box
    x, r = int(bx * width), int((bx + bw) * width)
    top, bottom = int(by * height), int((by + bh) * height)
    h = min(used, bottom - top)
    if panel.anchor == "bottom":
        return x, bottom - h, r, bottom
    if panel.anchor == "middle":
        y = (top + bottom - h) // 2
        return x, y, r, y + h
    return x, top, r, top + h


@lru_cache(maxsize=32)
def render_panel(panel: Panel, step: int, width: int, height: int, live: Live = ()) -> tuple[int, int, Image.Image]:
    """O cartão como imagem (com a margem da sombra) e onde a imagem vai na tela."""
    bx, _, bw, _ = panel.box
    w = int((bx + bw) * width) - int(bx * width)
    body = body_size(height)
    pad = max(min(int(w * 0.06), int(body * 1.3)), 14)   # numa faixa larga a margem não cresce com a largura
    inner_w = w - 2 * pad
    max_h = int(panel.box[3] * height) - 2 * pad
    values = dict(live)
    while True:
        layout = _Layout(panel, step, inner_w, body, values)
        used = layout.run(None, 0, 0)
        if used <= max_h or body <= 10:
            break
        body = max(int(body * 0.92), 10)
    x, y, r, b = panel_rect(panel, width, height, used + 2 * pad)
    image = Image.new("RGBA", (r - x + 2 * SHADOW, b - y + 2 * SHADOW), (0, 0, 0, 0))
    draw_panel(image, (SHADOW, SHADOW, SHADOW + r - x, SHADOW + b - y))
    layout.run(image, SHADOW + pad, SHADOW + pad)
    return x - SHADOW, y - SHADOW, image


def render_slide(slide: Slide, step: int, width: int, height: int,
                 live: dict[str, tuple[int, int]] | None = None) -> list[tuple[int, int, Image.Image]]:
    """Os cartões do slide; só os que têm gráfico ao vivo recebem os números (os outros ficam no cache)."""
    values: Live = tuple(sorted((live or {}).items()))
    return [render_panel(p, step if any(b.kind in ("pipeline", "places") for b in p.blocks) else 0,
                         width, height, values if p.live else ())
            for p in slide.panels]


def compose(slide: Slide, step: int, width: int, height: int,
            live: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    """Os cartões do slide numa imagem do tamanho da tela (para testes e prévias)."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for x, y, piece in render_slide(slide, step, width, height, live):
        image.alpha_composite(piece, (x, y)) if x >= 0 and y >= 0 else image.paste(piece, (x, y), piece)
    return image


def render_footer(index: int, total: int, width: int) -> Image.Image:
    """O número do slide, no canto de baixo à esquerda."""
    font = _font(20)
    text = f"{index + 1}/{total}"
    image = Image.new("RGBA", (120, 44), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    w = draw.textlength(text, font=font)
    draw.rounded_rectangle((0, 4, w + 20, 40), 8, fill=(20, 28, 24, 170))
    draw.text((10, 10), text, font=font, fill=(242, 232, 209))
    return image


@lru_cache(maxsize=8)
def heightmap_strip(seed: int, octaves: tuple[int, ...] = (1, 2, 3), size: int = 96) -> Image.Image:
    """Mapas de altura do gerador do jogo com 1, 2 e 3 oitavas, lado a lado, com legenda."""
    from src.world.terrain_options import make_generator
    import numpy as np
    base = make_generator(seed, None, vegetation=False)
    cells = 48
    gap = 12
    font = _font(max(size // 7, 13))
    label_h = font.size + 8
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
