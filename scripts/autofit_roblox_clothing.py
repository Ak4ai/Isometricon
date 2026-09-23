"""Módulo definitivo de Auto-Fit Universal de Roupas Superiores do Roblox (Python / Blender).

Funciona para QUALQUER asset do catálogo (mangas curtas, compridas ou regatas):
1. Sincronização Anatômica da Cage: Garante alinhamento esquerdo/direito da Inner Cage.
2. Identificação Topológica Robusta:
   - Separa mangas e torso com análise de travessia da linha média (midline crossing).
   - Suporta arquivos multi-componentes (camisa com gravata, botões, colarinho) e malhas soldadas.
3. Detecção Automática do Tipo de Manga:
   - Regata / Sem Manga (Sleeveless)
   - Manga Curta / Média (Short Sleeves)
   - Manga Longa / Comprida (Long Sleeves)
4. Ajuste Proporcional Adaptativo:
   - Manga Longa: encurtamento proporcional, projeção no antebraço e alargamento suave do punho.
   - Manga Curta / Regata: preserva 100% da anatomia do ombro e manga, sem distorções nem pontas.
5. Tapering Anatômico da Cintura e Gola contínua (Hermite/Smoothstep).
6. Binding Otimizado via SurfaceDeform:
   - Manga Curta / Regata: Single-Zone em A-Pose (28.5°) para preservar a costura ombro-manga.
   - Manga Longa: Dual-Zone (Tronco a 75° e Mangas a 28.5°) para evitar cross-binding no cós.
7. Roblox HSR Universal ("Mostrar só o necessário do braço"):
   - Restaura malhas puras dos braços superiores a partir de character_male.blend.
   - Manga Longa: braços superiores ocultos, antebraços mascarados para apenas a mão.
   - Manga Curta: antebraço 100% visível, braço superior seccionado exatamente na altura da bainha da manga,
     emergindo naturalmente sem gaps, sem flutuação e sem clipping.
   - Regata: braços 100% visíveis.
8. Renderização Completa (Pose Neutra, Detalhe dos Ombros e Pose de Ação) e Exportação FBX.
"""

import bpy
import bmesh
import os
import math
from mathutils import Vector

