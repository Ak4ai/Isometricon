"""Os modelos personalizados (.glb) do jogador em disco: a pasta deles e a escolha da última vez.

``saves/modelos/`` guarda cópias dos arquivos importados (``/skin modelo <caminho>``); ``saves/modelo.json`` guarda
qual está em uso e os ajustes (altura, giro, perfil de movimento). Sem o arquivo de escolha, o jogo usa o
personagem montado, como sempre.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from src.core.paths import saves_path

from .glb import ModelError, parse_model, read_model_bytes

MODELS_DIR = os.fspath(saves_path("modelos"))
CHOICE_PATH = os.fspath(saves_path("modelo.json"))
VERSION = 1
DEFAULT_CHOICE: Dict[str, Any] = {"arquivo": None, "altura": 1.8, "giro": 0, "perfil": None, "reparar": True}
MIN_HEIGHT, MAX_HEIGHT = 0.3, 6.0
_DOS_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"{dev}{index}" for dev in ("COM", "LPT") for index in range(1, 10))}


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
    data = read_model_bytes(source)
    parse_model(data)  # valide os mesmos bytes que serão publicados na biblioteca
    base = safe_name(source)[:80]
    if base.upper() in _DOS_DEVICES:
        base = f"modelo_{base}"
    signature = hashlib.sha256(data).hexdigest()
    temporary = None
    try:
        os.makedirs(directory, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        for name in (base, f"{base}-{signature}"):
            target = os.path.join(directory, name + ".glb")
            try:
                # No Windows, rename falha se o destino existe. No POSIX, o
                # hard link dá a mesma garantia sem expor um arquivo parcial.
                if os.name == "nt":
                    os.rename(temporary, target)
                    temporary = None
                else:
                    os.link(temporary, target)
                return name
            except FileExistsError:
                with open(target, "rb") as existing:
                    block_size = 1024 * 1024
                    if os.fstat(existing.fileno()).st_size == len(data) and all(
                        existing.read(block_size) == data[offset:offset + block_size]
                        for offset in range(0, len(data), block_size)
                    ):
                        return name
        raise ModelError("O identificador do modelo já existe com conteúdo diferente.")
    except OSError as error:
        raise ModelError(f"Não consegui guardar o modelo: {error}") from error
    finally:
        if temporary is not None:
            try:
                os.remove(temporary)
            except OSError:
                pass


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
