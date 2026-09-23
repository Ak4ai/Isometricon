"""Script Mestre Unificado para Baixar, Ajustar e Vestir qualquer roupa do Roblox pelo ID.

Funciona para QUALQUER asset do catálogo:
- Camisas / Camisetas / Regatas (detecta manga curta vs manga longa automaticamente)
- Suéteres / Jaquetas / Casacos
- Calças / Bermudas / Saias
- Sapatos / Botas

Uso via terminal:
    python scripts/wear_roblox_asset.py <ID_DO_ASSET>
"""

import sys
import os
import re
import json
import gzip
import urllib.request

# Adiciona diretório de scripts ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import blender_client
from import_roblox_clothing import load_roblox_cookie, fetch_roblox_asset, decode_roblox_mesh_to_obj

TOP_ASSET_TYPES = {64, 65, 67, 68}    # T-Shirt, Shirt, Jacket, Sweater
BOTTOM_ASSET_TYPES = {66, 69, 70, 71, 72} # Pants, Shorts, LeftShoe, RightShoe, Dress/Skirt

def get_asset_metadata(asset_id):
    """Consulta a API do Roblox para obter o nome e o tipo do asset."""
    url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "name": data.get("Name", f"clothing_{asset_id}"),
                "type_id": data.get("AssetTypeId", 65),
                "desc": data.get("Description", "")
            }
    except Exception as e:
        print(f"[!] Erro ao buscar metadados de {asset_id}: {e}")
        return {"name": f"clothing_{asset_id}", "type_id": 65, "desc": ""}

def download_and_extract_asset(asset_id, metadata):
    """Baixa malha e textura do Roblox e salva em assets/models/clothing/."""
    os.makedirs("assets/models/clothing", exist_ok=True)
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', metadata["name"]).strip('_')
    if not clean_name:
        clean_name = f"clothing_{asset_id}"

    raw_data = fetch_roblox_asset(asset_id)
    if not raw_data:
        raise ValueError(f"Falha ao baixar asset {asset_id}")

    decomp = raw_data
    if raw_data.startswith(b"\x1f\x8b"):
        try:
            decomp = gzip.decompress(raw_data)
        except:
            pass

    mesh_id = asset_id
    tex_id = None

    if decomp.startswith(b"<roblox") or decomp.startswith(b"<roblox!"):
        m_mesh = re.search(rb'(?:MeshId|MeshID).*?(?:rbxassetid://|id=)(\d+)', decomp)
        if m_mesh:
            mesh_id = m_mesh.group(1).decode("ascii")
        m_tex = re.search(rb'(?:ColorMap|TextureID|TexturePack).*?(?:rbxassetid://|id=)(\d+)', decomp)
        if m_tex:
            tex_id = m_tex.group(1).decode("ascii")

    obj_path = os.path.abspath(f"assets/models/clothing/{clean_name}_{asset_id}.obj")
    tex_path = os.path.abspath(f"assets/models/clothing/{clean_name}_{asset_id}.png")

    print(f"[*] Baixando geometria (MeshId: {mesh_id})...")
    mesh_bytes = fetch_roblox_asset(mesh_id)
    if not mesh_bytes:
        raise ValueError(f"Falha ao obter dados da malha {mesh_id}")
    decode_roblox_mesh_to_obj(mesh_bytes, obj_path)

    if tex_id:
        print(f"[*] Baixando textura (TextureId: {tex_id})...")
        tex_bytes = fetch_roblox_asset(tex_id)
        if tex_bytes:
            if tex_bytes.startswith(b"\x1f\x8b"):
                try:
                    tex_bytes = gzip.decompress(tex_bytes)
                except Exception as e:
                    print(f"[!] Erro ao descompactar textura gzip: {e}")
            with open(tex_path, "wb") as f:
                f.write(tex_bytes)
            print(f"[OK] Textura salva em: {tex_path}")
    else:
        tex_path = None

    return clean_name, obj_path, tex_path

