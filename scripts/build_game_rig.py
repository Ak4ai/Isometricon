"""Build the game rig (16 bones, hands included) on a body open in Blender.

Run inside Blender with 123.blend (female, parts are the objects of "Collection 6") or
male_cage_work.blend (male, parts are the Export_* vertex groups of Corpo_masculino).
Joints come from the body itself: where two parts meet, the centre of their seam ring;
where one part sinks into the next (neck, shoulders, ankles), the end ring of the child.
The rig is a new armature in the collection "Rig do jogo"; nothing is parented to it, so
the exported body is untouched. Adjust the bones by hand if needed, then run
scripts/export_rig.py.
"""
import bpy
import numpy as np
from mathutils import Vector

FEMALE_OBJECTS = {
    "cabeca": "cabeca.001", "pescoco": "pecoco.001", "torso": "Export_torso.001", "pelve": "Export_pelve.001",
    "braco_L": "Export_braco_superior_esquerdo.001", "antebraco_L": "Export_antebraco_esquerdo.001",
    "mao_L": "Export_mao_esquerda.001", "braco_R": "Export_braco_superior_direito.001",
    "antebraco_R": "Export_antebraco_direito.001", "mao_R": "Export_mao_direita.001",
    "coxa_L": "Export_coxa_esquerda.001", "canela_L": "Export_canela_esquerda.001", "pe_L": "pe_esquerdo.003",
    "coxa_R": "Export_coxa_direita.001", "canela_R": "Export_canela_direita.001", "pe_R": "pe_direito.003",
}
MALE_GROUPS = {
    "cabeca": "Export_cabeca", "pescoco": "Export_pecoco", "torso": "Export_torso", "pelve": "Export_pelve",
    "braco_L": "Export_braco_superior_esquerdo", "antebraco_L": "Export_antebraco_esquerdo", "mao_L": "Export_mao_esquerda",
    "braco_R": "Export_braco_superior_direito", "antebraco_R": "Export_antebraco_direito", "mao_R": "Export_mao_direita",
    "coxa_L": "Export_coxa_esquerda", "canela_L": "Export_canela_esquerda", "pe_L": "Export_pe_esquerdo",
    "coxa_R": "Export_coxa_direita", "canela_R": "Export_canela_direita", "pe_R": "Export_pe_direito",
}


def parts_from_objects(names):
    return {k: np.array([bpy.data.objects[n].matrix_world @ v.co for v in bpy.data.objects[n].data.vertices])
            for k, n in names.items()}


def parts_from_groups(obj, groups):
    index = {g.name: g.index for g in obj.vertex_groups}
    parts = {}
    for key, group in groups.items():
        gi = index[group]
        parts[key] = np.array([obj.matrix_world @ v.co for v in obj.data.vertices
                               if any(e.group == gi and e.weight > 0.5 for e in v.groups)])
    return parts


def joints(P):
    def end_ring(part, towards, band=0.015):
        """Centre of the end ring of ``part`` (along its long axis) closest to ``towards``."""
        X = P[part]
        c = X.mean(0)
        u = np.linalg.svd(X - c)[2][0]
        t = (X - c) @ u
        ends = [X[t > t.max() - band], X[t < t.min() + band]]
        dist = [np.linalg.norm(e[:, None] - P[towards][None], axis=2).min() for e in ends]
        return ends[int(np.argmin(dist))].mean(0)

    J = {"pescoco_base": end_ring("pescoco", "torso"), "pescoco_topo": end_ring("pescoco", "cabeca")}
    pelvis = P["pelve"]
    J["cintura"] = pelvis[pelvis[:, 2] > pelvis[:, 2].max() - 0.015].mean(0)
    for s in "LR":
        # Shoulder and thigh tops are slanted: their centres are taken over a longer band.
        J["ombro_" + s] = end_ring("braco_" + s, "torso", band=0.05)
        J["cotovelo_" + s] = (end_ring("braco_" + s, "antebraco_" + s) + end_ring("antebraco_" + s, "braco_" + s)) / 2
        J["pulso_" + s] = (end_ring("antebraco_" + s, "mao_" + s) + end_ring("mao_" + s, "antebraco_" + s)) / 2
        hand = P["mao_" + s]
        d = hand.mean(0) - J["pulso_" + s]
        d /= np.linalg.norm(d)
        J["mao_ponta_" + s] = J["pulso_" + s] + d * ((hand - J["pulso_" + s]) @ d).max()
        J["quadril_" + s] = end_ring("coxa_" + s, "pelve", band=0.06)
        J["joelho_" + s] = (end_ring("coxa_" + s, "canela_" + s) + end_ring("canela_" + s, "coxa_" + s)) / 2
        # Ankle: centre of the shin's cross-section at the top of the foot.
        shin, foot = P["canela_" + s], P["pe_" + s]
        top = foot[:, 2].max()
        section = shin[np.abs(shin[:, 2] - top) < 0.03]
        if len(section) < 3:
            section = shin[np.argsort(np.abs(shin[:, 2] - top))[:4]]
        J["tornozelo_" + s] = np.array([section[:, 0].mean(), section[:, 1].mean(), top - 0.015])
        J["dedos_" + s] = np.array([foot[:, 0].mean(), foot[:, 1].min(), foot[:, 2].min()])
    J["quadris"] = (J["quadril_L"] + J["quadril_R"]) / 2
    J["cabeca_topo"] = np.array([0.0, J["pescoco_topo"][1], P["cabeca"][:, 2].max()])
    return J


def bones():
    spec = [("Pelvis", None, "quadris", "cintura", False), ("Torso", "Pelvis", "cintura", "pescoco_base", True),
            ("Neck", "Torso", "pescoco_base", "pescoco_topo", True), ("Head", "Neck", "pescoco_topo", "cabeca_topo", True)]
    for s in "LR":
        spec += [(f"UpperArm_{s}", "Torso", f"ombro_{s}", f"cotovelo_{s}", False),
                 (f"LowerArm_{s}", f"UpperArm_{s}", f"cotovelo_{s}", f"pulso_{s}", True),
                 (f"Hand_{s}", f"LowerArm_{s}", f"pulso_{s}", f"mao_ponta_{s}", True),
                 (f"UpperLeg_{s}", "Pelvis", f"quadril_{s}", f"joelho_{s}", False),
                 (f"LowerLeg_{s}", f"UpperLeg_{s}", f"joelho_{s}", f"tornozelo_{s}", True),
                 (f"Foot_{s}", f"LowerLeg_{s}", f"tornozelo_{s}", f"dedos_{s}", True)]
    return spec


def build_rig(name, J):
    collection = bpy.data.collections.get("Rig do jogo") or bpy.data.collections.new("Rig do jogo")
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old)
    data = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, data)
    collection.objects.link(rig)
    active = bpy.context.view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    spec = bones()
    for bone, _, head, tail, _ in spec:
        b = data.edit_bones.new(bone)
        b.head, b.tail = Vector(J[head]), Vector(J[tail])
    for bone, parent, _, _, connect in spec:
        b = data.edit_bones[bone]
        b.parent = data.edit_bones[parent] if parent else None
        b.use_connect = connect
        b.align_roll(Vector((0, -1, 0)))  # local Z to the front
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    return rig


if __name__ == "__main__":
    if bpy.data.objects.get("Corpo_masculino") is not None:
        build_rig("Rig_Jogo_Masculino", joints(parts_from_groups(bpy.data.objects["Corpo_masculino"], MALE_GROUPS)))
    else:
        build_rig("Rig_Jogo_Feminino", joints(parts_from_objects(FEMALE_OBJECTS)))
