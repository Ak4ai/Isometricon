"""Export the local Roblox R15 FBX reference cages with their UV bindings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "artifacts" / "clothing_audit"
OUTPUT = ROOT / "assets" / "models" / "roblox_reference_cages.obj"

reference = json.loads((AUDIT / "r15_reference_snapshot.json").read_text(encoding="utf-8"))
lines = [
    "# Roblox R15 reference cages exported from ClassicMannequin_With-Cages.fbx",
    "# Positions are in FBX reference coordinates; vt/vt-index pairs retain per-corner UVs.",
]
vertex_offset = 0
uv_offset = 0
part_count = 0

for name, part in reference.items():
    if not name.endswith("_OuterCage") or name.startswith("_"):
        continue
    raw_vertices = part["verts"]
    assert len(raw_vertices) % 3 == 0, f"Invalid vertex array: {name}"
    vertices = [raw_vertices[i:i + 3] for i in range(0, len(raw_vertices), 3)]
    uvs = part["uv"]
    assert len(uvs) % 2 == 0, f"Invalid UV array: {name}"
    uvs = [uvs[i:i + 2] for i in range(0, len(uvs), 2)]

    faces = []
    face = []
    for encoded_index in part["indices"]:
        face.append(encoded_index if encoded_index >= 0 else -encoded_index - 1)
        if encoded_index < 0:
            faces.append(face)
            face = []
    assert not face, f"Unterminated polygon: {name}"

    uv_indices = part.get("uv_indices")
    assert uv_indices is not None, f"Reference cage has no UV indices: {name}"
    assert sum(map(len, faces)) == len(uv_indices), f"UV loop count mismatch: {name}"

    lines.append("")
    lines.append(f"o {name}")
    lines.extend("v " + " ".join(f"{float(c):.9f}" for c in v) for v in vertices)
    lines.extend("vt " + " ".join(f"{float(c):.9f}" for c in uv) for uv in uvs)

    loop = 0
    for polygon in faces:
        tokens = []
        for vertex_index in polygon:
            uv_index = uv_indices[loop]
            tokens.append(f"{vertex_offset + vertex_index + 1}/{uv_offset + uv_index + 1}")
            loop += 1
        lines.append("f " + " ".join(tokens))

    vertex_offset += len(vertices)
    uv_offset += len(uvs)
    part_count += 1

OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
assert part_count == 15, f"Expected 15 R15 body cages, found {part_count}"
print(json.dumps({"output": str(OUTPUT), "parts": part_count, "vertices": vertex_offset, "uvs": uv_offset}, indent=2))
