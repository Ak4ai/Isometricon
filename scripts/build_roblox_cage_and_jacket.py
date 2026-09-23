import bpy
import os
import math
from mathutils import Vector

cage_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\cages"
jacket_path = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\92028318196252.obj"
jacket_tex_path = r"C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\jacket_1_texture.png"

# Remove any old cage or jacket
for o_name in ['Roblox_Inner_Cage', 'Jacket_1']:
    o = bpy.data.objects.get(o_name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

# Build cage parts
parts_to_cage = [
    'LowerTorso', 'UpperTorso', 'Head',
    'LeftUpperArm', 'LeftLowerArm', 'LeftHand',
    'RightUpperArm', 'RightLowerArm', 'RightHand',
    'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot',
    'RightUpperLeg', 'RightLowerLeg', 'RightFoot'
]

arm_obj = bpy.data.objects.get('Armature_Roblox_R15')

cage_objects = []

for name in parts_to_cage:
    cage_file = os.path.join(cage_dir, f"{name}.obj")
    body_obj = bpy.data.objects.get(name)
    if not os.path.exists(cage_file) or not body_obj:
        continue
    
    # Read cage OBJ
    c_verts = []
    c_faces = []
    with open(cage_file, 'r') as f:
        for line in f:
            if line.startswith('v '):
                c_verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('f '):
                f_idx = [int(token.split('/')[0]) - 1 for token in line.split()[1:]]
                c_faces.append(f_idx)
    
    # In cage OBJ: X is Left/Right, Y is Up/Down, Z is Front/Back (-Z Front)
    # In Blender: X is Left/Right, Y is Front/Back (-Y Front), Z is Up/Down
    # Body bounds in Blender:
    b_verts = [v.co for v in body_obj.data.vertices]
    b_min_x, b_max_x = min(v.x for v in b_verts), max(v.x for v in b_verts)
    b_min_y, b_max_y = min(v.y for v in b_verts), max(v.y for v in b_verts)
    b_min_z, b_max_z = min(v.z for v in b_verts), max(v.z for v in b_verts)
    
    b_size_x = max(b_max_x - b_min_x, 0.05)
    b_size_y = max(b_max_y - b_min_y, 0.05)
    b_size_z = max(b_max_z - b_min_z, 0.05)
    b_center = Vector(((b_min_x + b_max_x)/2.0, (b_min_y + b_max_y)/2.0, (b_min_z + b_max_z)/2.0))
    
    # Cage native bounds:
    c_min_x, c_max_x = min(v[0] for v in c_verts), max(v[0] for v in c_verts)
    c_min_y, c_max_y = min(v[1] for v in c_verts), max(v[1] for v in c_verts)
    c_min_z, c_max_z = min(v[2] for v in c_verts), max(v[2] for v in c_verts)
    c_size_x = max(c_max_x - c_min_x, 0.01)
    c_size_y = max(c_max_y - c_min_y, 0.01) # height
    c_size_z = max(c_max_z - c_min_z, 0.01) # depth
    c_center = Vector(((c_min_x + c_max_x)/2.0, (c_min_y + c_max_y)/2.0, (c_min_z + c_max_z)/2.0))
    
    # Margin: 3% larger than body to ensure full wrap
    scale_x = (b_size_x / c_size_x) * 1.03
    scale_z = (b_size_z / c_size_y) * 1.03 # cage Y -> Blender Z
    scale_y = (b_size_y / c_size_z) * 1.03 # cage Z -> Blender Y
    
    transformed_verts = []
    for cv in c_verts:
        # relative to cage center
        rx = cv[0] - c_center.x
        ry = cv[1] - c_center.y
        rz = cv[2] - c_center.z
        
        # Transform to Blender coordinates:
        # rx -> Blender X
        # rz -> Blender Y (both have -Z / -Y as front)
        # ry -> Blender Z
        bx = b_center.x + rx * scale_x
        by = b_center.y + rz * scale_y
        bz = b_center.z + ry * scale_z
        transformed_verts.append((bx, by, bz))
    
    mesh = bpy.data.meshes.new(f"Cage_{name}")
    mesh.from_pydata(transformed_verts, [], c_faces)
    mesh.update()
    
    c_obj = bpy.data.objects.new(f"Cage_{name}", mesh)
    bpy.context.scene.collection.objects.link(c_obj)
    
    # Vertex group for this bone
    vg = c_obj.vertex_groups.new(name=name)
    vg.add(list(range(len(transformed_verts))), 1.0, 'REPLACE')
    
    cage_objects.append(c_obj)

# Join all cage objects into one single mesh
bpy.ops.object.select_all(action='DESELECT')
for o in cage_objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = cage_objects[0]
bpy.ops.object.join()

full_cage = bpy.context.active_object
full_cage.name = 'Roblox_Inner_Cage'
full_cage.parent = arm_obj
mod = full_cage.modifiers.new(name='Armature', type='ARMATURE')
mod.object = arm_obj

# Hide cage from renders (it's a deform target)
full_cage.hide_render = True
full_cage.display_type = 'WIRE'

print(f"Full cage created with {len(full_cage.data.vertices)} vertices and {len(full_cage.vertex_groups)} vertex groups.")

# Now import and setup Jacket_1
j_verts = []
j_uvs = []
j_faces = []
j_face_uvs = []

with open(jacket_path, 'r') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if parts[0] == 'v':
            j_verts.append([float(x) for x in parts[1:4]])
        elif parts[0] == 'vt':
            j_uvs.append([float(x) for x in parts[1:3]])
        elif parts[0] == 'f':
            fv = []
            fuv = []
            for token in parts[1:]:
                sub = token.split('/')
                fv.append(int(sub[0]) - 1)
                fuv.append(int(sub[1]) - 1 if len(sub) > 1 and sub[1] else None)
            j_faces.append(fv)
            j_face_uvs.append(fuv)

# Transform Jacket to match character:
# In jacket OBJ: X=[-1.50, 1.50], Y=[-0.90, 0.90], Z=[-0.44, 0.44]
# In Blender: UpperTorso + UpperArms span X=[-0.86, 0.84] (span 1.70)
# Chest center Z is around 2.80
ut_obj = bpy.data.objects.get('UpperTorso')
ut_center_z = (min(v.co.z for v in ut_obj.data.vertices) + max(v.co.z for v in ut_obj.data.vertices)) / 2.0

j_transformed_verts = []
for jv in j_verts:
    # jv[0] is X, jv[1] is Y (height), jv[2] is Z (depth)
    bx = jv[0]
    by = jv[2] # depth
    bz = ut_center_z + jv[1] # height
    j_transformed_verts.append((bx, by, bz))

j_mesh = bpy.data.meshes.new("Mesh_Jacket_1")
j_mesh.from_pydata(j_transformed_verts, [], j_faces)
j_mesh.update()

# Add UVs
j_uv_layer = j_mesh.uv_layers.new(name="UVMap")
j_mesh.calc_loop_triangles()
for fi, poly in enumerate(j_mesh.polygons):
    poly_uvs = j_face_uvs[fi]
    for i, loop in enumerate(j_mesh.loops[poly.loop_start:poly.loop_start + poly.loop_total]):
        uvi = poly_uvs[i]
        if uvi is not None and uvi < len(j_uvs):
            j_uv_layer.data[loop.index].uv = j_uvs[uvi]

j_obj = bpy.data.objects.new("Jacket_1", j_mesh)
bpy.context.scene.collection.objects.link(j_obj)

# Create material for Jacket
mat_j = bpy.data.materials.new(name="Mat_Jacket_1")
mat_j.use_nodes = True
nodes = mat_j.node_tree.nodes
links = mat_j.node_tree.links
nodes.clear()
out = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
if os.path.exists(jacket_tex_path):
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(jacket_tex_path)
    links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
j_obj.data.materials.append(mat_j)

# Bind Jacket to Cage via SurfaceDeform
sdef = j_obj.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')
sdef.target = full_cage

bpy.context.view_layer.objects.active = j_obj
bpy.ops.object.surfacedeform_bind(modifier=sdef.name)
print(f"SurfaceDeform bind status: {sdef.is_bound}")

# Render dressed preview
bpy.context.scene.render.filepath = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders\roblox_r15_jacket_preview.png'
bpy.ops.render.render(write_still=True)
print("Dressed preview rendered!")
