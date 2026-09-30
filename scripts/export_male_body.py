"""Export the male body and its R15 cages from assets/models/male_cage_work.blend.

Run inside Blender with male_cage_work.blend open (Text Editor > Run Script, or through
the Blender MCP). Writes:
  assets/models/character_male_clean_apose.obj  body, one object per Export_* group
  assets/models/male_cages_apose.obj            cages, in the female cage's exact topology

The body is one welded mesh: each face goes to the vertex group all its corners share;
a face on a seam between two groups goes to the one it faces away from. The cage OBJ is
the female cage file with every vertex moved to the male cage point of the same UV, so
both bodies have the same cage faces, order and UVs.
Blender (x, y, z) -> OBJ (x, z, -y): Y up, front +Z, like the female files.
"""
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

MODELS = Path(bpy.data.filepath).parent
BODY_GROUPS = [
    "Export_cabeca", "Export_pecoco", "Export_torso", "Export_pelve",
    "Export_braco_superior_esquerdo", "Export_antebraco_esquerdo", "Export_mao_esquerda",
    "Export_braco_superior_direito", "Export_antebraco_direito", "Export_mao_direita",
    "Export_coxa_esquerda", "Export_canela_esquerda", "Export_pe_esquerdo",
    "Export_coxa_direita", "Export_canela_direita", "Export_pe_direito",
]


def obj_point(co):
    return co.x, co.z, -co.y


def export_body(path):
    body = bpy.data.objects["Corpo_masculino"]
    mesh = body.data
    names = {group.index: group.name for group in body.vertex_groups}
    groups = [{names[e.group] for e in v.groups if e.weight > 0.5} for v in mesh.vertices]
    centre = {}
    for name in BODY_GROUPS:
        points = [v.co for v in mesh.vertices if name in groups[v.index]]
        centre[name] = sum(points, Vector()) / len(points)
    faces = {name: [] for name in BODY_GROUPS}
    for polygon in mesh.polygons:
        shared = set.intersection(*[groups[i] for i in polygon.vertices])
        if not shared:
            raise ValueError(f"face {polygon.index} sem grupo comum a todos os vértices")
        best = max(shared, key=lambda n: polygon.normal.dot((polygon.center - centre[n]).normalized()))
        faces[best].append(polygon)

    uv = mesh.uv_layers["UVMap"].data
    normals = mesh.corner_normals
    head = ["# Isometricon male A-pose clean mesh (same groups and pose as the female)",
            "# Exported from male_cage_work.blend by scripts/export_male_body.py",
            "mtllib character_female_clean.mtl"]
    head += ["v %.6f %.6f %.6f" % obj_point(v.co) for v in mesh.vertices]
    body_lines, corner = [], 0
    for name in BODY_GROUPS:
        body_lines += [f"o {name}", "usemtl " + ("Mat_Head_Atlas.011" if name == "Export_cabeca" else "Mat_Pele_Corpo")]
        for polygon in faces[name]:
            tokens = []
            for loop in polygon.loop_indices:
                corner += 1
                head.append("vt %.6f %.6f" % tuple(uv[loop].uv))
                head.append("vn %.4f %.4f %.4f" % obj_point(normals[loop].vector))
                tokens.append(f"{mesh.loops[loop].vertex_index + 1}/{corner}/{corner}")
            body_lines.append("f " + " ".join(tokens))
    path.write_text("\n".join(head + body_lines) + "\n", encoding="utf-8")
    return {name: len(f) for name, f in faces.items()}


def export_cages(path, female_path):
    by_part = {}
    for cage in bpy.data.collections["Cage masculina (partes)"].objects:
        part = cage.name.replace("_OuterCage_edit", "")
        uv = cage.data.uv_layers["UVMap"].data
        loops = [(tuple(uv[loop.index].uv), obj_point(cage.matrix_world @ cage.data.vertices[loop.vertex_index].co))
                 for loop in cage.data.loops]
        by_part[part] = (np.array([l[0] for l in loops]), np.array([l[1] for l in loops]))

    lines = female_path.read_text(encoding="utf-8").splitlines()
    uvs = [list(map(float, l.split()[1:3])) for l in lines if l.startswith("vt ")]
    part_of, vertex_uvs, part = [], {}, None
    for line in lines:
        if line.startswith("o "):
            part = line[2:].replace("_OuterCage", "")
        elif line.startswith("v "):
            part_of.append(part)
        elif line.startswith("f "):
            for token in line.split()[1:]:
                vertex, uv_index = (int(x) - 1 for x in token.split("/")[:2])
                vertex_uvs.setdefault(vertex, []).append(uvs[uv_index])

    positions = []
    for vertex, part in enumerate(part_of):
        male_uv, male_pos = by_part[part]
        found = []
        for uv in vertex_uvs[vertex]:
            distance = np.abs(male_uv - uv).max(1)
            nearest = int(distance.argmin())
            if distance[nearest] > 1e-3:
                raise ValueError(f"{part}: UV {uv} da cage feminina não existe na masculina")
            found.append(male_pos[nearest])
        if np.ptp(found, axis=0).max() > 1e-4:
            raise ValueError(f"{part}: a mesma UV em dois lugares na cage masculina (vértice {vertex})")
        positions.append(found[0])

    out, index = [], 0
    for line in lines:
        if line.startswith("#"):
            out.append("# Isometricon male R15 outer cages (same topology and UVs as the female cage)")
        elif line.startswith("v "):
            out.append("v %.9f %.9f %.9f" % tuple(positions[index]))
            index += 1
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(positions)


if __name__ == "__main__":
    print("corpo:", export_body(MODELS / "character_male_clean_apose.obj"))
    print("cage:", export_cages(MODELS / "male_cages_apose.obj", MODELS / "female_cages_apose_stage2.obj"), "vértices")
