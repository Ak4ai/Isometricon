from blender_client import execute_blender_code

code = '''
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def v_to_list(v, decimals=4):
    return [round(x, decimals) for x in v]

def audit_arm(side):
    pt = 'esquerdo' if side == 'Left' else 'direito'
    pt_f = 'esquerda' if side == 'Left' else 'direita'
    u_mesh_obj = bpy.data.objects[f'Export_braco_superior_{pt}.001']
    l_mesh_obj = bpy.data.objects[f'Export_antebraco_{pt}.001']
    h_mesh_obj = bpy.data.objects[f'Export_mao_{pt_f}.001']
    
    u_cage_obj = bpy.data.objects[f'{side}UpperArm_OuterCage']
    l_cage_obj = bpy.data.objects[f'{side}LowerArm_OuterCage']
    h_cage_obj = bpy.data.objects[f'{side}Hand_OuterCage']
    
    u_verts = [u_mesh_obj.matrix_world @ v.co for v in u_mesh_obj.data.vertices]
    l_verts = [l_mesh_obj.matrix_world @ v.co for v in l_mesh_obj.data.vertices]
    h_verts = [h_mesh_obj.matrix_world @ v.co for v in h_mesh_obj.data.vertices]
    
    # 1. Elbow cut vertices
    u_elbow = [v for v in u_verts if v.z < 1.20]
    l_elbow = [v for v in l_verts if v.z > 1.10]
    c_u_elbow = sum(u_elbow, Vector((0,0,0))) / len(u_elbow) if u_elbow else Vector((0,0,0))
    c_l_elbow = sum(l_elbow, Vector((0,0,0))) / len(l_elbow) if l_elbow else Vector((0,0,0))
    elbow_gap = (c_u_elbow - c_l_elbow).length
    
    # Individual vertex distances at elbow
    # For each upper elbow vert, find distance to nearest lower elbow vert
    elbow_vertex_dists = []
    for uv in u_elbow:
        d_min = min((uv - lv).length for lv in l_elbow)
        elbow_vertex_dists.append(d_min)
    max_elbow_gap = max(elbow_vertex_dists) if elbow_vertex_dists else 0.0
    min_elbow_gap = min(elbow_vertex_dists) if elbow_vertex_dists else 0.0
    
    # 2. Wrist cut vertices
    l_wrist = [v for v in l_verts if v.z < 0.90]
    h_wrist = [v for v in h_verts if v.z > 0.85]
    c_l_wrist = sum(l_wrist, Vector((0,0,0))) / len(l_wrist) if l_wrist else Vector((0,0,0))
    c_h_wrist = sum(h_wrist, Vector((0,0,0))) / len(h_wrist) if h_wrist else Vector((0,0,0))
    wrist_gap = (c_l_wrist - c_h_wrist).length
    
    wrist_vertex_dists = []
    for lv in l_wrist:
        d_min = min((lv - hv).length for hv in h_wrist)
        wrist_vertex_dists.append(d_min)
    max_wrist_gap = max(wrist_vertex_dists) if wrist_vertex_dists else 0.0
    
    print(f'=== {side} ARM AUDIT ===')
    print(f'Elbow Joint: Upper center={v_to_list(c_u_elbow)}, Lower center={v_to_list(c_l_elbow)}')
    print(f'  Center distance: {elbow_gap:.4f} | Vertex max gap: {max_elbow_gap:.4f} | Vertex min gap: {min_elbow_gap:.4f}')
    print(f'Wrist Joint: Forearm center={v_to_list(c_l_wrist)}, Hand center={v_to_list(c_h_wrist)}')
    print(f'  Center distance: {wrist_gap:.4f} | Vertex max gap: {max_wrist_gap:.4f}')
    
    # 3. Cage Containment Analysis
    def check_containment(mesh_obj, cage_obj, name):
        bm_cage = bmesh.new()
        bm_cage.from_mesh(cage_obj.data)
        bm_cage.transform(cage_obj.matrix_world)
        bvh = BVHTree.FromBMesh(bm_cage)
        
        outside_count = 0
        min_clearance = float('inf')
        max_clearance = 0.0
        
        for v in mesh_obj.data.vertices:
            w_co = mesh_obj.matrix_world @ v.co
            loc, norm, idx, dist = bvh.find_nearest(w_co)
            if loc:
                min_clearance = min(min_clearance, dist)
                max_clearance = max(max_clearance, dist)
                vec_to_v = w_co - loc
                if vec_to_v.dot(norm) > 0.001:
                    outside_count += 1
        bm_cage.free()
        print(f'{name:20s}: outside_verts={outside_count}/{len(mesh_obj.data.vertices)} min_clearance={min_clearance:.4f} max_clearance={max_clearance:.4f}')

    check_containment(u_mesh_obj, u_cage_obj, 'Upper Arm Cage')
    check_containment(l_mesh_obj, l_cage_obj, 'Lower Arm Cage')
    check_containment(h_mesh_obj, h_cage_obj, 'Hand Cage')

audit_arm('Left')
audit_arm('Right')
'''

res = execute_blender_code(code)
if res.get('status') == 'success':
    print(res['result']['result'])
else:
    print('Error:', res)
