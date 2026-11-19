"""O personagem montado guardado em disco, para abrir o jogo sem montá-lo de novo (sem OpenGL).

Montar o personagem (recortar a pele sob as roupas, pintar o rosto, ler as malhas) leva dezenas de segundos, e o
resultado só depende das escolhas dele, dos arquivos de ``assets/models`` e do código da montagem. A montagem em
segundo plano (``CharacterModel.poll``) grava aqui o que produziu, e na próxima vez, se nada disso mudou, lê de volta
em vez de montar.

Guarda só o último personagem, em ``saves/cache/personagem_montado.pkl``: as partes (malhas ainda na CPU, como a
thread de fundo as deixa), as imagens das texturas e o que a montagem descobriu sobre ele. A chave (``build_key``) é
uma assinatura de tudo o que muda o resultado; qualquer diferença faz montar do jeito normal e gravar de novo.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
from typing import Any, Dict, Optional

from PIL import Image

from src.clothing import character_save

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(PROJECT_ROOT, "saves", "cache")
FILE_NAME = "personagem_montado.pkl"
VERSION = 1

# O que a montagem deixa no modelo (o mesmo que ``CharacterModel.poll`` passa para o modelo mostrado).
STATE = ("textures", "white_tex_id", "cage_debug_mesh", "_garment_buffers", "_hide_feet", "hsr_cage", "hsr_hidden",
         "hsr_skin", "_hsr_call", "_edges", "built_nose_style", "tail_root", "wing_root", "hair_fades")
# O que ela anota na aparência (o cabelo e o rosto achados para este corpo).
CHOSEN = ("custom_face_path", "custom_hair_obj", "custom_hair_tex", "hair_style")
# Ajustes do modelo fora da aparência que mudam a montagem.
SETTINGS = ("outer_top_gap_mm", "outer_top_pull_mm", "show_cage", "hsr_edit")
# O código cuja mudança muda o resultado.
CODE_DIRS = (os.path.join(PROJECT_ROOT, "src", "clothing"),)
CODE_FILES = (os.path.join(PROJECT_ROOT, "src", "rendering", "mesh.py"),)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets", "models")

_code_digest: Optional[str] = None


def _code_fingerprint() -> str:
    """O conteúdo do código da montagem (calculado uma vez por execução)."""
    global _code_digest
    if _code_digest is None:
        digest = hashlib.sha256()
        paths = list(CODE_FILES)
        for directory in CODE_DIRS:
            paths += [os.path.join(directory, name) for name in sorted(os.listdir(directory)) if name.endswith(".py")]
        for path in paths:
            digest.update(os.path.basename(path).encode())
            with open(path, "rb") as handle:
                digest.update(handle.read())
        _code_digest = digest.hexdigest()
    return _code_digest


def _assets_fingerprint() -> str:
    """Nome, tamanho e data de cada arquivo de ``assets/models`` (as malhas, as roupas ajustadas, as texturas)."""
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(ASSETS_DIR):
        dirs.sort()
        for name in sorted(files):
            info = os.stat(os.path.join(root, name))
            digest.update(f"{os.path.relpath(os.path.join(root, name), ASSETS_DIR)}|{info.st_size}|{info.st_mtime_ns}\n"
                          .encode())
    return digest.hexdigest()


def _plain(value: Any) -> Any:
    return character_save._plain(value)


def build_key(model: Any) -> str:
    """Assinatura de tudo o que muda o personagem montado: as escolhas, os ajustes, os arquivos e o código."""
    data = {
        "versao": VERSION,
        "personagem": character_save.to_dict(model),
        "escolhido": {name: _plain(getattr(model.customization, name, None)) for name in CHOSEN},
        "ajustes": {name: _plain(getattr(model, name, None)) for name in SETTINGS},
        "arquivos": _assets_fingerprint(),
        "codigo": _code_fingerprint(),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def file_name(model: Any) -> str:
    """O arquivo do cache deste modelo: o do jogador, ou o de um NPC (``cache_name``), um por personagem."""
    name = getattr(model, "cache_name", None)
    return f"{name}.pkl" if name else FILE_NAME


def _image_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def save(model: Any, images: Dict[int, Image.Image], key: str, directory: str = CACHE_DIR) -> Optional[str]:
    """Grava o personagem montado em ``model`` (com as imagens das texturas por marcador). Nunca falha o jogo."""
    try:
        os.makedirs(directory, exist_ok=True)
        payload = {
            "chave": key,
            "partes": model.parts,
            "estado": {name: getattr(model, name, None) for name in STATE},
            "escolhido": {name: getattr(model.customization, name, None) for name in CHOSEN},
            "imagens": {placeholder: _image_bytes(image) for placeholder, image in images.items()},
        }
        path = os.path.join(directory, file_name(model))
        temporary = path + ".tmp"
        with open(temporary, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temporary, path)  # nunca fica um cache pela metade
        return path
    except Exception as exc:
        print(f"[CharacterModel] Não deu para guardar o personagem montado: {exc}")
        return None


def load(model: Any, key: str, directory: str = CACHE_DIR) -> Optional[Dict[int, Image.Image]]:
    """Põe em ``model`` o personagem guardado com a chave ``key`` e devolve as imagens das texturas por marcador;
    None se não há um guardado, se é de outra chave ou se o arquivo não pode ser lido."""
    path = os.path.join(directory, file_name(model))
    try:
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
        if not isinstance(payload, dict) or payload.get("chave") != key:
            return None
        images = {placeholder: Image.open(io.BytesIO(data)).convert("RGBA")
                  for placeholder, data in payload["imagens"].items()}
    except Exception:
        return None
    model.parts = payload["partes"]
    for name, value in payload["estado"].items():
        setattr(model, name, value)
    for name, value in payload["escolhido"].items():
        setattr(model.customization, name, value)
    return images
