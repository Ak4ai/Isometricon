"""Menus nativos do jogo, com layout inspirado no protótipo Figma."""
from __future__ import annotations
import copy
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
import glfw
from src.core.game_storage import ACTIONS, Preferences, WorldLibrary

PANEL = '#F2E8D1'
CARD = '#FBF4E4'
INK = '#293E34'
MUTED = '#6B7160'
GOLD = '#E7B65E'
LINE = '#CFC5AB'


@lru_cache(maxsize=64)
def font(size, heading=False):
    candidates = ['georgia.ttf', 'DejaVuSerif.ttf'] if heading else ['segoeui.ttf', 'DejaVuSans.ttf']
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


class GameMenus:
    def __init__(self, version, preferences=None, library=None, create_gl=True):
        self.version = version
        self.preferences = preferences or Preferences()
        self.library = library or WorldLibrary()
        self.page = 'welcome'
        self.return_page = 'welcome'
        self.world = None
        self.result = None
        self.fields = {'name': '', 'seed': ''}
        self.field = None
        self.capture = None
        self.message = ''
        self.pending_delete = None
        self.worlds_scroll = 0
        self.scroll = 0
        self.focus = 0
        self.hits = []
        self.dirty = True
        self.size = (0, 0)
        self.quad = None
        self.scene_quad = None
        if create_gl:
            from src.rendering.hud_quad import HudQuad
            self.quad = HudQuad()
        self.draft = copy.deepcopy(self.preferences.data)
        self.last_image = None

    @property
    def active(self):
        return self.page != 'game'

    def go(self, page):
        if self.page == 'create' or page == 'create':
            self.fields = {'name': '', 'seed': ''}
        self.page, self.message, self.field, self.capture = page, '', None, None
        self.scroll, self.focus, self.dirty = 0, 0, True
        self.hits = []

    def settings(self):
        self.return_page = self.page
        self.draft = copy.deepcopy(self.preferences.data)
        self.go('settings')

    def back(self):
        if self.capture:
            self.capture = None
            self.dirty = True
        elif self.page == 'settings' and self.draft != self.preferences.data:
            self.go('discard')
        elif self.page in ('settings', 'discard'):
            self.go(self.return_page)
        elif self.page == 'delete_world':
            self.activate('cancel_delete')
        elif self.page == 'pause':
            self.go('game')
        elif self.page in ('create', 'worlds', 'credits'):
            self.go('welcome')

    def activate(self, action):
        self.message = ''
        try:
            if action in ('create', 'worlds', 'credits', 'welcome', 'game'):
                self.go(action)
            elif action == 'settings':
                self.settings()
            elif action == 'back':
                self.back()
            elif action == 'keep':
                self.page, self.dirty = 'settings', True
                self.hits = []
            elif action == 'discard':
                self.go(self.return_page)
            elif action == 'exit':
                self.result = ('exit', None)
            elif action == 'save_exit':
                self.result = ('save_exit', None)
            elif action == 'create_world':
                self.world = self.library.create(self.fields['name'], self.fields['seed'])
                self.result = ('play', self.world)
                self.go('game')
            elif action.startswith('load:'):
                self.world = next(w for w in self.library.list() if w['id'] == action[5:])
                self.result = ('play', self.world)
                self.go('game')
            elif action.startswith('delete:'):
                self.pending_delete = next(w for w in self.library.list() if w['id'] == action[7:])
                self.worlds_scroll = self.scroll
                self.go('delete_world')
            elif action == 'cancel_delete':
                self.pending_delete = None
                self.go('worlds')
                self.scroll = self.worlds_scroll
            elif action == 'confirm_delete' and self.pending_delete:
                deleted_id = self.pending_delete['id']
                self.library.delete(deleted_id)
                # O mundo aberto anteriormente não deve ser recriado pelo save ao fechar.
                if self.world and self.world['id'] == deleted_id:
                    self.world = None
                self.pending_delete = None
                self.go('worlds')
                self.scroll = self.worlds_scroll
                self.message = 'Mundo excluído.'
            elif action.startswith('field:'):
                self.field = action[6:]
            elif action.startswith('bind:'):
                self.capture = action[5:]
            elif action.startswith('toggle:'):
                key = action[7:]
                self.draft[key] = not self.draft[key]
            elif action == 'sensitivity':
                self.draft['sensitivity'] = round(.25 + (self.draft['sensitivity'] % 2), 2)
            elif action == 'text_scale':
                self.draft['text_scale'] = 1.25 if self.draft['text_scale'] == 1 else 1
            elif action == 'defaults':
                from src.core.game_storage import DEFAULTS
                self.draft = copy.deepcopy(DEFAULTS)
            elif action == 'apply':
                previous = self.preferences.data
                self.preferences.data = copy.deepcopy(self.draft)
                try:
                    self.preferences.save()
                except OSError:
                    self.preferences.data = previous
                    raise
                self.message = 'Preferências salvas.'
            elif action in ('prev', 'next'):
                self.scroll = max(0, self.scroll + (-1 if action == 'prev' else 1))
        except (OSError, ValueError, StopIteration) as error:
            self.message = str(error) or 'Não foi possível abrir esse mundo.'
        self.dirty = True

    def key(self, key, action, mods=0):
        if not self.active:
            return False
        if action not in (glfw.PRESS, glfw.REPEAT):
            return True
        if self.capture:
            if key == glfw.KEY_ESCAPE:
                self.capture = None
            else:
                old = self.preferences.data
                self.preferences.data = self.draft
                try:
                    self.preferences.bind(self.capture, key)
                    self.capture = None
                    self.message = ''
                except ValueError as error:
                    self.message = str(error)
                finally:
                    self.preferences.data = old
            self.dirty = True
            return True
        if key == glfw.KEY_ESCAPE:
            self.back()
        elif self.field and key == glfw.KEY_BACKSPACE:
            self.fields[self.field] = self.fields[self.field][:-1]
        elif self.field and key == glfw.KEY_SPACE:
            return True  # O caractere espaço chega pelo callback Unicode.
        elif key in (glfw.KEY_TAB, glfw.KEY_DOWN, glfw.KEY_UP):
            self.field = None
            self.focus = (self.focus + (-1 if key == glfw.KEY_UP or mods & glfw.MOD_SHIFT else 1)) % max(len(self.hits), 1)
        elif key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER, glfw.KEY_SPACE):
            if self.field:
                self.field = None
            elif self.hits:
                self.activate(self.hits[self.focus % len(self.hits)][1])
        self.dirty = True
        return True

    def char(self, codepoint):
        if self.active and self.field and not self.capture and chr(codepoint).isprintable():
            limit = 64 if self.field == 'name' else 100
            self.fields[self.field] = (self.fields[self.field] + chr(codepoint))[:limit]
            self.dirty = True

    def capture_scene(self, width, height):
        if self.quad is None:
            return
        import OpenGL.GL as gl
        from src.rendering.hud_quad import HudQuad
        pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        image = Image.frombytes('RGBA', (width, height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if self.scene_quad is None:
            self.scene_quad = HudQuad()
        self.scene_quad.set_image(image)

    def hover(self, x, y):
        for index, (rect, _) in enumerate(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                if self.focus != index:
                    self.focus, self.dirty = index, True
                break

    def click(self, x, y):
        for index, (rect, action) in enumerate(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                self.focus = index
                self.activate(action)
                return

    def image(self, width, height):
        # Um canvas lógico mantém a leitura e as áreas de clique em diferentes resoluções.
        scale = min(width / 1320, height / 876)
        background = (0, 0, 0, 90) if self.page == 'pause' else (20, 40, 34, 255)
        image = Image.new('RGBA', (1320, 876), background)
        draw = ImageDraw.Draw(image)
        self.hits = []
        small = self.page in ('pause', 'create', 'discard', 'delete_world')
        left, right = (400, 920) if small else (36, 1284)
        top, bottom = 24, 828
        if self.page == 'welcome':
            left, right, top, bottom = 130, 1190, 108, 748
        if self.page == 'pause':
            left, right = 36, 556
        draw.rounded_rectangle((left, top, right, bottom), 16, fill=PANEL, outline='#E6D7B5', width=2)
        draw.rounded_rectangle((left + 8, top + 8, right - 8, bottom - 8), 10, outline=LINE)
        x, end = left + 36, right - 36
        text_factor = self.preferences.data['text_scale']

        def text(at, value, size=16, color=INK, heading=False):
            if size <= 15 and self.page != 'credits':
                size += 2
            draw.text(at, str(value), fill=color, font=font(round(size * text_factor), heading))

        def button(y, title, action, subtitle='', primary=False, bx=None, ex=None, color=INK):
            bx, ex = x if bx is None else bx, end if ex is None else ex
            height = (82 if subtitle else 50) if self.page == 'welcome' else 74 if subtitle else 46
            rect = (bx, y, ex, y + height)
            idx = len(self.hits)
            draw.rounded_rectangle(rect, 8, fill=GOLD if primary else CARD,
                                   outline='#5B7153' if idx == self.focus else LINE,
                                   width=2 if idx == self.focus else 1)
            if self.page == 'worlds':
                label_font = font(round(17 * text_factor))
                if draw.textlength(title, font=label_font) > ex-bx-32:
                    while title and draw.textlength(title + '…', font=label_font) > ex-bx-32:
                        title = title[:-1]
                    title += '…'
            text((bx + 16, y + 10), title, 19 if self.page == 'welcome' else 17, color)
            if subtitle:
                text((bx + 16, y + 44 if self.page == 'welcome' else y + 40), subtitle, 14 if self.page == 'welcome' else 12, MUTED)
            self.hits.append((rect, action))

        def input_field(y, field, placeholder):
            value = self.fields[field]
            focused = self.field == field
            label = value if value else '' if focused else placeholder
            if focused:
                label += ' |'
            # Exibe o fim do texto durante a digitação sem invadir a borda do campo.
            field_font = font(round(17 * text_factor))
            while label and draw.textlength(label, font=field_font) > end-x-32:
                label = label[1:]
            button(y, label, 'field:' + field, color=INK if value or focused else MUTED)

        if self.page == 'welcome':
            text((x, 160), 'ISOMETRICON · SINTA-SE EM CASA', 13, '#5B7153')
        title = {'welcome': 'Isometricon', 'pause': 'Hora do descanso?', 'create': 'Uma nova aventura',
                 'worlds': 'Suas aventuras', 'settings': 'Configurações', 'credits': 'Sobre o Isometricon',
                 'discard': 'Alterações pendentes', 'delete_world': 'Excluir mundo?'}.get(self.page, '')
        text((x, 230 if self.page == 'welcome' else 83), title, 64 if self.page == 'welcome' else 34 if small else 42, heading=True)
        if self.page == 'welcome':
            text((x, 335), 'Embarque no mundo', 22, MUTED)
            text((x, 370), 'de Isometricon.', 22, MUTED)
            draw.line((660, 180, 660, 650), fill=LINE)
            button(220, 'Comece uma nova aventura', 'create',
                   '~ Toda história começa com uma semente', True, bx=700, ex=1150)
            button(322, 'Continue sua aventura', 'worlds',
                   '~ O mundo aguarda seu retorno', bx=700, ex=1150)
            button(455, 'Configurações', 'settings', bx=700, ex=948)
            button(455, 'Sobre', 'credits', bx=968, ex=1150)
            button(525, 'Sair', 'exit', bx=700, ex=1150)
            text((x, 650), 'Versão ' + self.version, 14, MUTED)
        elif self.page == 'pause':
            text((x, 150), 'Essa história aguardará seu retorno.', 16, MUTED)
            button(240, 'Voltar ao jogo', 'game', primary=True)
            button(306, 'Configurações', 'settings')
            button(372, 'Salvar e voltar ao menu', 'save_exit')
            if self.world:
                text((x, 485), self.world['name'], 24, heading=True)
                text((x, 535), 'Seed: ' + str(self.world['seed']), 15, MUTED)
                text((x, 570), f"Tempo jogado: {int(self.world['played'] // 60)} min", 15, MUTED)
                text((x, 605), 'Último save: ' + self.world.get('saved_at', '—'), 13, MUTED)
            text((x, 735), 'ESC · Voltar ao jogo', 13, MUTED)
        elif self.page == 'create':
            text((x, 166), 'Dê um nome à sua história.', 17, MUTED)
            text((x, 230), 'Nome do mundo', 15)
            input_field(260, 'name', 'Meu mundo')
            text((x, 345), 'Seed · número ou texto (opcional)', 15)
            input_field(375, 'seed', 'Aleatória')
            text((x, 460), 'A mesma seed recria o mesmo terreno.', 14, MUTED)
            button(545, 'Criar e explorar', 'create_world', primary=True)
            button(610, 'Voltar', 'back')
        elif self.page == 'worlds':
            worlds = self.library.list()
            text((x, 145), 'Escolha um mundo para continuar sua aventura.', 16, MUTED)
            if not worlds:
                text((x, 245), 'Ainda não há mundos salvos. Crie sua primeira aventura!', 20)
            self.scroll = min(self.scroll, max(0, (len(worlds) - 1) // 5))
            for i, world in enumerate(worlds[self.scroll * 5:self.scroll * 5 + 5]):
                button(210 + i * 90, world['name'], 'load:' + world['id'],
                       f"Seed {world['seed']} · {world.get('saved_at', '')}", ex=end-160)
                button(224 + i * 90, 'Excluir', 'delete:' + world['id'], bx=end-140, ex=end)
            button(715, 'Voltar', 'back', bx=x, ex=x+200)
            if self.scroll:
                button(715, 'Anterior', 'prev', bx=x+225, ex=x+425)
            if (self.scroll+1)*5 < len(worlds):
                button(715, 'Próxima', 'next', bx=end-200, ex=end)
        elif self.page == 'settings':
            text((x, 136), 'Suas preferências, em todos os mundos.', 15, MUTED)
            for cx in (72, 670):
                for cy in (166, 430):
                    draw.rounded_rectangle((cx, cy, cx+578, cy+248), 8, fill=CARD, outline=LINE)
                    draw.line((cx+20, cy+70, cx+558, cy+70), fill=LINE)
            text((92, 184), 'Som', 28, heading=True)
            text((92, 262), 'Sons da floresta', 16, MUTED)
            text((92, 307), 'Áudio ainda não disponível no motor.', 15, MUTED)
            text((92, 355), 'Os controles serão ativados com o sistema de som.', 12, MUTED)
            text((92, 448), 'Controles', 28, heading=True)
            actions = list(ACTIONS.items())
            self.scroll = min(self.scroll, (len(actions)-1)//3)
            for i, (action, (label, _)) in enumerate(actions[self.scroll*3:self.scroll*3+3]):
                key = self.draft['bindings'][action]
                keyname = glfw.get_key_name(key, 0) if self.quad else None
                value = (keyname or {32: 'Espaço', 340: 'Shift', 341: 'Ctrl'}.get(key, chr(key) if 33 <= key <= 126 else str(key))).upper()
                caption = 'Pressione uma tecla…' if self.capture == action else f'{label}   [{value}]'
                button(512 + i*48, caption, 'bind:' + action, bx=92, ex=630)
            # Paginação compacta deixa o cadastro de ações crescer sem cortar a tela.
            text((304, 657), f'{self.scroll+1}/{(len(actions)+2)//3}', 11, MUTED)
            for rect, action, caption in [((92,658,220,676),'prev','< Anterior'),
                                          ((500,658,630,676),'next','Próxima >')]:
                text((rect[0]+5,rect[1]), caption, 11, MUTED)
                self.hits.append((rect,action))
            text((690, 184), 'Tela', 28, heading=True)
            button(250, 'Sincronização vertical · ' + ('Sim' if self.draft['vsync'] else 'Não'),
                   'toggle:vsync', bx=690, ex=1228)
            button(306, 'Inverter rotação · ' + ('Sim' if self.draft['invert_rotation'] else 'Não'),
                   'toggle:invert_rotation', bx=690, ex=1228)
            button(362, f"Sensibilidade do pan · {self.draft['sensitivity']:.2f}×", 'sensitivity', bx=690, ex=1228)
            text((690, 448), 'Acessibilidade', 28, heading=True)
            button(512, 'Reduzir movimento · ' + ('Sim' if self.draft['reduce_motion'] else 'Não'),
                   'toggle:reduce_motion', bx=690, ex=1228)
            button(568, f"Texto · {int(self.draft['text_scale']*100)}%", 'text_scale', bx=690, ex=1228)
            text((690, 635), 'ESC cancela a escolha de uma tecla.', 13, MUTED)
            draw.line((72,698,1248,698),fill=LINE)
            button(720, 'Voltar', 'back', bx=72, ex=250)
            button(720, 'Restaurar padrões', 'defaults', bx=270, ex=540)
            button(720, 'Aplicar alterações', 'apply', primary=True, bx=960, ex=1248)
            if self.draft != self.preferences.data:
                text((570, 735), 'Alterações não salvas', 13, '#A47B36')
        elif self.page == 'credits':
            lines = ['O Isometricon é um projeto que só foi possível pelo trabalho conjunto de:',
                     'Henrique Araújo de Freitas (Ak4ai)',
                     'Jader Oliveira Silva (0livas)',
                     'João Pedro Rodrigues Silva (Jottynha)',
                     'Rafael Adolfo Ferreira (Radsfer)',
                     'Samuel Silva Gomes (samuelsilvg)',
                     'Pedro Henrique Gontijo Moura (PedroAugusto08)',
                     'Licença do projeto: MIT',
                     'Tecnologias: Python, OpenGL, GLFW, NumPy, Pillow e SciPy',
                     'Assets e integração de roupas: ecossistema Roblox',
                     'Licenças e atribuições dos assets permanecem com seus autores.']
            for i, line in enumerate(lines):
                text((x, 200+i*48), line, 17, MUTED if i else INK)
            button(720, 'Voltar', 'back', bx=x, ex=x+200)
        elif self.page == 'delete_world':
            name = self.pending_delete['name'] if self.pending_delete else ''
            text((x, 210), 'Deseja excluir este mundo?', 20)
            # Quebra pelo espaço disponível, inclusive em nomes longos sem espaços.
            lines, current = [], ''
            for char in name:
                if draw.textlength(current + char, font=font(round(22*text_factor), True)) > end-x:
                    lines.append(current)
                    current = char
                else:
                    current += char
            lines.append(current)
            for i, line in enumerate(lines[:3]):
                text((x, 265+i*32), line, 22, heading=True)
            text((x, 390), 'O progresso salvo será apagado.', 17, MUTED)
            text((x, 420), 'Essa ação não pode ser desfeita.', 17, MUTED)
            button(510, 'Cancelar', 'cancel_delete', primary=True)
            button(580, 'Excluir mundo', 'confirm_delete')
        elif self.page == 'discard':
            text((x, 220), 'Sair sem aplicar suas preferências?', 18)
            button(330, 'Continuar ajustando', 'keep', primary=True)
            button(400, 'Descartar alterações', 'discard')
        if self.message:
            text((x, 785), self.message[:110], 13, '#9F4A32')
        resized = image.resize((max(1, round(1320*scale)), max(1, round(876*scale))), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (width, height), background)
        self.offset = ((width-resized.width)//2, (height-resized.height)//2)
        canvas.alpha_composite(resized, self.offset)
        self.hits = [((r[0]*scale+self.offset[0], r[1]*scale+self.offset[1],
                       r[2]*scale+self.offset[0], r[3]*scale+self.offset[1]), a) for r, a in self.hits]
        return canvas

    def render(self, width, height):
        if not self.active or width <= 0 or height <= 0:
            return
        if self.dirty or self.size != (width, height):
            self.last_image = self.image(width, height)
            if self.quad:
                self.quad.set_image(self.last_image)
            self.size, self.dirty = (width, height), False
        if self.quad:
            if self.page == 'pause' and self.scene_quad:
                self.scene_quad.draw(0, 0, width, height)
            self.quad.draw(0, 0, width, height)

    def delete(self):
        if self.scene_quad:
            self.scene_quad.delete()
        if self.quad:
            self.quad.delete()
