"""Export a game rig (Rig_Jogo_Feminino / Rig_Jogo_Masculino) to assets/models/rig_<body>.json.

Run inside Blender with the .blend that holds the rig open (123.blend for the female body,
male_cage_work.blend for the male one), from the Text Editor or the Blender MCP.
Every bone is written in the game's mesh coordinates (OBJ: x, y up, z front), in the A-pose
of the exported body: {"bones": [{"name", "parent", "head", "tail"}, ...]} parents first.
Blender (x, y, z) -> OBJ (x, z, -y), like scripts/export_male_body.py.
"""
import json
from pathlib import Path

import bpy

RIGS = {"Rig_Jogo_Feminino": "female", "Rig_Jogo_Masculino": "male"}


def obj_point(co):
    return [round(co.x, 6), round(co.z, 6), round(-co.y, 6)]


def export_rig(rig, path):
    bones = []
    for bone in rig.data.bones:  # Blender lists parents before their children
        bones.append({"name": bone.name, "parent": bone.parent.name if bone.parent else None,
                      "head": obj_point(rig.matrix_world @ bone.head_local),
                      "tail": obj_point(rig.matrix_world @ bone.tail_local)})
    path.write_text(json.dumps({"bones": bones}, indent=1), encoding="utf-8")
    return len(bones)


if __name__ == "__main__":
    models = Path(bpy.data.filepath).parent
    for name, body in RIGS.items():
        rig = bpy.data.objects.get(name)
        if rig is not None:
            print(name, "->", export_rig(rig, models / f"rig_{body}.json"), "ossos")
