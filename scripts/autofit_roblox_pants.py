"""Módulo de Auto-Fit Universal de Calças e Sapatos do Roblox (Python / Blender).

Aplica o pipeline exato do motor do Roblox para peças de pernas/quadril:
1. Posicionamento e Escala Natural com base na anatomia do personagem (cintura até a sola do pé).
2. Deformação via SurfaceDeform vinculado à Roblox_Inner_Cage_Universal.
3. HSR (Hidden Surface Removal) para evitar clipping nos membros cobertos.
4. Renderização e exportação FBX do outfit completo.
"""

import bpy
import bmesh
import os
import math
from mathutils import Vector, Euler

def autofit_pants(
    clothing_obj_name="Pants_1",
    raw_obj_path=None,
    target_waist_z=0.935,
    target_sole_z=-0.010,
    render_output=r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders\pants_universal_rest.png",
    output_fbx=r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_full_outfit.fbx"
):
    print("==================================================")
    print(f"  AUTO-FIT UNIVERSAL ROBLOX PANTS: {clothing_obj_name}")
    print("==================================================")

    cage = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
    arm = bpy.data.objects.get("Armature_Character")
    pants = bpy.data.objects.get(clothing_obj_name) or bpy.data.objects.get("clothing_109837605892174")

    assert cage and arm and pants, f"Objetos necessários ({clothing_obj_name}, cage, arm) não encontrados!"
    pants.name = clothing_obj_name

    clothing_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing"
    if raw_obj_path is None:
        target_v_count = len(pants.data.vertices)
        for fname in os.listdir(clothing_dir):
            if fname.endswith(".obj"):
                fpath = os.path.join(clothing_dir, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    c = sum(1 for l in f if l.startswith("v "))
                if c == target_v_count:
                    raw_obj_path = fpath
                    break
        if raw_obj_path is None:
            raw_obj_path = os.path.join(clothing_dir, "clothing_109837605892174.obj")

    # 1. Ler geometria bruta do OBJ
    raw_verts = []
    with open(raw_obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                raw_verts.append([float(x) for x in line.split()[1:4]])

    y_min_orig = min(v[1] for v in raw_verts)
    y_max_orig = max(v[1] for v in raw_verts)
    total_y_span = y_max_orig - y_min_orig

    # 2. Recriar ponteiro limpo para evitar cache C++ stale
    def recreate_clean_object(obj_name):
        old_obj = bpy.data.objects.get(obj_name)
        if not old_obj:
            return None
        col = old_obj.users_collection[0] if old_obj.users_collection else bpy.context.scene.collection
        mats = list(old_obj.data.materials)
        parent = old_obj.parent
        scale = tuple(old_obj.scale)
        rot = tuple(old_obj.rotation_euler)
        loc = tuple(old_obj.location)

        new_mesh = bpy.data.meshes.new(f"{obj_name}_Mesh")
        bm = bmesh.new()
        bm.from_mesh(old_obj.data)
        bm.to_mesh(new_mesh)
        bm.free()
        for m in mats:
            new_mesh.materials.append(m)

        old_mesh = old_obj.data
        bpy.data.objects.remove(old_obj)
        try:
            bpy.data.meshes.remove(old_mesh)
        except:
            pass

        new_obj = bpy.data.objects.new(obj_name, new_mesh)
        new_obj.scale = scale
        new_obj.rotation_euler = rot
        new_obj.location = loc
        new_obj.parent = parent
        col.objects.link(new_obj)
        bpy.context.view_layer.update()
        return new_obj

    pants = recreate_clean_object(clothing_obj_name)
    if pants.animation_data:
        pants.animation_data_clear()

    # Resetar vértices para o OBJ bruto
    for i, v in enumerate(pants.data.vertices):
        v.co = raw_verts[i]
    pants.data.update()

    # 3. Escala e Posicionamento Anatômico
    target_z_span = target_waist_z - target_sole_z
    scale_y = target_z_span / total_y_span
    loc_z = target_waist_z - y_max_orig * scale_y
    loc_y = 0.005

    pants.scale = (scale_y, scale_y, scale_y)
    pants.rotation_euler = (math.radians(90), 0, math.radians(180))
    pants.location = (0.0, loc_y, loc_z)
    bpy.context.view_layer.update()

    print(f"[*] Calça posicionada: scale={scale_y:.4f}, Z=[{target_sole_z:.3f}, {target_waist_z:.3f}]m")

    # 4. Bind via SurfaceDeform na Roblox_Inner_Cage_Universal com braços abertos (T-Pose a 85°)
    # Garante que nenhum vértice do cós da calça se prenda aos braços/mãos da cage
    pb_arm_l = arm.pose.bones.get("UpperArm_L")
    pb_arm_r = arm.pose.bones.get("UpperArm_R")
    if pb_arm_l and pb_arm_r:
        pb_arm_l.rotation_mode = 'XYZ'
        pb_arm_r.rotation_mode = 'XYZ'
        pb_arm_l.rotation_euler = (0, 0, math.radians(-85))
        pb_arm_r.rotation_euler = (0, 0, math.radians(85))
        bpy.context.view_layer.update()

    mod = pants.modifiers.new(name="SurfaceDeform", type="SURFACE_DEFORM")
    mod.target = cage
    with bpy.context.temp_override(object=pants, active_object=pants):
        bpy.ops.object.surfacedeform_bind(modifier="SurfaceDeform")
    print(f"[*] SurfaceDeform vinculado: {mod.is_bound}")

    # Retorna braços para o repouso
    if pb_arm_l and pb_arm_r:
        pb_arm_l.rotation_euler = (0, 0, 0)
        pb_arm_r.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()

    # 5. Roblox HSR (Ocultar membros cobertos pela calça)
    parts_covered = [
        "pelve", "coxa direita", "coxa esquerda",
        "canela direita", "canela esquerda", "pe direito", "pe esquerdo"
    ]
    for p in parts_covered:
        o = bpy.data.objects.get(p)
        if o:
            o.hide_render = True
            o.hide_viewport = True

    # 6. Salvar cena e renderizar
    if render_output:
        os.makedirs(os.path.dirname(render_output), exist_ok=True)
        cam = bpy.data.objects.get("Camera")
        if cam:
            cam.location = (0, -3.2, 0.95)
            cam.rotation_euler = (math.radians(90), 0, 0)
            bpy.context.view_layer.update()
            bpy.context.scene.render.filepath = render_output
            bpy.ops.render.render(write_still=True)
            print(f"[*] Render salvo em: {render_output}")
            cam.location = (0, -3.2, 1.25)
            cam.rotation_euler = (math.radians(88), 0, 0)
            bpy.context.view_layer.update()

    bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath)
    print(f"[*] Arquivo .blend salvo: {bpy.data.filepath}")

    # 7. Exportar FBX do Outfit Completo
    if output_fbx:
        for o in bpy.data.objects:
            o.select_set(False)
        export_names = [
            "Armature_Character", "cabeca", "cabelo", "laco_direito", "laco_esquerdo", "nariz.002",
            "pecoco", "antebraco esquerdo", "antebraco direito", "Sweater_1", clothing_obj_name
        ]
        for n in export_names:
            o = bpy.data.objects.get(n)
            if o:
                o.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.export_scene.fbx(
            filepath=output_fbx,
            use_selection=True,
            global_scale=1.0,
            axis_forward="-Z",
            axis_up="Y",
            apply_scale_options="FBX_SCALE_ALL",
            bake_space_transform=False,
            object_types={"ARMATURE", "MESH"},
            use_mesh_modifiers=True,
            add_leaf_bones=False,
            primary_bone_axis="Y",
            secondary_bone_axis="X",
            armature_nodetype="NULL"
        )
        print(f"[*] FBX com outfit completo exportado em: {output_fbx}")

    print("==================================================")
    print("  AUTO-FIT DE CALÇAS CONCLUÍDO COM SUCESSO!       ")
    return True

if __name__ == "__main__":
    autofit_pants()
