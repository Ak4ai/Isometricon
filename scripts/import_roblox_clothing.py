"""Módulo completo e automatizado para baixar, decodificar e importar roupas do Roblox direto para o Blender.

Suporta:
- Arquivos .rbxm do Roblox (extrai MeshId e TextureId)
- IDs diretos do catálogo do Roblox
- Decodificação do formato FileMesh v7.00 comprimido em Draco 3D
- Download automático da textura e aplicação de material PBR
- Alinhamento, escala e parentesco automático com o Torso do nosso boneco no Blender
"""
import os
import sys
import re
import gzip
import struct
import urllib.request
import urllib.error

# Importa DracoPy para descompactação da geometria
import DracoPy

# Adiciona o diretório de scripts para comunicar com o Blender
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import blender_client

def load_roblox_cookie():
    """Lê o cookie do Roblox configurado no arquivo .env."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if "ROBLOSECURITY=" in content:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("ROBLOSECURITY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return content.strip().strip('"').strip("'")

def fetch_roblox_asset(asset_id):
    """Baixa o payload de qualquer asset autenticado do Roblox."""
    cookie = load_roblox_cookie()
    url = f"https://assetdelivery.roblox.com/v1/asset/?id={asset_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Roblox/WinInet",
        "Cookie": f".ROBLOSECURITY={cookie}" if cookie else ""
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read()
    except Exception as e:
        print(f"[ERRO] Falha ao baixar asset {asset_id}: {e}")
        return None

def parse_rbxm_metadata(rbxm_path):
    """Lê um arquivo .rbxm e obtém o MeshId e o TextureId."""
    with open(rbxm_path, "rb") as f:
        data = f.read()

    # Procurar MeshId
    m_mesh = re.search(rb'MeshId.*?rbxassetid://(\d+)', data)
    mesh_id = m_mesh.group(1).decode('ascii') if m_mesh else None

    # Procurar TextureID
    m_tex = re.search(rb'TextureID.*?rbxassetid://(\d+)', data)
    tex_id = m_tex.group(1).decode('ascii') if m_tex else None

    # Nome da peça
    m_name = re.search(rb'Name\s*([A-Za-z0-9\s\(\)_-]+)PROP', data)
    name = m_name.group(1).decode('ascii', errors='ignore').strip() if m_name else os.path.splitext(os.path.basename(rbxm_path))[0]

    return {
        "name": name,
        "mesh_id": mesh_id,
        "texture_id": tex_id
    }

def decode_roblox_mesh_to_obj(mesh_bytes, output_obj_path):
    """Decodifica os bytes da malha do Roblox (suporta v7 Draco e v4.xx FileMesh) e salva em .obj."""
    # Descompacta gzip se estiver comprimido
    if mesh_bytes.startswith(b"\x1f\x8b"):
        mesh_bytes = gzip.decompress(mesh_bytes)

    # 0. Suporte a FileMesh v1.00 e v1.01 (formato ASCII clássico com vetores entre colchetes)
    if mesh_bytes.startswith(b"version 1.00") or mesh_bytes.startswith(b"version 1.01"):
        is_v101 = mesh_bytes.startswith(b"version 1.01")
        text = mesh_bytes.decode('ascii', errors='ignore')
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        num_faces = int(lines[1])
        data = lines[2]

        vector_pattern = re.compile(r'\[([^\]]+)\]')
        raw_vectors = vector_pattern.findall(data)

        parsed_vectors = []
        for v_str in raw_vectors:
            parts = [float(x.strip()) for x in v_str.split(',')]
            parsed_vectors.append(parts)

        coord_scale = 0.5 if is_v101 else 1.0
        total_verts = len(parsed_vectors) // 3

        with open(output_obj_path, "w", encoding="utf-8") as f:
            f.write("# Roblox Converted FileMesh v1\n")
            for i in range(0, len(parsed_vectors), 3):
                p = parsed_vectors[i]
                f.write(f"v {p[0]*coord_scale:.6f} {p[1]*coord_scale:.6f} {p[2]*coord_scale:.6f}\n")
            for i in range(1, len(parsed_vectors), 3):
                n = parsed_vectors[i]
                f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            for i in range(2, len(parsed_vectors), 3):
                u = parsed_vectors[i]
                f.write(f"vt {u[0]:.6f} {1.0 - u[1]:.6f}\n")
            for i in range(num_faces):
                i0 = i * 3 + 1
                i1 = i * 3 + 2
                i2 = i * 3 + 3
                f.write(f"f {i0}/{i0}/{i0} {i1}/{i1}/{i1} {i2}/{i2}/{i2}\n")

        print(f"[OK] FileMesh v1 decodificado: {total_verts} vértices, {num_faces} faces -> {output_obj_path}")
        return output_obj_path

    # FileMesh v2: 12-byte header followed by 40-byte vertices and 12-byte faces.
    if mesh_bytes.startswith(b"version 2.00\n"):
        hdr_end = mesh_bytes.find(b"\n") + 1
        sizeof_hdr, sizeof_vert, sizeof_face, num_verts, num_faces = struct.unpack_from(
            '<HBBII', mesh_bytes, hdr_end
        )
        if (sizeof_hdr != 12 or sizeof_vert < 32 or sizeof_face != 12 or
                len(mesh_bytes) < hdr_end + sizeof_hdr + num_verts * sizeof_vert + num_faces * sizeof_face):
            raise ValueError("FileMesh v2 inválido ou truncado")
        vertex_start = hdr_end + sizeof_hdr
        face_start = vertex_start + num_verts * sizeof_vert
        verts = [struct.unpack_from('<8f', mesh_bytes, vertex_start + i * sizeof_vert)
                 for i in range(num_verts)]
        faces = [struct.unpack_from('<3I', mesh_bytes, face_start + i * sizeof_face)
                 for i in range(num_faces)]
        if any(max(face) >= num_verts for face in faces):
            raise ValueError("FileMesh v2 contém índices de face inválidos")
        with open(output_obj_path, "w", encoding="utf-8") as f:
            f.write("# Roblox Converted FileMesh v2\n")
            for v in verts:
                f.write(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n")
            for v in verts:
                f.write(f"vt {v[6]:.9f} {1.0 - v[7]:.9f}\n")
            for a, b, c in faces:
                f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")
        return output_obj_path

    # 1. Suporte a FileMesh v4.xx (v4.00, v4.01, v5.00)
    if mesh_bytes.startswith(b"version 4.") or mesh_bytes.startswith(b"version 5."):
        hdr_end = mesh_bytes.find(b"\n") + 1
        header_data = mesh_bytes[hdr_end:hdr_end + 24]
        sizeof_hdr, lod_type, num_verts, num_faces, num_lods, num_bones, sz_bones, num_subsets = struct.unpack(
            '<H H I I H H I H', header_data[:22]
        )

        payload = mesh_bytes[hdr_end + sizeof_hdr:]
        # Cada vértice no formato v4 tem exatamente 40 bytes:
        # px, py, pz (12) + nx, ny, nz (12) + u, v (8) + tangent (4) + color (4) = 40 bytes
        sizeof_vert = 40
        verts = []
        for i in range(num_verts):
            px, py, pz, nx, ny, nz, u, v = struct.unpack_from('<8f', payload, i * sizeof_vert)
            verts.append((px, py, pz, u, v))

        # Dados de skinning: se num_bones > 0, cada vértice possui 8 bytes (boneIndices[4] + boneWeights[4])
        # posicionados em bloco logo após todos os vértices e antes das faces
        skinning_size = (num_verts * 8) if num_bones > 0 else 0
        face_offset = (num_verts * sizeof_vert) + skinning_size

        faces = []
        for i in range(num_faces):
            i0, i1, i2 = struct.unpack_from('<3I', payload, face_offset + i * 12)
            faces.append((i0, i1, i2))

        # The face list holds every level of detail back to back; the LOD table
        # after it gives each level's first face. Keep only LOD0, as Roblox
        # renders up close (and Studio exports), and drop the vertices that only
        # lower levels use — LOD0 always references a prefix of the vertex list.
        if num_lods >= 2:
            lods = struct.unpack_from(f'<{num_lods}I', payload, face_offset + num_faces * 12)
            if 0 <= lods[0] < lods[1] <= num_faces:
                faces = faces[lods[0]:lods[1]]
                used = max(max(face) for face in faces) + 1
                if len({i for face in faces for i in face}) == used:
                    verts = verts[:used]

        with open(output_obj_path, "w", encoding="utf-8") as f:
            f.write("# Roblox Converted FileMesh v4\n")
            for v in verts:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for v in verts:
                f.write(f"vt {v[3]:.6f} {1.0 - v[4]:.6f}\n")
            for face in faces:
                f.write(f"f {face[0]+1}/{face[0]+1} {face[1]+1}/{face[1]+1} {face[2]+1}/{face[2]+1}\n")

        print(f"[OK] FileMesh v4 decodificado: {len(verts)} vértices, {len(faces)} faces -> {output_obj_path}")
        return output_obj_path

    # 2. Suporte a Draco 3D (v7)
    d_idx = mesh_bytes.find(b"DRACO")
    if d_idx != -1:
        draco_stream = mesh_bytes[d_idx:]
        decoded = DracoPy.decode(draco_stream)
        has_uv = hasattr(decoded, 'tex_coord') and decoded.tex_coord is not None and len(decoded.tex_coord) > 0
        
        with open(output_obj_path, "w", encoding="utf-8") as f:
            f.write("# Roblox Converted Mesh Draco\n")
            for p in decoded.points:
                f.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
            if has_uv:
                for uv in decoded.tex_coord:
                    f.write(f"vt {uv[0]:.6f} {1.0 - uv[1]:.6f}\n")
            for face in decoded.faces:
                if has_uv:
                    f.write(f"f {face[0]+1}/{face[0]+1} {face[1]+1}/{face[1]+1} {face[2]+1}/{face[2]+1}\n")
                else:
                    f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

        print(f"[OK] Malha Draco decodificada: {len(decoded.points)} vértices, {len(decoded.faces)} faces -> {output_obj_path}")
        return output_obj_path

    raise ValueError("Formato de malha desconhecido (nem Draco nem FileMesh v4).")

def import_and_align_in_blender(obj_path, tex_path=None, name="Jaqueta_Roblox"):
    """Comunica com o Blender ativo para importar, aplicar textura e alinhar ao Torso."""
    escaped_obj = os.path.abspath(obj_path).replace("\\", "\\\\")
    escaped_tex = os.path.abspath(tex_path).replace("\\", "\\\\") if tex_path else ""

    blender_code = f"""
