"""List meshes inside local ClassicMannequin FBX without Blender."""
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
DATA = (ROOT / "ClassicMannequin_With-Cages.fbx").read_bytes()
VERSION = struct.unpack_from("<I", DATA, 23)[0]
assert VERSION < 7500


def property_at(offset):
    kind = chr(DATA[offset]); offset += 1
    scalar = {"Y": "h", "C": "?", "I": "i", "F": "f", "D": "d", "L": "q"}
    if kind in scalar:
        fmt = "<" + scalar[kind]
        value = struct.unpack_from(fmt, DATA, offset)[0]
        return value, offset + struct.calcsize(fmt)
    if kind in "SR":
        length = struct.unpack_from("<I", DATA, offset)[0]; offset += 4
        raw = DATA[offset:offset + length]
        return (raw.decode("utf-8", errors="replace") if kind == "S" else raw), offset + length
    if kind in "fdlibc":
        length, encoding, compressed_length = struct.unpack_from("<III", DATA, offset)
        offset += 12
        raw = DATA[offset:offset + compressed_length]
        if encoding:
            raw = zlib.decompress(raw)
        fmt = {"f": "f", "d": "d", "l": "q", "i": "i", "b": "?", "c": "B"}[kind]
        return struct.unpack("<" + fmt * length, raw), offset + compressed_length
    raise ValueError(f"Unknown FBX property {kind} at {offset}")


def nodes(start, stop):
    offset = start
    result = []
    while offset + 13 <= stop:
        end, count, length, name_length = struct.unpack_from("<IIIB", DATA, offset)
        if end == 0:
            break
        name = DATA[offset + 13:offset + 13 + name_length].decode("ascii", errors="replace")
        position = offset + 13 + name_length
        props = []
        for _ in range(count):
            value, position = property_at(position)
            props.append(value)
        children = nodes(position, end - 13) if position < end - 13 else []
        result.append((name, props, children))
        offset = end
    return result


def load_classic_body(path=None):
    """Return triangulated FBX Geo parts in engine XYZ coordinates."""
    import numpy as np
    global DATA
    if path is not None:
        DATA = Path(path).read_bytes()
    root = nodes(27, len(DATA))
    objects = next(children for name, _, children in root if name == "Objects")
    connections = next(children for name, _, children in root if name == "Connections")
    models = {props[0]: props[1].split("\x00")[0]
              for name, props, _ in objects if name == "Model"}
    parents = {props[1]: props[2] for name, props, _ in connections
               if name == "C" and props[0] == "OO"}
    vertices = []
    faces = []
    names = []
    for name, props, children in objects:
        if name != "Geometry":
            continue
        part_name = models.get(parents.get(props[0]), "")
        if not part_name.endswith("_Geo"):
            continue
        fields = {child_name: child_props[0] for child_name, child_props, _ in children
                  if child_name in ("Vertices", "PolygonVertexIndex")}
        raw = np.asarray(fields["Vertices"], dtype=np.float64).reshape(-1, 3)
        converted = raw[:, [0, 2, 1]]
        start = len(vertices)
        vertices.extend(converted)
        polygon = []
        for encoded in fields["PolygonVertexIndex"]:
            polygon.append(encoded if encoded >= 0 else -encoded - 1)
            if encoded < 0:
                faces.extend((start + polygon[0], start + polygon[i], start + polygon[i + 1])
                             for i in range(1, len(polygon) - 1))
                polygon = []
        names.append(part_name)
    if len(names) != 15:
        raise ValueError(f"Expected 15 Blocky R15 body parts, got {len(names)}")
    return np.asarray(vertices), np.asarray(faces, dtype=np.int32), names


def export_outer_cages_obj(path, output):
    """Export 15 official FBX outer cages with per-corner UV identity intact."""
    global DATA
    DATA = Path(path).read_bytes()
    root = nodes(27, len(DATA))
    objects = next(children for name, _, children in root if name == "Objects")
    connections = next(children for name, _, children in root if name == "Connections")
    models = {props[0]: props[1].split("\x00")[0]
              for name, props, _ in objects if name == "Model"}
    parents = {props[1]: props[2] for name, props, _ in connections
               if name == "C" and props[0] == "OO"}
    lines = ["# Outer cages from " + Path(path).name]
    vertex_offset = uv_offset = parts = 0
    for name, props, children in objects:
        part_name = models.get(parents.get(props[0]), "") if name == "Geometry" else ""
        if not part_name.endswith("_OuterCage"):
            continue
        fields = {child_name: child_props[0] for child_name, child_props, _ in children
                  if child_name in ("Vertices", "PolygonVertexIndex")}
        uv_children = next(items for child_name, _, items in children
                           if child_name == "LayerElementUV")
        uv_fields = {child_name: child_props[0] for child_name, child_props, _ in uv_children
                     if child_name in ("UV", "UVIndex")}
        vertices = list(zip(*[iter(fields["Vertices"])] * 3))
        uvs = list(zip(*[iter(uv_fields["UV"])] * 2))
        indices = fields["PolygonVertexIndex"]
        uv_indices = uv_fields["UVIndex"]
        if len(indices) != len(uv_indices):
            raise ValueError(f"UV loop mismatch in {part_name}")
        lines.append(f"o {part_name}")
        lines.extend("v " + " ".join(f"{value:.9f}" for value in vertex) for vertex in vertices)
        lines.extend("vt " + " ".join(f"{value:.9f}" for value in uv) for uv in uvs)
        polygon = []
        for encoded, uv_index in zip(indices, uv_indices):
            index = encoded if encoded >= 0 else -encoded - 1
            polygon.append(f"{vertex_offset + index + 1}/{uv_offset + uv_index + 1}")
            if encoded < 0:
                lines.append("f " + " ".join(polygon))
                polygon = []
        if polygon:
            raise ValueError(f"Unterminated polygon in {part_name}")
        vertex_offset += len(vertices)
        uv_offset += len(uvs)
        parts += 1
    if parts != 15:
        raise ValueError(f"Expected 15 outer cages, got {parts}")
    Path(output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"parts": parts, "vertices": vertex_offset, "uvs": uv_offset}


if __name__ == "__main__":
    root = nodes(27, len(DATA))
    objects = next(children for name, _, children in root if name == "Objects")
    for name, props, children in objects:
        if name in ("Geometry", "Model"):
            print(name, props[:3], "verts", next((len(p[0]) // 3 for n, p, _ in children
                                                   if n == "Vertices"), ""))
