"""Algoritmo Universal de Auto-Fit e Segmentação Modular de Roupas:
Adapta e molda automaticamente qualquer roupa (Roblox/externa) a qualquer modelo humanoide (bloco/estilizado).

Etapas:
1. Leitura Anatômica Dinâmica: Mede os limites do corpo ativo (Torso, Braços E/D).
2. Normalização e Escala Automática: Ajusta X, Y e Z para cobrir os ombros e a cintura com margem precisa.
3. Alinhamento de Gola: Posiciona a gola da jaqueta no início do pescoço sem encobrir o queixo.
4. Auto-Segmentação dos Membros (Clustering Modular):
   - Separa a malha em 3 peças articuladas:
     a) jaqueta_torso -> parentada ao Torso
     b) jaqueta_manga_esq -> parentada ao Braço Superior Esquerdo
     c) jaqueta_manga_dir -> parentada ao Braço Superior Direito
5. Preservação de Materiais e Texturas.
"""
import bpy
import bmesh
import mathutils

def get_world_bounds(obj):
    """Calcula a caixa delimitadora em coordenadas globais de um objeto."""
    mw = obj.matrix_world
    wverts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in wverts]
    ys = [v.y for v in wverts]
    zs = [v.z for v in wverts]
    return {
        "min": mathutils.Vector((min(xs), min(ys), min(zs))),
        "max": mathutils.Vector((max(xs), max(ys), max(zs))),
        "center": mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)),
        "size": mathutils.Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
    }

def auto_fit_clothing(clothing_obj_name="92028318196252"):
    clothing = bpy.data.objects.get(clothing_obj_name)
    torso = bpy.data.objects.get("torso")
    arm_l = bpy.data.objects.get("braco superior esquerdo")
    arm_r = bpy.data.objects.get("braco superior direito")

    if not clothing or not torso:
        print(f"[ERRO] Objeto da roupa '{clothing_obj_name}' ou 'torso' não encontrado.")
        return False

    print(f"[*] Iniciando Auto-Fit Inteligente para '{clothing_obj_name}'...")

    # 1. Obter anatomia do modelo atual
    torso_b = get_world_bounds(torso)
    
    # Calcular envergadura total dos ombros considerando os braços
    shoulder_l_x = arm_l.matrix_world.translation.x if arm_l else torso_b["max"].x
    shoulder_r_x = arm_r.matrix_world.translation.x if arm_r else torso_b["min"].x
    shoulder_width = abs(shoulder_l_x - shoulder_r_x) + (0.12 * 2) # Margem dos ombros

    target_top_z = torso_b["max"].z + 0.02 # Altura da gola nos ombros
    target_bottom_z = torso_b["min"].z - 0.03 # Barra na cintura
    target_height = target_top_z - target_bottom_z
    target_depth = torso_b["size"].y * 1.15 # 15% de folga peito/costas

    # 2. Medir a roupa em seu estado local
    cloth_local_verts = [v.co for v in clothing.data.vertices]
    c_xs = [v.x for v in cloth_local_verts]
    c_ys = [v.y for v in cloth_local_verts]
    c_zs = [v.z for v in cloth_local_verts]
    cloth_size = mathutils.Vector((max(c_xs) - min(c_xs), max(c_ys) - min(c_ys), max(c_zs) - min(c_zs)))

    # 3. Calcular Fatores de Escala Anatômica Independentes (X, Y, Z)
    # A largura da roupa de ombro a ombro corresponde a ~60% da envergadura total das mangas estendidas
    scale_x = (shoulder_width * 1.6) / cloth_size.x
    scale_y = target_depth / cloth_size.y
    scale_z = (target_height * 1.35) / cloth_size.z

    # Desvincular parentesco temporário para aplicar transformação limpa
    clothing.parent = None
    clothing.scale = (scale_x, scale_y, scale_z)
    
    # Alinhar centro e gola
    clothing.location.x = torso_b["center"].x
    clothing.location.y = torso_b["center"].y + 0.01 # Ligeiro avanço frontal
    clothing.location.z = target_bottom_z + (cloth_size.z * scale_z * 0.46)
    
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    clothing.select_set(True)
    bpy.context.view_layer.objects.active = clothing
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # 4. Auto-Segmentação em 3 Partes Modulares (Tronco e Mangas)
    print("[*] Segmentando malha da roupa em Torso e Mangas articuladas...")
    bm = bmesh.new()
    bm.from_mesh(clothing.data)
    mw = clothing.matrix_world

    # Limiares de corte anatômico baseados nos ombros
    x_cut_left = shoulder_l_x - 0.04
    x_cut_right = shoulder_r_x + 0.04

    # Identificar faces de cada segmento
    faces_torso = []
    faces_arm_l = []
    faces_arm_r = []

    for f in bm.faces:
        center_world = mw @ f.calc_center_median()
        if center_world.x > x_cut_left:
            faces_arm_l.append(f)
        elif center_world.x < x_cut_right:
            faces_arm_r.append(f)
        else:
            faces_torso.append(f)

    print(f"    Distribuição: Torso={len(faces_torso)} faces, Manga Esq={len(faces_arm_l)} faces, Manga Dir={len(faces_arm_r)} faces")

    # Função auxiliar para extrair uma nova malha a partir de uma lista de faces
    def extract_submesh(name, target_faces, parent_obj):
        bm_sub = bmesh.new()
        vert_map = {}
        uv_src = bm.loops.layers.uv.active
        uv_dst = bm_sub.loops.layers.uv.new("UVMap")

        for f in target_faces:
            new_verts = []
            for v in f.verts:
                if v not in vert_map:
                    vert_map[v] = bm_sub.verts.new(v.co)
                new_verts.append(vert_map[v])
            bm_sub.verts.ensure_lookup_table()
            try:
                new_face = bm_sub.faces.new(new_verts)
                if uv_src:
                    for l_old, l_new in zip(f.loops, new_face.loops):
                        l_new[uv_dst].uv = l_old[uv_src].uv
            except ValueError:
                pass

        bm_sub.to_mesh(clothing.data) # Atualiza temporário
        new_m = bpy.data.meshes.new(f"{name}_mesh")
        bm_sub.to_mesh(new_m)
        bm_sub.free()

        sub_obj = bpy.data.objects.new(name, new_m)
        torso.users_collection[0].objects.link(sub_obj)
        sub_obj.matrix_world = clothing.matrix_world.copy()
        
        # Copia materiais da jaqueta
        for m in clothing.data.materials:
            sub_obj.data.materials.append(m)

        # Parenta ao membro correspondente
        if parent_obj:
            sub_obj.parent = parent_obj
            sub_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()

        return sub_obj

    # Criar as 3 partes separadas
    part_torso = extract_submesh(f"{clothing_obj_name}_corpo", faces_torso, torso)
    part_arm_l = extract_submesh(f"{clothing_obj_name}_manga_esq", faces_arm_l, arm_l)
    part_arm_r = extract_submesh(f"{clothing_obj_name}_manga_dir", faces_arm_r, arm_r)

    bm.free()

    # Ocultar a malha bruta original inteira
    clothing.hide_render = True
    clothing.hide_viewport = True

    bpy.context.view_layer.update()
    print(f"[SUCESSO] Auto-fit e segmentação concluídos para '{clothing_obj_name}'!")
    return {
        "torso": part_torso.name,
        "arm_l": part_arm_l.name,
        "arm_r": part_arm_r.name
    }

if __name__ == "__main__":
    auto_fit_clothing("92028318196252")
