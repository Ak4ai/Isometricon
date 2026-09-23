import bpy
import os

collection_6 = bpy.data.collections.get('Collection 6')
cages_col = bpy.data.collections.get('Cages_Feminino')

if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')


name_mapping = {
    'cabeca.001': 'Export_cabeca',
    'pecoco.001': 'Export_pecoco',
    'Export_torso.001': 'Export_torso',
    'Export_pelve.001': 'Export_pelve',
    'Export_braco_superior_esquerdo.001': 'Export_braco_superior_esquerdo',
    'Export_braco_superior_direito.001': 'Export_braco_superior_direito',
    'Export_antebraco_esquerdo.001': 'Export_antebraco_esquerdo',
    'Export_antebraco_direito.001': 'Export_antebraco_direito',
    'Export_coxa_esquerda.001': 'Export_coxa_esquerda',
    'Export_coxa_direita.001': 'Export_coxa_direita',
    'Export_canela_esquerda.001': 'Export_canela_esquerda',
    'Export_canela_direita.001': 'Export_canela_direita',
    'pe_esquerdo.003': 'Export_pe_esquerdo',
    'pe_direito.003': 'Export_pe_direito',
}

# 1. Export character_female_clean.obj
out_lines = []
out_lines.append('# Blender female export for Isometricon\n')
out_lines.append('mtllib character_female_clean.mtl\n')

v_offset = 0
vt_offset = 0
vn_offset = 0

for b_name, exp_name in name_mapping.items():
    obj = collection_6.objects.get(b_name)
    if not obj:
        continue
    
    mesh = obj.data
    mw = obj.matrix_world
    
    out_lines.append(f'o {exp_name}\n')
    if exp_name in ('Export_cabeca', 'Export_cabelo'):
        out_lines.append('usemtl Mat_Head_Atlas\n')
    else:
        out_lines.append('usemtl Mat_Pele_Corpo\n')
    
    # Vertices (coordinate conversion: x=w.x, y=w.z, z=-w.y)
    for v in mesh.vertices:
        w = mw @ v.co
        out_lines.append(f'v {w.x:.6f} {w.z:.6f} {-w.y:.6f}\n')
    
    # Normals
    for v in mesh.vertices:
        nw = (mw.to_3x3() @ v.normal).normalized()
        out_lines.append(f'vn {nw.x:.4f} {nw.z:.4f} {-nw.y:.4f}\n')
    
    # UVs
    has_uv = len(mesh.uv_layers) > 0
    uv_layer = mesh.uv_layers.active.data if has_uv else None
    if has_uv:
        for poly in mesh.polygons:
            for l_idx in poly.loop_indices:
                uv = uv_layer[l_idx].uv
                out_lines.append(f'vt {uv.x:.6f} {uv.y:.6f}\n')
                
    # Faces
    loop_offset = 0
    for poly in mesh.polygons:
        tokens = []
        for v_idx in poly.vertices:
            v_i = v_offset + v_idx + 1
            vn_i = vn_offset + v_idx + 1
            if has_uv:
                vt_i = vt_offset + loop_offset + 1
                tokens.append(f'{v_i}/{vt_i}/{vn_i}')
                loop_offset += 1
            else:
                tokens.append(f'{v_i}//{vn_i}')
        out_lines.append('f ' + ' '.join(tokens) + '\n')
        
    v_offset += len(mesh.vertices)
    vn_offset += len(mesh.vertices)
    if has_uv:
        vt_offset += len(mesh.loops)

repo_root = r'C:\Users\Henrique\Documents\GitHub\Isometricon'
female_obj_path = os.path.join(repo_root, 'assets', 'models', 'character_female_clean.obj')
with open(female_obj_path, 'w', encoding='utf-8') as f:
    f.writelines(out_lines)

print(f'Successfully exported female body to {female_obj_path}. Total vertices: {v_offset}')

# 2. Export female cages to assets/models/clothing/female_cages.obj
cage_lines = []
cage_lines.append('# Blender female cages export for Isometricon\n')

cv_offset = 0
cvn_offset = 0
for cage_obj in sorted(cages_col.objects, key=lambda x: x.name):
    mesh = cage_obj.data
    mw = cage_obj.matrix_world
    
    cage_lines.append(f'o {cage_obj.name}\n')
    for v in mesh.vertices:
        w = mw @ v.co
        cage_lines.append(f'v {w.x:.6f} {w.z:.6f} {-w.y:.6f}\n')
    
    for v in mesh.vertices:
        nw = (mw.to_3x3() @ v.normal).normalized()
        cage_lines.append(f'vn {nw.x:.4f} {nw.z:.4f} {-nw.y:.4f}\n')
        
    for poly in mesh.polygons:
        tokens = []
        for v_idx in poly.vertices:
            v_i = cv_offset + v_idx + 1
            vn_i = cvn_offset + v_idx + 1
            tokens.append(f'{v_i}//{vn_i}')
        cage_lines.append('f ' + ' '.join(tokens) + '\n')
        
    cv_offset += len(mesh.vertices)
    cvn_offset += len(mesh.vertices)

female_cage_path = os.path.join(repo_root, 'assets', 'models', 'clothing', 'female_cages.obj')
with open(female_cage_path, 'w', encoding='utf-8') as f:
    f.writelines(cage_lines)

print(f'Successfully exported female cages to {female_cage_path}. Total vertices: {cv_offset}')

