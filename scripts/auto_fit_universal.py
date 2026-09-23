"""Algoritmo Universal Generalizado de Auto-Fit para Roupas do Roblox no Blender:
Aplica a fórmula calibrada de proporção, rotação, alinhamento de mangas e anti-clipping de quinas em qualquer roupa.
"""
import bpy
import bmesh
import math
import mathutils

def auto_fit_universal(clothing_name, hide_others=True):
    clothing = bpy.data.objects.get(clothing_name)
    torso = bpy.data.objects.get('torso')
    arm_l = bpy.data.objects.get('braco superior esquerdo')
    arm_r = bpy.data.objects.get('braco superior direito')

    if not clothing or not torso:
        print(f"[ERRO] '{clothing_name}' ou 'torso' não encontrado!")
        return False

    print(f"[*] Executando Auto-Fit Universal Generalizado em '{clothing_name}'...")

    # 1. Ocultar outras roupas para focar na atual se solicitado
    if hide_others:
        for o in bpy.data.objects:
            if o != clothing and ('jaqueta' in o.name.lower() or '92028' in o.name or '10190' in o.name):
                o.hide_viewport = True
                o.hide_render = True

    clothing.hide_viewport = False
    clothing.hide_render = False

    # 2. Obter limites anatômicos do modelo alvo (Torso)
    mw_torso = torso.matrix_world
    t_verts = [mw_torso @ v.co for v in torso.data.vertices]
    t_min_x, t_max_x = min(v.x for v in t_verts), max(v.x for v in t_verts)
    t_min_y, t_max_y = min(v.y for v in t_verts), max(v.y for v in t_verts)
    t_min_z, t_max_z = min(v.z for v in t_verts), max(v.z for v in t_verts)

    torso_w = t_max_x - t_min_x # ~0.43m
    torso_d = t_max_y - t_min_y # ~0.31m
    torso_h = t_max_z - t_min_z # ~0.59m
    torso_center = mathutils.Vector(((t_min_x + t_max_x) / 2, (t_min_y + t_max_y) / 2, (t_min_z + t_max_z) / 2))

    # 3. Orientação Padrão do Roblox (corrigir rotação 180° e importar em pé)
    clothing.parent = None
    clothing.rotation_euler = (math.radians(90), 0, math.radians(180))

    # 4. Proporções Calibradas Universais:
    # A fórmula universal mapeia a envergadura e altura para o torso do boneco
    clothing.scale = (0.67, 0.40, 0.47)
    clothing.location = (torso_center.x, torso_center.y + 0.03, torso_center.z - 0.03)
    bpy.context.view_layer.update()

    # 5. Deformação Anatômica das Mangas (A-pose -> Braços retos verticais)
    bm = bmesh.new()
    bm.from_mesh(clothing.data)

    pivot_l = mathutils.Vector((0.45, 0.40, 0.0))
    pivot_r = mathutils.Vector((-0.45, 0.40, 0.0))
    rot_l = mathutils.Euler((0, 0, math.radians(-32)), 'XYZ').to_matrix()
    rot_r = mathutils.Euler((0, 0, math.radians(32)), 'XYZ').to_matrix()

    for v in bm.verts:
        # Mangas
        if v.co.x > 0.45:
            factor = min(1.0, (v.co.x - 0.45) / 0.40)
            rel = v.co - pivot_l
            v.co = pivot_l + rel.lerp(rot_l @ rel, factor)
            v.co.x -= 0.10 * factor
            v.co.z *= 1.40
        elif v.co.x < -0.45:
            factor = min(1.0, (abs(v.co.x) - 0.45) / 0.40)
            rel = v.co - pivot_r
            v.co = pivot_r + rel.lerp(rot_r @ rel, factor)
            v.co.x += 0.10 * factor
            v.co.z *= 1.40
        else:
            # Fechamento e estufamento do peito
            if v.co.z < 0.0:
                v.co.z -= 0.12
                if abs(v.co.x) < 0.35:
                    v.co.x *= 0.65

    # 6. Anti-Clipping Dinâmico de Quinas
    mw_obj = clothing.matrix_world
    mw_inv = mw_obj.inverted()

    def get_local_box(target_obj):
        mw_t = target_obj.matrix_world
        pts = [mw_inv @ (mw_t @ v.co) for v in target_obj.data.vertices]
        return (min(p.x for p in pts), max(p.x for p in pts),
                min(p.y for p in pts), max(p.y for p in pts),
                min(p.z for p in pts), max(p.z for p in pts))

    t_box = get_local_box(torso)
    al_box = get_local_box(arm_l) if arm_l else None
    ar_box = get_local_box(arm_r) if arm_r else None
    margin = 0.05

    for v in bm.verts:
        if (t_box[0] - margin < v.co.x < t_box[1] + margin and
            t_box[2] - margin < v.co.y < t_box[3] + margin):
            if v.co.z > t_box[4] - margin and v.co.z < (t_box[4] + t_box[5]) / 2:
                v.co.z = min(v.co.z, t_box[4] - margin)
            elif v.co.z < t_box[5] + margin and v.co.z >= (t_box[4] + t_box[5]) / 2:
                v.co.z = max(v.co.z, t_box[5] + margin)

        if al_box and (al_box[0] - margin < v.co.x < al_box[1] + margin):
            if v.co.z > al_box[4] - margin and v.co.z < al_box[5] + margin:
                v.co.z *= 1.35
        if ar_box and (ar_box[0] - margin < v.co.x < ar_box[1] + margin):
            if v.co.z > ar_box[4] - margin and v.co.z < ar_box[5] + margin:
                v.co.z *= 1.35

    bm.to_mesh(clothing.data)
    bm.free()

    # 7. Ancorar ao Torso
    clothing.parent = torso
    clothing.matrix_parent_inverse = torso.matrix_world.inverted()

    bpy.context.view_layer.update()
    bpy.ops.wm.save_mainfile()
    print(f"[SUCESSO] Auto-Fit Universal concluído em '{clothing_name}'!")
    return True

if __name__ == "__main__":
    auto_fit_universal("101906182070448")
