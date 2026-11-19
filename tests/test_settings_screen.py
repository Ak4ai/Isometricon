"""A tela de Configurações (abas, linhas, painel) e as preferências gráficas."""
import json

import glfw

from src.core.frame_limiter import FrameLimiter
from src.core.game_storage import DEFAULTS, GRAPHICS, Preferences, WorldLibrary
from src.interactive import settings_screen
from src.interactive.game_menus import GameMenus
from src.rendering.scene_target import scaled_size


def open_settings(tmp_path, tab=None):
    menus = GameMenus('test', Preferences(tmp_path / 'prefs.json'), WorldLibrary(tmp_path / 'worlds'),
                      create_gl=False)
    menus.settings()
    if tab:
        menus.switch_tab(tab=tab)
    menus.render(1320, 876)
    return menus


def click(menus, action):
    rect = next(r for r, a in menus.hits if a == action)
    menus.click((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
    menus.render(1320, 876)


def test_graphics_defaults_and_bad_values_fall_back(tmp_path):
    path = tmp_path / 'prefs.json'
    path.write_text(json.dumps({'msaa': 3, 'fxaa': 1, 'render_scale': 0.75, 'shadows': 'ultra',
                                'fps_limit': True, 'render_distance': 4, 'shadow_strength': 1}))
    data = Preferences(path).data
    assert data['msaa'] == GRAPHICS['msaa'][0]                 # 3 não é uma opção
    assert data['fxaa'] is False                               # 1 não vale como True
    assert data['fps_limit'] == 0                              # True não vale como 1
    assert data['shadows'] == 'high'
    assert data['render_scale'] == 0.75 and data['render_distance'] == 4
    assert data['shadow_strength'] == 1.0                      # o inteiro 1 vale como 1.0


def test_tabs_switch_with_q_e_and_clicks(tmp_path):
    menus = open_settings(tmp_path)
    assert menus.settings_tab == 'general'
    menus.key(glfw.KEY_E, glfw.PRESS)
    menus.render(1320, 876)
    assert menus.settings_tab == 'graphics'
    assert menus.focused_row_id() == 'vsync'
    menus.key(glfw.KEY_Q, glfw.PRESS)
    menus.key(glfw.KEY_Q, glfw.PRESS)
    assert menus.settings_tab == 'access'                      # dá a volta
    menus.render(1320, 876)
    click(menus, 'tab:controls')
    assert menus.settings_tab == 'controls'


def test_graphics_rows_change_the_draft_and_apply_saves(tmp_path):
    menus = open_settings(tmp_path, 'graphics')
    menus.focus = menus.hits_order.index('row:msaa')
    menus.key(glfw.KEY_LEFT, glfw.PRESS)                       # 4x -> 2x
    assert menus.draft['msaa'] == 2
    menus.render(1320, 876)
    click(menus, 'shift:msaa:-1')                              # 2x -> desligado
    assert menus.draft['msaa'] == 0
    click(menus, 'shift:msaa:-1')                              # já no primeiro: fica
    assert menus.draft['msaa'] == 0
    click(menus, 'row:fxaa')                                   # o clique na linha liga e desliga
    assert menus.draft['fxaa'] is True
    menus.focus = menus.hits_order.index('row:shadows')
    menus.key(glfw.KEY_RIGHT, glfw.PRESS)                      # já no último (alta): fica
    assert menus.draft['shadows'] == 'high'
    menus.activate('row:shadows')                              # Enter/clique: o próximo, dando a volta
    assert menus.draft['shadows'] == 'off'
    assert menus.preferences.data['msaa'] == 4                 # nada gravado ainda
    menus.activate('apply')
    saved = Preferences(menus.preferences.path).data
    assert (saved['msaa'], saved['fxaa'], saved['shadows']) == (0, True, 'off')


def test_keyboard_skips_arrow_hits_and_list_follows_focus(tmp_path):
    menus = open_settings(tmp_path, 'graphics')
    assert menus.focused_row_id() == 'vsync'
    menus.focus = menus.hits_order.index('row:vsync')
    for _ in range(len(settings_screen.rows('graphics', DEFAULTS)) - 1):
        menus.key(glfw.KEY_DOWN, glfw.PRESS)
        menus.render(1320, 876)
        assert not menus.hits_order[menus.focus].startswith('shift:')
    assert menus.focused_row_id() == 'shadow_strength'
    assert menus.list_scroll > 0                               # rolou para mostrar a última linha
    rect = next(r for r, a in menus.hits if a == 'row:shadow_strength')
    assert rect[3] > rect[1]                                   # e ela está visível (clicável)
    hidden = next(r for r, a in menus.hits if a == 'row:vsync')
    assert hidden[2] < hidden[0]                               # a primeira saiu de vista: sem área de clique


def test_wheel_scrolls_list(tmp_path):
    menus = open_settings(tmp_path, 'controls')
    menus.wheel(-3)
    menus.render(1320, 876)
    assert menus.list_scroll > 0
    menus.wheel(10)
    menus.render(1320, 876)
    assert menus.list_scroll == 0


def test_binding_row_captures_the_next_key(tmp_path):
    menus = open_settings(tmp_path, 'controls')
    action = next(a for a in menus.hits_order if a.startswith('row:bind_'))
    menus.activate(action)
    assert menus.capture == action[len('row:bind_'):]
    menus.key(glfw.KEY_I, glfw.PRESS)
    assert menus.capture is None
    assert menus.draft['bindings'][action[len('row:bind_'):]] == glfw.KEY_I


def test_every_tab_renders_with_large_text(tmp_path):
    menus = open_settings(tmp_path)
    menus.preferences.data['text_scale'] = 1.25
    for tab, _ in settings_screen.TABS:
        menus.switch_tab(tab=tab)
        menus.render(1320, 876)
        for focus in range(len(menus.hits_order)):
            menus.focus = focus
            menus.dirty = True
            menus.render(1320, 876)


def test_frame_limiter_holds_each_frame_to_the_period():
    now = [0.0]

    def clock():
        now[0] += 0.00001
        return now[0]

    def sleep(seconds):
        now[0] += seconds

    limiter = FrameLimiter(clock=clock, sleep=sleep)
    limiter.wait(50)                       # primeiro quadro: espera um período inteiro (20 ms)
    first = now[0]
    assert 0.0199 < first < 0.0205
    now[0] += 0.005                        # o quadro levou 5 ms
    limiter.wait(50)
    assert abs(now[0] - 2 * first) < 0.001  # fecha 20 ms desde o anterior, não 25
    now[0] += 1.0                          # um travamento de 1 s: não tenta recuperar quadros
    start = now[0]
    limiter.wait(50)
    assert 0.019 < now[0] - start < 0.021
    before = now[0]
    limiter.wait(0)                        # sem limite: volta na hora
    assert now[0] - before < 0.001


def test_scene_size_follows_scale():
    assert scaled_size(1280, 720, 1.0) == (1280, 720)
    assert scaled_size(1280, 720, 0.5) == (640, 360)
    assert scaled_size(1, 1, 0.5) == (1, 1)


def test_coordinates_are_on_by_default_and_can_be_hidden_in_general(tmp_path):
    assert DEFAULTS['show_coords'] is True
    menus = open_settings(tmp_path)                            # abre na aba Geral
    assert 'row:show_coords' in menus.hits_order
    click(menus, 'row:show_coords')
    assert menus.draft['show_coords'] is False and menus.preferences.data['show_coords'] is True
    menus.activate('apply')
    assert Preferences(menus.preferences.path).data['show_coords'] is False
    (tmp_path / 'lixo.json').write_text(json.dumps({'show_coords': 0}), encoding='utf-8')
    assert Preferences(tmp_path / 'lixo.json').data['show_coords'] is True   # valor que não é bool: o padrão
