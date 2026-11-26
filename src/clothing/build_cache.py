
"""Montagem de personagem em disco: metadados JSON, buffers numéricos e texturas PNG.

O cache guarda as partes ainda na CPU, como a thread de montagem as deixou. A chave
identifica a configuração, o código e os assets usados. Caches .pkl antigos são ignorados.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import Any, Dict, Optional
from zipfile import ZIP_STORED, BadZipFile, ZipFile

import numpy as np
from PIL import Image

from src.clothing import character_save
from src.clothing.customization import HairStyle
from src.clothing.model_paths import GENERATED_MODELS, RESOURCE_MODELS
from src.core.paths import RESOURCE_ROOT, saves_path
from src.rendering.mesh import DEFERRED, TexturedMesh

CACHE_DIR = os.fspath(saves_path("cache"))
FILE_NAME = "personagem_montado.zip"
VERSION = 2
MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ENTRIES = 256
MAX_TEXTURE_PIXELS = 32 * 1024 * 1024

STATE = ("textures", "white_tex_id", "cage_debug_mesh", "_garment_buffers", "_hide_feet", "hsr_cage", "hsr_hidden",
         "hsr_skin", "_hsr_call", "_edges", "built_nose_style", "tail_root", "wing_root", "hair_fades")
CHOSEN = ("custom_face_path", "custom_hair_obj", "custom_hair_tex", "hair_style")
SETTINGS = ("outer_top_gap_mm", "outer_top_pull_mm", "show_cage", "hsr_edit")
CODE_DIRS = (RESOURCE_ROOT / "src" / "clothing",)
CODE_FILES = (RESOURCE_ROOT / "src" / "rendering" / "mesh.py",)
ASSETS_DIR = RESOURCE_MODELS

_code_digest: Optional[str] = None


def _code_fingerprint() -> str:
    """Hash do código de montagem ou do executável que contém o código empacotado."""
    global _code_digest
    if _code_digest is None:
        digest = hashlib.sha256()
        if getattr(sys, "frozen", False):
            paths = [Path(sys.executable)]
        else:
            paths = list(CODE_FILES)
            for directory in CODE_DIRS:
                paths.extend(sorted(directory.glob("*.py")))
        for path in paths:
            digest.update(path.name.encode())
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        _code_digest = digest.hexdigest()
    return _code_digest


def _assets_fingerprint() -> str:
    """Identifica os assets, sem depender da data de extração dos arquivos do OneFile."""
    digest = hashlib.sha256()
    frozen = getattr(sys, "frozen", False)
    directories = [(ASSETS_DIR, frozen)]
    if GENERATED_MODELS != ASSETS_DIR:
        directories.append((GENERATED_MODELS, False))
    for directory, packaged in directories:
        digest.update(b"\0")
        for root, dirs, files in os.walk(directory):
            dirs.sort()
            for name in sorted(files):
                path = os.path.join(root, name)
                info = os.stat(path)
                stamp = 0 if packaged else info.st_mtime_ns
                digest.update(f"{os.path.relpath(path, directory)}|{info.st_size}|{stamp}\n".encode())
    return digest.hexdigest()


def build_key(model: Any) -> str:
    """Assinatura das escolhas, dos ajustes, dos arquivos e do código do personagem."""
    data = {
        "versao": VERSION,
        "personagem": character_save.to_dict(model),
        "escolhido": {name: character_save._plain(getattr(model.customization, name, None)) for name in CHOSEN},
        "ajustes": {name: character_save._plain(getattr(model, name, None)) for name in SETTINGS},
        "arquivos": _assets_fingerprint(),
        "codigo": _code_fingerprint(),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def file_name(model: Any) -> str:
    """Nome do cache do jogador ou do NPC."""
    name = getattr(model, "cache_name", None)
    if not name:
        return FILE_NAME
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", name):
        raise ValueError("Nome de cache inválido.")
    return f"{name}.zip"


def _numeric_dtype(dtype: np.dtype) -> bool:
    return dtype.kind in "biuf" and dtype.itemsize in (1, 2, 4, 8)


class _Archive:
    """Codifica somente os tipos de dados que a montagem produz."""

    def __init__(self, archive: ZipFile):
        self.archive = archive
        self.next_member = 0
        self.pixel_count = 0
        self.read_members: set[str] = set()

    def _write(self, data: bytes) -> str:
        name = str(self.next_member)
        self.next_member += 1
        self.archive.writestr(name, data)
        return name

    def _read(self, name: str) -> bytes:
        if not isinstance(name, str) or not name.isascii() or not name.isdecimal() or name in self.read_members:
            raise ValueError("Nome de dado inválido no cache.")
        self.read_members.add(name)
        return self.archive.read(name)

    def encode(self, value: Any) -> Any:
        if isinstance(value, HairStyle):
            return {"hair_style": value.value}
        if isinstance(value, str):
            if os.path.isabs(value):
                try:
                    return {"resource": Path(value).relative_to(RESOURCE_ROOT).as_posix()}
                except ValueError:
                    pass
            return value
        if value is None or type(value) in (bool, int, float):
            return value
        if isinstance(value, np.generic):
            return self.encode(value.item())
        if isinstance(value, np.ndarray) and _numeric_dtype(value.dtype):
            return {"array": self._write(value.tobytes()), "dtype": value.dtype.str, "shape": value.shape}
        if isinstance(value, TexturedMesh) and value._pending is not None:
            vertices, indices = value._pending
            return {"mesh": [self.encode(vertices), self.encode(indices)]}
        if isinstance(value, tuple):
            return {"tuple": [self.encode(item) for item in value]}
        if isinstance(value, list):
            return [self.encode(item) for item in value]
        if isinstance(value, dict) and all(isinstance(key, str) for key in value):
            return {"dict": {key: self.encode(item) for key, item in value.items()}}
        raise ValueError("Tipo não suportado no cache de montagem.")

    def decode(self, value: Any) -> Any:
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if isinstance(value, list):
            return [self.decode(item) for item in value]
        if not isinstance(value, dict):
            raise ValueError("Valor inválido no cache.")
        if set(value) == {"array", "dtype", "shape"}:
            return self._array(value)
        if set(value) == {"tuple"} and isinstance(value["tuple"], list):
            return tuple(self.decode(item) for item in value["tuple"])
        if set(value) == {"dict"} and isinstance(value["dict"], dict):
            return {key: self.decode(item) for key, item in value["dict"].items()}
        if set(value) == {"hair_style"}:
            return HairStyle(value["hair_style"])
        if set(value) == {"resource"}:
            rel = Path(value["resource"])
            if rel.anchor or ".." in rel.parts:
                raise ValueError("Caminho de recurso inválido no cache.")
            return os.fspath(RESOURCE_ROOT / rel)
        if set(value) == {"mesh"}:
            return self._mesh(value["mesh"])
        raise ValueError("Tipo inválido no cache.")

    def _array(self, value: dict) -> np.ndarray:
        dtype_text, shape, name = value["dtype"], value["shape"], value["array"]
        if not isinstance(dtype_text, str) or not re.fullmatch(r"[<>|][biuf][1248]", dtype_text):
            raise ValueError("Tipo de array inválido no cache.")
        dtype = np.dtype(dtype_text)
        if (not _numeric_dtype(dtype) or not isinstance(shape, list) or len(shape) > 4
                or any(type(n) is not int or not 0 <= n <= MAX_CACHE_BYTES for n in shape)):
            raise ValueError("Dimensões de array inválidas no cache.")
        count = math.prod(shape)
        if not isinstance(name, str) or self.archive.getinfo(name).file_size != count * dtype.itemsize:
            raise ValueError("Tamanho de array inválido no cache.")
        return np.frombuffer(self._read(name), dtype=dtype).reshape(shape).copy()

    def _mesh(self, values: list) -> TexturedMesh:
        vertices, indices = (self.decode(value) for value in values)
        if not _valid_mesh_arrays(vertices, indices):
            raise ValueError("Buffers de malha inválidos no cache.")
        was_deferred = getattr(DEFERRED, "on", False)
        try:
            DEFERRED.on = True
            return TexturedMesh(vertices, indices)
        finally:
            DEFERRED.on = was_deferred

    def write_image(self, image: Image.Image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=1)
        return self._write(buffer.getvalue())

    def read_image(self, name: str) -> Image.Image:
        with Image.open(io.BytesIO(self._read(name)), formats=("PNG",)) as image:
            self.pixel_count += image.width * image.height
            if self.pixel_count > MAX_TEXTURE_PIXELS:
                raise ValueError("Texturas grandes demais no cache.")
            return image.convert("RGBA")


def _valid_mesh_arrays(vertices: Any, indices: Any) -> bool:
    if (not isinstance(vertices, np.ndarray) or vertices.dtype != np.float32 or vertices.size % 11
            or vertices.ndim not in (1, 2) or (vertices.ndim == 2 and vertices.shape[1] != 11)
            or not np.isfinite(vertices).all()):
        return False
    return indices is None or (isinstance(indices, np.ndarray) and indices.dtype == np.uint32
                               and indices.ndim == 1 and indices.size % 3 == 0
                               and (indices.size == 0 or indices.max() < vertices.size // 11))


def _tuple_of(value: Any, size: int) -> bool:
    return isinstance(value, tuple) and len(value) == size


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _coords(value: Any, size: int) -> bool:
    return isinstance(value, (tuple, list)) and len(value) == size and all(_number(item) for item in value)


def _rows(array: Any, width: int) -> bool:
    return isinstance(array, np.ndarray) and array.ndim == 2 and array.shape[1] == width


def _valid_state(state: dict, images: dict) -> bool:
    textures, white = state["textures"], state["white_tex_id"]
    if (not isinstance(textures, list) or any(type(t) is not int or t not in images for t in textures)
            or (white is not None and (type(white) is not int or white not in images))
            or (state["cage_debug_mesh"] is not None and not isinstance(state["cage_debug_mesh"], TexturedMesh))):
        return False

    garments, edges = state["_garment_buffers"], state["_edges"]
    if not isinstance(garments, dict) or not isinstance(edges, dict):
        return False
    for entry in garments.values():
        if not _tuple_of(entry, 2) or entry[1] is None or not _valid_mesh_arrays(*entry):
            return False
    for entry in edges.values():
        if not _tuple_of(entry, 2):
            return False
        key, heights = entry
        if (not _tuple_of(key, 2) or not isinstance(key[0], str) or not _number(key[1])
                or (heights is not None and not _coords(heights, 2))):
            return False

    if any(state[name] is not None and not _coords(state[name], 3) for name in ("tail_root", "wing_root")):
        return False

    cage, hidden, skin, call = (state[name] for name in ("hsr_cage", "hsr_hidden", "hsr_skin", "_hsr_call"))
    if call is not None and (not _tuple_of(call, 7) or not isinstance(call[0], str)
                             or not _coords(call[1], 3) or any(
                                 p is not None and not isinstance(p, str) for p in call[2:4])
                             or any(type(flag) is not bool for flag in call[4:6])
                             or not isinstance(call[6], tuple)
                             or any(p is not None and not isinstance(p, str) for p in call[6])):
        return False
    if cage is None:
        return True
    if not _tuple_of(cage, 3):
        return False
    points, raw_hidden, faces = cage
    if not _rows(points, 3) or not len(points) or not np.isfinite(points).all():
        return False
    if any(not isinstance(mask, np.ndarray) or mask.shape != (len(points),) or not np.isfinite(mask).all()
           for mask in (raw_hidden, hidden)):
        return False

    def valid_corners(corners: Any) -> bool:
        return (_rows(corners, 3) and corners.dtype.kind in "iu"
                and (not corners.size or 0 <= corners.min() <= corners.max() < len(points)))

    if faces is not None and not valid_corners(faces):
        return False
    if skin is not None:
        if not _tuple_of(skin, 3):
            return False
        where, corners, shares = skin
        if (not _rows(where, 3) or not valid_corners(corners) or where.shape != corners.shape
                or not _rows(shares, 3) or where.shape != shares.shape
                or not np.isfinite(where).all() or not np.isfinite(shares).all()):
            return False
    return True


def save(model: Any, images: Dict[int, Image.Image], key: str, directory: str = CACHE_DIR) -> Optional[str]:
    """Grava o personagem montado com substituição atômica."""
    temporary = None
    try:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, file_name(model))
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            with ZipFile(handle, "w", compression=ZIP_STORED) as archive:
                content = _Archive(archive)
                payload = {
                    "versao": VERSION,
                    "chave": key,
                    "partes": [[part.name, content.encode(part.mesh), part.texture_id,
                                content.encode(part.transform), content.encode(part.source_obj)] for part in model.parts],
                    "estado": {name: content.encode(getattr(model, name, None)) for name in STATE},
                    "escolhido": {name: content.encode(getattr(model.customization, name, None)) for name in CHOSEN},
                    "imagens": [[placeholder, content.write_image(image)] for placeholder, image in images.items()],
                }
                archive.writestr("manifest.json", json.dumps(payload, allow_nan=False))
        os.replace(temporary, path)
        temporary = None
        return path
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        print(f"[CharacterModel] Não deu para guardar o personagem montado: {exc}")
        return None
    finally:
        if temporary is not None:
            try:
                os.remove(temporary)
            except OSError:
                pass


def load(model: Any, key: str, directory: str = CACHE_DIR) -> Optional[Dict[int, Image.Image]]:
    """Recupera apenas caches válidos da chave, sem modificar o modelo em caso de erro."""
    from src.clothing.character_model import CharacterPart

    try:
        path = os.path.join(directory, file_name(model))
        with open(path, "rb") as handle:
            file_size = os.fstat(handle.fileno()).st_size
            if not 22 <= file_size <= MAX_CACHE_BYTES:
                return None
            # O gravador sempre usa ZIP simples, sem comentário. Limite o diretório antes
            # que ZipFile aloque os objetos de metadados para todas as entradas.
            handle.seek(-22, os.SEEK_END)
            signature, disk, directory_disk, local_entries, entries, size, offset, comment = struct.unpack(
                "<4s4H2IH", handle.read(22))
            if (signature != b"PK\x05\x06" or disk or directory_disk or comment
                    or local_entries != entries or entries > MAX_ENTRIES or size > 64 * 1024
                    or offset + size != file_size - 22):
                return None
            with ZipFile(handle, "r") as archive:
                infos = archive.infolist()
                if (len(infos) != entries
                        or len(infos) != len({entry.filename for entry in infos})
                        or any(entry.compress_type != ZIP_STORED or entry.file_size != entry.compress_size
                               for entry in infos)
                        or sum(entry.file_size for entry in infos) > MAX_CACHE_BYTES
                        or archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES):
                    return None
                payload = json.loads(archive.read("manifest.json"))
                if payload["versao"] != VERSION or payload["chave"] != key:
                    return None
                content = _Archive(archive)
                state = {name: content.decode(payload["estado"][name]) for name in STATE}
                chosen = {name: content.decode(payload["escolhido"][name]) for name in CHOSEN}
                if any(value is not None and not isinstance(value, str) for value in chosen.values()):
                    return None
                images = {placeholder: content.read_image(name) for placeholder, name in payload["imagens"]}
                if (len(images) != len(payload["imagens"])
                        or any(type(t) is not int or t >= 0 for t in images)):
                    return None
                parts = []
                for name, raw_mesh, texture, raw_transform, source in payload["partes"]:
                    mesh, transform, source = content.decode(raw_mesh), content.decode(raw_transform), content.decode(source)
                    if (not isinstance(name, str) or not isinstance(mesh, TexturedMesh)
                            or type(texture) is not int or texture not in images
                            or (transform is not None and (
                                not isinstance(transform, np.ndarray) or transform.shape != (4, 4)
                                or not np.isfinite(transform).all()))
                            or (source is not None and not isinstance(source, str))):
                        return None
                    parts.append(CharacterPart(name, mesh, texture, transform, source))
                if not _valid_state(state, images):
                    return None
    except (OSError, AttributeError, BadZipFile, Image.DecompressionBombError, KeyError, OverflowError,
            RuntimeError, TypeError, ValueError, struct.error):
        return None
    model.parts = parts
    for name, value in state.items():
        setattr(model, name, value)
    for name, value in chosen.items():
        setattr(model.customization, name, value)
    return images
