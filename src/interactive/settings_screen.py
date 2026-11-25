"""Tela de Configurações: abas no topo, uma linha grande por opção e um painel que explica a opção em foco.

O desenho segue as Configurações do Steam for Consoles (Stremio_For_Gamepad), com a paleta do Isometricon:
- abas em pílula, trocadas com Q e E (ou clicando);
- cada linha tem ícone, título, uma linha de detalhe e o valor; nas de escolha, ‹ e › (ou ← e →) mudam o valor,
  e Enter (ou o clique) avança para o próximo;
- o painel da direita mostra o que a opção faz, o padrão, o custo e as alternativas.

Tudo muda só o rascunho (``menus.draft``); "Aplicar alterações" grava e o jogo aplica no quadro seguinte.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import glfw
from PIL import Image, ImageDraw

from src.core.game_storage import ACTIONS, DEFAULTS, GRAPHICS

INK = '#293E34'
MUTED = '#6B7160'
LINE = '#CFC5AB'
CARD = '#FBF4E4'
GOLD = '#E7B65E'
GREEN = '#355B48'

TABS = [('general', 'Geral'), ('graphics', 'Gráficos'), ('controls', 'Controles'), ('access', 'Acessibilidade')]
TAB_TEXT = {
    'general': 'Câmera e som: como o mundo responde ao mouse e ao teclado.',
    'graphics': 'Qualidade da imagem e desempenho. As mudanças valem assim que você aplica, sem reiniciar.',
    'controls': 'As teclas de cada ação. Enter numa linha e depois a tecla nova; Esc cancela.',
    'access': 'Leitura e conforto: tamanho do texto e menos movimento na tela.',
}

# opções que não são gráficas, com a mesma forma de GRAPHICS (padrão, valores)
CHOICES = {
    **GRAPHICS,
    'sensitivity': (1.0, (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)),
    'text_scale': (1.0, (1.0, 1.25)),
    'vsync': (True, (False, True)),
    'invert_rotation': (False, (False, True)),
    'reduce_motion': (False, (False, True)),
    'show_fps': (False, (False, True)),
    'show_coords': (True, (False, True)),
}

LIST = (72, 202, 790, 690)     # a coluna das linhas
PANEL = (818, 202, 1248, 690)  # o painel da direita
ROW_H, ROW_GAP, GROUP_H = 60, 8, 32


@dataclass
class Row:
    id: str
    title: str
    detail: str
    icon: str
    kind: str                       # 'toggle', 'choice', 'bind' ou 'info'
    group: Optional[str] = None
    key: Optional[str] = None       # a chave em menus.draft (ou a ação, nas teclas)
    help: str = ''
    facts: List[Tuple[str, str]] = field(default_factory=list)


def value_text(key: str, value) -> str:
    if isinstance(value, bool):
        return 'Sim' if value else 'Não'
    if key == 'msaa':
        return 'Desligado' if not value else f'{value}×'
    if key in ('render_scale', 'shadow_strength', 'text_scale'):
        return f'{round(value * 100)}%'
    if key == 'render_distance':
        return f'{value} chunk' + ('s' if value != 1 else '')
    if key == 'shadow_distance':
        return '1 chunk (perto)' if value == 1 else f'{value} chunks'
    if key == 'shadows':
        return {'off': 'Desligadas', 'low': 'Baixa', 'medium': 'Média', 'high': 'Alta'}[value]
    if key == 'shadow_detail':
        return ('Leve', 'Formas', 'Plantas', 'Completa')[value]
    if key == 'shadow_range':
        return {16: 'Curto', 32: 'Médio', 56: 'Longo'}.get(value, str(value))
    if key == 'gpu':
        return {'high': 'Dedicada (mais forte)', 'low': 'Integrada (economiza bateria)',
                'auto': 'O Windows decide'}[value]
    if key == 'fps_limit':
        return 'Sem limite' if not value else f'{value} FPS'
    if key == 'sensitivity':
        return f'{value:.2f}×'
    return str(value)


def key_name(code: int, gl_ready: bool) -> str:
    name = glfw.get_key_name(code, 0) if gl_ready else None
    return (name or {32: 'Espaço', 340: 'Shift', 341: 'Ctrl', 61: '=', 45: '-', 47: '/'}.get(
        code, chr(code) if 33 <= code <= 126 else str(code))).upper()


def rows(tab: str, draft: dict, gl_ready: bool = False) -> List[Row]:
    if tab == 'general':
        return [
            Row('invert_rotation', 'Inverter rotação', 'Q e E giram a câmera no sentido contrário', 'rotate',
                'toggle', 'Câmera', 'invert_rotation',
                'Troca o sentido em que Q e E giram a mesa. Útil se o giro padrão parece ao contrário para você.'),
            Row('sensitivity', 'Sensibilidade do pan', 'Quanto a câmera anda ao arrastar com o mouse', 'mouse',
                'choice', None, 'sensitivity',
                'A velocidade com que a câmera acompanha o mouse quando você arrasta a vista (Shift + clique).'),
            Row('show_coords', 'Mostrar coordenadas', 'A posição X Y Z no canto de cima à esquerda', 'pin',
                'toggle', 'Interface', 'show_coords',
                'Mostra onde o personagem está no mundo (X, Y e Z), como no Minecraft. Desligada, a tela fica limpa '
                'e o contador de FPS, se estiver ligado, sobe para o lugar dela.'),
            Row('audio', 'Sons da floresta', 'Ainda não disponível no motor', 'sound', 'info', 'Som', None,
                'O áudio chega junto com o sistema de som do motor. Por enquanto não há volume para ajustar.'),
        ]
    if tab == 'graphics':
        return [
            Row('vsync', 'Sincronização vertical', 'Espera a tela para desenhar cada quadro', 'monitor', 'toggle',
                'Tela', 'vsync',
                'Acompanha a frequência do monitor e evita o "rasgo" na imagem. Com ela ligada, o FPS fica preso à '
                'tela (60, 120, 144…).',
                [('Custo', 'Nenhum'), ('Com ela ligada', 'o limite de FPS só vale abaixo da tela')]),
            Row('show_fps', 'Mostrar FPS', 'Contador de quadros sob as coordenadas', 'gauge', 'toggle', None,
                'show_fps',
                'Mostra no canto superior esquerdo quantos quadros por segundo o jogo está desenhando, lido a cada '
                'meio segundo.',
                [('Custo', 'Nenhum')]),
            Row('gpu', 'Placa de vídeo', 'Em notebooks com duas placas, qual o jogo usa', 'gauge', 'choice', None,
                'gpu',
                'Notebooks com duas placas (uma integrada, Intel ou AMD, e uma dedicada, NVIDIA ou AMD) põem os '
                'programas na integrada, mais fraca. Na dedicada o jogo roda bem mais rápido; na integrada a bateria '
                'dura mais. O jogo grava a escolha nas configurações de gráficos do Windows e vale na próxima vez que '
                'ele abrir. Com uma placa só, não muda nada.',
                [('Custo', 'Nenhum (a dedicada gasta mais bateria)')]),
            Row('fps_limit', 'Limite de FPS', 'Teto de quadros por segundo', 'gauge', 'choice', None, 'fps_limit',
                'Segura o jogo num número fixo de quadros por segundo. Economiza bateria e deixa a placa mais fria, '
                'e o ritmo dos quadros fica mais estável.',
                [('Custo', 'Nenhum; menos FPS gasta menos')]),
            Row('render_scale', 'Escala da resolução', 'Resolução interna do mundo', 'scale', 'choice', None,
                'render_scale',
                'Desenha o mundo numa resolução menor e amplia na tela. A interface (chat, cursor, menus) continua '
                'nítida. É o ajuste que mais ganha desempenho quando a placa é o limite.',
                [('Custo', 'Menor escala = mais FPS'), ('Visual', 'abaixo de 75% o mundo fica borrado')]),
            Row('msaa', 'MSAA', 'Antisserrilhado das bordas dos blocos', 'aa', 'choice', 'Antisserrilhado', 'msaa',
                'Suaviza a escada de pixels nas bordas dos blocos, das plantas e do personagem, amostrando cada pixel '
                'várias vezes. Não borra as texturas.',
                [('Custo', 'Médio (8× é o mais pesado)')]),
            Row('fxaa', 'FXAA', 'Suavização rápida da imagem pronta', 'aa2', 'toggle', None, 'fxaa',
                'Suaviza as bordas olhando a imagem final, numa passada só. Quase não custa, mas amacia um pouco as '
                'texturas de pixel. Bom junto com MSAA desligado ou com a escala abaixo de 100%.',
                [('Custo', 'Muito baixo')]),
            Row('render_distance', 'Distância de render', 'Chunks carregados em volta do personagem', 'cube',
                'choice', 'Mundo', 'render_distance',
                'Quantos chunks (16 × 16 blocos) em volta do personagem ficam carregados e desenhados. Mais distância '
                'mostra mais mundo, mas gera e guarda mais terreno.',
                [('Custo', 'Alto acima de 3 (memória e geração)')]),
            Row('shadows', 'Sombras do sol', 'Qualidade da sombra que o sol projeta', 'sun', 'choice', 'Sombras',
                'shadows',
                'Alta: penumbra suave e borda nítida junto aos blocos (até 18 raios por pixel). Média: a mesma sombra '
                'com menos raios (até 11), um pouco mais granulada. Baixa: um raio só, sombra dura em degraus de pixel. '
                'Desligadas: sem sombra do sol.',
                [('Custo', 'O maior da cena')]),
            Row('shadow_detail', 'Detalhe da sombra', 'O que faz sombra pelo formato de verdade', 'leaf', 'choice',
                None, 'shadow_detail',
                'Leve: cada bloco faz sombra de cubo inteiro, como antes (lajes, escadas e cercas viram cubos; placas '
                'e plantas não fazem sombra). Formas: lajes, escadas, cercas, placas e lanternas fazem sombra pelo '
                'formato. Plantas: também mudas, flores e cogumelos, pelo desenho das folhas. Completa: também o '
                'capim do chão, o mais pesado.',
                [('Custo', 'Baixo a alto (o capim é o mais pesado)')]),
            Row('shadow_range', 'Alcance da sombra', 'Até onde o raio procura o que tapa o sol', 'range', 'choice',
                None, 'shadow_range',
                'Com o sol baixo, um morro distante pode sombrear o personagem. O alcance diz até quantos blocos o raio '
                'do sol procura: Curto 16, Médio 32, Longo 56. Sombras compridas somem no curto.',
                [('Custo', 'Baixo a médio')]),
            Row('shadow_distance', 'Distância das sombras', 'Até quantos chunks em volta há sombra do sol', 'range',
                'choice', None, 'shadow_distance',
                'A sombra do sol só existe numa área em volta do personagem; fora dela tudo fica no sol. 1 chunk é '
                'a área de sempre (48 × 48 blocos). Mais chunks mostram as sombras das árvores e dos morros lá longe '
                '(até a distância de render), mas a área é refeita quando o personagem anda e ocupa mais memória de '
                'vídeo.',
                [('Custo', 'Médio a alto acima de 3 (um tranco curto a cada 8 blocos andados)')]),
            Row('shadow_half', 'Sombra em meia resolução', 'Calcula a sombra em quadrados de 2 x 2 pixels', 'scale',
                'toggle', None, 'shadow_half',
                'Os quatro pixels de cada quadrado dividem os raios do sol (cada um traça só a sua parte) e juntam o '
                'resultado. As texturas e as bordas dos blocos continuam nítidas; só a sombra perde um pouco de '
                'precisão no contorno. Pesa bem menos onde quase tudo é penumbra, como debaixo das árvores altas da '
                'taiga. Vale para as qualidades Média e Alta.',
                [('Custo', 'Diminui (até ~3x menos raios)'), ('Visual', 'contorno da sombra um pouco mais mole')]),
            Row('shadow_strength', 'Intensidade da sombra', 'O quanto a sombra escurece', 'contrast', 'choice', None,
                'shadow_strength',
                'Só o escuro da sombra: 100% é a sombra inteira, 25% é um sombreado leve. Não muda o desempenho.',
                [('Custo', 'Nenhum')]),
        ]
    if tab == 'controls':
        out = []
        for index, (action, (label, _)) in enumerate(ACTIONS.items()):
            out.append(Row('bind_' + action, label, 'Enter e depois a tecla nova', 'key', 'bind',
                           'Teclas' if index == 0 else None, action,
                           'Pressione Enter (ou clique) e depois a tecla que quer usar. Esc cancela. Uma tecla não '
                           'pode estar em duas ações.'))
        return out
    return [
        Row('reduce_motion', 'Reduzir movimento', 'Sem transições nem giro animado da câmera', 'motion', 'toggle',
            'Conforto', 'reduce_motion',
            'Tira as animações dos menus e faz a câmera girar de uma vez, sem a volta animada.'),
        Row('text_scale', 'Tamanho do texto', 'Texto dos menus', 'text', 'choice', 'Leitura', 'text_scale',
            'Aumenta o texto dos menus para 125%.'),
    ]


def row_value(row: Row, draft: dict, gl_ready: bool) -> str:
    if row.kind == 'bind':
        return key_name(draft['bindings'][row.key], gl_ready)
    if row.kind == 'info':
        return 'Em breve'
    return value_text(row.key, draft[row.key])


def shift(draft: dict, key: str, step: int, wrap: bool = False) -> None:
    """Muda a escolha ``key`` do rascunho para a vizinha (``wrap``: do último volta ao primeiro)."""
    default, options = CHOICES[key]
    value = draft.get(key, default)
    index = options.index(value) if value in options else options.index(default)
    index = (index + step) % len(options) if wrap else max(0, min(len(options) - 1, index + step))
    draft[key] = options[index]


def find_row(tab: str, row_id: str) -> Optional[Row]:
    return next((r for r in rows(tab, DEFAULTS) if r.id == row_id), None)


# --------------------------------------------------------------------------------------------- desenho
def _icon(draw: ImageDraw.ImageDraw, kind: str, x: float, y: float, s: float, color: str) -> None:
    from src.interactive.menu_style import icon as base_icon

    def p(a, b):
        return x + a * s, y + b * s

    def line(points, width=2):
        draw.line([p(a, b) for a, b in points], fill=color, width=width, joint='curve')

    if kind == 'monitor':
        draw.rounded_rectangle((*p(.08, .15), *p(.92, .7)), 3, outline=color, width=2)
        line([(.5, .7), (.5, .85)]); line([(.3, .88), (.7, .88)])
    elif kind == 'pin':    # um marcador de mapa (a posição no mundo)
        draw.ellipse((*p(.22, .05), *p(.78, .61)), outline=color, width=2)
        draw.ellipse((*p(.42, .25), *p(.58, .41)), fill=color)
        line([(.27, .48), (.5, .95), (.73, .48)])
    elif kind == 'gauge':
        draw.arc((*p(.05, .12), *p(.95, 1.02)), 180, 360, fill=color, width=2)
        line([(.5, .57), (.75, .3)]); draw.ellipse((*p(.43, .5), *p(.57, .64)), fill=color)
    elif kind == 'scale':
        draw.rectangle((*p(.08, .08), *p(.92, .92)), outline=color, width=2)
        draw.rectangle((*p(.08, .45), *p(.55, .92)), fill=color)
    elif kind == 'aa':
        line([(.1, .85), (.1, .6), (.35, .6), (.35, .35), (.6, .35), (.6, .12), (.9, .12)])
    elif kind == 'aa2':
        line([(.1, .85), (.9, .12)]); line([(.1, .6), (.6, .12)], 1); line([(.35, .85), (.9, .35)], 1)
    elif kind == 'sun':
        draw.ellipse((*p(.3, .3), *p(.7, .7)), outline=color, width=2)
        for i in range(8):
            a = i * math.pi / 4
            line([(.5 + .32 * math.cos(a), .5 + .32 * math.sin(a)), (.5 + .47 * math.cos(a), .5 + .47 * math.sin(a))])
    elif kind == 'range':
        line([(.08, .5), (.92, .5)]); line([(.75, .32), (.92, .5), (.75, .68)]); line([(.08, .3), (.08, .7)])
    elif kind == 'leaf':   # uma folha (a sombra pelo formato das coisas)
        draw.chord((*p(.12, .1), *p(.88, .9)), 135, 315, fill=color)
        line([(.15, .88), (.82, .18)])
    elif kind == 'contrast':
        draw.ellipse((*p(.1, .1), *p(.9, .9)), outline=color, width=2)
        draw.pieslice((*p(.1, .1), *p(.9, .9)), 90, 270, fill=color)
    elif kind == 'rotate':
        draw.arc((*p(.12, .12), *p(.88, .88)), 30, 320, fill=color, width=2)
        line([(.88, .2), (.88, .45), (.64, .45)])
    elif kind == 'mouse':
        draw.rounded_rectangle((*p(.25, .05), *p(.75, .95)), int(s * .25), outline=color, width=2)
        line([(.5, .12), (.5, .35)])
    elif kind == 'sound':
        draw.polygon([p(.1, .38), p(.32, .38), p(.55, .15), p(.55, .85), p(.32, .62), p(.1, .62)], outline=color)
        draw.arc((*p(.5, .3), *p(.85, .7)), -60, 60, fill=color, width=2)
    elif kind == 'key':
        draw.rounded_rectangle((*p(.05, .2), *p(.95, .8)), 4, outline=color, width=2)
        for cx in (.25, .5, .75):
            draw.rectangle((*p(cx - .06, .38), *p(cx + .06, .48)), fill=color)
        line([(.3, .63), (.7, .63)])
    elif kind == 'motion':
        line([(.08, .5), (.92, .5)]); line([(.08, .28), (.6, .28)], 1); line([(.08, .72), (.6, .72)], 1)
    elif kind == 'text':
        line([(.15, .15), (.85, .15)]); line([(.5, .15), (.5, .88)])
    else:
        base_icon(draw, kind, x, y, s, color)


def _wrap(text: str, width: float, measure: Callable[[str], float]) -> List[str]:
    lines, current = [], ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if measure(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def layout(items: List[Row]) -> Tuple[List[Tuple[str, Row, float]], float]:
    """A posição de cada cabeçalho de grupo e de cada linha na coluna (a partir de 0) e a altura total."""
    out, y = [], 0.0
    for row in items:
        if row.group:
            if out:
                y += 6
            out.append(('group', row, y))
            y += GROUP_H
        out.append(('row', row, y))
        y += ROW_H + ROW_GAP
    return out, y - ROW_GAP


def draw_settings(m, image: Image.Image, draw: ImageDraw.ImageDraw, text, font, add_hit) -> None:
    """Desenha abas, linhas e painel na imagem do menu; ``add_hit(rect, action)`` registra as áreas de clique."""
    from src.interactive.game_menus import text_stamp
    factor = m.preferences.data['text_scale']
    gl_ready = m.quad is not None
    items = rows(m.settings_tab, m.draft, gl_ready)
    placed, total = layout(items)
    lx, ly, lr, lb = LIST
    view_h = lb - ly
    focused_id = m.focused_row_id() if m.hits_order else (items[0].id if items else None)
    # a coluna rola para manter a linha em foco à vista (a roda do mouse rola livre)
    if m.follow_focus and focused_id:
        found = next(((y, r) for kind, r, y in placed if kind == 'row' and r.id == focused_id), None)
        if found is not None:
            top, focused_row = found
            header = top - GROUP_H if focused_row.group else top
            if header < m.list_scroll:
                m.list_scroll = header
            elif top + ROW_H > m.list_scroll + view_h:
                m.list_scroll = top + ROW_H - view_h
    m.list_scroll = max(0.0, min(m.list_scroll, max(0.0, total - view_h)))

    # ---- linhas, numa camada recortada pela coluna
    layer = Image.new('RGBA', (lr - lx, view_h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    def ltext(at, value, size, color=INK, heading=False):
        stamp, left, top = text_stamp(str(value), round(size * factor), color, heading)
        layer.alpha_composite(stamp, (round(at[0] + left), round(at[1] + top)))

    def fit(value, size, width):
        f = font(round(size * factor))
        if ld.textlength(value, font=f) <= width:
            return value
        while value and ld.textlength(value + '…', font=f) > width:
            value = value[:-1]
        return value + '…'

    chevrons = []
    for kind, row, y in placed:
        top = y - m.list_scroll
        if kind == 'group':
            if -GROUP_H < top < view_h:
                ltext((4, top + 8), row.group.upper(), 13, '#8A7A55')
            continue
        action = 'row:' + row.id
        visible = top + ROW_H > 0 and top < view_h
        if not visible:
            add_hit((0, 0, -1, -1), action)
            continue
        glow = m._effects.get(action, 1. if focused_id == row.id else 0.)
        on = glow > .25
        x0, x1 = 2, lr - lx - 4
        ld.rounded_rectangle((x0, top + 3, x1, top + ROW_H + 3), 10, fill='#D9CCAE')
        ld.rounded_rectangle((x0, top, x1, top + ROW_H), 10, fill='#FFF9EC' if on else '#F8F0DF',
                             outline='#A17A34' if on else '#D3C6A6', width=2 if on else 1)
        if glow > .05:
            ld.rounded_rectangle((x0 + 3, top + 10, x0 + 6, top + ROW_H - 10), 2, fill='#BC923E')
        ld.rounded_rectangle((x0 + 14, top + 10, x0 + 54, top + 50), 8, fill='#EEE3C6' if on else '#F1E8D2')
        muted_row = row.kind == 'info'
        _icon(ld, row.icon, x0 + 23, top + 19, 22, GREEN if on and not muted_row else '#7C8270')
        value = 'Pressione uma tecla…' if row.kind == 'bind' and m.capture == row.key \
            else row_value(row, m.draft, gl_ready)
        value_font = font(round(17 * factor))
        value_w = ld.textlength(value, font=value_font)
        right = x1 - 18
        if row.kind == 'toggle':
            sx = right - 46
            enabled = bool(m.draft[row.key])
            ld.rounded_rectangle((sx, top + 18, sx + 46, top + 42), 12, fill=GREEN if enabled else '#B6B8A5')
            knob = sx + 26 if enabled else sx + 4
            ld.ellipse((knob, top + 22, knob + 16, top + 38), fill=GOLD if enabled else '#FBF4E4')
            value_left = sx - 10 - value_w
            ltext((value_left, top + 17), value, 17, INK)
        elif row.kind == 'choice':
            arrow = '#4D725B' if on else '#A9A58F'
            ld.polygon([(right - 8, top + 22), (right, top + 30), (right - 8, top + 38)], fill=arrow)
            value_left = right - 18 - value_w
            ltext((value_left, top + 17), value, 17, INK)
            left_arrow = value_left - 12
            ld.polygon([(left_arrow, top + 22), (left_arrow - 8, top + 30), (left_arrow, top + 38)], fill=arrow)
            value_left = left_arrow - 14
            chevrons.append(((left_arrow - 14, top + 10, left_arrow + 6, top + 50), f'shift:{row.id}:-1'))
            chevrons.append(((right - 14, top + 10, right + 6, top + 50), f'shift:{row.id}:1'))
        else:
            value_left = right - value_w
            ltext((value_left, top + 17), value, 17, MUTED if muted_row else INK)
        title_w = value_left - (x0 + 70) - 16
        ltext((x0 + 70, top + 9), fit(row.title, 17, title_w), 17, MUTED if muted_row else INK)
        ltext((x0 + 70, top + 34), fit(row.detail, 12, title_w), 12, MUTED)
        clip_top, clip_bottom = max(top, 0), min(top + ROW_H, view_h)
        add_hit((lx + x0, ly + clip_top, lx + x1, ly + clip_bottom), action)
    image.alpha_composite(layer, (lx, ly))
    # sinais de que há mais acima ou abaixo
    if m.list_scroll > 0.5:
        draw.polygon([(lx + (lr - lx) / 2 - 9, ly - 4), (lx + (lr - lx) / 2 + 9, ly - 4), (lx + (lr - lx) / 2, ly - 13)],
                     fill='#A98C50')
    if m.list_scroll + view_h < total - 0.5:
        draw.polygon([(lx + (lr - lx) / 2 - 9, lb + 6), (lx + (lr - lx) / 2 + 9, lb + 6), (lx + (lr - lx) / 2, lb + 15)],
                     fill='#A98C50')

    # ---- abas
    pill_font = font(round(16 * factor))
    widths = [draw.textlength(label, font=pill_font) + 40 for _, label in TABS]
    gap = 10
    total_w = sum(widths) + gap * (len(TABS) - 1)
    tx = 660 - total_w / 2
    ty = 140
    for badge_x, letter in ((tx - 44, 'Q'), (tx + total_w + 14, 'E')):
        draw.rounded_rectangle((badge_x, ty + 5, badge_x + 30, ty + 33), 6, fill='#EDE3CB', outline='#C7B68D')
        text((badge_x + 9, ty + 9), letter, 13, MUTED)
    for (tab, label), w in zip(TABS, widths):
        selected = tab == m.settings_tab
        action = 'tab:' + tab
        glow = m._effects.get(action, 0.)
        draw.rounded_rectangle((tx, ty, tx + w, ty + 38), 19,
                               fill=GREEN if selected else ('#FFF9EC' if glow > .25 else '#F8F0DF'),
                               outline=GREEN if selected else ('#A17A34' if glow > .25 else '#C7B68D'),
                               width=2 if glow > .25 else 1)
        text((tx + 20, ty + 7), label, 16, '#FBF4E4' if selected else INK)
        add_hit((tx, ty, tx + w, ty + 38), action)
        tx += w + gap

    for rect, action in chevrons:
        r = (lx + rect[0], ly + max(rect[1], 0), lx + rect[2], ly + min(rect[3], view_h))
        if r[3] > r[1]:
            add_hit(r, action)

    # ---- painel da direita
    px, py, pr, pb = PANEL
    draw.rounded_rectangle((px, py + 4, pr, pb + 4), 14, fill='#D9CCAE')
    draw.rounded_rectangle((px, py, pr, pb), 14, fill=CARD, outline=LINE)
    inner = pr - px - 56

    def drawn(size):
        # o text() dos menus aumenta em 2 os tamanhos até 15 (ver GameMenus.image)
        return font(round((size + 2 if size <= 15 else size) * factor))

    measure_help = lambda s: draw.textlength(s, font=drawn(15))
    row = next((r for r in items if r.id == focused_id), None)
    cx, cy = px + 28, py + 26
    if row is None:
        label = dict(TABS)[m.settings_tab]
        text((cx, cy), 'SEÇÃO', 12, '#8A7A55')
        text((cx, cy + 26), label, 28, INK, True)
        for i, line in enumerate(_wrap(TAB_TEXT[m.settings_tab], inner, measure_help)):
            text((cx, cy + 82 + i * 24), line, 15, MUTED)
        text((cx, pb - 46), '↑ ↓ escolher · ← → mudar · Enter alterar', 12, MUTED)
        return
    group = None
    for item in items:   # o grupo é o do último cabeçalho até a linha
        group = item.group or group
        if item is row:
            break
    text((cx, cy), (group or dict(TABS)[m.settings_tab]).upper(), 12, '#8A7A55')
    text((cx, cy + 26), row.title, 26, INK, True)
    y = cy + 80
    for line in _wrap(row.help, inner, measure_help):
        text((cx, y), line, 15, MUTED)
        y += 24
    y += 14
    facts = list(row.facts)
    if row.key in CHOICES:
        facts.insert(0, ('Padrão', value_text(row.key, CHOICES[row.key][0])))
    if row.kind == 'bind':
        facts.insert(0, ('Padrão', key_name(ACTIONS[row.key][1], gl_ready)))
    for label, value in facts:
        text((cx, y), label, 13, MUTED)
        lines = _wrap(value, inner - 120, lambda s: draw.textlength(s, font=drawn(13)))
        for i, part in enumerate(lines):
            text((cx + 120, y + i * 22), part, 13, INK)
        y += 22 * max(1, len(lines)) + 8
    if row.kind == 'choice':
        # as alternativas, a atual em destaque (como as pílulas do Steam for Consoles)
        y += 8
        text((cx, y), 'OPÇÕES', 12, '#8A7A55')
        y += 26
        bx = cx
        pill = drawn(13)
        for option in CHOICES[row.key][1]:
            label = value_text(row.key, option)
            w = draw.textlength(label, font=pill) + 24
            if bx + w > pr - 28:
                bx, y = cx, y + 36
            current = option == m.draft[row.key]
            draw.rounded_rectangle((bx, y, bx + w, y + 28), 14, fill=GREEN if current else '#F3EAD6',
                                   outline=GREEN if current else '#C7B68D')
            text((bx + 12, y + 5), label, 13, '#FBF4E4' if current else MUTED)
            bx += w + 8
    hint = {'bind': 'Enter trocar a tecla · Esc cancelar · Q E abas',
            'toggle': 'Enter ou ← → liga e desliga · Q E abas',
            'info': '↑ ↓ escolher · Q E abas'}.get(row.kind, '← → mudar · Enter próximo · Q E abas')
    text((cx, pb - 46), hint, 12, MUTED)
