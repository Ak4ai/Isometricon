"""Minimal reader for Roblox binary models (.rbxm): instances, their properties and parents.

Only the property types an accessory needs are decoded (strings, bools, floats, Vector3,
CFrame and references); other properties are skipped. Format reference:
https://dom.rojo.space/binary.html
"""
from __future__ import annotations

import gzip
import os
import struct
from pathlib import Path

import numpy as np

# Rotation ids of the special-case CFrames: (Y, X, Z) Euler angles in degrees.
from .wear_engine import ROBLOX_ROTATION_TABLE, euler_yxz_to_matrix


def _deinterleave(data: bytes, count: int, width: int = 4) -> list[bytes]:
    """Values stored byte-plane by byte-plane (all first bytes, then all second bytes...)."""
    return [bytes(data[plane * count + i] for plane in range(width)) for i in range(count)]


def _roblox_floats(data: bytes, count: int) -> list[float]:
    values = []
    for raw in _deinterleave(data, count):
        bits = struct.unpack(">I", raw)[0]
        values.append(struct.unpack(">f", struct.pack(">I", ((bits & 1) << 31) | (bits >> 1)))[0])
    return values


def _roblox_ints(data: bytes, count: int) -> list[int]:
    values = []
    for raw in _deinterleave(data, count):
        bits = struct.unpack(">I", raw)[0]
        values.append((bits >> 1) ^ -(bits & 1))
    return values


def _referents(data: bytes, count: int) -> list[int]:
    values, total = [], 0
    for delta in _roblox_ints(data, count):
        total += delta
        values.append(total)
    return values


def _decode(type_id: int, data: bytes, count: int):
    if type_id == 0x01:  # String
        values, offset = [], 0
        for _ in range(count):
            size = struct.unpack_from("<I", data, offset)[0]
            values.append(data[offset + 4:offset + 4 + size])
            offset += 4 + size
        return values
    if type_id == 0x02:  # Bool
        return [bool(b) for b in data[:count]]
    if type_id == 0x04:  # Float32
        return _roblox_floats(data, count)
    if type_id == 0x0E:  # Vector3
        xs, ys, zs = (_roblox_floats(data[i * 4 * count:(i + 1) * 4 * count], count) for i in range(3))
        return [np.array(v, dtype=np.float64) for v in zip(xs, ys, zs)]
    if type_id == 0x10:  # CFrame: rotations for all instances, then the positions as Vector3s
        rotations, offset = [], 0
        for _ in range(count):
            kind = data[offset]
            offset += 1
            if kind == 0:
                rotations.append(np.asarray(struct.unpack_from("<9f", data, offset), dtype=np.float64).reshape(3, 3))
                offset += 36
            else:
                rotations.append(euler_yxz_to_matrix(*ROBLOX_ROTATION_TABLE[kind]))
        positions = _decode(0x0E, data[offset:], count)
        return list(zip(rotations, positions))
    if type_id == 0x13:  # Referent
        return _referents(data, count)
    return None


class Instance:
    def __init__(self, class_name: str, referent: int):
        self.class_name = class_name
        self.referent = referent
        self.properties: dict = {}
        self.parent: Instance | None = None
        self.children: list[Instance] = []

    @property
    def name(self) -> str:
        value = self.properties.get("Name", b"")
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()

    def __repr__(self):
        return f"<{self.class_name} {self.name!r}>"


def read_rbxm(source: str | os.PathLike | bytes) -> list[Instance]:
    """All instances of a binary .rbxm, parents linked; roots have ``parent`` None."""
    import lz4.block
    data = source if isinstance(source, (bytes, bytearray)) else Path(source).read_bytes()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    if not data.startswith(b"<roblox!"):
        raise ValueError("RBXM binário esperado")
    classes, by_referent = {}, {}
    offset = 32
    while offset + 16 <= len(data):
        fourcc, compressed, size, _ = struct.unpack_from("<4sIII", data, offset)
        chunk = data[offset + 16:offset + 16 + compressed] if compressed else data[offset + 16:offset + 16 + size]
        offset += 16 + (compressed or size)
        if compressed:
            chunk = lz4.block.decompress(chunk, uncompressed_size=size)
        if fourcc == b"INST":
            class_id, name_size = struct.unpack_from("<II", chunk)
            name = chunk[8:8 + name_size].decode("utf-8")
            count = struct.unpack_from("<I", chunk, 9 + name_size)[0]
            referents = _referents(chunk[13 + name_size:], count)
            instances = [Instance(name, r) for r in referents]
            classes[class_id] = instances
            by_referent.update((i.referent, i) for i in instances)
        elif fourcc == b"PROP":
            class_id, name_size = struct.unpack_from("<II", chunk)
            name = chunk[8:8 + name_size].decode("utf-8")
            instances = classes.get(class_id, [])
            values = _decode(chunk[8 + name_size], chunk[9 + name_size:], len(instances))
            if values is not None:
                for instance, value in zip(instances, values):
                    instance.properties[name] = value
        elif fourcc == b"PRNT":
            count = struct.unpack_from("<I", chunk, 1)[0]
            children = _referents(chunk[5:5 + 4 * count], count)
            parents = _referents(chunk[5 + 4 * count:], count)
            for child, parent in zip(children, parents):
                if child in by_referent and parent in by_referent:
                    by_referent[child].parent = by_referent[parent]
                    by_referent[parent].children.append(by_referent[child])
        elif fourcc == b"END ":
            break
    return list(by_referent.values())
