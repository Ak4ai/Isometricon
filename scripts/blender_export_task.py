import os
import bpy
from mathutils import Vector

OUT_CAGES_PATH = "C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/clothing/female_cages_apose.obj"
OUT_CLEAN_PATH = "C:/Users/Henrique/Documents/GitHub/Isometricon/assets/models/character_female_clean_apose.obj"

# ==========================================
# 1. EXPORT CAGES
# ==========================================
cages_order = [
    "Head_OuterCage",
    "UpperTorso_OuterCage",
    "LowerTorso_OuterCage",
    "LeftUpperArm_OuterCage",
    "LeftLowerArm_OuterCage",
    "LeftHand_OuterCage",
    "RightUpperArm_OuterCage",
    "RightLowerArm_OuterCage",
    "RightHand_OuterCage",
    "LeftUpperLeg_OuterCage",
    "LeftLowerLeg_OuterCage",
    "LeftFoot_OuterCage",
    "RightUpperLeg_OuterCage",
    "RightLowerLeg_OuterCage",
    "RightFoot_OuterCage"
]

cages_lines = [
    "# Canonical Roblox A-Pose Female Outer Cages (15 R15 parts)",
    "# Exported from Blender with perfect 30-deg A-pose and symmetry"
]

v_offset = 0
total_cage_verts = 0
total_cage_faces = 0

for c_name in cages_order:
    obj = bpy.data.objects.get(c_name)
    if not obj:
        print(f"ERROR: Cage {c_name} not found!")
        continue
        
    cages_lines.append(f"o {c_name}")
    
    # Vertices (Blender to OBJ: X -> X, Z -> Y, -Y -> Z)
    for v in obj.data.vertices:
        w = obj.matrix_world @ v.co
        x_obj = w.x
        y_obj = w.z
        z_obj = -w.y
        cages_lines.append(f"v {x_obj:.6f} {y_obj:.6f} {z_obj:.6f}")
        
    num_verts = len(obj.data.vertices)
    total_cage_verts += num_verts
    
    # Faces
    for poly in obj.data.polygons:
        f_indices = [str(idx + 1 + v_offset) for idx in poly.vertices]
        cages_lines.append(f"f {' '.join(f_indices)}")
        total_cage_faces += 1
        
    v_offset += num_verts

with open(OUT_CAGES_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(cages_lines) + "\n")
    
print(f"Cages exported to {OUT_CAGES_PATH}: {total_cage_verts} verts, {total_cage_faces} faces.")

# ==========================================
# 2. EXPORT CLEAN CHARACTER BODY
# ==========================================
body_order = [
    ("cabeca.001", "Export_cabeca"),
    ("pecoco.001", "Export_pecoco"),
    ("Export_torso.001", "Export_torso"),
    ("Export_pelve.001", "Export_pelve"),
    ("Export_braco_superior_esquerdo.001", "Export_braco_superior_esquerdo"),
    ("Export_antebraco_esquerdo.001", "Export_antebraco_esquerdo"),
    ("Export_mao_esquerda.001", "Export_mao_esquerda"),
    ("Export_braco_superior_direito.001", "Export_braco_superior_direito"),
    ("Export_antebraco_direito.001", "Export_antebraco_direito"),
    ("Export_mao_direita.001", "Export_mao_direita"),
    ("Export_coxa_esquerda.001", "Export_coxa_esquerda"),
    ("Export_canela_esquerda.001", "Export_canela_esquerda"),
    ("pe_esquerdo.003", "Export_pe_esquerdo"),
    ("Export_coxa_direita.001", "Export_coxa_direita"),
    ("Export_canela_direita.001", "Export_canela_direita"),
    ("pe_direito.003", "Export_pe_direito")
]

body_lines = [
    "# Canonical Roblox A-Pose Female Character Clean Mesh",
    "# Exported from Blender with 30-deg A-pose, separated hands, anatomical head posture",
    "mtllib character_female_clean.mtl"
]

v_offset_b = 0
vt_offset_b = 0
vn_offset_b = 0
total_body_verts = 0
total_body_faces = 0

for b_obj_name, export_name in body_order:
    obj = bpy.data.objects.get(b_obj_name)
    if not obj:
        print(f"ERROR: Body object {b_obj_name} not found!")
        continue
        
    body_lines.append(f"o {export_name}")
    
    mat_name = obj.data.materials[0].name if obj.data.materials and obj.data.materials[0] else "Mat_Pele_Corpo"
    body_lines.append(f"usemtl {mat_name}")
    
    # Vertices
    for v in obj.data.vertices:
        w = obj.matrix_world @ v.co
        body_lines.append(f"v {w.x:.6f} {w.z:.6f} {-w.y:.6f}")
    num_verts = len(obj.data.vertices)
    total_body_verts += num_verts
    
    # UVs & Normals
    mesh = obj.data
    uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    has_uv = uv_layer is not None and len(uv_layer) > 0
    
    mat_rot = obj.matrix_world.to_3x3()
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            v_idx = mesh.loops[loop_idx].vertex_index
            norm = (mat_rot @ mesh.vertices[v_idx].normal).normalized()
            body_lines.append(f"vn {norm.x:.4f} {norm.z:.4f} {-norm.y:.4f}")
            
            if has_uv:
                uv = uv_layer[loop_idx].uv
                body_lines.append(f"vt {uv.x:.6f} {uv.y:.6f}")
            else:
                body_lines.append("vt 0.000000 0.000000")
                
    num_loops = len(mesh.loops)
    
    # Faces
    loop_counter = 0
    for poly in mesh.polygons:
        face_toks = []
        for v_idx in poly.vertices:
            cur_v = v_idx + 1 + v_offset_b
            cur_vt = loop_counter + 1 + vt_offset_b
            cur_vn = loop_counter + 1 + vn_offset_b
            face_toks.append(f"{cur_v}/{cur_vt}/{cur_vn}")
            loop_counter += 1
            
        body_lines.append(f"f {' '.join(face_toks)}")
        total_body_faces += 1
        
    v_offset_b += num_verts
    vt_offset_b += num_loops
    vn_offset_b += num_loops

with open(OUT_CLEAN_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(body_lines) + "\n")
    
print(f"Body exported to {OUT_CLEAN_PATH}: {total_body_verts} verts, {total_body_faces} faces.")
