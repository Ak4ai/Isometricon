"""Qual textura o Minecraft põe em cada face de um bloco, lida dos blockstates e modelos do jogo.

O Minecraft diz, para cada bloco (``minecraft:oak_log[axis=x]``), qual modelo usar (blockstate) e, em cada modelo,
a textura de cada face (``models/block``, com herança entre modelos). Aqui isso é lido do ``client.jar`` do
Minecraft do próprio jogador, sob demanda e sem copiar nada para o projeto; sem o jar, ``MinecraftModels.find()``
devolve ``None`` e o atlas segue com o palpite por nome.

Os modelos vêm, de preferência, da cópia local ``assets/minecraft_models`` (os JSON de ``blockstates`` e de
``models/block`` extraídos do jogo; a pasta não vai para o git). Sem ela, do ``client.jar``.

Daqui saem a textura por face (``face_texture``) e as caixas do bloco (``boxes``), para os que não têm regra em
``block_shapes``.
"""

from __future__ import annotations

import glob
import json
import os
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Tuple

ENV_JAR = "ISOMETRICON_MC_JAR"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_MODELS = os.path.join(PROJECT_ROOT, "assets", "minecraft_models")
_PREFIX = "assets/minecraft/"

# Direções do Minecraft (norte = -z, sul = +z, leste = +x)
_VECTORS = {"up": (0, 1, 0), "down": (0, -1, 0), "north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0),
            "west": (-1, 0, 0)}
_BY_VECTOR = {v: k for k, v in _VECTORS.items()}
# O malhador das construções chama de "north" a face de +z e de "south" a de -z (e "top"/"bottom" as de cima e baixo)
_MESHER_FACE = {"top": "up", "+y": "up", "bottom": "down", "-y": "down", "north": "south", "south": "north",
                "east": "east", "west": "west", "up": "up", "down": "down", "side": "south", "all": "south"}


def find_jar() -> Optional[str]:
    """O ``client.jar`` do Minecraft do jogador (``ISOMETRICON_MC_JAR``, o Prism Launcher, o launcher oficial)."""
    path = os.environ.get(ENV_JAR)
    if path and os.path.isfile(path):
        return path
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(appdata, "PrismLauncher", "libraries", "com", "mojang", "minecraft", "*", "minecraft-*-client.jar"),
        os.path.join(appdata, "PrismLauncher", "libraries", "com", "mojang", "minecraft", "*", "*.jar"),
        os.path.join(appdata, ".minecraft", "versions", "*", "*.jar"),
        os.path.join(home, ".minecraft", "versions", "*", "*.jar"),
        os.path.join(home, ".local", "share", "PrismLauncher", "libraries", "com", "mojang", "minecraft", "*", "*.jar"),
        os.path.join(home, "Library", "Application Support", "minecraft", "versions", "*", "*.jar"),
    ]
    found = []
    for pattern in patterns:
        found.extend(p for p in glob.glob(pattern) if _has_models(p))
    return max(found, key=os.path.getmtime) if found else None


def has_local_models(folder: str = LOCAL_MODELS) -> bool:
    return os.path.isfile(os.path.join(folder, "blockstates", "stone.json"))


