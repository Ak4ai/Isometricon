"""
Setup a clean, mathematical Lattice deformer on Roblox_Inner_Cage and Jacket_1:
Calibrated with precise arm forward angle and wider chest margin.
"""
import bpy
import os
import math
import json
from mathutils import Vector, Quaternion

arm_obj = bpy.data.objects.get('Armature_Character')
jacket = bpy.data.objects.get('Jacket_1')
torso = bpy.data.objects.get('torso')
cage = bpy.data.objects.get('Roblox_Inner_Cage')

# 1. Put Armature in Roblox A-Pose
apose_quats = {
    'UpperArm_L': Quaternion((0.9723699, -0.0585698, 0.0, -0.2259149)),
    'UpperArm_R': Quaternion((0.9723699, -0.0585698, 0.0, 0.2259149)),
}
for pb in arm_obj.pose.bones:
    if pb.name in apose_quats:
        pb.rotation_quaternion = apose_quats[pb.name]
    else:
        pb.rotation_quaternion = Quaternion((1, 0, 0, 0))
bpy.context.view_layer.update()

# 2. Reset Cage and Jacket
for m in list(cage.modifiers):
    cage.modifiers.remove(m)
if cage.data.shape_keys:
    cage.shape_key_clear()

for m in list(jacket.modifiers):
    if m.type == 'SURFACE_DEFORM' and m.is_bound:
        bpy.ops.object.select_all(action='DESELECT')
        jacket.select_set(True)
        bpy.context.view_layer.objects.active = jacket
        bpy.ops.object.surfacedeform_bind(modifier=m.name)
    jacket.modifiers.remove(m)

# Remove old Lattice if exists
old_lat = bpy.data.objects.get('Cage_Lattice')
if old_lat:
    me = old_lat.data
    bpy.data.objects.remove(old_lat, do_unlink=True)
    bpy.data.lattices.remove(me, do_unlink=True)

# Restore raw inner cage
cage_obj_path = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\inner_cage.obj'
raw_verts = []
with open(cage_obj_path, 'r') as f:
    for line in f:
        if line.startswith('v '):
            p = line.strip().split()
            raw_verts.append(Vector((float(p[1]), float(p[2]), float(p[3]))))

for i, v in enumerate(cage.data.vertices):
    v.co = raw_verts[i]

cage.location = (0.0, 0.0, 0.91)
cage.rotation_euler = (math.radians(90), 0.0, math.radians(180))
cage.scale = (0.3309, 0.3309, 0.3309)
bpy.context.view_layer.update()

# 3. Position Jacket in standard Roblox alignment
jacket.parent = None
jacket.location = (0.0, 0.015, 1.16)
jacket.rotation_euler = (math.radians(90), 0.0, math.radians(180))
jacket.scale = (0.52, 0.56, 0.44)

for slot in jacket.material_slots:
    if slot.material:
        mat = slot.material
        if hasattr(mat, 'blend_method'):
            mat.blend_method = 'OPAQUE'
        mat.use_backface_culling = False
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED' and 'Alpha' in node.inputs:
                    node.inputs['Alpha'].default_value = 1.0

# Recalculate jacket normals outside
bpy.ops.object.select_all(action='DESELECT')
jacket.select_set(True)
bpy.context.view_layer.objects.active = jacket
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')

bpy.context.view_layer.update()

# 4. Bind Jacket to raw Cage BEFORE Lattice deformation
sd_mod = jacket.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')
sd_mod.target = cage

bpy.ops.object.select_all(action='DESELECT')
jacket.select_set(True)
bpy.context.view_layer.objects.active = jacket
bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)

# 5. Create Cage_Lattice
lat_data = bpy.data.lattices.new('Cage_Lattice')
lat_obj = bpy.data.objects.new('Cage_Lattice', lat_data)
bpy.context.collection.objects.link(lat_obj)

lat_obj.location = (0.0, 0.0, 1.18)
lat_obj.scale = (1.60, 0.55, 0.95)

res_u = 6
res_v = 4
res_w = 6
lat_data.points_u = res_u
lat_data.points_v = res_v
lat_data.points_w = res_w
lat_data.interpolation_type_u = 'KEY_BSPLINE'
lat_data.interpolation_type_v = 'KEY_BSPLINE'
lat_data.interpolation_type_w = 'KEY_BSPLINE'

# Deform lattice points:
for w in range(res_w):
    lz = -0.5 + w / (res_w - 1)
    
    for v in range(res_v):
        ly = -0.5 + v / (res_v - 1)
        
        for u in range(res_u):
            lx = -0.5 + u / (res_u - 1)
            pt = lat_data.points[u + v * res_u + w * res_u * res_v]
            
            nx, ny, nz = lx, ly, lz
            
            # Torso: central columns u=2, u=3
            if (u == 2 or u == 3) and (1 <= w <= 4):
                if ly > 0.05:
                    ny = ly * 1.50
                elif ly < -0.05:
                    ny = ly * 1.50
                nx = lx * 1.40
            
            # Shoulder columns u=1 and u=4
            elif (u == 1 or u == 4) and (2 <= w <= 5):
                if abs(ly) > 0.1:
                    ny = ly * 1.40
                nx = lx * 1.30
            
            # Arm columns u=0 and u=5
            elif (u == 0 or u == 5) and (1 <= w <= 4):
                # Arm reaches forward in Y (-Y direction):
                # Lower forearm points (w=1,2) shift forward (-Y)
                arm_fwd_shift = -0.08 * (1.0 - (w / 4.0))
                ny = (ly * 1.60) + arm_fwd_shift
                nx = lx * 1.25
            
            pt.co_deform = Vector((nx, ny, nz))

bpy.context.view_layer.update()

# 6. Add Lattice modifier to Roblox_Inner_Cage
lat_mod = cage.modifiers.new(name='Lattice_Fit', type='LATTICE')
lat_mod.object = lat_obj

bpy.context.view_layer.update()

# 7. Render shots
output_dir = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders'
os.makedirs(output_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 800
scene.render.resolution_y = 1200
scene.render.film_transparent = False

cam = scene.camera
cam.data.lens = 70

shots = [
    ('lattice_front.png', (0.0, -3.5, 0.95), (math.radians(90), 0.0, 0.0)),
    ('lattice_34.png', (2.2, -2.4, 1.15), (math.radians(78), 0.0, math.radians(45))),
    ('lattice_side.png', (3.2, 0.0, 0.95), (math.radians(90), 0.0, math.radians(90))),
]

cage.hide_render = True
jacket.hide_render = False
lat_obj.hide_render = True

for filename, loc, rot in shots:
    cam.location = loc
    cam.rotation_euler = rot
    scene.render.filepath = os.path.join(output_dir, filename)
    bpy.ops.render.render(write_still=True)

# Copy to D:\blender\assets\renders
for filename, loc, rot in shots:
    src = os.path.join(output_dir, filename)
    dst = os.path.join(r'D:\blender\assets\renders', filename)
    try:
        import shutil
        shutil.copy2(src, dst)
    except Exception:
        pass

bpy.ops.wm.save_mainfile()

report = {
    'jacket_bound': sd_mod.is_bound,
    'lattice_name': lat_obj.name,
    'status': 'SUCCESS'
}
print("CALIBRATED_LATTICE_DONE:" + json.dumps(report, indent=2))
