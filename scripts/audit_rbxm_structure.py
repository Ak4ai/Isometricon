"""List binary RBXM classes and property names for one cached clothing asset."""
from pathlib import Path
import gzip
import struct
import sys
import lz4.block

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
root = project_root / "assets/models/clothing"
asset = sys.argv[1] if len(sys.argv) > 1 else "16185652164"
data = next(root.glob(f"*_{asset}.rbxm")).read_bytes()
if data.startswith(b"\x1f\x8b"):
    data = gzip.decompress(data)
classes = {}
properties = {}
property_payloads = {}
offset = 32
while offset + 16 <= len(data):
    fourcc, compressed, decoded, _ = struct.unpack_from("<4sIII", data, offset)
    chunk = data[offset + 16:offset + 16 + compressed]
    offset += 16 + compressed
    if compressed:
        chunk = lz4.block.decompress(chunk, uncompressed_size=decoded)
    if fourcc == b"INST":
        class_id, length = struct.unpack_from("<II", chunk)
        classes[class_id] = chunk[8:8 + length].decode()
    elif fourcc == b"PROP":
        class_id, length = struct.unpack_from("<II", chunk)
        name = chunk[8:8 + length].decode()
        properties.setdefault(class_id, []).append(name)
        property_payloads[(class_id,name)] = (chunk[8+length],chunk[9+length:])
    elif fourcc == b"END ":
        break
for class_id, name in classes.items():
    print(name, class_id, sorted(properties.get(class_id, [])))
    if name == "MeshPart":
        from src.clothing.wrap_layer_fit import _property_cframe
        for prop in ("HasSkinnedMesh", "CFrame", "PivotOffset"):
            if (class_id,prop) not in property_payloads:
                continue
            typ,payload=property_payloads[(class_id,prop)]
            if prop == "HasSkinnedMesh":
                value=bool(payload[0]) if payload else None
            elif typ == 0x10:
                rotation,origin=_property_cframe({prop:(typ,payload)},prop)
                value={"rotation":rotation.tolist(),"origin":origin.tolist()}
            else:
                value="unparsed"
            print("  ",prop,"type",typ,"value",value)
    if name == "WrapLayer" and (class_id,"AutoSkin") in property_payloads:
        typ,payload=property_payloads[(class_id,"AutoSkin")]
        print("   AutoSkin type",typ,"value",int.from_bytes(payload[:4],"little"))
