"""A preferência de placa de vídeo do Windows, com um registro de mentira."""
from src import gpu_preference as gp


class FakeRegistry:
    HKEY_CURRENT_USER = object()
    REG_SZ = 1

    def __init__(self, values=None):
        self.values = dict(values or {})

    def CreateKey(self, root, path):
        assert path == gp.KEY
        return self

    def CloseKey(self, key):
        pass

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise OSError
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        del self.values[name]


EXE = r"C:\Jogos\Isometricon.exe"


def test_dedicada_grava_a_preferencia_de_alto_desempenho_uma_vez():
    reg = FakeRegistry()
    assert gp.apply('high', EXE, reg)
    assert reg.values[EXE] == "GpuPreference=2;"
    assert not gp.apply('high', EXE, reg)      # da segunda vez já está lá: não abre o jogo de novo


def test_integrada_troca_a_preferencia():
    reg = FakeRegistry({EXE: "GpuPreference=2;"})
    assert gp.apply('low', EXE, reg)
    assert reg.values[EXE] == "GpuPreference=1;"


def test_automatico_so_apaga_o_que_o_jogo_gravou():
    reg = FakeRegistry({EXE: "GpuPreference=2;"})
    assert gp.apply('auto', EXE, reg) and EXE not in reg.values
    other = FakeRegistry({EXE: "SwapEffectUpgradeEnable=1;"})
    assert not gp.apply('auto', EXE, other) and other.values[EXE] == "SwapEffectUpgradeEnable=1;"


def test_a_preferencia_e_so_do_executavel_do_jogo():
    reg = FakeRegistry({r"C:\outro.exe": "GpuPreference=1;"})
    gp.apply('high', EXE, reg)
    assert reg.values[r"C:\outro.exe"] == "GpuPreference=1;"


def test_abrir_de_novo_repete_os_argumentos_e_marca_para_nao_repetir():
    assert gp.relaunch_command("python.exe", ["src/main.py", "--terrain"], frozen=False) == \
        ["python.exe", "src/main.py", "--terrain", gp.RELAUNCHED]
    assert gp.relaunch_command(EXE, [EXE, "--terrain"], frozen=True) == [EXE, "--terrain", gp.RELAUNCHED]


def test_o_padrao_e_a_placa_dedicada():
    from src.core.game_storage import GRAPHICS
    assert GRAPHICS['gpu'][0] == 'high'
