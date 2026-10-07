"""O personagem gravado em disco: aparência, cabelo e roupas, para voltar na próxima vez.

``saves/personagem.json`` guarda os campos de ``AvatarCustomization`` e o que o modelo veste.
É gravado ao fechar a tela de criação e por ``/skin salvar``; ao abrir o jogo é carregado, a
menos que a linha de comando escolha o personagem (``--top``, ``--female``...) ou peça um novo
(``--novo``).
"""
from __future__ import annotations

from dataclasses import fields
from enum import Enum
import json
import os
from typing import Any, Dict, Optional

from .customization import (
    AvatarCustomization,
    BodyType,
    EyebrowStyle,
    EyeStyle,
    FaceOption,
    HairColor,
    HairStyle,
    HeadType,
    IrisColor,
    MouthStyle,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAVE_PATH = os.path.join(PROJECT_ROOT, "saves", "personagem.json")
VERSION = 1

# What the model wears, and the hair's manual placement.
WORN = ("top_id", "bottom_id", "outer_top_id", "shoes_id", "hair_id", "tool_id")
HAIR_PLACEMENT = ("hair_offset_x", "hair_offset_y", "hair_offset_z", "hair_scale_x", "hair_scale_y", "hair_scale_z")
# Paths chosen while the model is built: they depend on the body and are found again on loading.
NOT_SAVED = ("custom_face_path", "custom_hair_obj", "custom_hair_tex")
ENUMS = {"body_type": BodyType, "head_type": HeadType, "face": FaceOption, "hair_style": HairStyle,
         "hair_color": HairColor, "eye_style": EyeStyle, "iris_color": IrisColor, "mouth_style": MouthStyle,
         "eyebrow_style": EyebrowStyle, "eyebrow_color": HairColor}
# Command-line options that choose the character themselves: with any of them the save is not loaded.
CHARACTER_FLAGS = ("--novo", "--new", "--female", "--fem", "--woman", "--mulher", "--male", "--man", "--homem",
                   "--masculino", "--body", "--corpo", "--model", "--head", "--mouth", "--eyes", "--iris",
                   "--hair-color", "--hair", "--skin", "--top", "--bottom", "--calca", "--pants", "--tool")


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def to_dict(model: Any) -> Dict[str, Any]:
    """Tudo o que define o personagem, em tipos que o JSON guarda."""
    custom = {f.name: _plain(getattr(model.customization, f.name)) for f in fields(model.customization)
              if f.name not in NOT_SAVED}
    data = {"versao": VERSION, "aparencia": custom}
    data["veste"] = {name: _plain(getattr(model, name, None)) for name in WORN}
    data["cabelo"] = {name: float(getattr(model, name)) for name in HAIR_PLACEMENT if hasattr(model, name)}
    return data


def customization_from(data: Dict[str, Any]) -> AvatarCustomization:
    """``AvatarCustomization`` de um personagem gravado (campos desconhecidos são ignorados)."""
    known = {f.name for f in fields(AvatarCustomization)}
    values = {}
    for name, value in (data.get("aparencia") or {}).items():
        if name not in known or name in NOT_SAVED:
            continue
        if isinstance(value, list):
            value = tuple(value)
        if isinstance(value, str) and name in ENUMS:
            try:
                value = ENUMS[name](value)
            except ValueError:
                pass  # a value of another kind (a colour of its own): kept as written
        values[name] = value
    custom = AvatarCustomization(**values)
    for name, value in (data.get("cabelo") or {}).items():
        if name in HAIR_PLACEMENT:
            setattr(custom, name, float(value))
    return custom


def model_arguments(data: Dict[str, Any]) -> Dict[str, Any]:
    """Argumentos de ``CharacterModel`` para o personagem gravado."""
    arguments: Dict[str, Any] = {"customization": customization_from(data)}
    for name in WORN:
        arguments[name] = (data.get("veste") or {}).get(name)
    return arguments


def apply(model: Any, data: Dict[str, Any]) -> None:
    """Põe o personagem gravado num modelo já criado e o reconstrói."""
    arguments = model_arguments(data)
    model.customization = arguments.pop("customization")
    for name, value in arguments.items():
        setattr(model, name, value)
    for name in HAIR_PLACEMENT:
        setattr(model, name, float(getattr(model.customization, name)))
    if getattr(model, "hair_id", None) is not None and not getattr(model, "async_loading", False):
        model._resolve_hair()
    model.reload()


def save(model: Any, path: str = SAVE_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(to_dict(model), handle, indent=1, ensure_ascii=False)
    os.replace(temporary, path)  # never leaves a half-written save
    return path


def load(path: str = SAVE_PATH) -> Optional[Dict[str, Any]]:
    """O personagem gravado, ou None se não há um (ou se o arquivo não pode ser lido)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("aparencia"), dict) else None


def wanted(arguments) -> bool:
    """Se a linha de comando deixa o personagem gravado ser carregado."""
    return not any(a.split("=")[0] in CHARACTER_FLAGS for a in arguments)
