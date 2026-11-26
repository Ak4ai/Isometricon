"""A névoa de guerra do /mestre: o mapa do explorado, o painel e o comando."""
from src.interactive.master_panel import MasterPanel
from src.interactive.skin_commands import SkinCommandHandler
from src.rendering.ambience import Ambience
from src.rendering.fog_of_war import RADIUS, ExploredMap


def test_andar_revela_um_disco_e_guarda():
    m = ExploredMap()
    assert m.reveal(0.5, 0.5)
    assert m.explored(0, 0) and m.explored(int(RADIUS) - 1, 0) and not m.explored(int(RADIUS) + 2, 0)
    assert not m.reveal(0.9, 0.1)                    # o mesmo bloco: nada novo
    m.reveal(20.5, -30.5)                            # outro pedaço, com coordenadas negativas
    assert m.explored(20, -30)
    copy = ExploredMap()
    copy.load(m.to_data())
    assert (copy.window(-40, -50, 96) == m.window(-40, -50, 96)).all()


def test_janela_e_recobrir():
    m = ExploredMap()
    m.reveal(5.5, 5.5)
    window = m.window(0, 0, 16)
    assert window[5, 5] == 255 and window[15, 15] == 0          # [z, x]
    m.clear()
    assert not m.explored(5, 5) and m.window(0, 0, 16).max() == 0


def test_painel_escolhe_o_modo_e_recobre():
    recovered = []
    panel = MasterPanel(Ambience(), create_gl=False)
    panel.on_recover = lambda: recovered.append(1)
    panel.open()
    panel.tab = 'guerra'                              # a névoa de guerra fica na aba Guerra
    panel.draw_image()
    for action in ('war:1', 'recover'):
        rect = next(r for r, a in panel.hits if a == action)
        x, y = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        panel.handle_mouse_button(x, y, True)
        panel.handle_mouse_button(x, y, False)
    assert panel.ambience.fog_war == 1 and recovered == [1]


def test_painel_encolhido_acerta_os_cliques():
    panel = MasterPanel(Ambience(), create_gl=False)
    panel.open()
    panel.tab = 'guerra'
    panel.draw_image()
    rect = next(r for r, a in panel.hits if a == 'war:2')
    panel.scale = 0.5                                 # numa janela baixa o painel é desenhado pela metade
    x = 16 + ((rect[0] + rect[2]) / 2 - 16) * 0.5
    y = 16 + ((rect[1] + rect[3]) / 2 - 16) * 0.5
    panel.handle_mouse_button(x, y, True)
    panel.handle_mouse_button(x, y, False)
    assert panel.ambience.fog_war == 2


def test_comando_guerra_e_recobrir():
    handler = SkinCommandHandler.__new__(SkinCommandHandler)
    handler.master_panel = MasterPanel(Ambience(), create_gl=False)
    recovered = []
    handler.master_panel.on_recover = lambda: recovered.append(1)
    assert SkinCommandHandler.master(handler, ['guerra', 'revela'])[0]
    assert handler.master_panel.ambience.fog_war == 1
    assert SkinCommandHandler.master(handler, ['recobrir'])[0] and recovered == [1]
    assert not SkinCommandHandler.master(handler, ['guerra', 'talvez'])[0]


def test_guerra_salva_e_pinta_o_fundo():
    a = Ambience(fog_war=2)
    assert Ambience.from_dict(a.to_dict()).fog_war == 2
    assert a.background() != Ambience().background()
