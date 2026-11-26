"""A tela de criação do personagem desenha sem ambientação: nada do quadro do mundo pode ficar ligado."""
from src.rendering.ambience import Ambience


class FakeShader:
    def __init__(self):
        self.defines = {"EDGE_FOG": True, "MIST": True, "MIST_RAYS": True, "SHADOW_ACCUM": True}
        self.values = {}
        self.bound = 0

    def set_define(self, name, on):
        self.defines[name] = bool(on)

    def use(self):
        self.bound += 1

    def __getattr__(self, name):
        if name.startswith("set_"):
            return lambda uniform, *values: self.values.__setitem__(uniform, values)
        raise AttributeError(name)


def test_neutral_desliga_as_variantes_que_o_mundo_deixou():
    shader = FakeShader()
    Ambience.neutral(shader)
    # a névoa da borda cobria o personagem do /skin interface com a cor do fundo
    assert not any(shader.defines.values())
    assert shader.values["u_MistAmount"] == (0.0,)
    assert shader.values["u_FogAmount"] == (0.0,)


def test_neutral_deixa_o_programa_do_mundo_em_uso():
    shader = FakeShader()
    Ambience.neutral(shader)
    assert shader.bound >= 1
