import bpy
import bmesh
import mathutils

def run():
    scene = bpy.context.scene
    
    # 1. Clean up previously generated split objects
    split_names = [
        "braco superior direito", "antebraco direito",
        "braco superior esquerdo", "antebraco esquerdo",
        "coxa direita", "canela direita",
        "coxa esquerda", "canela esquerda"
    ]
    for name in split_names:
        old_obj = bpy.data.objects.get(name)
        if old_obj:
            old_mesh = old_obj.data
            bpy.data.objects.remove(old_obj, do_unlink=True)
            if old_mesh:
                bpy.data.meshes.remove(old_mesh)

    # 2. Get backup collection & personagem collection
    backup_coll = bpy.data.collections.get("Backup_Originais")
    if not backup_coll:
        backup_coll = bpy.data.collections.new("Backup_Originais")
        scene.collection.children.link(backup_coll)
    backup_coll.hide_viewport = True
    backup_coll.hide_render = True

    personagem_coll = bpy.data.collections.get("personagem")
    if not personagem_coll:
        personagem_coll = scene.collection

    # 3. Clean origin & identity matrix setter
    def create_limb_object(name, mesh, pivot_world):
        obj = bpy.data.objects.new(name, mesh)
        personagem_coll.objects.link(obj)
        # Set matrix_world with pure translation at pivot_world and identity rot/scale
        M_new = mathutils.Matrix.Translation(pivot_world)
        obj.matrix_world = M_new
        bpy.context.view_layer.update()
        return obj

    def parent_keep_transform(child_obj, parent_obj):
        child_obj.parent = parent_obj
        child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
        bpy.context.view_layer.update()

    # 4. Split Arm
    # Polys:
    # Upper Arm: 4, 6, 7, 8, 9, 10 + elbow cap
    # Forearm:   0, 1, 2, 3, 5    + elbow cap
    def split_arm(orig_name, name_upper, name_lower):
        orig_obj = bpy.data.objects.get(orig_name)
        if not orig_obj:
            print(f"Object {orig_name} not found!")
            return None, None
            
        upper_poly_indices = [4, 6, 7, 8, 9, 10]
        lower_poly_indices = [0, 1, 2, 3, 5]
        
        shoulder_indices = [0, 2, 4, 6, 12, 13]
        shoulder_world = sum([orig_obj.matrix_world @ orig_obj.data.vertices[i].co for i in shoulder_indices], mathutils.Vector()) / len(shoulder_indices)
        elbow_world = sum([orig_obj.matrix_world @ orig_obj.data.vertices[i].co for i in [8, 9, 10, 11]], mathutils.Vector()) / 4.0
        
        # Build Upper Arm mesh in world space relative to shoulder_world
        mesh_upper = bpy.data.meshes.new(name_upper + "_mesh")
        bm_up = bmesh.new()
        vert_map_up = {}
        for p_idx in upper_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            for v_idx in poly.vertices:
                if v_idx not in vert_map_up:
                    v_world = orig_obj.matrix_world @ orig_obj.data.vertices[v_idx].co
                    vert_map_up[v_idx] = bm_up.verts.new(v_world - shoulder_world)
        bm_up.verts.ensure_lookup_table()
        for p_idx in upper_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            bm_up.faces.new([vert_map_up[v_idx] for v_idx in poly.vertices])
        try:
            bm_up.faces.new([vert_map_up[8], vert_map_up[9], vert_map_up[10], vert_map_up[11]])
        except ValueError:
            pass
        bmesh.ops.recalc_face_normals(bm_up, faces=bm_up.faces)
        bm_up.to_mesh(mesh_upper)
        bm_up.free()
        
        # Build Forearm mesh in world space relative to elbow_world
        mesh_lower = bpy.data.meshes.new(name_lower + "_mesh")
        bm_low = bmesh.new()
        vert_map_low = {}
        for p_idx in lower_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            for v_idx in poly.vertices:
                if v_idx not in vert_map_low:
                    v_world = orig_obj.matrix_world @ orig_obj.data.vertices[v_idx].co
                    vert_map_low[v_idx] = bm_low.verts.new(v_world - elbow_world)
        bm_low.verts.ensure_lookup_table()
        for p_idx in lower_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            bm_low.faces.new([vert_map_low[v_idx] for v_idx in poly.vertices])
        try:
            bm_low.faces.new([vert_map_low[8], vert_map_low[11], vert_map_low[10], vert_map_low[9]])
        except ValueError:
            pass
        bmesh.ops.recalc_face_normals(bm_low, faces=bm_low.faces)
        bm_low.to_mesh(mesh_lower)
        bm_low.free()
        
        obj_upper = create_limb_object(name_upper, mesh_upper, shoulder_world)
        obj_lower = create_limb_object(name_lower, mesh_lower, elbow_world)
        
        parent_keep_transform(obj_lower, obj_upper)
        
        if orig_obj.name not in backup_coll.objects:
            backup_coll.objects.link(orig_obj)
        for coll in list(orig_obj.users_collection):
            if coll != backup_coll:
                coll.objects.unlink(orig_obj)
                
        return obj_upper, obj_lower

    # 5. Split Leg
    # Polys:
    # Thigh:     4, 6, 7, 8, 9 + knee cap
    # Calf/Shin: 0, 1, 2, 3, 5 + knee cap
    def split_leg(orig_name, name_upper, name_lower, foot_name):
        orig_obj = bpy.data.objects.get(orig_name)
        if not orig_obj:
            print(f"Object {orig_name} not found!")
            return None, None
            
        upper_poly_indices = [4, 6, 7, 8, 9]
        lower_poly_indices = [0, 1, 2, 3, 5]
        
        hip_indices = [0, 2, 4, 6]
        hip_world = sum([orig_obj.matrix_world @ orig_obj.data.vertices[i].co for i in hip_indices], mathutils.Vector()) / len(hip_indices)
        knee_world = sum([orig_obj.matrix_world @ orig_obj.data.vertices[i].co for i in [8, 9, 10, 11]], mathutils.Vector()) / 4.0
        
        # Build Thigh mesh in world space relative to hip_world
        mesh_upper = bpy.data.meshes.new(name_upper + "_mesh")
        bm_up = bmesh.new()
        vert_map_up = {}
        for p_idx in upper_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            for v_idx in poly.vertices:
                if v_idx not in vert_map_up:
                    v_world = orig_obj.matrix_world @ orig_obj.data.vertices[v_idx].co
                    vert_map_up[v_idx] = bm_up.verts.new(v_world - hip_world)
        bm_up.verts.ensure_lookup_table()
        for p_idx in upper_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            bm_up.faces.new([vert_map_up[v_idx] for v_idx in poly.vertices])
        try:
            bm_up.faces.new([vert_map_up[8], vert_map_up[9], vert_map_up[10], vert_map_up[11]])
        except ValueError:
            pass
        bmesh.ops.recalc_face_normals(bm_up, faces=bm_up.faces)
        bm_up.to_mesh(mesh_upper)
        bm_up.free()
        
        # Build Calf mesh in world space relative to knee_world
        mesh_lower = bpy.data.meshes.new(name_lower + "_mesh")
        bm_low = bmesh.new()
        vert_map_low = {}
        for p_idx in lower_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            for v_idx in poly.vertices:
                if v_idx not in vert_map_low:
                    v_world = orig_obj.matrix_world @ orig_obj.data.vertices[v_idx].co
                    vert_map_low[v_idx] = bm_low.verts.new(v_world - knee_world)
        bm_low.verts.ensure_lookup_table()
        for p_idx in lower_poly_indices:
            poly = orig_obj.data.polygons[p_idx]
            bm_low.faces.new([vert_map_low[v_idx] for v_idx in poly.vertices])
        try:
            bm_low.faces.new([vert_map_low[8], vert_map_low[11], vert_map_low[10], vert_map_low[9]])
        except ValueError:
            pass
        bmesh.ops.recalc_face_normals(bm_low, faces=bm_low.faces)
        bm_low.to_mesh(mesh_lower)
        bm_low.free()
        
        obj_upper = create_limb_object(name_upper, mesh_upper, hip_world)
        obj_lower = create_limb_object(name_lower, mesh_lower, knee_world)
        
        parent_keep_transform(obj_lower, obj_upper)
        
        foot_obj = bpy.data.objects.get(foot_name)
        if foot_obj:
            parent_keep_transform(foot_obj, obj_lower)
            
        if orig_obj.name not in backup_coll.objects:
            backup_coll.objects.link(orig_obj)
        for coll in list(orig_obj.users_collection):
            if coll != backup_coll:
                coll.objects.unlink(orig_obj)
                
        return obj_upper, obj_lower

    # Execute splits
    arm_up_r, arm_low_r = split_arm("braco direito", "braco superior direito", "antebraco direito")
    arm_up_l, arm_low_l = split_arm("braco esquerdo", "braco superior esquerdo", "antebraco esquerdo")
    leg_up_r, leg_low_r = split_leg("perna direita", "coxa direita", "canela direita", "pe direito")
    leg_up_l, leg_low_l = split_leg("perna esquerda", "coxa esquerda", "canela esquerda", "pe esquerdo")

    # Body hierarchy
    torso = bpy.data.objects.get("torso")
    pelve = bpy.data.objects.get("pelve")
    cabeca = bpy.data.objects.get("cabeca")
    pecoco = bpy.data.objects.get("pecoco")

    if torso:
        if arm_up_r:
            parent_keep_transform(arm_up_r, torso)
        if arm_up_l:
            parent_keep_transform(arm_up_l, torso)
    
    if pelve:
        if leg_up_r:
            parent_keep_transform(leg_up_r, pelve)
        if leg_up_l:
            parent_keep_transform(leg_up_l, pelve)
        if torso:
            parent_keep_transform(torso, pelve)
            
    if pecoco and torso:
        parent_keep_transform(pecoco, torso)
    if cabeca and pecoco:
        parent_keep_transform(cabeca, pecoco)

    print("PERFECT WORLD-ALIGNED SPLIT COMPLETED!")

run()
