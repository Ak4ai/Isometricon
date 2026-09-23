"""Refinamento estético supremo do cabelo 2D+3D e dos laços com base milimétrica na referência roupa.jpeg."""
import bpy
import bmesh
import math
import mathutils

def build_refined_head():
    scene = bpy.context.scene
    coll = bpy.data.collections.get("personagem")
    if not coll:
        coll = scene.collection

    head = bpy.data.objects.get("cabeca")
    if not head:
        print("Erro: objeto 'cabeca' não encontrado!")
        return

    # Limpar objetos antigos
    for item in ["cabelo", "cabelo_base", "cabelo_franja", "cabelo_mechas", "laco_esquerdo", "laco_direito"]:
        obj = bpy.data.objects.get(item)
        if obj:
            m = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if m:
                bpy.data.meshes.remove(m)

    # -------------------------------------------------------------
    # 1. Textura e Material PBR Pixel-Art
    # -------------------------------------------------------------
    tex_path = r"C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/textures/character_head_full.png"
    img = bpy.data.images.load(tex_path, check_existing=True)

    mat_head = bpy.data.materials.get("Mat_Head_Atlas")
    if not mat_head:
        mat_head = bpy.data.materials.new("Mat_Head_Atlas")
    mat_head.use_nodes = True
    nodes = mat_head.node_tree.nodes
    nodes.clear()

    node_out = nodes.new("ShaderNodeOutputMaterial")
    node_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    node_tex = nodes.new("ShaderNodeTexImage")
    node_tex.image = img
    node_tex.interpolation = "Closest" # Pixel art nítido 100% estilo Minecraft

    node_bsdf.inputs["Roughness"].default_value = 0.65
    mat_head.node_tree.links.new(node_tex.outputs["Color"], node_bsdf.inputs["Base Color"])
    mat_head.node_tree.links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])

    # -------------------------------------------------------------
    # 2. UVs da Cabeça Base (Camada 2D)
    # -------------------------------------------------------------
    uv_data = head.data.uv_layers.active.data
    # Frente (Face + Cabelo 2D na testa)
    uv_data[12].uv = (0.50, 0.50) # vert 8
    uv_data[13].uv = (0.50, 1.00) # vert 4
    uv_data[14].uv = (0.00, 1.00) # vert 1
    uv_data[15].uv = (0.00, 0.50) # vert 7

    # Queixo frontal
    uv_data[23].uv = (0.25, 0.50)
    uv_data[24].uv = (0.50, 0.52)
    uv_data[25].uv = (0.00, 0.52)

    # Traseira (Corte chanel 2D com nuca aparente)
    for loop_idx in head.data.polygons[1].loop_indices:
        uv_data[loop_idx].uv = (0.75, 0.85)

    # Topo (Cabelo com sheen)
    for loop_idx in head.data.polygons[5].loop_indices:
        uv_data[loop_idx].uv = (0.75, 0.58)

    # Laterais
    for p_idx in (0, 2):
        for loop_idx in head.data.polygons[p_idx].loop_indices:
            uv_data[loop_idx].uv = (0.65, 0.80)

    # Base pescoço
    for p_idx in (4, 7, 8):
        for loop_idx in head.data.polygons[p_idx].loop_indices:
            uv_data[loop_idx].uv = (0.25, 0.52)

    if head.data.materials:
        head.data.materials[0] = mat_head
    else:
        head.data.materials.append(mat_head)

    # -------------------------------------------------------------
    # 3. Cabelo 3D (Hat Layer / Detalhes em Relevo)
    # -------------------------------------------------------------
    bm_hair = bmesh.new()
    uv_hair = bm_hair.loops.layers.uv.new("UVMap")

    def add_mesh_box(bm, v_coords, u_min=0.05, u_max=0.45, v_min=0.08, v_max=0.45):
        # 8 vértices
        verts = [bm.verts.new(pt) for pt in v_coords]
        bm.verts.ensure_lookup_table()
        face_defs = [
            ((0, 1, 2, 3), (u_min, v_min, u_max, v_min + 0.05)),
            ((4, 7, 6, 5), (u_min, v_max - 0.05, u_max, v_max)),
            ((0, 4, 5, 1), (u_min, v_min, u_max, v_max)), # frente
            ((2, 6, 7, 3), (u_min, v_min, u_max, v_max)), # trás
            ((0, 3, 7, 4), (u_min, v_min, u_min + 0.1, v_max)),
            ((1, 5, 6, 2), (u_max - 0.1, v_min, u_max, v_max)),
        ]
        for f_indices, (u1, v1, u2, v2) in face_defs:
            try:
                face = bm.faces.new([verts[i] for i in f_indices])
                uvs = [(u1, v1), (u1, v2), (u2, v2), (u2, v1)]
                for loop, uv in zip(face.loops, uvs):
                    loop[uv_hair].uv = uv
            except ValueError:
                pass

    def add_axis_box(bm, x1, x2, y1, y2, z1, z2, u_min=0.05, u_max=0.45, v_min=0.08, v_max=0.45):
        pts = [
            (x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1),
            (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2)
        ]
        add_mesh_box(bm, pts, u_min, u_max, v_min, v_max)

    # --- A. Topo do Cabelo (Cobre suavemente a cabeça com acabamento limpo) ---
    add_axis_box(bm_hair, -0.146, 0.142, -0.148, 0.162, 1.868, 1.896, 0.55, 0.95, 0.52, 0.65)

    # --- B. Franja 3D Fiel à Referência roupa.jpeg ---
    # Na referência:
    # - 5 mechas em placas finas (~0.009m de espessura)
    # - A mecha mais à esquerda é levemente inclinada para fora
    # - A mecha mais à direita é levemente inclinada para fora
    # - As mechas centrais têm comprimentos variados, cobrindo a testa sem tampar os olhos!
    yf_front = -0.154
    yf_back  = -0.145
    
    # 1. Mecha esquerda externa (levemente angulada para fora)
    pts_b1 = [
        (-0.142, yf_front - 0.004, 1.728), (-0.096, yf_front, 1.734),
        (-0.096, yf_back, 1.734), (-0.142, yf_back, 1.728),
        (-0.138, yf_front, 1.874), (-0.094, yf_front, 1.874),
        (-0.094, yf_back, 1.874), (-0.138, yf_back, 1.874),
    ]
    add_mesh_box(bm_hair, pts_b1, 0.05, 0.15, 0.12, 0.45)

    # 2. Mecha esquerda média (mais longa, ponta sutil sobre o olho esquerdo)
    add_axis_box(bm_hair, -0.092, -0.046, yf_front, yf_back, 1.712, 1.874, 0.15, 0.25, 0.08, 0.45)

    # 3. Mecha central (dente central estilizado)
    add_axis_box(bm_hair, -0.042,  0.010, yf_front, yf_back, 1.725, 1.874, 0.22, 0.32, 0.10, 0.45)

    # 4. Mecha direita média (mais longa, ponta sobre o olho direito)
    add_axis_box(bm_hair,  0.014,  0.060, yf_front, yf_back, 1.712, 1.874, 0.25, 0.35, 0.08, 0.45)

    # 5. Mecha direita externa (levemente angulada para fora)
    pts_b5 = [
        ( 0.064, yf_front, 1.734), ( 0.110, yf_front - 0.004, 1.728),
        ( 0.110, yf_back, 1.728), ( 0.064, yf_back, 1.734),
        ( 0.062, yf_front, 1.874), ( 0.106, yf_front, 1.874),
        ( 0.106, yf_back, 1.874), ( 0.062, yf_back, 1.874),
    ]
    add_mesh_box(bm_hair, pts_b5, 0.35, 0.45, 0.12, 0.45)

    # --- C. Mechas Laterais Longas (Side Locks) ---
    # Esquerda (-X): desce rente à bochecha até a mandíbula, chanfrada na ponta
    add_axis_box(bm_hair, -0.146, -0.118, -0.154, -0.128, 1.480, 1.870, 0.05, 0.18, 0.08, 0.45)
    # Pontinha chanfrada da mecha esquerda
    pts_tip_l = [
        (-0.144, -0.152, 1.450), (-0.124, -0.152, 1.465),
        (-0.124, -0.130, 1.465), (-0.144, -0.130, 1.450),
        (-0.146, -0.154, 1.480), (-0.118, -0.154, 1.480),
        (-0.118, -0.128, 1.480), (-0.146, -0.128, 1.480)
    ]
    add_mesh_box(bm_hair, pts_tip_l, 0.05, 0.15, 0.05, 0.15)

    # Direita (+X): simétrica
    add_axis_box(bm_hair,  0.114,  0.142, -0.154, -0.128, 1.480, 1.870, 0.32, 0.45, 0.08, 0.45)
    pts_tip_r = [
        ( 0.120, -0.152, 1.465), ( 0.140, -0.152, 1.450),
        ( 0.140, -0.130, 1.450), ( 0.120, -0.130, 1.465),
        ( 0.114, -0.154, 1.480), ( 0.142, -0.154, 1.480),
        ( 0.142, -0.128, 1.480), ( 0.114, -0.128, 1.480)
    ]
    add_mesh_box(bm_hair, pts_tip_r, 0.35, 0.45, 0.05, 0.15)

    # --- D. Camadas Traseiras 3D (Corte Chanel / Bob na Nuca) ---
    add_axis_box(bm_hair, -0.146, -0.055, 0.146, 0.165, 1.540, 1.870, 0.05, 0.45, 0.15, 0.42)
    add_axis_box(bm_hair,  0.051,  0.142, 0.146, 0.165, 1.540, 1.870, 0.05, 0.45, 0.15, 0.42)
    add_axis_box(bm_hair, -0.055,  0.051, 0.148, 0.165, 1.585, 1.870, 0.10, 0.40, 0.20, 0.42)

    # Laterais altas da cabeça
    add_axis_box(bm_hair, -0.148, -0.135, -0.120, 0.146, 1.620, 1.870, 0.05, 0.45, 0.20, 0.42)
    add_axis_box(bm_hair,  0.131,  0.144, -0.120, 0.146, 1.620, 1.870, 0.05, 0.45, 0.20, 0.42)

    bmesh.ops.recalc_face_normals(bm_hair, faces=bm_hair.faces)
    mesh_hair = bpy.data.meshes.new("cabelo_mesh")
    bm_hair.to_mesh(mesh_hair)
    bm_hair.free()

    obj_hair = bpy.data.objects.new("cabelo", mesh_hair)
    coll.objects.link(obj_hair)
    obj_hair.data.materials.append(mat_head)
    obj_hair.matrix_world = head.matrix_world.copy()
    mesh_hair.transform(obj_hair.matrix_world.inverted())
    obj_hair.parent = head
    obj_hair.matrix_parent_inverse = head.matrix_world.inverted()

    # -------------------------------------------------------------
    # 4. LAÇOS BRANCOS GRANDES EM V (Fieis à roupa.jpeg)
    # -------------------------------------------------------------
    # Na referência roupa.jpeg:
    # - Os laços são GRANDES e PROEMINENTES, inclinados para fora e para cima (~30° a 35° em Y)
    # - Formato em dobradura de origami (duas asas volumosas com vinco central)
    # - Fita branca vertical fina pendurada reto para baixo
    def build_origami_ribbon(name, is_left):
        bm = bmesh.new()
        uv_rib = bm.loops.layers.uv.new("UVMap")

        sign = -1.0 if is_left else 1.0
        # Ângulos de rotação: inclinado para fora (+32° em Y para esquerda, -32° para direita)
        # e levemente inclinado para frente (+12° em X)
        rot_y = math.radians(sign * -32.0)
        rot_x = math.radians(12.0)
        R = mathutils.Euler((rot_x, rot_y, 0.0), 'XYZ').to_matrix().to_4x4()

        # Centro do laço na lateral alta da cabeça
        pivot_world = mathutils.Vector((sign * 0.146, -0.015, 1.815))

        def add_transformed_box(bm, local_x1, local_x2, local_y1, local_y2, local_z1, local_z2, has_seam=True):
            raw_pts = [
                mathutils.Vector((local_x1, local_y1, local_z1)),
                mathutils.Vector((local_x2, local_y1, local_z1)),
                mathutils.Vector((local_x2, local_y2, local_z1)),
                mathutils.Vector((local_x1, local_y2, local_z1)),
                mathutils.Vector((local_x1, local_y1, local_z2)),
                mathutils.Vector((local_x2, local_y1, local_z2)),
                mathutils.Vector((local_x2, local_y2, local_z2)),
                mathutils.Vector((local_x1, local_y2, local_z2)),
            ]
            # Aplica rotação local e translada para pivot_world
            transformed_pts = [(pivot_world + (R @ p)) for p in raw_pts]
            verts = [bm.verts.new(tp) for tp in transformed_pts]
            bm.verts.ensure_lookup_table()

            u_min, u_max = (0.55, 0.85) if has_seam else (0.75, 0.98)
            v_min, v_max = 0.05, 0.48
            face_defs = [
                ((0, 1, 2, 3), (u_min, v_min, u_max, v_min + 0.1)),
                ((4, 7, 6, 5), (u_min, v_max - 0.1, u_max, v_max)),
                ((0, 4, 5, 1), (u_min, v_min, u_max, v_max)),
                ((2, 6, 7, 3), (u_min, v_min, u_max, v_max)),
                ((0, 3, 7, 4), (0.80, v_min, 0.95, v_max)),
                ((1, 5, 6, 2), (0.80, v_min, 0.95, v_max)),
            ]
            for f_indices, (u1, v1, u2, v2) in face_defs:
                try:
                    face = bm.faces.new([verts[i] for i in f_indices])
                    uvs = [(u1, v1), (u1, v2), (u2, v2), (u2, v1)]
                    for loop, uv in zip(face.loops, uvs):
                        loop[uv_rib].uv = uv
                except ValueError:
                    pass

        # 1. Nó Central do Laço
        add_transformed_box(bm, -0.015, 0.015, -0.018, 0.018, -0.018, 0.018, has_seam=False)

        # 2. Asa do Laço Superior / Frontal (Lobo dobrado para cima e para fora)
        # Dimensões expressivas e volumosas
        add_transformed_box(bm, sign*0.005, sign*0.058, -0.048, -0.008, -0.010, 0.075, has_seam=True)

        # 3. Asa do Laço Superior / Traseira (Lobo dobrado para cima e para trás)
        add_transformed_box(bm, sign*0.005, sign*0.058,  0.008,  0.048, -0.010, 0.075, has_seam=True)

        # 4. Fita Branca Pendurada (Cai reto verticalmente pela bochecha)
        # Não rotacionada pela inclinação do laço: cai reta pela gravidade!
        fx1 = pivot_world.x - 0.006
        fx2 = pivot_world.x + 0.006
        fy1 = pivot_world.y - 0.008
        fy2 = pivot_world.y + 0.002
        fz1 = pivot_world.z - 0.145
        fz2 = pivot_world.z - 0.015
        pts_tape = [
            mathutils.Vector((fx1, fy1, fz1)), mathutils.Vector((fx2, fy1, fz1)),
            mathutils.Vector((fx2, fy2, fz1)), mathutils.Vector((fx1, fy2, fz1)),
            mathutils.Vector((fx1, fy1, fz2)), mathutils.Vector((fx2, fy1, fz2)),
            mathutils.Vector((fx2, fy2, fz2)), mathutils.Vector((fx1, fy2, fz2)),
        ]
        verts_t = [bm.verts.new(tp) for tp in pts_tape]
        bm.verts.ensure_lookup_table()
        for f_indices in [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]:
            try:
                face = bm.faces.new([verts_t[i] for i in f_indices])
                for loop in face.loops:
                    loop[uv_rib].uv = (0.85, 0.25)
            except ValueError:
                pass

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        m = bpy.data.meshes.new(f"{name}_mesh")
        bm.to_mesh(m)
        bm.free()

        obj = bpy.data.objects.new(name, m)
        coll.objects.link(obj)
        obj.data.materials.append(mat_head)
        obj.matrix_world = head.matrix_world.copy()
        m.transform(obj.matrix_world.inverted())
        obj.parent = head
        obj.matrix_parent_inverse = head.matrix_world.inverted()
        return obj

    build_origami_ribbon("laco_esquerdo", is_left=True)
    build_origami_ribbon("laco_direito", is_left=False)

    bpy.context.view_layer.update()
    print("Cabeça, cabelo 2D+3D e laços de origami reconstruídos com perfeição!")

build_refined_head()
