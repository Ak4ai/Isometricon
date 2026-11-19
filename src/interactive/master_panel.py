"""O painel do mestre (``/mestre``): a ambientação do mundo num pergaminho à esquerda da tela.

Hora do dia (e o relógio, que pode andar sozinho), claridade, cor da luz, névoa, cores, a luz do grupo e cenas
prontas (amanhecer, meio-dia, entardecer, noite, tempestade, sombrio). Tudo muda na hora, enquanto se arrasta; o
mundo guarda a ambientação ao salvar. Clique e arraste nas trilhas; Esc ou o X fecha.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from src.interactive import combat_style as style
from src.rendering.ambience import CLOCK_SPEEDS, PRESETS, Ambience

WIDTH = 340
LEFT, TOP = 16, 16
PAD = 22
HEIGHT = 0   # a altura do pergaminho (o fim do conteúdo); calculada abaixo, na primeira vez
Rect = Tuple[float, float, float, float]

# (campo, rótulo, mínimo, máximo, texto do valor)
SLIDERS = (
    ('brightness', 'Claridade', 0, 200, lambda v: f'{v}%'),
    ('temperature', 'Cor da luz', -100, 100,
     lambda v: 'neutra' if v == 0 else f'{"quente" if v > 0 else "fria"} {abs(v)}'),
    ('fog', 'Névoa', 0, 100, lambda v: 'sem' if v == 0 else f'{v}%'),
    ('saturation', 'Cores', 0, 200, lambda v: f'{v}%'),
    ('torch', 'Luz do grupo', 0, 100, lambda v: 'apagada' if v == 0 else f'{v}%'),
)
CLOCK_LABELS = ('Parado', '1×', '10×', '60×')
WAR_LABELS = ('Sem', 'Revela', 'Em volta')
WAR_HINTS = ('o mundo todo à vista', 'o explorado fica limpo', 'a névoa fecha atrás de você')
# a altura das nuvens da névoa de guerra (acima do relevo, ou das construções se elas ficam cobertas)
WAR_SLIDERS = (
    ('war_height', 'Altura da névoa', 0, 16, lambda v: 'rente' if v == 0 else f'+{v} bloco' + ('s' if v > 1 else '')),
)
OBJECT_LABELS = ('Mostrar acima', 'Cobrir objetos')


class MasterPanel:
    def __init__(self, ambience: Ambience, create_gl: bool = True) -> None:
        self.ambience = ambience
        self.is_open = False
        self.hits: List[Tuple[Rect, str]] = []      # em pixels da janela
        self.hover: Optional[str] = None
        self.pressed: Optional[str] = None
        self.height = 0
        self.quad = None
        self._signature = None
        self.image: Optional[Image.Image] = None
        self.on_change = None                       # chamado quando o mestre muda algo (o main grava o mundo)
        self.on_recover = None                      # "Recobrir": cobre de novo o explorado (o main liga)
        self.scale = 1.0                            # numa janela baixa, o painel encolhe para caber
        if create_gl:
            from src.rendering.hud_quad import HudQuad
            self.quad = HudQuad()

    # ---- abrir e fechar ----
    def open(self) -> None:
        self.is_open = True
        self._signature = None

    def close(self) -> None:
        self.is_open = False
        self.pressed = self.hover = None

    def toggle(self) -> bool:
        self.close() if self.is_open else self.open()
        return self.is_open

    @property
    def right(self) -> float:
        return LEFT + WIDTH * self.scale

    def _local(self, x: float, y: float) -> Tuple[float, float]:
        """Da janela para o desenho do painel (sem a escala)."""
        return LEFT + (x - LEFT) / self.scale, TOP + (y - TOP) / self.scale

    def contains(self, x: float, y: float) -> bool:
        x, y = self._local(x, y)
        return self.is_open and LEFT <= x <= LEFT + WIDTH and TOP <= y <= TOP + max(self.height, 1)

    # ---- entrada ----
    def hit_at(self, x: float, y: float) -> Optional[str]:
        x, y = self._local(x, y)
        for rect, action in reversed(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return action
        return None

    def handle_mouse_button(self, x: float, y: float, press: bool) -> bool:
        """Clique esquerdo (``press`` aperta, senão solta), em pixels da janela; True se foi no painel."""
        if not self.is_open:
            return False
        if press:
            if not self.contains(x, y):
                return False
            self.pressed = self.hit_at(x, y)
            if self.pressed and self.pressed.startswith('slider:'):
                self._drag(self.pressed, x)
            return True
        pressed, self.pressed = self.pressed, None
        if pressed is None:
            return self.contains(x, y)
        if not pressed.startswith('slider:') and self.hit_at(x, y) == pressed:
            self.activate(pressed)
        return True

    def handle_cursor(self, x: float, y: float) -> bool:
        """O mouse andou: arrasta a trilha apertada; True se o painel está debaixo dele (ou arrastando)."""
        if not self.is_open:
            return False
        if self.pressed and self.pressed.startswith('slider:'):
            self._drag(self.pressed, x)
            return True
        self.hover = self.hit_at(x, y) if self.contains(x, y) else None
        return self.contains(x, y)

    def _drag(self, action: str, x: float) -> None:
        rect = next((r for r, a in self.hits if a == action), None)
        if rect is None:
            return
        x = self._local(x, 0)[0]
        t = max(0.0, min(1.0, (x - rect[0]) / max(rect[2] - rect[0], 1.0)))
        name = action[7:]
        if name == 'hour':
            value = round(t * 24 * 4) / 4 % 24.0      # de 15 em 15 minutos
        else:
            low, high = next((lo, hi) for key, _, lo, hi, _ in SLIDERS + WAR_SLIDERS if key == name)
            value = int(round(low + (high - low) * t))
            if name in ('brightness', 'saturation') and abs(value - 100) <= 3:
                value = 100                             # o neutro "gruda"
            if name == 'temperature' and abs(value) <= 4:
                value = 0
        if getattr(self.ambience, name) != value:
            setattr(self.ambience, name, value)
            self._changed()

    def activate(self, action: str) -> None:
        a = self.ambience
        if action == 'close':
            self.close()
            return
        if action == 'reset':
            a.reset()
        elif action.startswith('clock:'):
            a.clock = int(action[6:])
        elif action.startswith('war:'):
            a.fog_war = int(action[4:])
        elif action.startswith('objects:'):
            a.war_objects = int(action[8:])
        elif action == 'recover':
            if self.on_recover is not None:
                self.on_recover()
        elif action.startswith('preset:'):
            values = dict(PRESETS)[action[7:]]
            for key, value in values.items():
                setattr(a, key, value)
            a.clock = 0
        a.clamp()
        self._changed()

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    # ---- desenho ----
    def _signature_now(self):
        return (tuple(sorted(self.ambience.to_dict().items(), key=lambda kv: kv[0]))
                if self.ambience.clock == 0 else self.ambience.clock_text(),
                tuple(self.ambience.to_dict()[k] for k in ('clock', 'brightness', 'temperature', 'fog', 'saturation',
                                                          'torch', 'fog_war', 'war_height',
                                                          'war_objects')),
                self.hover, self.pressed)

    def draw_image(self) -> Image.Image:
        """O pergaminho do painel; ``self.hits`` em pixels da janela."""
        a = self.ambience
        hits: List[Tuple[Rect, str]] = []
        height = HEIGHT or 900
        sheet, pad = style.card(WIDTH, height)
        draw = ImageDraw.Draw(sheet)
        ox, oy = pad, pad                    # do papel para a imagem
        x0, x1 = ox + PAD, ox + WIDTH - PAD

        def hit(box, action):
            hits.append(((box[0] - ox + LEFT, box[1] - oy + TOP, box[2] - ox + LEFT, box[3] - oy + TOP), action))

        def chip(box, label, action, selected=False):
            hot = self.hover == action or self.pressed == action
            x, y, r, b = box
            draw.rounded_rectangle((x, y + 3, r, b + 3), 7, fill=(*style.BUTTON_SHADOW, 255))
            fill = style.FOREST if selected else ((255, 249, 236) if hot else style.BUTTON)
            draw.rounded_rectangle(box, 7, fill=(*fill, 255),
                                   outline=(*((161, 122, 52) if hot or selected else style.BUTTON_EDGE), 255),
                                   width=2 if hot else 1)
            size = 14
            w = style.measure(label, size)
            style.write(draw, ((x + r - w) / 2, (y + b) / 2 - 8), label, size, style.CREAM if selected else style.INK)
            hit(box, action)

        def track(y, key, ratio, label, value_text):
            action = 'slider:' + key
            hot = self.hover == action or self.pressed == action
            style.write(draw, (x0, y), label, 15, style.INK)
            w = style.measure(value_text, 14)
            style.write(draw, (x1 - w, y + 1), value_text, 14, style.GOLD_DARK)
            ty = y + 30
            draw.rounded_rectangle((x0, ty - 3, x1, ty + 3), 3, fill=(*style.TRACK, 255))
            knob = x0 + (x1 - x0) * ratio
            draw.rounded_rectangle((x0, ty - 3, knob, ty + 3), 3, fill=(*style.FOREST, 255))
            r = 10 if hot else 8
            draw.ellipse((knob - r, ty - r, knob + r, ty + r), fill=(234, 195, 116, 255),
                         outline=(161, 122, 52, 255) if hot else (*style.BUTTON_SHADOW, 255), width=2)
            hit((x0 - 4, ty - 14, x1 + 4, ty + 14), action)

        y = oy + 22
        style.write(draw, (x0, y), 'MESTRE', 12, style.GOLD_DARK, bold=True)
        close = (x1 - 26, y - 4, x1, y + 22)
        hot = self.hover == 'close'
        draw.rounded_rectangle(close, 6, fill=(*((255, 249, 236) if hot else style.BUTTON), 255),
                               outline=(*style.BUTTON_EDGE, 255))
        cx, cy = (close[0] + close[2]) / 2, (close[1] + close[3]) / 2
        for sx in (-1, 1):
            draw.line((cx - 5, cy - 5 * sx, cx + 5, cy + 5 * sx), fill=(*style.INK, 255), width=2)
        hit(close, 'close')
        style.write(draw, (x0, y + 22), 'Ambientação', 26, style.INK, heading=True)
        style.rule(draw, x0, x0 + 90, y + 64)

        # o relógio
        y += 80
        style.write(draw, (x0, y), 'Hora do dia', 15, style.INK)
        clock = a.clock_text()
        w = style.measure(clock, 28, heading=True)
        style.write(draw, (x1 - w, y - 8), clock, 28, style.INK, heading=True)
        period = ('madrugada' if a.hour < 5 else 'manhã' if a.hour < 12 else 'tarde' if a.hour < 18
                  else 'noite')
        style.write(draw, (x0, y + 22), period, 12, style.MUTED)
        ty = y + 52
        # a trilha da hora: o céu do dia por baixo (noite, amanhecer, dia, entardecer, noite)
        sky = Image.new('RGBA', (int(x1 - x0), 8))
        sky_draw = ImageDraw.Draw(sky)
        probe = Ambience()
        for i in range(sky.width):
            probe.hour = 24.0 * i / max(sky.width - 1, 1)
            c = probe.daylight()
            sky_draw.line((i, 0, i, 7), fill=tuple(int(max(0, min(255, v * 200))) for v in c) + (255,))
        mask = Image.new('L', sky.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, sky.width - 1, 7), 4, fill=255)
        sheet.paste(sky, (int(x0), int(ty - 4)), mask)
        knob = x0 + (x1 - x0) * a.hour / 24.0
        hot = self.hover == 'slider:hour' or self.pressed == 'slider:hour'
        r = 11 if hot else 9
        draw.ellipse((knob - r, ty - r, knob + r, ty + r), fill=(234, 195, 116, 255),
                     outline=(161, 122, 52, 255) if hot else (*style.BUTTON_SHADOW, 255), width=2)
        hit((x0 - 4, ty - 14, x1 + 4, ty + 14), 'slider:hour')
        y = ty + 24
        style.write(draw, (x0, y), 'Relógio · minutos de jogo por segundo', 13, style.MUTED)
        y += 22
        gap = 8
        cw = (x1 - x0 - gap * 3) / 4
        for i, label in enumerate(CLOCK_LABELS):
            bx = x0 + i * (cw + gap)
            chip((bx, y, bx + cw, y + 30), label, f'clock:{i}', selected=a.clock == i)
        y += 40
        draw.line((x0, y, x1, y), fill=(*style.LINE, 255))
        y += 14
        for key, label, low, high, text in SLIDERS:
            value = getattr(a, key)
            track(y, key, (value - low) / (high - low), label, text(value))
            y += 45

        # a névoa de guerra: o que o grupo ainda não viu fica coberto
        style.write(draw, (x0, y), 'Névoa de guerra', 15, style.INK)
        hint = WAR_HINTS[a.fog_war]
        style.write(draw, (x1 - style.measure(hint, 12), y + 3), hint, 12, style.MUTED)
        y += 26
        for i, label in enumerate(WAR_LABELS):
            bx = x0 + i * (cw + gap)
            chip((bx, y, bx + cw, y + 30), label, f'war:{i}', selected=a.fog_war == i)
        bx = x0 + 3 * (cw + gap)
        chip((bx, y, bx + cw, y + 30), 'Recobrir', 'recover')
        y += 44
        # até onde as nuvens sobem, e se o que é mais alto (uma torre, uma árvore construída) aparece por cima
        for key, label, low, high, text in WAR_SLIDERS:
            value = getattr(a, key)
            track(y, key, (value - low) / (high - low), label, text(value))
            y += 45
        ow = (x1 - x0 - gap) / 2
        for i, label in enumerate(OBJECT_LABELS):
            bx = x0 + i * (ow + gap)
            chip((bx, y, bx + ow, y + 30), label, f'objects:{i}', selected=a.war_objects == i)
        y += 44
        draw.line((x0, y, x1, y), fill=(*style.LINE, 255))
        y += 14
        style.write(draw, (x0, y), 'Cenas prontas', 15, style.INK)
        y += 26
        cw = (x1 - x0 - gap * 2) / 3
        for i, (name, _) in enumerate(PRESETS):
            col, row = i % 3, i // 3
            bx, by = x0 + col * (cw + gap), y + row * 36
            chip((bx, by, bx + cw, by + 30), name, 'preset:' + name)
        y += -(-len(PRESETS) // 3) * 36 + 4
        chip((x0, y, x1, y + 32), 'Restaurar o padrão', 'reset')
        y += 32 + 20
        if height != int(y - oy):            # a primeira vez: mede o conteúdo e refaz no tamanho certo
            globals()['HEIGHT'] = int(y - oy)
            return self.draw_image()
        self.height = height
        image = sheet
        self.hits = hits
        self.image = image
        self.offset = (LEFT - pad, TOP - pad)
        return image

    def render(self, width: int, height: int) -> None:
        if not self.is_open:
            return
        signature = self._signature_now()
        if signature != self._signature or self.image is None:
            self.draw_image()
            self._signature = signature
            if self.quad is not None:
                self.quad.set_image(self.image)
        if self.quad is not None:
            self.scale = min(1.0, (height - 2 * TOP) / max(self.height + 8, 1))
            pad = TOP - self.offset[1]
            self.quad.draw(LEFT - pad * self.scale, TOP - pad * self.scale, width, height,
                           size=(self.image.width * self.scale, self.image.height * self.scale))

    def delete(self) -> None:
        if self.quad is not None:
            self.quad.delete()
            self.quad = None