import bpy, os

# 1. Importa a malha OBJ
bpy.ops.wm.obj_import(filepath='{escaped_obj}')
imported = bpy.context.selected_objects[0] if bpy.context.selected_objects else None

if imported:
    imported.name = '{name}'
    
    # 2. Configura Material e Textura se fornecida
    if '{escaped_tex}' and os.path.exists('{escaped_tex}'):
        mat = bpy.data.materials.new(name='Mat_{name}')
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        
        node_out = nodes.new('ShaderNodeOutputMaterial')
        node_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        node_tex = nodes.new('ShaderNodeTexImage')
        
        img = bpy.data.images.load('{escaped_tex}', check_existing=True)
        node_tex.image = img
        node_tex.interpolation = 'Closest'
        
        mat.node_tree.links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
        mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])
        
        if imported.data.materials:
            imported.data.materials[0] = mat
        else:
            imported.data.materials.append(mat)
            
    # 3. Mantém o objeto na raiz sem parentesco para o pipeline universal de auto-fit
    imported.parent = None
    imported.location = (0, 0, 0)
    imported.scale = (1, 1, 1)
    imported.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    print(f'Roupa {name} importada com sucesso no Blender!')
"""
    res = blender_client.execute_blender_code(blender_code)
    print("Blender:", res.get("result", {}).get("result", ""))
    return True

def process_and_import(rbxm_or_id):
    """Executa o pipeline completo para um arquivo .rbxm ou ID de catálogo direto."""
    os.makedirs("assets/models/clothing", exist_ok=True)

    name = None
    mesh_id = None
    tex_id = None

    if os.path.exists(rbxm_or_id) and rbxm_or_id.endswith(".rbxm"):
        meta = parse_rbxm_metadata(rbxm_or_id)
        name = meta["name"]
        mesh_id = meta["mesh_id"]
        tex_id = meta["texture_id"]
    else:
        # Se for um ID numérico de catálogo, pode ser um Accessory (.rbxm) ou Mesh direto
        print(f"[*] Verificando tipo de asset para ID {rbxm_or_id}...")
        raw_data = fetch_roblox_asset(rbxm_or_id)
        if not raw_data:
            print(f"[!] Não foi possível baixar o asset {rbxm_or_id}.")
            return False

        decomp = raw_data
        if raw_data.startswith(b"\x1f\x8b"):
            try:
                decomp = gzip.decompress(raw_data)
            except:
                pass

        if decomp.startswith(b"<roblox"):
            # É um pacote/Accessory RBXM
            m_mesh = re.search(rb'MeshId.*?rbxassetid://(\d+)', decomp)
            mesh_id = m_mesh.group(1).decode('ascii') if m_mesh else None

            # Procura ColorMap ou TextureID
            m_tex = re.search(rb'ColorMap.*?rbxassetid://(\d+)', decomp) or re.search(rb'TextureID.*?rbxassetid://(\d+)', decomp)
            tex_id = m_tex.group(1).decode('ascii') if m_tex else None

            m_name = re.search(rb'Name\s*([A-Za-z0-9\s\(\)_-]+)PROP', decomp)
            name = m_name.group(1).decode('ascii', errors='ignore').strip() if m_name else f"clothing_{rbxm_or_id}"
            print(f"[*] Accessory catalog detectado: '{name}' (MeshId: {mesh_id}, TextureId: {tex_id})")
        else:
            name = f"clothing_{rbxm_or_id}"
            mesh_id = rbxm_or_id
            tex_id = None

    print(f"\n==========================================")
    print(f"[*] Processando: {name}")
    print(f"    MeshId: {mesh_id} | TextureId: {tex_id}")
    print(f"==========================================")

    # 1. Baixar Malha
    print("[1/3] Baixando malha do catálogo...")
    mesh_bytes = fetch_roblox_asset(mesh_id)
    if not mesh_bytes:
        print("[!] Não foi possível obter os dados da malha.")
        return False

    # 2. Decodificar para OBJ
    print("[2/3] Decodificando geometria para formato OBJ padrão...")
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    obj_path = os.path.abspath(f"assets/models/clothing/{clean_name}.obj")
    decode_roblox_mesh_to_obj(mesh_bytes, obj_path)

    # 3. Baixar Textura se existir
    tex_path = None
    if tex_id:
        print("[3/3] Baixando textura associada...")
        tex_bytes = fetch_roblox_asset(tex_id)
        if tex_bytes:
            if tex_bytes.startswith(b"\x1f\x8b"):
                try:
                    tex_bytes = gzip.decompress(tex_bytes)
                except Exception as e:
                    print(f"[!] Falha ao descompactar textura gzip: {e}")
            tex_path = os.path.abspath(f"assets/models/clothing/{clean_name}.png")
            with open(tex_path, "wb") as f:
                f.write(tex_bytes)
            print(f"[OK] Textura salva em: {tex_path}")

    # 4. Importar para o Blender ativo
    print("[+] Enviando e encaixando modelo na sessão do Blender...")
    import_and_align_in_blender(obj_path, tex_path=tex_path, name=clean_name)
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_and_import(sys.argv[1])
    else:
        # Importa as duas jaquetas baixadas por padrão
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        p1 = os.path.join(downloads, "92028318196252.rbxm")
        p2 = os.path.join(downloads, "101906182070448.rbxm")
        if os.path.exists(p1):
            process_and_import(p1)
        if os.path.exists(p2):
            process_and_import(p2)
