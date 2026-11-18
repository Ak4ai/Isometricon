"""Os modelos personalizados (.glb) do jogador em disco: a pasta deles e a escolha da última vez.

``saves/modelos/`` guarda cópias dos arquivos importados (``/skin modelo <caminho>``); ``saves/modelo.json`` guarda
qual está em uso e os ajustes (altura, giro, perfil de movimento). Sem o arquivo de escolha, o jogo usa o
personagem montado, como sempre.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from .glb import ModelError, load_model

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(PROJECT_ROOT, "saves", "modelos")
CHOICE_PATH = os.path.join(PROJECT_ROOT, "saves", "modelo.json")
VERSION = 1
DEFAULT_CHOICE: Dict[str, Any] = {"arquivo": None, "altura": 1.8, "giro": 0, "perfil": None, "reparar": True}
MIN_HEIGHT, MAX_HEIGHT = 0.3, 6.0


def safe_name(text: str) -> str:
    """Um nome de arquivo simples (letras, números, - e _) tirado de ``text``."""
    name = re.sub(r"[^0-9A-Za-z_-]+", "_", os.path.splitext(os.path.basename(text))[0]).strip("_")
    return name or "modelo"


def list_models(directory: str = MODELS_DIR) -> List[str]:
    """Os nomes (sem ``.glb``) dos modelos guardados, em ordem."""
    if not os.path.isdir(directory):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(directory) if f.lower().endswith(".glb"))


def path_of(name: str, directory: str = MODELS_DIR) -> Optional[str]:
    """O arquivo do modelo guardado ``name``, ou ``None`` se não existe."""
    path = os.path.join(directory, safe_name(name) + ".glb")
    return path if os.path.isfile(path) else None


def roles_path(name: str, directory: str = MODELS_DIR) -> str:
    """Onde ficam os papéis dos ossos ajustados à mão do modelo ``name`` (pode não existir)."""
    return os.path.join(directory, safe_name(name) + ".papeis.json")


def import_model(source: str, directory: str = MODELS_DIR) -> str:
    """Confere ``source`` (``ModelError`` se não serve), copia para a pasta e devolve o nome guardado."""
    if not os.path.isfile(source):
        raise ModelError(f"Não achei o arquivo '{source}'.")
    load_model(source)   # lê tudo antes de guardar: um arquivo ruim não entra na lista
    name = safe_name(source)
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, name + ".glb")
    if os.path.abspath(source) != os.path.abspath(target):
        shutil.copyfile(source, target)
    return name


def clamp_height(value: float) -> float:
    return max(MIN_HEIGHT, min(MAX_HEIGHT, float(value)))


def save_choice(choice: Dict[str, Any], path: str = CHOICE_PATH) -> str:
    data = {**DEFAULT_CHOICE, **choice, "versao": VERSION}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return path


def load_choice(path: str = CHOICE_PATH) -> Optional[Dict[str, Any]]:
    """A escolha gravada, ou ``None`` se não há (ou está ilegível, ou não escolhe modelo)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("arquivo"):
        return None
    choice = dict(DEFAULT_CHOICE)
    try:
        choice["arquivo"] = str(data["arquivo"])
        choice["altura"] = clamp_height(data.get("altura", choice["altura"]))
        choice["giro"] = int(data.get("giro", 0)) % 4
    except (TypeError, ValueError):
        return None
    perfil = data.get("perfil")
    choice["perfil"] = perfil if isinstance(perfil, str) else None
    choice["reparar"] = bool(data.get("reparar", True))
    return choice


def clear_choice(path: str = CHOICE_PATH) -> None:
    """Volta ao personagem montado na próxima vez."""
    try:
        os.remove(path)
    except OSError:
        pass


__all__ = ["MODELS_DIR", "CHOICE_PATH", "DEFAULT_CHOICE", "safe_name", "list_models", "path_of", "roles_path", "import_model",
           "clamp_height", "save_choice", "load_choice", "clear_choice"]
