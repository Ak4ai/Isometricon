"""Menus nativos do jogo, com layout inspirado no protótipo Figma."""
from __future__ import annotations
import copy
import json
import time
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
import glfw
from src.core.game_storage import ACTIONS, Preferences, WorldLibrary
from src.interactive.menu_style import icon, world_thumbnail, menu_base

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


@lru_cache(maxsize=1024)
def text_stamp(value, size, color, heading):
    """Reutiliza os glifos já rasterizados durante hover e transições."""
    selected_font=font(size,heading)
    left,top,right,bottom=selected_font.getbbox(value)
    stamp=Image.new('RGBA',(max(1,right-left),max(1,bottom-top)))
    ImageDraw.Draw(stamp).text((-left,-top),value,fill=color,font=selected_font)
    return stamp,left,top


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
        self.scrim_quad = None
        self._last_effect_signature = ()
        self._worlds = None
        self._raster_state = None
        self._rendered_pressed = None
        self._control_bounds = {}
        self._layout_hits = []
        self.scene_image = None
        self.scene_owner = None
        self.landscape = None
        self._effects = {}
        self._last_animation = time.monotonic()
        self._effect_time = self._last_animation
        self._pressed = None
        self._transition_started = time.monotonic()
        if create_gl:
            from src.rendering.hud_quad import HudQuad
            self.quad = HudQuad()
            self.scrim_quad = HudQuad()
            self.scrim_quad.set_image(Image.new('RGBA',(1,1),(9,26,21,100)))

        self.draft = copy.deepcopy(self.preferences.data)
        self.last_image = None

    @property
    def active(self):
        return self.page != 'game'

    def go(self, page):
        if self.page == 'create' or page == 'create':
            self.fields = {'name': '', 'seed': ''}
        self.page, self.message, self.field, self.capture = page, '', None, None
        self._effects.clear()
        self._raster_state = None
        self._last_effect_signature = ()
        if page == 'worlds':
            self._worlds = self.library.list()
        self._pressed = None
        self._transition_started = time.monotonic()
        self.scroll, self.focus, self.dirty = 0, 0, True
        self.hits = []
        self._layout_hits = []

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
        self.scene_image = image
        self.scene_owner = self.world["id"] if self.world else None

    def adjust_sensitivity(self, x):
        rect = next((r for r,a in self.hits if a=='sensitivity'),None)
        if rect:
            scale=(rect[2]-rect[0])/538
            percent=max(0.,min(1.,(x-(rect[2]-186*scale))/(116*scale)))
            self.draft['sensitivity']=round(.25+percent*1.75,2)
            self.dirty=True

    def hover(self, x, y):
        if self._pressed == 'sensitivity':
            self.adjust_sensitivity(x)
        for index, (rect, _) in enumerate(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                if self.focus != index:
                    self.focus, self.dirty = index, True
                break

    def mouse_button(self, x, y, action):
        if action == glfw.PRESS:
            self._pressed = next((a for rect,a in self.hits if rect[0]<=x<=rect[2] and rect[1]<=y<=rect[3]), None)
            self.dirty = True
        elif action == glfw.RELEASE:
            if self._pressed == 'sensitivity':
                self.adjust_sensitivity(x)
                self._pressed = None
                return
            pressed, self._pressed = self._pressed, None
            self.dirty = True
            if pressed and any(a==pressed and rect[0]<=x<=rect[2] and rect[1]<=y<=rect[3] for rect,a in self.hits):
                self.activate(pressed)

    def click(self, x, y):
        for index, (rect, action) in enumerate(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                self.focus = index
                self.activate(action)
                return

    def image(self, width, height, *, native=False):
        # Um canvas lógico mantém a leitura e as áreas de clique em diferentes resoluções.
        scale = min(width / 1320, height / 876)
        background = (7, 22, 18, 90) if self.page == 'pause' else (9, 26, 21, 100)
        self.hits = []
        self._control_bounds = {}
        small = self.page in ('pause', 'create', 'discard', 'delete_world')
        left, right = (400, 920) if small else (36, 1284)
        top, bottom = 24, 828
        if self.page == 'welcome':
            left, right, top, bottom = 748, 1272, 126, 782
        if self.page == 'pause':
            left, right = 36, 556
        image = menu_base(self.page=='pause',(left,top,right,bottom)).copy()
        draw = ImageDraw.Draw(image)
        x, end = left + 36, right - 36
        text_factor = self.preferences.data['text_scale']

        def text(at, value, size=16, color=INK, heading=False):
            if size <= 15 and self.page != 'credits':
                size += 2
            stamp,left,top=text_stamp(str(value),round(size*text_factor),color,heading)
            image.alpha_composite(stamp,(round(at[0]+left),round(at[1]+top)))

        def button(y, title, action, subtitle='', primary=False, bx=None, ex=None, color=INK):
            bx, ex = x if bx is None else bx, end if ex is None else ex
            height = (82 if subtitle else 50) if self.page == 'welcome' else 74 if subtitle else 46
            rect = (bx, y, ex, y + height)
            idx = len(self.hits)
            glow = self._effects.get(action, 1. if idx == self.focus else 0.)
            pressed = self._pressed == action
            lift = 2 if pressed else -round(glow*2)
            by = y+lift
            field = action.startswith('field:')
            danger = action.startswith('delete:') or action == 'confirm_delete'
            primary = primary or (self.page=='welcome' and action=='worlds')
            fill = '#D5AA52' if primary else '#F8F0DF'
            if self.page=='welcome' and action=='worlds':
                fill = '#294F40'
                color = '#FBF4E4'
            elif glow > .25 and not field:
                fill = '#EBC371' if primary else '#FFF9EC'
            if danger:
                color = '#914634'
            draw.rounded_rectangle((bx,by+4,ex,by+height+4),7,fill='#B0986E' if not field else '#E1D6BE')
            draw.rounded_rectangle((bx,by,ex,by+height),7,fill=fill,
                                   outline='#A17A34' if glow>.25 else '#C7B68D',width=2 if glow>.25 else 1)
            if not field:
                draw.line((bx+9,by+2,ex-9,by+2),fill='#F8DEA5' if primary else '#FFFCF3')
            if glow>.05 and not field:
                draw.rounded_rectangle((bx+2,by+8,bx+5,by+height-8),2,fill='#BC923E')
            thumbnail = action.startswith('load:')
            decorated = self.page == 'welcome' or danger or action == 'game'
            inset = 100 if thumbnail else 50 if decorated else 16
            kind = 'create' if action=='create_world' else action.split(':')[0]
            if decorated:
                icon(draw,kind,bx+16,by+(height-22)//2,22,color)
            if thumbnail:
                world = next((w for w in self._visible_worlds if w['id']==action[5:]),None)
                if world:
                    thumb=world_thumbnail(self.library,world)
                    image.paste(thumb,(int(bx+10),int(by+10)))
                    draw.rounded_rectangle((bx+9,by+9,bx+89,by+63),4,outline='#B49A68')
            label_size=19 if self.page=='welcome' else 17
            available=ex-bx-inset-18
            toggle = action.startswith('toggle:')
            slider = action == 'sensitivity'
            if toggle:
                title = title.split(' · ')[0]
                available -= 65
                on = self.draft[action[7:]]
                sx, sy = ex-65, by+13
                draw.rounded_rectangle((sx,sy,sx+46,sy+24),12,fill='#355B48' if on else '#B6B8A5')
                knob = sx+26 if on else sx+4
                draw.ellipse((knob,sy+4,knob+16,sy+20),fill='#EAC374' if on else '#FBF4E4')
            if slider:
                title = 'Sensibilidade do pan'
                available -= 190
                sx, ex_track, sy = ex-186, ex-70, by+23
                percent = (self.draft['sensitivity']-.25)/1.75
                knob=sx+(ex_track-sx)*percent
                draw.rounded_rectangle((sx,sy-3,ex_track,sy+3),3,fill='#D2C8AD')
                draw.rounded_rectangle((sx,sy-3,max(sx+1,knob),sy+3),3,fill='#4D725B')
                draw.ellipse((knob-7,sy-7,knob+7,sy+7),fill=GOLD,outline='#A58244')
                text((ex-58,by+13),f"{self.draft['sensitivity']:.2f}×",12)
            label_font=font(round(label_size*text_factor))
            if not field and draw.textlength(title,font=label_font)>available:
                while title and draw.textlength(title+'…',font=label_font)>available:
                    title=title[:-1]
                title+='…'
            text((bx+inset,by+10),title,label_size,color)
            if subtitle:
                subtitle_color = '#D8E2CC' if self.page=='welcome' and action=='worlds' else MUTED
                text((bx+inset,by+44 if self.page=='welcome' else by+40),subtitle,14 if self.page=='welcome' else 12,subtitle_color)
            self.hits.append((rect, action))
            self._control_bounds[action]=(max(0,int(bx)-3),max(0,int(y)-5),
                                          min(1320,int(ex)+3),min(876,int(y+height)+9))

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
            icon(draw,'cube',94,96,62,'#E7B65E')
            draw.line((177,124,357,124),fill='#B8944F',width=1)
            text((94,180),'ISOMETRICON · SINTA-SE EM CASA',13,'#E7C980')
        title = {'welcome':'Isometricon','pause':'Hora do descanso?','create':'Uma nova aventura',
                 'worlds':'Suas aventuras','settings':'Configurações','credits':'Sobre o Isometricon',
                 'discard':'Alterações pendentes','delete_world':'Excluir mundo?'}.get(self.page,'')
        if self.page == 'welcome':
            # A marca fica sobre a paisagem, com sombra para manter o contraste.
            text((95,232),title,76,'#122C22',True)
            text((92,228),title,76,'#FFF3D4',True)
            text((96,350),'Um mundo. Infinitas histórias.',23,'#F4E4C4')
            text((96,396),'Encontre seu caminho entre',18,'#D4DDCA')
            text((96,426),'blocos, mapas e novas aventuras.',18,'#D4DDCA')
            draw.line((96,495,340,495),fill='#A98C50')
            draw.polygon(((350,490),(355,495),(350,500),(345,495)),fill='#E7B65E')
            text((x,166),'SEU PRÓXIMO CAPÍTULO',13,'#7E673A')
            text((x,200),'A aventura espera.',30,INK,True)
            button(278,'Nova aventura','create','Toda história começa com uma semente',True)
            button(384,'Continuar aventura','worlds','O mundo aguarda seu retorno')
            draw.line((x,500,end,500),fill=LINE)
            button(530,'Configurações','settings')
            button(598,'Sobre','credits',bx=x,ex=x+207)
            button(598,'Sair','exit',bx=x+225,ex=end)
            text((x,711),'Explore. Crie. Volte para contar.',14,MUTED)
            text((96,742),'Versão '+self.version,14,'#D3D9C6')
        else:
            text((x,83),title,34 if small else 42,heading=True)
            draw.line((x,64,min(x+90,end),64),fill='#B38A3F',width=2)
        if self.page == 'pause':
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
            if self._worlds is None:
                self._worlds = self.library.list()
            worlds = self._worlds
            self._visible_worlds = worlds
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
                    draw.rounded_rectangle((cx,cy+4,cx+578,cy+252),8,fill='#CFBFA0')
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
                     'Pedro Henrique Gontijo Moura (PedroAugusto08)',
                     'Rafael Adolfo Ferreira (Radsfer)',
                     'Samuel Silva Gomes (samuelsilvg)',
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
        self.offset = ((width-round(1320*scale))//2,(height-round(876*scale))//2)
        self.hits = [((r[0]*scale+self.offset[0], r[1]*scale+self.offset[1],
                       r[2]*scale+self.offset[0], r[3]*scale+self.offset[1]), a) for r,a in self.hits]
        self._layout_hits = self.hits.copy()
        if native:
            return image
        resized = image.resize((max(1,round(1320*scale)),max(1,round(876*scale))),Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA',(width,height),background)
        canvas.alpha_composite(resized,self.offset)
        return canvas

    def prepare_background(self, wait=False):
        if self.quad and self.landscape is None:
            from src.interactive.menu_landscape import MenuLandscape
            self.landscape = MenuLandscape()
        if self.landscape:
            self.landscape.prepare(wait)

    def render(self, width, height):
        if not self.active or width <= 0 or height <= 0:
            return
        now = time.monotonic()
        reduced = self.preferences.data['reduce_motion']
        selected = self.hits[self.focus % len(self.hits)][1] if self.hits else None
        step = min((now-self._effect_time)*14,1.)
        self._effect_time = now
        for _, action in self.hits:
            old = self._effects.get(action,0.)
            target = 1. if action==selected else 0.
            value = target if reduced else old+(target-old)*step
            self._effects[action] = value
        signature = tuple((action,round(value*2),value>.25,value>.05)
                          for action,value in self._effects.items())
        if signature != self._last_effect_signature:
            self.dirty = True
        if self.dirty or self.size != (width, height):
            # Modelo estável: somente os controles que mudaram precisam voltar à GPU.
            world_state=tuple((self.world or {}).get(k) for k in ('id','name','seed','played','saved_at'))
            state=(self.page,width,height,tuple(self.fields.items()),self.field,self.capture,
                   self.message,self.scroll,self.version,world_state,
                   self.preferences.data['text_scale'],json.dumps(self.draft,sort_keys=True))
            region=None
            redraw=True
            if self.quad and state==self._raster_state:
                previous={entry[0]:entry[1:] for entry in self._last_effect_signature}
                current={entry[0]:entry[1:] for entry in signature}
                changed={a for a in previous.keys()|current.keys() if previous.get(a)!=current.get(a)}
                if self._rendered_pressed != self._pressed:
                    changed.update(a for a in (self._rendered_pressed,self._pressed) if a)
                bounds=[self._control_bounds[a] for a in changed if a in self._control_bounds]
                if bounds:
                    region=(min(r[0] for r in bounds),min(r[1] for r in bounds),
                            max(r[2] for r in bounds),max(r[3] for r in bounds))
                else:
                    redraw=False
            if redraw:
                self.last_image = self.image(width,height,native=self.quad is not None)
                if self.quad:
                    self.quad.set_image(self.last_image,region=region)
            self.size, self.dirty = (width, height), False
            self._last_animation = now
            self._last_effect_signature = signature
            self._raster_state = state
            self._rendered_pressed = self._pressed
        if self.quad:
            paused = self.page == 'pause' or (self.page in ('settings','discard') and self.return_page=='pause')
            if paused and self.scene_quad:
                self.scene_quad.draw(0,0,width,height)
            else:
                self.prepare_background()
                self.landscape.draw(width,height,reduced)
            scrim_alpha = .9 if self.page=='pause' else 1.
            self.scrim_quad.draw(0,0,width,height,size=(width,height),opacity=scrim_alpha)
            scale=min(width/1320,height/876)
            progress = 1. if reduced else min(1.,(now-self._transition_started)/.18)
            slide=8*(1-progress)*scale
            self.hits=[((r[0],r[1]+slide,r[2],r[3]+slide),a) for r,a in self._layout_hits]
            self.quad.draw(self.offset[0],self.offset[1]+slide,width,height,
                           size=(1320*scale,876*scale),opacity=.72+.28*progress)

    def delete(self):
        if self.scrim_quad:
            self.scrim_quad.delete()
        if self.landscape:
            self.landscape.delete()
        if self.scene_quad:
            self.scene_quad.delete()
        if self.quad:
            self.quad.delete()
