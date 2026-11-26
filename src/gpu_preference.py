"""Qual placa de vídeo o Windows dá ao jogo (Configurações > Gráficos > Placa de vídeo).

Num notebook com duas placas (a integrada, Intel ou AMD, e a dedicada, NVIDIA ou AMD), o Windows põe todo programa na
integrada, a não ser que o executável peça a outra. O jeito de pedir pelo próprio executável (exportar
``NvOptimusEnablement`` / ``AmdPowerXpressRequestHighPerformance``) não serve a um programa em Python: quem exporta é o
``python.exe`` ou o executável do PyInstaller, não o jogo. O que serve é a mesma preferência que o usuário marca em
Configurações do Windows > Sistema > Tela > Gráficos: um valor por executável em
``HKEY_CURRENT_USER\\Software\\Microsoft\\DirectX\\UserGpuPreferences`` (sem pedir administrador; vale para NVIDIA e AMD,
no OpenGL também).

O Windows lê essa preferência quando o processo começa. Então, se ao abrir o jogo o valor precisou mudar, o jogo se
abre de novo uma vez (``relaunch``), já na placa escolhida; das próximas vezes o valor já está lá e nada acontece.

Rodando do código-fonte, o executável é o ``python.exe``: a preferência vale para tudo o que rodar com ele.

Fica fora de ``src.core`` de propósito: importar aquele pacote carrega o PyOpenGL, e o main precisa desligar a
checagem de erros dele (OpenGL.ERROR_CHECKING) antes disso.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
VALUES = {'high': "GpuPreference=2;", 'low': "GpuPreference=1;"}
OURS = set(VALUES.values())   # o que o jogo grava (no "automático" só estes são apagados)
RELAUNCHED = "--gpu-relaunched"


def wanted_value(choice: str) -> Optional[str]:
    """O valor do registro para a escolha ('high', 'low' ou 'auto': None, o Windows decide)."""
    return VALUES.get(choice)


def apply(choice: str, executable: str, registry=None) -> bool:
    """Deixa a preferência do executável como a escolha pede. Devolve True se o registro mudou."""
    if registry is None:
        import winreg as registry
    want = wanted_value(choice)
    try:
        key = registry.CreateKey(registry.HKEY_CURRENT_USER, KEY)
    except OSError:
        return False
    try:
        try:
            current, _ = registry.QueryValueEx(key, executable)
        except OSError:
            current = None
        if want is None:
            if current in OURS:
                registry.DeleteValue(key, executable)
                return True
            return False
        if current == want:
            return False
        registry.SetValueEx(key, executable, 0, registry.REG_SZ, want)
        return True
    except OSError:
        return False
    finally:
        registry.CloseKey(key)


def relaunch_command(executable: str, argv, frozen: bool):
    """A linha para abrir o jogo de novo, igual, marcada para não abrir uma terceira vez."""
    args = list(argv[1:]) if frozen else list(argv)
    return [executable] + args + [RELAUNCHED]


def ensure(choice: str) -> None:
    """No começo do main, antes de qualquer OpenGL: acerta a preferência e, se ela mudou, roda o jogo de novo neste
    mesmo terminal e sai com o código dele."""
    if sys.platform != "win32" or RELAUNCHED in sys.argv or os.environ.get("ISOMETRICON_NO_GPU_PREF"):
        return
    if not apply(choice, sys.executable):
        return
    env = dict(os.environ)
    if choice == 'high':
        env["SHIM_MCCOMPAT"] = "0x800000001"   # o mesmo pedido, para o driver NVIDIA (lido no começo do processo)
    print(f"[Vídeo] Placa de vídeo: {'dedicada' if choice == 'high' else 'integrada' if choice == 'low' else 'automática'}"
          " (preferência do Windows atualizada); abrindo o jogo de novo nela.")
    try:
        code = subprocess.call(relaunch_command(sys.executable, sys.argv, bool(getattr(sys, "frozen", False))), env=env)
    except OSError:
        return                                  # não conseguiu: segue nesta mesmo
    sys.exit(code)


def saved_choice() -> str:
    """A escolha salva nas preferências (sem carregar o resto do jogo)."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'saves' / 'preferences.json'   # o mesmo de game_storage.Preferences
    try:
        choice = json.loads(path.read_text(encoding='utf-8')).get('gpu', 'high')
    except (OSError, ValueError, AttributeError):
        return 'high'
    return choice if choice in ('high', 'low', 'auto') else 'high'
