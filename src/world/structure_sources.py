"""De onde vem uma construção: um .schem, a vitrine de formas ou um objeto do editor.

Uma *entrada* (``dict``, que vai para o save) diz como refazer a construção:

- ``{"kind": "schem", "name": <nome da pasta ou caminho>}``
- ``{"kind": "schem", "name": <rótulo>, "sha256": <hash da cópia local>}``
- ``{"kind": "formas"}`` (a vitrine montada em código, ``src/world/shape_showcase.py``)
- ``{"kind": "object", "object": <VoxelObject.to_dict()>, "name": <rótulo>}`` — o objeto vai inteiro, como o editor do
  Rafael já guardava: o que foi colocado não muda se o arquivo da biblioteca for editado depois.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Dict, List, Optional, Tuple

from src.core.paths import saves_path
from src.world.schematic import Schematic

Entry = Dict
SHOWCASE_NAMES = ("formas", "vitrine", "shapes")


def _clean(text: str) -> str:
    return text.strip().strip("\"'").strip()


def _schem_path(name: str, schematics_dir: str) -> Optional[str]:
    candidates = [name, name + ".schem", os.path.join(schematics_dir, name), os.path.join(schematics_dir, name + ".schem")]
    return next((p for p in candidates if os.path.isfile(p)), None)


def _object_entry(path: str) -> Entry:
    from src.editor.voxel_object import VoxelObject
    obj = VoxelObject.load(path)
    return {"kind": "object", "object": obj.to_dict(), "name": os.path.splitext(os.path.basename(path))[0]}


def library(schematics_dir: str, object_paths: List[str]) -> List[Tuple[str, Entry]]:
    """(rótulo, entrada) de tudo que dá para colocar: os .schem da pasta, a vitrine e os objetos (os inválidos saem)."""
    items: List[Tuple[str, Entry]] = []
    try:
        files = sorted(f for f in os.listdir(schematics_dir) if f.lower().endswith(".schem"))
    except OSError:
        files = []
    for name in files:
        stem = os.path.splitext(name)[0]
        items.append((stem, {"kind": "schem", "name": stem}))
    items.append(("formas", {"kind": "formas"}))
    for path in object_paths:
        try:
            entry = _object_entry(path)
        except Exception:   # JSON quebrado ou de outro formato: fica fora da lista
            continue
        items.append((entry["name"], entry))
    return items


def entry_for_text(text: str, schematics_dir: str) -> Optional[Entry]:
    """A entrada para o que se digita no ``/schem load``: nome da pasta, caminho de .schem ou .json, ou a vitrine."""
    text = _clean(text)
    if not text:
        return None
    if text.lower() in SHOWCASE_NAMES:
        return {"kind": "formas"}
    if text.lower().endswith(".json") and os.path.isfile(text):
        try:
            return _object_entry(text)
        except Exception:
            return None
    path = _schem_path(text, schematics_dir)
    if path is None:
        return None
    stem = os.path.splitext(os.path.basename(path))[0]
    inside = os.path.isfile(os.path.join(schematics_dir, stem + ".schem")) and \
        os.path.samefile(path, os.path.join(schematics_dir, stem + ".schem"))
    return {"kind": "schem", "name": stem if inside else os.path.abspath(path)}


def _managed_path(digest: str) -> Path:
    if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("Identificador da cópia .schem inválido.")
    return saves_path("schematics", digest + ".schem")


def _read_schem_bytes(path: Path) -> bytes:
    from src.world.schematic import MAX_SCHEM_FILE_BYTES

    with path.open("rb") as source:
        raw = source.read(MAX_SCHEM_FILE_BYTES + 1)
    if len(raw) > MAX_SCHEM_FILE_BYTES:
        raise ValueError("Arquivo .schem maior que o limite de importação.")
    return raw


def snapshot_external(entry: Entry) -> Tuple[Entry, Schematic]:
    """Valida e guarda os mesmos bytes importados, independentemente do arquivo de origem."""
    source = Path(entry["name"])
    raw = _read_schem_bytes(source)
    schematic = Schematic.load_from_bytes(raw, source.stem)
    digest = hashlib.sha256(raw).hexdigest()
    destination = _managed_path(digest)
    try:
        synchronized = hashlib.sha256(_read_schem_bytes(destination)).hexdigest() == digest
    except (OSError, ValueError):
        synchronized = False
    if not synchronized:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                temporary.write(raw)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary.close()
                os.replace(temporary_path, destination)
            finally:
                temporary.close()
                temporary_path.unlink(missing_ok=True)
    return {"kind": "schem", "name": source.stem, "sha256": digest}, schematic


def load_entry(entry: Entry, schematics_dir: str) -> Schematic:
    """A construção (sem giro) de uma entrada. ``FileNotFoundError`` se o .schem sumiu; ``ValueError`` se não dá."""
    kind = entry.get("kind")
    if kind == "formas":
        from src.world.shape_showcase import showcase_schematic
        return showcase_schematic()
    if kind == "schem":
        name = str(entry.get("name", ""))
        if "sha256" in entry:
            digest = entry["sha256"]
            raw = _read_schem_bytes(_managed_path(digest))
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("A cópia local da construção perdeu a integridade.")
            return Schematic.load_from_bytes(raw, name)
        path = _schem_path(name, schematics_dir)
        if path is None:
            raise FileNotFoundError(f"Construção '{name}' não encontrada.")
        return Schematic.load_from_file(path)
    if kind == "object":
        from src.editor.room_structures import object_schematic
        from src.editor.voxel_object import VoxelObject
        name = str(entry.get("name") or "objeto")
        return object_schematic(VoxelObject.from_dict(entry["object"]), name)
    raise ValueError(f"Tipo de construção desconhecido: {kind!r}")