def wear(asset_id):
    """Executa o pipeline universal de ponta a ponta."""
    print(f"\n==================================================")
    print(f"  VESTIR ASSET ROBLOX: {asset_id}")
    print(f"==================================================")

    # 1. Metadados do catálogo
    meta = get_asset_metadata(asset_id)
    type_id = meta["type_id"]
    is_top = type_id in TOP_ASSET_TYPES or type_id not in BOTTOM_ASSET_TYPES
    kind_str = "PARTE SUPERIOR (Camisa/Jaqueta/Suéter)" if is_top else "PARTE INFERIOR (Calça/Bermuda/Botas)"
    print(f"[*] Asset: '{meta['name']}' (Tipo {type_id} -> {kind_str})")

    # 2. Download e decodificação
    clean_name, obj_path, tex_path = download_and_extract_asset(asset_id, meta)

    # 3. Execução no Blender ativo
    escaped_obj = obj_path.replace("\\", "\\\\")
    escaped_tex = tex_path.replace("\\", "\\\\") if tex_path else ""
    obj_blender_name = f"{'Top' if is_top else 'Bottom'}_{asset_id}"

    blender_code = f"""
import bpy, os, sys
sys.path.insert(0, r"C:/Users/Henrique/Documents/GitHub/Isometricon")

# Limpa instância anterior do mesmo objeto
for name in list(bpy.data.objects.keys()):
    if name == '{obj_blender_name}' or name.startswith('{obj_blender_name}.'):
        o = bpy.data.objects.get(name)
        if o:
            m = o.data
            bpy.data.objects.remove(o)
            try:
                bpy.data.meshes.remove(m)
            except:
                pass

# 1. Importa OBJ sem parentesco
bpy.ops.wm.obj_import(filepath='{escaped_obj}')
imported = bpy.context.selected_objects[0] if bpy.context.selected_objects else None
if imported:
    imported.name = '{obj_blender_name}'
    imported.parent = None
    imported.location = (0, 0, 0)
    imported.scale = (1, 1, 1)
    imported.rotation_euler = (0, 0, 0)

    # Configura Material PBR
    if '{escaped_tex}' and os.path.exists('{escaped_tex}'):
        mat_name = 'Mat_{obj_blender_name}'
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        node_out = nodes.new('ShaderNodeOutputMaterial')
        node_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        node_tex = nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load('{escaped_tex}', check_existing=True)
        node_tex.image = img
        node_tex.interpolation = 'Closest'
        node_bsdf.inputs['Roughness'].default_value = 0.8
        mat.node_tree.links.new(node_tex.outputs['Color'], node_bsdf.inputs['Base Color'])
        mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])
        if imported.data.materials:
            imported.data.materials[0] = mat
        else:
            imported.data.materials.append(mat)
    bpy.context.view_layer.update()

# 2. Executa o Auto-Fit especializado de acordo com o tipo da roupa
if {is_top}:
    import importlib
    import scripts.autofit_roblox_clothing as af_top
    importlib.reload(af_top)
    af_top.autofit(
        clothing_obj_name='{obj_blender_name}',
        raw_obj_path='{escaped_obj}',
        render_output=r'C:/Users/Henrique/Documents/GitHub/Isometricon/assets/renders/wear_{asset_id}.png',
        output_fbx=r'C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/character_wear_{asset_id}.fbx'
    )
else:
    import importlib
    import scripts.autofit_roblox_pants as af_bottom
    importlib.reload(af_bottom)
    af_bottom.autofit_pants(
        clothing_obj_name='{obj_blender_name}',
        raw_obj_path='{escaped_obj}',
        render_output=r'C:/Users/Henrique/Documents/GitHub/Isometricon/assets/renders/wear_{asset_id}.png',
        output_fbx=r'C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/character_wear_{asset_id}.fbx'
    )
"""
    res = blender_client.execute_blender_code(blender_code, timeout=90.0)
    print("Blender:", res.get("result", {}).get("result", ""))
    print(f"[OK] Roupa vestida com sucesso! Render em: assets/renders/wear_{asset_id}.png")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        wear(sys.argv[1])
    else:
        print("Uso: python scripts/wear_roblox_asset.py <asset_id>")
