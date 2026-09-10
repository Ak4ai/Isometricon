import bpy
import bmesh
import json
import os
import mathutils

DEFAULT_COLORS = {
    "cabeca": [0.92, 0.76, 0.65],
    "pecoco": [0.85, 0.70, 0.60],
    "torso": [0.22, 0.44, 0.72],
    "braco superior direito": [0.22, 0.44, 0.72],
    "braco superior esquerdo": [0.22, 0.44, 0.72],
    "antebraco direito": [0.90, 0.74, 0.63],
    "antebraco esquerdo": [0.90, 0.74, 0.63],
    "pelve": [0.18, 0.20, 0.26],
    "coxa direita": [0.22, 0.26, 0.36],
    "coxa esquerda": [0.22, 0.26, 0.36],
    "canela direita": [0.20, 0.24, 0.34],
    "canela esquerda": [0.20, 0.24, 0.34],
    "pe direito": [0.28, 0.20, 0.15],
    "pe esquerdo": [0.28, 0.20, 0.15],
}

def export():
    coll = bpy.data.collections.get("personagem")
    if not coll:
        print("Error: collection 'personagem' not found")
        return

    objects_data = {}
    
    # Map Blender (X, Y, Z) to OpenGL (X, Z, -Y) where:
    # X_gl = X_b (Right)
    # Y_gl = Z_b (Up)
    # Z_gl = -Y_b (Front faces +Z)
    def b2gl(v):
        return [float(v[0]), float(v[2]), -float(v[1])]

    for obj in coll.objects:
        if obj.type != 'MESH':
            continue
            
        parent_name = obj.parent.name if (obj.parent and obj.parent in coll.objects.values()) else None
        pivot_world_b = obj.matrix_world.translation.copy()
        pivot_gl = b2gl(pivot_world_b)
        
        # Triangulate mesh using bmesh
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        
        # Base color
        col = DEFAULT_COLORS.get(obj.name, [0.8, 0.8, 0.8])
        
        # Extract vertices in OpenGL format relative to object pivot:
        # [pos_x, pos_y, pos_z, norm_x, norm_y, norm_z, u, v, r, g, b] (11 floats)
        vertices = []
        indices = []
        
        # To avoid duplicate vertex merging issues with flat shading normals,
        # we export per-triangle vertices
        for face in bm.faces:
            fn_b = face.normal
            fn_gl = b2gl(fn_b)
            # Normalize
            length = (fn_gl[0]**2 + fn_gl[1]**2 + fn_gl[2]**2) ** 0.5
            if length > 1e-6:
                fn_gl = [fn_gl[0]/length, fn_gl[1]/length, fn_gl[2]/length]
                
            face_verts = []
            for vert in face.verts:
                # world coordinate in blender
                vw_b = obj.matrix_world @ vert.co
                # position relative to object's pivot in blender
                v_rel_b = vw_b - pivot_world_b
                # convert to gl
                v_rel_gl = b2gl(v_rel_b)
                
                # Default UV center
                u, v = 0.5, 0.5
                
                v_entry = [
                    round(v_rel_gl[0], 5), round(v_rel_gl[1], 5), round(v_rel_gl[2], 5),
                    round(fn_gl[0], 4), round(fn_gl[1], 4), round(fn_gl[2], 4),
                    u, v,
                    col[0], col[1], col[2]
                ]
                face_verts.append(v_entry)
                
            # Direct CCW winding preserved by -90 deg rotation around X
            base_idx = len(vertices)
            vertices.extend([face_verts[0], face_verts[1], face_verts[2]])
            indices.extend([base_idx, base_idx + 1, base_idx + 2])
            
        bm.free()
        
        objects_data[obj.name] = {
            "name": obj.name,
            "parent": parent_name,
            "pivot": [round(x, 5) for x in pivot_gl],
            "vertex_count": len(vertices),
            "index_count": len(indices),
            "vertices": vertices,
            "indices": indices,
        }

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(repo_root, "assets", "models", "character_modular.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(objects_data, f, indent=2)
        
    print(f"Exported {len(objects_data)} parts to {output_path}")

export()