def autofit(
    clothing_obj_name="Sweater_1",
    raw_obj_path=None,
    output_fbx=r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\character_dressed_complete.fbx",
    render_output=r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders\sweater_universal_rest.png",
    target_torso_bottom_z=0.890,
    target_waist_width=0.300,
    target_waist_depth=0.245,
    target_collar_z=1.490,
    target_mid_shoulder_z=1.478,
    target_outer_shoulder_z=1.445
):
    print("==================================================")
    print(f"  AUTO-FIT UNIVERSAL ROBLOX CLOTHING: {clothing_obj_name}")
    print("==================================================")

    cage = bpy.data.objects.get("Roblox_Inner_Cage_Universal")
    arm = bpy.data.objects.get("Armature_Character")
    jacket = bpy.data.objects.get(clothing_obj_name)

    assert cage and arm and jacket, f"Objetos necessários ({clothing_obj_name}, cage, arm) não encontrados!"

    # 1. Garantir que os grupos de vértices da cage estão alinhados com os ossos
    vg_l = cage.vertex_groups.get("UpperArm_L")
    if vg_l:
        verts_l = [v.co.x for v in cage.data.vertices if any(g.group == vg_l.index and g.weight > 0.5 for g in v.groups)]
        if verts_l and (sum(verts_l) / len(verts_l)) < 0:
            print("[*] Corrigindo inversão de lados L/R na Inner Cage...")
            pairs = [
                ('UpperArm_L', 'UpperArm_R'),
                ('LowerArm_L', 'LowerArm_R'),
                ('UpperLeg_L', 'UpperLeg_R'),
                ('LowerLeg_L', 'LowerLeg_R'),
                ('Foot_L', 'Foot_R')
            ]
            for nl, nr in pairs:
                vl = cage.vertex_groups.get(nl)
                vr = cage.vertex_groups.get(nr)
                if vl and vr:
                    vl.name = nl + '__TEMP'
                    vr.name = nl
                    vl.name = nr

    # 2. Recriar ponteiro limpo do objeto (elimina 100% de cache C++ corrompido de modificadores antigos)
    def recreate_clean_object(obj_name):
        old_obj = bpy.data.objects.get(obj_name)
        if not old_obj:
            return None
        col = old_obj.users_collection[0] if old_obj.users_collection else bpy.context.scene.collection
        mats = list(old_obj.data.materials)
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
        new_obj.parent = None
        col.objects.link(new_obj)
        bpy.context.view_layer.update()
        return new_obj

    jacket = recreate_clean_object(clothing_obj_name)
    if jacket.animation_data:
        jacket.animation_data_clear()

    clothing_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing"
    if raw_obj_path is None:
        if "sweater" in clothing_obj_name.lower():
            raw_obj_path = os.path.join(clothing_dir, "sweater_9240757332.obj")
        elif "jacket" in clothing_obj_name.lower():
            raw_obj_path = os.path.join(clothing_dir, "92028318196252.obj")
        else:
            target_v_count = len(jacket.data.vertices)
            for fname in os.listdir(clothing_dir):
                if fname.endswith(".obj"):
                    fpath = os.path.join(clothing_dir, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        c = sum(1 for l in f if l.startswith("v "))
                    if c == target_v_count:
                        raw_obj_path = fpath
                        break
            if raw_obj_path is None:
                raise FileNotFoundError(f"Não foi possível encontrar OBJ bruto para {clothing_obj_name}")

    # 3. Ler geometria bruta do OBJ original
    raw_verts = []
    with open(raw_obj_path, 'r', encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith('v '):
                raw_verts.append([float(x) for x in line.split()[1:4]])

    for i, v in enumerate(jacket.data.vertices):
        v.co = raw_verts[i]
    jacket.data.update()

    # 4. Análise e Normalização Geométrica Universal
    max_abs_x = max(abs(v[0]) for v in raw_verts)
    y_min_orig = min(v[1] for v in raw_verts)
    y_max_orig = max(v[1] for v in raw_verts)
    total_y_span = y_max_orig - y_min_orig
    norm_scale = 1.80 / total_y_span if total_y_span > 2.0 else 1.0
    uniform_scale = 0.54 * norm_scale
    loc_z = 1.185

    # 5. Identificação Robusta de Componentes (Midline Crossing)
    bm = bmesh.new()
    bm.from_mesh(jacket.data)
    visited = set()
    components = []
    for v in bm.verts:
        if v not in visited:
            comp = []
            stack = [v]
            visited.add(v)
            while stack:
                curr = stack.pop()
                comp.append(curr.index)
                for edge in curr.link_edges:
                    other = edge.other_vert(curr)
                    if other not in visited:
                        visited.add(other)
                        stack.append(other)
            components.append(comp)
    bm.free()

    sleeve_indices = set()
    torso_indices = set()

    if len(components) > 1:
        for c in components:
            min_x = min(raw_verts[idx][0] for idx in c)
            max_x = max(raw_verts[idx][0] for idx in c)
            comp_max_abs_x = max(abs(min_x), abs(max_x))
            crosses_midline = (min_x < -0.15 and max_x > 0.15)
            # Mangas ficam estritamente em um dos lados e projetam-se para fora
            if not crosses_midline and comp_max_abs_x > 0.38 * max_abs_x:
                sleeve_indices.update(c)
            else:
                torso_indices.update(c)
    else:
        # Malha única soldada: divide por limiar anatômico do tórax
        for idx, v in enumerate(raw_verts):
            if abs(v[0]) > 0.40 * max_abs_x:
                sleeve_indices.add(idx)
            else:
                torso_indices.add(idx)

    print(f"[*] Topologia identificada: {len(sleeve_indices)} vértices de mangas, {len(torso_indices)} vértices de torso/gola.")

    # 6. Detecção Inteligente do Comprimento da Manga
    elbow_z = (arm.matrix_world @ arm.pose.bones['UpperArm_L'].tail).z
    wrist_z = (arm.matrix_world @ arm.pose.bones['LowerArm_L'].tail).z

    if sleeve_indices:
        sleeve_ys = [raw_verts[idx][1] for idx in sleeve_indices]
        min_sleeve_y = min(sleeve_ys)
        lowest_sleeve_z = loc_z + min_sleeve_y * uniform_scale
    else:
        min_sleeve_y = 1.0
        lowest_sleeve_z = 2.0

    is_sleeveless = (len(sleeve_indices) == 0 or lowest_sleeve_z > 1.30)
    is_short_sleeves = (lowest_sleeve_z > elbow_z - 0.05) and not is_sleeveless
    is_long_sleeves = not is_sleeveless and not is_short_sleeves

    sleeve_type_str = "REGATA / SEM MANGA" if is_sleeveless else ("MANGA CURTA" if is_short_sleeves else "MANGA LONGA")
    print(f"[*] Tipo de Manga: {sleeve_type_str} (Z cuff = {lowest_sleeve_z:.3f}m | Cotovelo = {elbow_z:.3f}m | Pulso = {wrist_z:.3f}m)")

    # 7. Medição Dinâmica da Bainha Inferior e Cintura
    torso_verts = [raw_verts[idx] for idx in torso_indices]
    torso_y_min = min(v[1] for v in torso_verts) if torso_verts else y_min_orig
    torso_y_max = max(v[1] for v in torso_verts) if torso_verts else y_max_orig
    hem_y_threshold = torso_y_min + 0.15 * (torso_y_max - torso_y_min)
    hem_verts = [v for v in torso_verts if v[1] < hem_y_threshold]

    raw_hem_width = (max(v[0] for v in hem_verts) - min(v[0] for v in hem_verts)) if hem_verts else 0.50
    raw_hem_depth = (max(v[2] for v in hem_verts) - min(v[2] for v in hem_verts)) if hem_verts else 0.40
    target_local_waist_x = target_waist_width / uniform_scale
    target_local_waist_z = target_waist_depth / uniform_scale

    target_scale_waist_x = min(1.0, target_local_waist_x / raw_hem_width) if raw_hem_width > 0 else 0.57
    target_scale_waist_z = min(1.0, target_local_waist_z / raw_hem_depth) if raw_hem_depth > 0 else 0.64

    Y_anchor_bottom = 0.15 * norm_scale
    Y_target_min = (target_torso_bottom_z - loc_z) / uniform_scale
    torso_compression = (Y_anchor_bottom - Y_target_min) / (Y_anchor_bottom - torso_y_min)

    adjusted_verts = [list(v) for v in raw_verts]

    # 8. Encurtamento Proporcional das Mangas (APENAS para Mangas Longas)
    if is_long_sleeves:
        sh_lx, sh_ly = 0.57 * norm_scale, 0.52 * norm_scale
        sh_rx, sh_ry = -0.57 * norm_scale, 0.52 * norm_scale
        shorten_factor_sleeves = 0.84

        for idx in sleeve_indices:
            v = raw_verts[idx]
            x, y, z = v[0], v[1], v[2]
            if x > 0:
                dx = x - sh_lx
                dy = y - sh_ly
                t = min(max(dx / (0.90 * norm_scale), 0.0), 1.0)
                factor = 1.0 - (1.0 - shorten_factor_sleeves) * (t ** 1.1)
                adjusted_verts[idx] = [sh_lx + dx * factor, sh_ly + dy * factor, z]
            else:
                dx = x - sh_rx
                dy = y - sh_ry
                t = min(max(abs(dx) / (0.90 * norm_scale), 0.0), 1.0)
                factor = 1.0 - (1.0 - shorten_factor_sleeves) * (t ** 1.1)
                adjusted_verts[idx] = [sh_rx + dx * factor, sh_ry + dy * factor, z]

    # 9. Tapering Anatômico da Cintura do Tronco
    for idx in torso_indices:
        v = adjusted_verts[idx]
        x, y, z = v[0], v[1], v[2]
        if y < Y_anchor_bottom:
            t_waist = (Y_anchor_bottom - y) / (Y_anchor_bottom - torso_y_min)
            blend_waist = min(max(t_waist, 0.0), 1.0)
            curve_waist = blend_waist ** 1.2
            sc_x = 1.0 - (1.0 - target_scale_waist_x) * curve_waist
            sc_z = 1.0 - (1.0 - target_scale_waist_z) * curve_waist
            y = Y_anchor_bottom + (y - Y_anchor_bottom) * torso_compression
            x = x * sc_x
            z = z * sc_z
            adjusted_verts[idx] = [x, y, z]

    # 10. Curva Hermite/Smoothstep de Gola e Ombros
    Y_anchor_top = 0.35 * norm_scale
    num_bins = 30
    envelope = {}
    for v in adjusted_verts:
        if v[1] > Y_anchor_top:
            bin_idx = int(min(abs(v[0]) / max_abs_x, 0.999) * num_bins)
            envelope[bin_idx] = max(envelope.get(bin_idx, Y_anchor_top), v[1])

    def smoothstep(e0, e1, x):
        t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)

    def target_world_z_curve(wx):
        ax = abs(wx)
        w_collar = 0.08
        w_shoulder = 0.26
        z_collar = target_collar_z
        z_shoulder = 1.458
        if ax < w_collar:
            return z_collar
        elif ax < w_shoulder:
            s = smoothstep(w_collar, w_shoulder, ax)
            return z_collar - s * (z_collar - z_shoulder)
        else:
            s_arm = smoothstep(w_shoulder, w_shoulder + 0.12, ax)
            return z_shoulder - s_arm * 0.085

    for idx in range(len(adjusted_verts)):
        v = adjusted_verts[idx]
        x, y, z = v[0], v[1], v[2]
        if y > Y_anchor_top:
            bin_idx = int(min(abs(x) / max_abs_x, 0.999) * num_bins)
            orig_top = envelope.get(bin_idx, y)
            if orig_top > Y_anchor_top:
                wx = abs(x) * uniform_scale
                target_wz = target_world_z_curve(wx)
                target_top_y = (target_wz - loc_z) / uniform_scale
                if orig_top > target_top_y:
                    ratio = (target_top_y - Y_anchor_top) / (orig_top - Y_anchor_top)
                    y = Y_anchor_top + (y - Y_anchor_top) * ratio
                if is_long_sleeves:
                    corner_t = smoothstep(0.24, 0.28, wx) * (1.0 - smoothstep(0.32, 0.38, wx))
                    x = x * (1.0 - 0.045 * corner_t)
                adjusted_verts[idx] = [x, y, z]

    for i, v in enumerate(jacket.data.vertices):
        v.co = adjusted_verts[i]

    # 11. Ajuste Anatômico de Punho e Projeção (APENAS para Manga Longa)
    if is_long_sleeves:
        from mathutils import Matrix, Euler
        e = Euler((math.radians(90), 0, math.radians(180)), 'XYZ')
        R = e.to_matrix().to_4x4()
        S = Vector((uniform_scale, uniform_scale, uniform_scale))
        T = Vector((0, 0.007, loc_z))
        M = Matrix.Translation(T) @ R @ Matrix.Diagonal((*S, 1.0))
        M_inv = M.inverted()

        pb_l = arm.pose.bones.get("UpperArm_L")
        pb_r = arm.pose.bones.get("UpperArm_R")
        pb_l.rotation_mode = 'XYZ'
        pb_r.rotation_mode = 'XYZ'
        pb_l.rotation_euler = (0, 0, math.radians(-28.5))
        pb_r.rotation_euler = (0, 0, math.radians(28.5))
        bpy.context.view_layer.update()

        mw = arm.matrix_world
        p_el_l = M_inv @ (mw @ pb_l.tail)
        p_wr_l = M_inv @ (mw @ arm.pose.bones['LowerArm_L'].tail)
        bone_axis_l = (p_wr_l - p_el_l).normalized()
        bone_len_l = (p_wr_l - p_el_l).length
        axis_u_l = bone_axis_l.cross(Vector((0, 0, 1))).normalized()
        axis_v_l = bone_axis_l.cross(axis_u_l).normalized()

        p_el_r = M_inv @ (mw @ pb_r.tail)
        p_wr_r = M_inv @ (mw @ arm.pose.bones['LowerArm_R'].tail)
        bone_axis_r = (p_wr_r - p_el_r).normalized()
        bone_len_r = (p_wr_r - p_el_r).length
        axis_u_r = bone_axis_r.cross(Vector((0, 0, 1))).normalized()
        axis_v_r = bone_axis_r.cross(axis_u_r).normalized()

        target_wrist_ru = 0.110
        target_wrist_rv = 0.120
        local_target_ru = target_wrist_ru / uniform_scale
        local_target_rv = target_wrist_rv / uniform_scale

        cuff_u, cuff_v = [], []
        t_sleeve_max_l = 0.0
        for idx in sleeve_indices:
            co = Vector(jacket.data.vertices[idx].co)
            if co.x < 0:
                d = co - p_el_l
                proj = d.dot(bone_axis_l)
                t = proj / bone_len_l
                if t > t_sleeve_max_l:
                    t_sleeve_max_l = t
                if t > 0.65:
                    cuff_u.append(abs(d.dot(axis_u_l)))
                    cuff_v.append(abs(d.dot(axis_v_l)))
        cuff_u.sort()
        cuff_v.sort()
        r_u = cuff_u[int(len(cuff_u) * 0.85)] if cuff_u else 0.1
        r_v = cuff_v[int(len(cuff_v) * 0.85)] if cuff_v else 0.1

        req_sc_u = max(1.0, local_target_ru / r_u)
        req_sc_v = max(1.0, local_target_rv / r_v)
        flare_boost_u = req_sc_u - 1.0
        flare_boost_v = req_sc_v - 1.0

        t_start = 0.35
        t_end = min(1.0, max(t_sleeve_max_l, 0.85))
        for idx in sleeve_indices:
            co = Vector(jacket.data.vertices[idx].co)
            if co.x < 0:
                d = co - p_el_l
                proj = d.dot(bone_axis_l)
                t = proj / bone_len_l
                if t > t_start:
                    blend = min(max((t - t_start) / (t_end - t_start), 0.0), 1.0)
                    curve = blend ** 1.3
                    sc_u = 1.0 + flare_boost_u * curve
                    sc_v = 1.0 + flare_boost_v * curve
                    cu = d.dot(axis_u_l)
                    cv = d.dot(axis_v_l)
                    u_center = 0.020 * blend
                    v_center = -0.008 * blend
                    new_cu = u_center + (cu - u_center) * sc_u
                    new_cv = v_center + (cv - v_center) * sc_v
                    jacket.data.vertices[idx].co = p_el_l + proj * bone_axis_l + new_cu * axis_u_l + new_cv * axis_v_l
            else:
                d = co - p_el_r
                proj = d.dot(bone_axis_r)
                t = proj / bone_len_r
                if t > t_start:
                    blend = min(max((t - t_start) / (t_end - t_start), 0.0), 1.0)
                    curve = blend ** 1.3
                    sc_u = 1.0 + flare_boost_u * curve
                    sc_v = 1.0 + flare_boost_v * curve
                    cu = d.dot(axis_u_r)
                    cv = d.dot(axis_v_r)
                    u_center = -0.020 * blend
                    v_center = -0.008 * blend
                    new_cu = u_center + (cu - u_center) * sc_u
                    new_cv = v_center + (cv - v_center) * sc_v
                    jacket.data.vertices[idx].co = p_el_r + proj * bone_axis_r + new_cu * axis_u_r + new_cv * axis_v_r

    jacket.data.update()

    # 12. Escala e Posicionamento no Mundo
    jacket.scale = (uniform_scale, uniform_scale, uniform_scale)
    jacket.rotation_euler = (math.radians(90), 0, math.radians(180))
    jacket.location = (0, 0.007, loc_z)
    jacket.parent = None
    bpy.context.view_layer.update()

    # 13. Vinculação SurfaceDeform na Inner Cage
    pb_l = arm.pose.bones.get("UpperArm_L")
    pb_r = arm.pose.bones.get("UpperArm_R")
    pb_l.rotation_mode = 'XYZ'
    pb_r.rotation_mode = 'XYZ'

    for m in list(jacket.modifiers):
        jacket.modifiers.remove(m)

    if is_long_sleeves:
        # Dual-Zone Binding para Mangas Longas (evita cross-binding da manga comprida no quadril)
        vg_torso = jacket.vertex_groups.get('VG_Torso') or jacket.vertex_groups.new(name='VG_Torso')
        vg_torso.add(list(torso_indices), 1.0, 'REPLACE')
        vg_sleeves = jacket.vertex_groups.get('VG_Sleeves') or jacket.vertex_groups.new(name='VG_Sleeves')
        vg_sleeves.add(list(sleeve_indices), 1.0, 'REPLACE')

        # Torso em T-Pose (75°)
        pb_l.rotation_euler = (0, 0, math.radians(-75))
        pb_r.rotation_euler = (0, 0, math.radians(75))
        bpy.context.view_layer.update()

        sd_torso = jacket.modifiers.new(name="SurfaceDeform_Torso", type='SURFACE_DEFORM')
        sd_torso.target = cage
        sd_torso.vertex_group = 'VG_Torso'
        with bpy.context.temp_override(object=jacket, active_object=jacket):
            bpy.ops.object.surfacedeform_bind(modifier=sd_torso.name)
        assert sd_torso.is_bound, "Falha ao vincular SurfaceDeform_Torso!"

        # Mangas em A-Pose nativa (28.5°)
        pb_l.rotation_euler = (0, 0, math.radians(-28.5))
        pb_r.rotation_euler = (0, 0, math.radians(28.5))
        bpy.context.view_layer.update()

        sd_sleeves = jacket.modifiers.new(name="SurfaceDeform_Sleeves", type='SURFACE_DEFORM')
        sd_sleeves.target = cage
        sd_sleeves.vertex_group = 'VG_Sleeves'
        with bpy.context.temp_override(object=jacket, active_object=jacket):
            bpy.ops.object.surfacedeform_bind(modifier=sd_sleeves.name)
        assert sd_sleeves.is_bound, "Falha ao vincular SurfaceDeform_Sleeves!"
    else:
        # Single-Zone Binding em A-Pose (28.5°) para Mangas Curtas e Regatas
        # Preserva 100% da costura ombro-manga e axilas sem distorção
        pb_l.rotation_euler = (0, 0, math.radians(-28.5))
        pb_r.rotation_euler = (0, 0, math.radians(28.5))
        bpy.context.view_layer.update()

        sd = jacket.modifiers.new(name="SurfaceDeform", type='SURFACE_DEFORM')
        sd.target = cage
        with bpy.context.temp_override(object=jacket, active_object=jacket):
            bpy.ops.object.surfacedeform_bind(modifier=sd.name)
        assert sd.is_bound, "Falha ao vincular SurfaceDeform!"

    # 14. Retornar esqueleto para Rest Pose (0°)
    pb_l.rotation_euler = (0, 0, 0)
    pb_r.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    # 15. HSR Universal dos Braços ("Mostrar só o necessário do braço")
    # Restaura malha pura dos braços superiores a partir de character_male.blend
    with bpy.data.libraries.load(r"C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/character_male.blend") as (data_from, data_to):
        data_to.objects = ['braco superior esquerdo', 'braco superior direito']

    for o_imported in data_to.objects:
        base_name = 'braco superior esquerdo' if 'esquerdo' in o_imported.name else 'braco superior direito'
        target = bpy.data.objects.get(base_name)
        if target:
            target.data = o_imported.data.copy()
            for m in list(target.modifiers):
                target.modifiers.remove(m)
        bpy.data.objects.remove(o_imported)

    if is_sleeveless:
        for name in ['braco superior esquerdo', 'braco superior direito']:
            b = bpy.data.objects.get(name)
            if b:
                b.hide_render = False
                b.hide_viewport = False
        for name in ['antebraco esquerdo', 'antebraco direito']:
            ab = bpy.data.objects.get(name)
            if ab:
                ab.hide_render = False
                ab.hide_viewport = False
                for m in ab.modifiers:
                    if m.type == 'MASK':
                        m.show_render = False
                        m.show_viewport = False
    elif is_short_sleeves:
        # Antebraços 100% visíveis
        for name in ['antebraco esquerdo', 'antebraco direito']:
            ab = bpy.data.objects.get(name)
            if ab:
                ab.hide_render = False
                ab.hide_viewport = False
                for m in ab.modifiers:
                    if m.type == 'MASK':
                        m.show_render = False
                        m.show_viewport = False

        # Determina a menor altura Z da manga na pose de repouso avaliada
        dg = bpy.context.evaluated_depsgraph_get()
        eval_jacket = jacket.evaluated_get(dg)
        eval_sleeve_zs = [(eval_jacket.matrix_world @ eval_jacket.data.vertices[i].co).z for i in sleeve_indices]
        cuff_z = min(eval_sleeve_zs) if eval_sleeve_zs else lowest_sleeve_z
        cut_z = cuff_z + 0.020  # 2cm acima da barra da manga para embutir perfeitamente
        print(f"[*] HSR Manga Curta: Seccionando braço superior em Z = {cut_z:.3f}m (cotovelo Z = {elbow_z:.3f}m)")

        for name in ['braco superior esquerdo', 'braco superior direito']:
            b = bpy.data.objects[name]
            b.hide_render = False
            b.hide_viewport = False

            bm = bmesh.new()
            bm.from_mesh(b.data)
            m_inv = b.matrix_world.inverted()
            p_local = m_inv @ Vector((0, 0, cut_z))
            norm_local = (m_inv.to_3x3() @ Vector((0, 0, 1))).normalized()

            res = bmesh.ops.bisect_plane(
                bm,
                geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                plane_co=p_local,
                plane_no=norm_local,
                clear_outer=True,
                clear_inner=False
            )
            cut_edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
            if cut_edges:
                try:
                    bmesh.ops.edgeloop_fill(bm, edges=cut_edges)
                except:
                    pass
            bm.to_mesh(b.data)
            b.data.update()
            bm.free()
    else:
        # Manga Longa: Braços superiores ocultos, antebraços mascarados para a mão
        for name in ['braco superior esquerdo', 'braco superior direito']:
            b = bpy.data.objects.get(name)
            if b:
                b.hide_render = True
                b.hide_viewport = True

        for side in ['esquerdo', 'direito']:
            ab = bpy.data.objects.get(f'antebraco {side}')
            if ab:
                ab.hide_render = False
                ab.hide_viewport = False
                vg = ab.vertex_groups.get('Mao')
                if not vg:
                    vg = ab.vertex_groups.new(name='Mao')
                    hand_indices = [v.index for v in ab.data.vertices if v.co.z < -0.29]
                    vg.add(hand_indices, 1.0, 'REPLACE')
                mask_mod = ab.modifiers.get('Mask_Jacket')
                if not mask_mod:
                    mask_mod = ab.modifiers.new(name='Mask_Jacket', type='MASK')
                mask_mod.vertex_group = 'Mao'
                mask_mod.show_render = True
                mask_mod.show_viewport = True

    # 16. Ocultar malhas cobertas pelo vestuário e isolar peças ativas
    cage.hide_render = True
    torso_obj = bpy.data.objects.get('torso')
    if torso_obj:
        torso_obj.hide_render = True

    # Oculta qualquer outro Top do catálogo
    for o in bpy.data.objects:
        if o.name.startswith(('Top_', 'Sweater_', 'Jacket_')) and o.name != clothing_obj_name:
            o.hide_render = True
            o.hide_viewport = True
    jacket.hide_render = False
    jacket.hide_viewport = False

    # Se calça estiver presente na cena, mantém membros inferiores ocultos
    has_pants = any(
        (o.name.startswith(('Bottom_', 'Pants_')) and not o.hide_render)
        for o in bpy.data.objects
    )
    if has_pants:
        for p in ['pelve', 'coxa direita', 'coxa esquerda', 'canela direita', 'canela esquerda', 'pe direito', 'pe esquerdo']:
            o = bpy.data.objects.get(p)
            if o:
                o.hide_render = True
                o.hide_viewport = True

    # 17. Renderização de Verificação Visual
    if render_output:
        os.makedirs(os.path.dirname(render_output), exist_ok=True)
        cam = bpy.data.objects.get("Camera")
        if cam:
            # 17A: Pose Neutra de Corpo Inteiro
            cam.location = (0, -3.2, 0.95)
            cam.rotation_euler = (math.radians(90), 0, 0)
            bpy.context.view_layer.update()
            bpy.context.scene.render.filepath = render_output
            bpy.ops.render.render(write_still=True)
            print(f"[*] Render neutro salvo em: {render_output}")

            # 17B: Close-up de Ombros e Gola
            shoulder_render = os.path.join(os.path.dirname(render_output), f"{clothing_obj_name.lower()}_shoulders.png")
            cam.location = (0, -1.35, 1.40)
            cam.rotation_euler = (math.radians(90), 0, 0)
            bpy.context.view_layer.update()
            bpy.context.scene.render.filepath = shoulder_render
            bpy.ops.render.render(write_still=True)
            print(f"[*] Render de detalhe dos ombros salvo em: {shoulder_render}")

            # 17C: Pose de Ação / Caminhada (Prova cabal de ausência de deformações e descolamentos)
            action_render = os.path.join(os.path.dirname(render_output), f"{clothing_obj_name.lower()}_action.png")
            pb_r = arm.pose.bones['UpperArm_R']
            pb_l = arm.pose.bones['UpperArm_L']
            pb_el_r = arm.pose.bones['LowerArm_R']
            pb_el_l = arm.pose.bones['LowerArm_L']
            pb_r.rotation_mode = 'XYZ'
            pb_l.rotation_mode = 'XYZ'
            pb_el_r.rotation_mode = 'XYZ'
            pb_el_l.rotation_mode = 'XYZ'

            pb_r.rotation_euler = (math.radians(-40), 0, math.radians(20))
            pb_el_r.rotation_euler = (math.radians(-35), 0, 0)
            pb_l.rotation_euler = (math.radians(35), 0, math.radians(-15))
            pb_el_l.rotation_euler = (math.radians(-15), 0, 0)

            cam.location = (0, -3.2, 0.95)
            cam.rotation_euler = (math.radians(90), 0, 0)
            bpy.context.view_layer.update()
            bpy.context.scene.render.filepath = action_render
            bpy.ops.render.render(write_still=True)
            print(f"[*] Render de pose de ação salvo em: {action_render}")

            # Resetar Armature e Câmera
            pb_r.rotation_euler = (0, 0, 0)
            pb_l.rotation_euler = (0, 0, 0)
            pb_el_r.rotation_euler = (0, 0, 0)
            pb_el_l.rotation_euler = (0, 0, 0)
            cam.location = (0, -3.2, 1.25)
            cam.rotation_euler = (math.radians(88), 0, 0)
            bpy.context.view_layer.update()

    # 18. Salvar Blend e Exportar FBX
    bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath)
    print(f"[*] Blend salvo: {bpy.data.filepath}")

    if output_fbx:
        for o in bpy.data.objects:
            o.select_set(False)
        export_names = [
            'Armature_Character', 'cabeca', 'cabelo', 'laco_direito', 'laco_esquerdo', 'nariz.002',
            'pecoco', 'pelve', 'coxa direita', 'coxa esquerda', 'canela direita', 'canela esquerda',
            'pe direito', 'pe esquerdo', 'braco superior esquerdo', 'braco superior direito',
            'antebraco esquerdo', 'antebraco direito', clothing_obj_name
        ]
        for n in export_names:
            o = bpy.data.objects.get(n)
            if o and not o.hide_render:
                o.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.export_scene.fbx(
            filepath=output_fbx,
            use_selection=True,
            global_scale=1.0,
            axis_forward='-Z',
            axis_up='Y',
            apply_scale_options='FBX_SCALE_ALL',
            bake_space_transform=False,
            object_types={'ARMATURE', 'MESH'},
            use_mesh_modifiers=True,
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            armature_nodetype='NULL'
        )
        print(f"[*] FBX final exportado em: {output_fbx}")

    print("==================================================")
    print("  AUTO-FIT UNIVERSAL CONCLUÍDO COM SUCESSO!       ")
    return True

if __name__ == '__main__':
    autofit()
