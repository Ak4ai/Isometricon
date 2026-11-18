"""O /mestre: a ambientação (hora, claridade, névoa...), o painel à esquerda e o comando."""
import math


from src.interactive.master_panel import MasterPanel
from src.interactive.skin_commands import SkinCommandHandler
from src.rendering.ambience import DEFAULT_SUN, PRESETS, Ambience


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def test_padrao_e_a_luz_de_sempre():
    a = Ambience()
    assert a.is_default
    assert all(abs(x - y) < 1e-9 for x, y in zip(a.light_direction(), _unit(DEFAULT_SUN)))
    assert a.tint() == (1.0, 1.0, 1.0)


def test_a_hora_move_o_sol_e_escurece_a_noite():
    a = Ambience(hour=12.0)
    noon = a.light_direction()
    a.hour = 7.0
    morning = a.light_direction()
    assert noon[1] > morning[1] > 0
    a.hour = 23.0
    assert a.light_direction()[1] > 0                  # a lua: a luz ainda vem de cima
    assert max(a.tint()) < 0.6 and a.tint()[2] > a.tint()[0]   # escura e azulada


def test_relogio_anda_e_da_a_volta():
    a = Ambience(hour=23.5, clock=3)                   # 60 min de jogo por segundo
    assert a.update(1.0)
    assert abs(a.hour - 0.5) < 1e-9
    a.clock = 0
    assert not a.update(5.0)


def test_carrega_qualquer_coisa_sem_quebrar():
    a = Ambience.from_dict({'hour': '30', 'fog': 400, 'torch': 'x', 'clock': 9})
    assert a.hour == 6.0 and a.fog == 100 and a.torch == 0 and a.clock == 3
    assert Ambience.from_dict(a.to_dict()) == a


def _panel():
    return MasterPanel(Ambience(), create_gl=False)


def _center(panel, action):
    rect = next(r for r, a in panel.hits if a == action)
    return (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2, rect


def test_arrastar_a_hora_e_a_nevoa():
    panel = _panel()
    panel.open()
    panel.draw_image()
    _, y, rect = _center(panel, 'slider:hour')
    assert panel.handle_mouse_button(rect[0] + (rect[2] - rect[0]) * 0.75, y, True)
    assert panel.ambience.hour == 18.0
    _, y, rect = _center(panel, 'slider:fog')
    panel.handle_mouse_button(rect[0], y, False)       # solta a hora
    panel.handle_mouse_button(rect[0] + 1, y, True)
    panel.handle_cursor(rect[2], y)                    # arrasta até o fim
    panel.handle_mouse_button(rect[2], y, False)
    assert panel.ambience.fog == 100


def test_cena_relogio_padrao_e_fechar():
    changes = []
    panel = _panel()
    panel.on_change = lambda: changes.append(1)
    panel.open()
    panel.draw_image()
    for action in ('preset:Noite', 'clock:2'):
        x, y, _ = _center(panel, action)
        panel.handle_mouse_button(x, y, True)
        panel.handle_mouse_button(x, y, False)
    assert panel.ambience.hour == dict(PRESETS)['Noite']['hour'] and panel.ambience.clock == 2
    x, y, _ = _center(panel, 'reset')
    panel.handle_mouse_button(x, y, True)
    panel.handle_mouse_button(x, y, False)
    assert panel.ambience.is_default and len(changes) == 3
    x, y, _ = _center(panel, 'close')
    panel.handle_mouse_button(x, y, True)
    panel.handle_mouse_button(x, y, False)
    assert not panel.is_open


def test_clique_fora_do_painel_passa_para_o_jogo():
    panel = _panel()
    panel.open()
    panel.draw_image()
    assert not panel.handle_mouse_button(900, 300, True)


def test_comando_mestre():
    handler = SkinCommandHandler.__new__(SkinCommandHandler)
    handler.master_panel = None
    assert not SkinCommandHandler.master(handler, [])[0]
    handler.master_panel = _panel()
    assert SkinCommandHandler.master(handler, [])[0] and handler.master_panel.is_open
    ok, text, _ = SkinCommandHandler.master(handler, ['hora', '18:30'])
    assert ok and handler.master_panel.ambience.hour == 18.5 and '18:30' in text
    assert SkinCommandHandler.master(handler, ['cena', 'tempes'])[0]
    assert handler.master_panel.ambience.fog == dict(PRESETS)['Tempestade']['fog']
    assert not SkinCommandHandler.master(handler, ['hora', '25'])[0]
    SkinCommandHandler.master(handler, ['padrao'])
    assert handler.master_panel.ambience.is_default
    SkinCommandHandler.master(handler, ['fechar'])
    assert not handler.master_panel.is_open