def _has_models(path: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return "assets/minecraft/blockstates/stone.json" in set(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def _parse(name: str) -> Tuple[str, Dict[str, str]]:
    base = name.split("[")[0].strip()
    base = base.split(":", 1)[1] if ":" in base else base
    props: Dict[str, str] = {}
    if "[" in name and name.rstrip().endswith("]"):
        for pair in name[name.index("[") + 1:name.rindex("]")].split(","):
            key, _, value = pair.partition("=")
            if key.strip():
                props[key.strip()] = value.strip()
    return base.lower(), props


def _rotate(vector: Tuple[int, int, int], x_turns: int, y_turns: int) -> Tuple[int, int, int]:
    """Gira uma direção como o blockstate faz: primeiro em x (para cima vira norte), depois em y (horário, visto de
    cima: norte vira leste). Em passos de 90 graus."""
    x, y, z = vector
    for _ in range(x_turns % 4):
        y, z = z, -y            # up (0,1,0) -> north (0,0,-1) -> down (0,-1,0)
    for _ in range(y_turns % 4):
        x, z = -z, x            # north (0,0,-1) -> east (1,0,0)
    return x, y, z


def _rotate_box(lo, hi, x_turns: int, y_turns: int):
    """Gira a caixa em volta do centro do bloco, como o blockstate: primeiro em x, depois em y (passos de 90°)."""
    points = []
    for cx in (lo[0] - 8.0, hi[0] - 8.0):
        for cy in (lo[1] - 8.0, hi[1] - 8.0):
            for cz in (lo[2] - 8.0, hi[2] - 8.0):
                x, y, z = cx, cy, cz
                for _ in range(x_turns % 4):
                    y, z = z, -y
                for _ in range(y_turns % 4):
                    x, z = -z, x
                points.append((x, y, z))
    new_lo = tuple(min(p[i] for p in points) + 8.0 for i in range(3))
    new_hi = tuple(max(p[i] for p in points) + 8.0 for i in range(3))
    return new_lo, new_hi


class MinecraftModels:
    """Leitor de blockstates e modelos, de uma pasta local ou de um ``client.jar``."""

    def __init__(self, source: str) -> None:
        self.source = self.jar_path = source
        self._zip: Optional[zipfile.ZipFile] = None
        if os.path.isdir(source):
            self._files = set()
            for sub in ("blockstates", os.path.join("models", "block")):
                base = os.path.join(source, sub)
                for dirpath, _, names in os.walk(base):
                    for name in names:
                        relative = os.path.relpath(os.path.join(dirpath, name), source).replace(os.sep, "/")
                        self._files.add(_PREFIX + relative)
        else:
            self._zip = zipfile.ZipFile(source)
            self._files = set(self._zip.namelist())
        self._json: Dict[str, Optional[dict]] = {}
        self._boxes: Dict[str, Optional[List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]]] = {}
        self._resolved: Dict[str, Tuple[Dict[str, str], List[dict]]] = {}
        self._answers: Dict[Tuple[str, str], Optional[str]] = {}

    @classmethod
    def find(cls) -> Optional["MinecraftModels"]:
        """A cópia local dos modelos, se existe; senão o ``client.jar`` do jogador; senão ``None``."""
        if has_local_models():
            try:
                return cls(LOCAL_MODELS)
            except OSError:
                pass
        path = find_jar()
        if path is None:
            return None
        try:
            return cls(path)
        except (OSError, zipfile.BadZipFile):
            return None

    # ------------------------------------------------------------------------------------------- arquivos
    def _load(self, path: str) -> Optional[dict]:
        if path not in self._json:
            data = None
            if path in self._files:
                try:
                    if self._zip is not None:
                        raw = self._zip.read(path)
                    else:
                        with open(os.path.join(self.source, path[len(_PREFIX):]), "rb") as handle:
                            raw = handle.read()
                    data = json.loads(raw.decode("utf-8"))
                except (ValueError, OSError, KeyError):
                    data = None
            self._json[path] = data
        return self._json[path]

    def has_blockstate(self, base: str) -> bool:
        return f"assets/minecraft/blockstates/{base}.json" in self._files

    @staticmethod
    def _model_path(name: str) -> str:
        name = name.split(":", 1)[1] if ":" in name else name
        return f"assets/minecraft/models/{name}.json"

    def _model(self, name: str) -> Tuple[Dict[str, str], List[dict]]:
        """(texturas, elementos) de um modelo, com a herança resolvida (o filho manda sobre o pai)."""
        key = name.split(":", 1)[1] if ":" in name else name
        if key in self._resolved:
            return self._resolved[key]
        self._resolved[key] = ({}, [])           # corta ciclos
        data = self._load(self._model_path(name)) or {}
        textures: Dict[str, str] = {}
        elements: List[dict] = []
        parent = data.get("parent")
        if parent and not parent.endswith(("builtin/generated", "builtin/entity")):
            textures, elements = self._model(parent)
            textures = dict(textures)
        textures.update(data.get("textures", {}))
        if data.get("elements") is not None:
            elements = data["elements"]
        self._resolved[key] = (textures, elements)
        return self._resolved[key]

    # ------------------------------------------------------------------------------------------- blockstates
    def _applied_models(self, base: str, props: Dict[str, str]) -> List[dict]:
        """Os ``apply`` (modelo, x, y) que valem para o bloco com essas propriedades."""
        state = self._load(f"assets/minecraft/blockstates/{base}.json")
        if not state:
            return []
        if "variants" in state:
            best, best_score = None, -1
            for key, value in state["variants"].items():
                conditions = [pair.split("=", 1) for pair in key.split(",") if "=" in pair]
                if any(props.get(k) != v for k, v in conditions if k in props):
                    continue
                score = sum(1 for k, v in conditions if props.get(k) == v)
                if score > best_score:
                    best, best_score = value, score
            if best is None:
                return []
            return [best[0] if isinstance(best, list) else best]
        applied = []
        for part in state.get("multipart", []):
            if self._matches(part.get("when"), props):
                apply = part["apply"]
                applied.append(apply[0] if isinstance(apply, list) else apply)
        return applied

    def _matches(self, when, props: Dict[str, str]) -> bool:
        if when is None:
            return True
        if "OR" in when:
            return any(self._matches(w, props) for w in when["OR"])
        if "AND" in when:
            return all(self._matches(w, props) for w in when["AND"])
        return all(props.get(k) in str(v).split("|") for k, v in when.items())

    # ------------------------------------------------------------------------------------------- texturas
    def face_texture(self, block_name: str, face: str) -> Optional[str]:
        """O nome (sem pasta) da textura da face ``face`` do bloco, ou ``None`` se o Minecraft não diz (bloco sem
        modelo de blocos, como o baú). ``face`` é a do malhador: top, bottom, north (+z), south (-z), east, west."""
        key = (block_name, face)
        if key not in self._answers:
            self._answers[key] = self._face_texture(block_name, face)
        return self._answers[key]

    def _face_texture(self, block_name: str, face: str) -> Optional[str]:
        base, props = _parse(block_name)
        wanted = _MESHER_FACE.get(face)
        if wanted is None or not self.has_blockstate(base):
            return None
        anything = None
        for apply in self._applied_models(base, props):
            textures, elements = self._model(apply["model"])
            x_turns, y_turns = int(apply.get("x", 0)) // 90, int(apply.get("y", 0)) // 90
            for element in elements:
                for direction, data in element.get("faces", {}).items():
                    texture = self._resolve(data.get("texture", ""), textures)
                    if texture is None:
                        continue
                    if anything is None:
                        anything = texture
                    if _BY_VECTOR.get(_rotate(_VECTORS[direction], x_turns, y_turns)) == wanted:
                        return texture
        return anything

    @staticmethod
    def _resolve(reference, textures: Dict[str, str]) -> Optional[str]:
        for _ in range(8):
            if isinstance(reference, dict):
                reference = reference.get("sprite", "")     # o formato novo: {"sprite": "block/x", ...}
            if not isinstance(reference, str) or not reference.startswith("#"):
                break
            reference = textures.get(reference[1:], "")
        if not isinstance(reference, str) or not reference or reference.startswith("#"):
            return None
        return re.split(r"[:/]", reference)[-1]

    # ------------------------------------------------------------------------------------------- caixas
    def boxes(self, block_name: str):
        """As caixas ((x0, y0, z0), (x1, y1, z1)) do bloco, em 1/16, com a rotação do blockstate; ``None`` quando o
        bloco não tem modelo de caixas (baú, cama), tem peças inclinadas ou planas (plantas, trilhos), ou é um cubo
        inteiro (``[]``: sem forma própria)."""
        if block_name not in self._boxes:
            self._boxes[block_name] = self._compute_boxes(block_name)
        return self._boxes[block_name]

    def _compute_boxes(self, block_name: str):
        base, props = _parse(block_name)
        if not self.has_blockstate(base):
            return None
        result = []
        for apply in self._applied_models(base, props):
            _, elements = self._model(apply["model"])
            x_turns, y_turns = int(apply.get("x", 0)) // 90, int(apply.get("y", 0)) // 90
            for element in elements:
                rotation = element.get("rotation")
                if rotation and float(rotation.get("angle", 0)) != 0.0:
                    return None  # peça inclinada: não é uma caixa
                lo, hi = [float(v) for v in element["from"]], [float(v) for v in element["to"]]
                if any(a == b for a, b in zip(lo, hi)):
                    return None  # plano de espessura zero (planta em cruz, trilho): fica a cargo das regras
                result.append(_rotate_box(lo, hi, x_turns, y_turns))
        if not result:
            return None
        if len(result) == 1 and result[0] == ((0.0, 0.0, 0.0), (16.0, 16.0, 16.0)):
            return []
        return result

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
