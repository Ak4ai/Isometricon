"""Reconstrói com perfeição máxima o outlayer (cabelo) no Blender com base em roupa.jpeg:
- Franja flutuante com gap estilo Minecraft outer layer (~14mm de folga da testa)
- Mechas com espaçamento sutil (frestas naturais) e profundidade alternada (relevo 3D real)
- Assimetria anime e corte bagunçado fiel a roupa.jpeg (mecha central proeminente sobre o nariz)
- Costeletas longas anguladas para fora com ponta chanfrada
- Bochechas e mandíbula abertas (sem aspecto de capacete)
- Nuca em camadas com 5 mechas escalonadas em bloco deixando o pescoço visível
- Coroa superior volumosa que abraça os laços brancos
"""
import bpy
import bmesh
import math
import mathutils

def build_outlayer_hair():
    head = bpy.data.objects.get("cabeca")
    if not head:
        print("Erro: objeto 'cabeca' não encontrado!")
        return {"status": "error", "message": "cabeca not found"}

    mat = bpy.data.materials.get("Mat_Head_Atlas")
    if not mat:
        mat = bpy.data.materials.new("Mat_Head_Atlas")

    cabelo_obj = bpy.data.objects.get("cabelo")
    if not cabelo_obj:
        mesh_new = bpy.data.meshes.new("cabelo_mesh")
        cabelo_obj = bpy.data.objects.new("cabelo", mesh_new)
        head.users_collection[0].objects.link(cabelo_obj)
        cabelo_obj.parent = head
        cabelo_obj.data.materials.append(mat)
    
    old_mesh = cabelo_obj.data
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    mw_head = head.matrix_world
    mw_head_inv = mw_head.inverted()

    def add_mesh_box_world(v_world_pts, u_min=0.05, u_max=0.45, v_min=0.08, v_max=0.45):
        local_pts = [mw_head_inv @ mathutils.Vector(pt) for pt in v_world_pts]
        verts = [bm.verts.new(lp) for lp in local_pts]
        bm.verts.ensure_lookup_table()
        face_defs = [
            ((0, 1, 2, 3), (u_min, v_min, u_max, v_min + 0.05)), # baixo
            ((4, 7, 6, 5), (u_min, v_max - 0.05, u_max, v_max)), # cima
            ((0, 4, 5, 1), (u_min, v_min, u_max, v_max)),         # frente
            ((2, 6, 7, 3), (u_min, v_min, u_max, v_max)),         # trás
            ((0, 3, 7, 4), (u_min, v_min, u_min + 0.08, v_max)), # lateral esq
            ((1, 5, 6, 2), (u_max - 0.08, v_min, u_max, v_max)), # lateral dir
        ]
        for f_indices, (u1, v1, u2, v2) in face_defs:
            try:
                face = bm.faces.new([verts[i] for i in f_indices])
                uvs = [(u1, v1), (u1, v2), (u2, v2), (u2, v1)]
                for loop, uv in zip(face.loops, uvs):
                    loop[uv_layer].uv = uv
            except ValueError:
                pass

    def add_tapered_box_world(x1_bot, x2_bot, y_f_bot, y_b_bot, z_bot,
                              x1_top, x2_top, y_f_top, y_b_top, z_top,
                              u_min=0.05, u_max=0.45, v_min=0.08, v_max=0.45):
        pts = [
            (x1_bot, y_f_bot, z_bot), (x2_bot, y_f_bot, z_bot),
            (x2_bot, y_b_bot, z_bot), (x1_bot, y_b_bot, z_bot),
            (x1_top, y_f_top, z_top), (x2_top, y_f_top, z_top),
            (x2_top, y_b_top, z_top), (x1_top, y_b_top, z_top)
        ]
        add_mesh_box_world(pts, u_min, u_max, v_min, v_max)

    def add_axis_box_world(x1, x2, y1, y2, z1, z2, u_min=0.05, u_max=0.45, v_min=0.08, v_max=0.45):
        add_tapered_box_world(x1, x2, y1, y2, z1, x1, x2, y1, y2, z2, u_min, u_max, v_min, v_max)

    # =========================================================================
    # 1. COROA SUPERIOR (Volume no topo do crânio com destaque e marquise)
    # Crânio termina em Z = 1.809. O volume vai até 1.850.
    # =========================================================================
    # Bloco superior central volumoso
    add_axis_box_world(-0.134, 0.132, -0.128, 0.128, 1.804, 1.850, 0.55, 0.95, 0.52, 0.65)
    # Marquise frontal que faz a transição para as mechas flutuantes
    add_axis_box_world(-0.136, 0.134, -0.152, -0.126, 1.796, 1.834, 0.55, 0.95, 0.52, 0.65)

    # =========================================================================
    # 2. FRANJA FLUTUANTE 3D COM GAP MINECRAFT (Outer Layer com Espaço Livre)
    # Testa no mundo: Y = -0.1335.
    # Verso das mechas: Y = -0.146 a -0.149 (13 a 16mm de vão livre!)
    # Frente das mechas: Y = -0.158 a -0.166 (espessura expressiva)
    # Pequenas frestas de ~2mm entre algumas mechas para separação visual voxel
    # =========================================================================
    z_top = 1.826
    y_f_top = -0.155
    y_b_top = -0.144

    # Mecha 1: Lateral Esquerda Alta (Transição para têmpora)
    add_tapered_box_world(-0.128, -0.093, -0.158, -0.147, 1.724,
                          -0.126, -0.092, y_f_top, y_b_top, z_top,
                          0.05, 0.14, 0.15, 0.45)

    # Mecha 2: Frontal Esquerda Longa (Mais volumosa e saliente, cai sobre a sobrancelha esq)
    add_tapered_box_world(-0.091, -0.053, -0.165, -0.149, 1.666,
                          -0.090, -0.052, y_f_top - 0.004, y_b_top, z_top,
                          0.12, 0.22, 0.07, 0.45)

    # Mecha 3: Dente Central-Esquerdo (Mais curto, recuado em profundidade)
    add_tapered_box_world(-0.051, -0.015, -0.157, -0.146, 1.708,
                          -0.050, -0.014, y_f_top, y_b_top, z_top,
                          0.20, 0.28, 0.12, 0.45)

    # Mecha 4: Mecha Central Proeminente (Assimetria anime: desce até 1.658 sobre o nariz!)
    add_tapered_box_world(-0.013,  0.031, -0.167, -0.150, 1.658,
                          -0.012,  0.030, y_f_top - 0.005, y_b_top, z_top,
                          0.24, 0.34, 0.05, 0.45)

    # Mecha 5: Dente Central-Direito (Mais curto, recuado em profundidade)
    add_tapered_box_world( 0.033,  0.067, -0.157, -0.146, 1.702,
                           0.032,  0.066, y_f_top, y_b_top, z_top,
                           0.28, 0.36, 0.12, 0.45)

    # Mecha 6: Frontal Direita Longa (Mais saliente, cai sobre a sobrancelha dir)
    add_tapered_box_world( 0.069,  0.107, -0.165, -0.149, 1.668,
                           0.068,  0.106, y_f_top - 0.004, y_b_top, z_top,
                           0.32, 0.42, 0.07, 0.45)

    # Mecha 7: Lateral Direita Alta (Transição para têmpora)
    add_tapered_box_world( 0.109,  0.134, -0.158, -0.147, 1.724,
                           0.108,  0.132, y_f_top, y_b_top, z_top,
                           0.38, 0.48, 0.15, 0.45)

    # =========================================================================
    # 3. MECHAS LATERAIS LONGAS (Costeletas / Side Locks na Bochecha)
    # Inclinadas ligeiramente para fora (+X e -X) com ponta chanfrada
    # =========================================================================
    # Esquerda: topo em X=-0.136..-0.112, base abre para X=-0.144..-0.118
    add_tapered_box_world(-0.144, -0.118, -0.157, -0.130, 1.410,
                          -0.136, -0.112, -0.155, -0.128, 1.815,
                          0.05, 0.18, 0.08, 0.45)
    pts_tip_l = [
        (-0.142, -0.155, 1.385), (-0.122, -0.155, 1.400),
        (-0.122, -0.132, 1.400), (-0.142, -0.132, 1.385),
        (-0.144, -0.157, 1.410), (-0.118, -0.157, 1.410),
        (-0.118, -0.130, 1.410), (-0.144, -0.130, 1.410)
    ]
    add_mesh_box_world(pts_tip_l, 0.05, 0.15, 0.05, 0.15)

    # Direita: topo em X=0.112..0.136, base abre para X=0.118..0.144
    add_tapered_box_world( 0.118,  0.144, -0.157, -0.130, 1.410,
                           0.112,  0.136, -0.155, -0.128, 1.815,
                           0.32, 0.45, 0.08, 0.45)
    pts_tip_r = [
        ( 0.122, -0.155, 1.400), ( 0.142, -0.155, 1.385),
        ( 0.142, -0.132, 1.385), ( 0.122, -0.132, 1.400),
        ( 0.118, -0.157, 1.410), ( 0.144, -0.157, 1.410),
        ( 0.144, -0.130, 1.410), ( 0.118, -0.130, 1.410)
    ]
    add_mesh_box_world(pts_tip_r, 0.35, 0.45, 0.05, 0.15)

    # =========================================================================
    # 4. LATERAIS SUPERIORES POSTERIORES (Atrás das orelhas/laços)
    # Inicia em Y = 0.005, mantendo as bochechas completamente abertas e limpas!
    # =========================================================================
    add_axis_box_world(-0.144, -0.128, 0.005, 0.105, 1.670, 1.825, 0.05, 0.45, 0.18, 0.42)
    add_axis_box_world( 0.128,  0.144, 0.005, 0.105, 1.670, 1.825, 0.05, 0.45, 0.18, 0.42)

    # =========================================================================
    # 5. TRASEIRA VOLUMOSA EM CAMADAS (Bob com Mechas Escalonadas na Nuca)
    # Traseira do crânio em Y = 0.118.
    # Camada superior de volume + 5 mechas inferiores de comprimento variado
    # =========================================================================
    # Camada superior traseira volumosa
    add_axis_box_world(-0.138, 0.136, 0.118, 0.148, 1.660, 1.830, 0.05, 0.45, 0.15, 0.42)

    # Mechas inferiores escalonadas fiéis a roupa.jpeg:
    # 1. Esquerda externa (longa Z=1.490)
    add_axis_box_world(-0.138, -0.088, 0.116, 0.144, 1.490, 1.675, 0.05, 0.20, 0.10, 0.38)
    # 2. Esquerda média (curta Z=1.580 - deixa a nuca/pescoço visível)
    add_axis_box_world(-0.090, -0.038, 0.118, 0.142, 1.580, 1.675, 0.15, 0.28, 0.15, 0.38)
    # 3. Central (longa Z=1.515)
    add_axis_box_world(-0.040,  0.038, 0.120, 0.145, 1.515, 1.675, 0.20, 0.32, 0.12, 0.38)
    # 4. Direita média (curta Z=1.580 - deixa a nuca/pescoço visível)
    add_axis_box_world( 0.036,  0.088, 0.118, 0.142, 1.580, 1.675, 0.25, 0.38, 0.15, 0.38)
    # 5. Direita externa (longa Z=1.490)
    add_axis_box_world( 0.086,  0.136, 0.116, 0.144, 1.490, 1.675, 0.32, 0.45, 0.10, 0.38)

    # Finalizar a nova malha
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    new_mesh = bpy.data.meshes.new("cabelo_mesh")
    bm.to_mesh(new_mesh)
    bm.free()

    cabelo_obj.data = new_mesh
    if old_mesh:
        bpy.data.meshes.remove(old_mesh)

    cabelo_obj.matrix_world = head.matrix_world.copy()
    cabelo_obj.matrix_parent_inverse = head.matrix_world.inverted()

    if not cabelo_obj.data.materials:
        cabelo_obj.data.materials.append(mat)
    else:
        cabelo_obj.data.materials[0] = mat

    bpy.context.view_layer.update()
    print("Outlayer refinado com perfeição máxima no Blender!")
    return {"status": "success", "message": "outlayer hair rebuilt successfully"}

build_outlayer_hair()
