"""Configurações > Mostrar FPS: desligado por padrão, guardado nas preferências, e o contador de FPS do HUD."""

import json
from src.core.game_storage import DEFAULTS, Preferences, WorldLibrary
from src.interactive.fps_overlay import INTERVAL, FpsOverlay
from src.interactive.game_menus import GameMenus


def make_menus(tmp_path):
    return GameMenus('test', Preferences(tmp_path / 'prefs.json'), WorldLibrary(tmp_path / 'worlds'), create_gl=False)


def test_show_fps_is_off_by_default_and_remembered(tmp_path):
    assert DEFAULTS['show_fps'] is False
    preferences = Preferences(tmp_path / 'prefs.json')
    assert preferences.data['show_fps'] is False
    preferences.data['show_fps'] = True
    preferences.save()
    assert Preferences(tmp_path / 'prefs.json').data['show_fps'] is True
    (tmp_path / 'prefs.json').write_text(json.dumps({'show_fps': 'sim'}), encoding='utf-8')   # lixo: volta ao padrão
    assert Preferences(tmp_path / 'prefs.json').data['show_fps'] is False
    (tmp_path / 'velho.json').write_text(json.dumps({'vsync': False}), encoding='utf-8')       # arquivo de antes da opção
    assert Preferences(tmp_path / 'velho.json').data['show_fps'] is False


def test_the_graphics_tab_has_the_option_and_applying_it_saves(tmp_path):
    menus = make_menus(tmp_path)
    menus.settings()
    menus.switch_tab(tab='graphics')
    menus.render(1320, 876)
    assert 'row:show_fps' in menus.hits_order and 'row:vsync' in menus.hits_order
    assert menus.draft['show_fps'] is False
    menus.activate('row:show_fps')
    assert menus.draft['show_fps'] is True and menus.preferences.data['show_fps'] is False   # só vale ao aplicar
    menus.activate('apply')
    assert menus.preferences.data['show_fps'] is True
    assert json.loads((tmp_path / 'prefs.json').read_text(encoding='utf-8'))['show_fps'] is True
    menus.activate('defaults')
    assert menus.draft['show_fps'] is False                                                     # restaurar padrões desliga


def test_the_counter_reads_the_average_of_each_interval():
    overlay = FpsOverlay()
    assert overlay.text == "0 fps"
    for _ in range(32):                                   # 32 quadros de 1/64 s = meio segundo: 64 fps
        overlay.update(1 / 64)
    assert overlay.fps == 64.0 and overlay.text == "64 fps"
    overlay.update(1 / 16)                                # dentro do intervalo seguinte a leitura não muda
    assert overlay.text == "64 fps"
    for _ in range(7):
        overlay.update(1 / 16)                            # 8 quadros de 1/16 s = meio segundo: 16 fps
    assert overlay.text == "16 fps"
    overlay.update(-1.0)                                  # um tempo negativo não derruba nada
    assert overlay.frames == 1 and INTERVAL == 0.5
