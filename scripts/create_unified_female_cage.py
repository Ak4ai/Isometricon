import bpy
import bmesh
import mathutils

def run():
    cages_col = bpy.data.collections.get('Cages_Feminino')
    if not cages_col:
        print('Error: Cages_Feminino collection not found!')
        return

    # 1. Clean up any existing unified female cage object if it exists
    old_obj = bpy.data.objects.get('Roblox_Female_Cage_Universal')
    if old_obj:
        old_mesh = old_obj.data
        bpy.data.objects.remove(old_obj, do_unlink=True)
        if old_mesh:
            bpy.data.meshes.remove(old_mesh)

    # 2. Build unified mesh from copies of the 15 cages (originals remain completely untouched)
    bm = bmesh.new()
    part_objs = sorted(cages_col.objects, key=lambda x: x.name)
    print(f'Reading {len(part_objs)} original cages from Cages_Feminino...')

    total_src_verts = 0
    total_src_faces = 0
    for obj in part_objs:
        mw = obj.matrix_world
        bm_part = bmesh.new()
        bm_part.from_mesh(obj.data)

        # Transform part vertices to world space
        bmesh.ops.transform(bm_part, matrix=mw, verts=bm_part.verts)

        # Copy into bm
        vert_map = {}
        for v in bm_part.verts:
            vert_map[v] = bm.verts.new(v.co)
        bm.verts.ensure_lookup_table()

        for f in bm_part.faces:
            try:
                bm.faces.new([vert_map[v] for v in f.verts])
            except ValueError:
                pass

        total_src_verts += len(bm_part.verts)
        total_src_faces += len(bm_part.faces)
        bm_part.free()

    print(f'Combined raw: {len(bm.verts)} verts, {len(bm.faces)} faces')

    # 3. Merge coincident vertices at the touching boundaries (dist <= 2.5mm)
    # Welds arms, knees, waist, and identical boundary vertices
    verts_before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0025)
    print(f'Merged coincident boundary vertices: {verts_before - len(bm.verts)} vertices merged')

    # 4. Helper to find closest vert by position
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    def get_vert(x, y, z, tol=0.025):
        best_v = None
        best_d = tol
        target = mathutils.Vector((x, y, z))
        for v in bm.verts:
            d = (v.co - target).length
            if d < best_d:
                best_d = d
                best_v = v
        return best_v

    # 5. Seal crotch and hip boundary pairs:
    # Right hip pairs (weld leg rim to lower torso socket)
    rh_pairs = [
        ((-0.185, 0.076, 0.848), (-0.190, 0.075, 0.859)),
        ((-0.200, -0.039, 0.848), (-0.197, -0.052, 0.859)),
        ((-0.200, -0.158, 0.848), (-0.200, -0.150, 0.858)),
    ]
    for p1, p2 in rh_pairs:
        v1 = get_vert(*p1)
        v2 = get_vert(*p2)
        if v1 and v2 and v1 != v2:
            bmesh.ops.pointmerge(bm, verts=[v1, v2], merge_co=(v1.co + v2.co) * 0.5)

    # Front midline sliver pair
    v_fm1 = get_vert(0.0, 0.038, 0.785)
    v_fm2 = get_vert(0.0, 0.038, 0.782)
    if v_fm1 and v_fm2 and v_fm1 != v_fm2:
        bmesh.ops.pointmerge(bm, verts=[v_fm1, v_fm2], merge_co=mathutils.Vector((0.0, 0.0382, 0.7838)))

    # Medial bottom crotch pair (inner thigh seam)
    v_bm1 = get_vert(0.0033, -0.0485, 0.777)
    v_bm2 = get_vert(-0.0033, -0.0485, 0.777)
    if v_bm1 and v_bm2 and v_bm1 != v_bm2:
        bmesh.ops.pointmerge(bm, verts=[v_bm1, v_bm2], merge_co=mathutils.Vector((0.0, -0.0485, 0.7772)))

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 6. Add bridging faces to close the crotch opening and lateral hip gaps
    v_front_mid = get_vert(0.0, 0.0382, 0.7838, tol=0.01)
    v_mid = get_vert(0.0, -0.0485, 0.7772, tol=0.01)
    v_back_mid = get_vert(0.0, -0.1195, 0.7837, tol=0.01)

    v_fl = get_vert(0.0621, 0.0851, 0.8097, tol=0.01)
    v_fil = get_vert(0.0279, 0.0747, 0.7990, tol=0.01)
    v_bil = get_vert(0.0199, -0.1035, 0.7882, tol=0.01)
    v_bl = get_vert(0.0591, -0.1839, 0.8002, tol=0.01)

    v_fr = get_vert(-0.0621, 0.0851, 0.8097, tol=0.01)
    v_fir = get_vert(-0.0279, 0.0747, 0.7990, tol=0.01)
    v_bir = get_vert(-0.0199, -0.1035, 0.7882, tol=0.01)
    v_br = get_vert(-0.0591, -0.1839, 0.8002, tol=0.01)

    v_hip_back_l1 = get_vert(0.200, -0.150, 0.858, tol=0.01)
    v_hip_back_l2 = get_vert(0.128, -0.167, 0.828, tol=0.01)
    v_hip_back_l3 = get_vert(0.181, -0.158, 0.848, tol=0.01)

    v_hip_back_r1 = get_vert(-0.200, -0.154, 0.853, tol=0.02)
    v_hip_back_r2 = get_vert(-0.128, -0.167, 0.828, tol=0.01)
    v_hip_back_r3 = get_vert(-0.181, -0.158, 0.848, tol=0.01)

    def add_face_safe(verts):
        if not all(v is not None for v in verts):
            return None
        try:
            return bm.faces.new(verts)
        except ValueError:
            try:
                return bm.faces.new(verts[::-1])
            except ValueError:
                pass
        return None

    # Front crotch faces
    add_face_safe([v_front_mid, v_fl, v_fil])
    add_face_safe([v_front_mid, v_fil, v_mid])
    add_face_safe([v_front_mid, v_fir, v_fr])
    add_face_safe([v_front_mid, v_mid, v_fir])

    # Back crotch faces
    add_face_safe([v_mid, v_bil, v_back_mid])
    add_face_safe([v_bil, v_bl, v_back_mid])
    add_face_safe([v_mid, v_back_mid, v_bir])
    add_face_safe([v_bir, v_back_mid, v_br])

    # Lateral hip faces
    if v_hip_back_l1 and v_hip_back_l2 and v_bl and v_hip_back_l3:
        add_face_safe([v_hip_back_l1, v_hip_back_l2, v_bl, v_hip_back_l3])

    if v_hip_back_r1 and v_hip_back_r2 and v_br and v_hip_back_r3:
        add_face_safe([v_hip_back_r1, v_hip_back_r3, v_br, v_hip_back_r2])

    # 7. Clean any 0-face wire edges or isolated vertices
    bm.edges.ensure_lookup_table()
    wire_edges = [e for e in bm.edges if len(e.link_faces) == 0]
    if wire_edges:
        bmesh.ops.delete(bm, geom=wire_edges, context='EDGES')

    bm.verts.ensure_lookup_table()
    iso_verts = [v for v in bm.verts if len(v.link_faces) == 0 and len(v.link_edges) == 0]
    if iso_verts:
        bmesh.ops.delete(bm, geom=iso_verts, context='VERTS')

    # Recalculate face normals outward
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    print(f'Final sealed unified cage: {len(bm.verts)} verts, {len(bm.faces)} faces')

    # 8. Create new Mesh & Object
    new_mesh = bpy.data.meshes.new('Roblox_Female_Cage_Universal_mesh')
    bm.to_mesh(new_mesh)
    bm.free()
    new_mesh.update()

    new_obj = bpy.data.objects.new('Roblox_Female_Cage_Universal', new_mesh)

    # Put in dedicated collection 'Cages_Feminino_Unificada'
    out_col = bpy.data.collections.get('Cages_Feminino_Unificada')
    if not out_col:
        out_col = bpy.data.collections.new('Cages_Feminino_Unificada')
        bpy.context.scene.collection.children.link(out_col)
    out_col.objects.link(new_obj)

    # Keep Armature_Character.001 as parent
    arm = bpy.data.objects.get('Armature_Character.001')
    if arm:
        new_obj.parent = arm
        new_obj.matrix_parent_inverse = arm.matrix_world.inverted()

    # Show edges and wire
    new_obj.show_wire = True
    new_obj.show_all_edges = True

    bpy.context.view_layer.update()

    # Save the blend file
    bpy.ops.wm.save_mainfile()
    print('SUCCESS: Created Roblox_Female_Cage_Universal with sealed crotch and saved 123.blend!')

if __name__ == '__main__':
    run()
else:
    run()
