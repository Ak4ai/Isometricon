import bpy
import os
import math

# Clean scene first
keep_names = {'Camera', 'KeyLight', 'FillLight', 'RimLight', 'FrontLight'}
for o in [obj for obj in bpy.data.objects if obj.name not in keep_names]:
    bpy.data.objects.remove(o, do_unlink=True)

obj_path = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\teste.obj"
tex_body_path = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\Rigautosetup1_diff.png"
tex_head_path = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\Rigautosetup6_diff.png"

mapping = {
    'UpperTorso': 'Rigautosetup14',
    'LowerTorso': 'Rigautosetup11',
    'Head': 'Rigautosetup6',
    'LeftUpperArm': 'Rigautosetup8',
    'LeftLowerArm': 'Rigautosetup1',
    'LeftHand': 'Rigautosetup7',
    'RightUpperArm': 'Rigautosetup3',
    'RightLowerArm': 'Rigautosetup15',
    'RightHand': 'Rigautosetup2',
    'LeftUpperLeg': 'Rigautosetup5',
    'LeftLowerLeg': 'Rigautosetup9',
    'LeftFoot': 'Rigautosetup4',
    'RightUpperLeg': 'Rigautosetup12',
    'RightLowerLeg': 'Rigautosetup13',
    'RightFoot': 'Rigautosetup10'
}
rev_mapping = {v: k for k, v in mapping.items()}

all_verts = []
all_uvs = []
all_normals = []

group_faces = {k: [] for k in mapping.keys()}
current_group = None

with open(obj_path, 'r') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        tag = parts[0]
        if tag == 'v':
            all_verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif tag == 'vt':
            all_uvs.append([float(parts[1]), float(parts[2])])
        elif tag == 'vn':
            all_normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif tag == 'g':
            gname = parts[1]
            current_group = rev_mapping.get(gname)
        elif tag == 'f' and current_group:
            face_v = []
            face_uv = []
            for token in parts[1:]:
                sub = token.split('/')
                vi = int(sub[0]) - 1
                uvi = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else None
                face_v.append(vi)
                face_uv.append(uvi)
            group_faces[current_group].append((face_v, face_uv))

center_x = -115.295
floor_y = 1.29257
center_z = 116.011

# Pure rigid rotation:
# Roblox +X (Right) -> Blender -X (Right)
# Roblox +Y (Up)    -> Blender +Z (Up)
# Roblox -Z (Front) -> Blender -Y (Front)
# Det = +1. No reflection!
def transform_vert(v):
    ox, oy, oz = v
    bx = -(ox - center_x)
    by = oz - center_z
    bz = oy - floor_y
    return (bx, by, bz)

def setup_material(mat_name, img_path):
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.8
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    
    if os.path.exists(img_path):
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(img_path)
        tex.interpolation = 'Closest'
        links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    return mat

mat_body = setup_material('Mat_Roblox_Body', tex_body_path)
mat_head = setup_material('Mat_Roblox_Head', tex_head_path)

created_objects = {}

for r15_name, faces_data in group_faces.items():
    if not faces_data:
        continue
    
    used_v_map = {}
    local_verts = []
    
    for face_v, _ in faces_data:
        for gvi in face_v:
            if gvi not in used_v_map:
                used_v_map[gvi] = len(local_verts)
                local_verts.append(transform_vert(all_verts[gvi]))
    
    local_faces = []
    local_face_uvs = []
    for face_v, face_uv in faces_data:
        # Det = +1, so keep original winding order!
        local_faces.append([used_v_map[vi] for vi in face_v])
        local_face_uvs.append(face_uv)
    
    mesh = bpy.data.meshes.new(f"Mesh_{r15_name}")
    mesh.from_pydata(local_verts, [], local_faces)
    mesh.update()
    
    uv_layer = mesh.uv_layers.new(name="UVMap")
    mesh.calc_loop_triangles()
    for fi, poly in enumerate(mesh.polygons):
        poly_uvs = local_face_uvs[fi]
        for i, loop in enumerate(mesh.loops[poly.loop_start:poly.loop_start + poly.loop_total]):
            uvi = poly_uvs[i]
            if uvi is not None and uvi < len(all_uvs):
                uv_layer.data[loop.index].uv = all_uvs[uvi]
    
    obj = bpy.data.objects.new(r15_name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    
    if r15_name == 'Head':
        obj.data.materials.append(mat_head)
    else:
        obj.data.materials.append(mat_body)
    
    created_objects[r15_name] = obj

# Setup standard Front camera (at -Y looking towards +Y)
cam = bpy.data.objects.get('Camera')
if cam:
    cam.location = (0, -6.5, 2.1)
    cam.rotation_euler = (math.radians(90), 0, 0)

# Setup lights
fl = bpy.data.objects.get('FrontLight')
if fl:
    fl.location = (0, -3.5, 2.5)
    fl.data.energy = 800.0

# Render front view
bpy.context.scene.render.filepath = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders\roblox_r15_standard_front.png'
bpy.ops.render.render(write_still=True)
print("Rendered standard front view!")
