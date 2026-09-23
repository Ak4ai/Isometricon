"""
Standard Industry / Roblox Pipeline:
1. Reset cage to clean inner_cage.obj (Roblox native mesh).
2. Armature in matching Roblox A-pose.
3. Create clean vertex groups for Torso, Arm_L, Arm_R, Pelvis.
4. Apply isolated Shrinkwrap modifiers per limb with uniform 2.2 cm offset.
5. Apply Smooth / Corrective Smooth modifier to seamlessly relax joints and transitions.
6. Bind Jacket via SurfaceDeform.
7. Render Front, 3/4 and Side views.
"""
import bpy
import os
import math
import json
import bmesh
from mathutils import Vector, Quaternion

report = {}

arm_obj = bpy.data.objects.get('Armature_Character')
cage = bpy.data.objects.get('Roblox_Inner_Cage')
jacket = bpy.data.objects.get('Jacket_1')
torso = bpy.data.objects.get('torso')
pelvis = bpy.data.objects.get('pelve')

assert arm_obj and cage and jacket and torso and pelvis, "Missing required objects!"

# ----------------------------------------------------
# 1. Put Armature in matching Roblox A-Pose
# ----------------------------------------------------
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
report['step1'] = 'Armature set to A-pose'

# ----------------------------------------------------
# 2. Reset Cage and Jacket
# ----------------------------------------------------
# Clear any shape keys and modifiers
for m in list(cage.modifiers):
    cage.modifiers.remove(m)
if cage.data.shape_keys:
    cage.shape_key_clear()
cage.vertex_groups.clear()

for m in list(jacket.modifiers):
    if m.type == 'SURFACE_DEFORM':
        if m.is_bound:
            bpy.ops.object.select_all(action='DESELECT')
            jacket.select_set(True)
            bpy.context.view_layer.objects.active = jacket
            bpy.ops.object.surfacedeform_bind(modifier=m.name)
        jacket.modifiers.remove(m)

# Restore raw Roblox inner cage from OBJ
cage_obj_path = r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\models\clothing\inner_cage.obj'
raw_verts = []
with open(cage_obj_path, 'r') as f:
    for line in f:
        if line.startswith('v '):
            p = line.strip().split()
            raw_verts.append(Vector((float(p[1]), float(p[2]), float(p[3]))))

assert len(raw_verts) == len(cage.data.vertices)
for i, v in enumerate(cage.data.vertices):
    v.co = raw_verts[i]

cage.location = (0.0, 0.0, 0.91)
cage.rotation_euler = (math.radians(90), 0.0, math.radians(180))
cage.scale = (0.3309, 0.3309, 0.3309)
bpy.context.view_layer.update()

# ----------------------------------------------------
# 3. Create Clean Combined Target Meshes for the Arms
# ----------------------------------------------------
# We combine upper arm and forearm into a single target for each arm
# to let the sleeve wrap smoothly around the entire arm without gap at elbow.

def create_combined_arm_target(name, part_names):
    # Remove existing if any
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for pname in part_names:
        obj = bpy.data.objects.get(pname)
        if obj:
            obj_eval = obj.evaluated_get(depsgraph)
            me = obj_eval.to_mesh()
            bm_part = bmesh.new()
            bm_part.from_mesh(me)
            bm_part.transform(obj_eval.matrix_world)
            
            # Append to bm
            vert_map = {}
            for v in bm_part.verts:
                vert_map[v.index] = bm.verts.new(v.co)
            bm.verts.ensure_lookup_table()
            for f in bm_part.faces:
                try:
                    bm.faces.new([vert_map[v.index] for v in f.verts])
                except ValueError:
                    pass
            bm_part.free()
            obj_eval.to_mesh_clear()
    
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    
    new_obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(new_obj)
    new_obj.hide_viewport = True
    new_obj.hide_render = True
    return new_obj

target_arm_l = create_combined_arm_target('Target_Arm_L', ['braco superior esquerdo', 'antebraco esquerdo'])
target_arm_r = create_combined_arm_target('Target_Arm_R', ['braco superior direito', 'antebraco direito'])
report['step3'] = 'Arm targets created'

# ----------------------------------------------------
# 4. Create Precise Anatomical Vertex Groups on Cage
# ----------------------------------------------------
cage_mat = cage.matrix_world
wv = [cage_mat @ v.co for v in cage.data.vertices]

vg_torso = cage.vertex_groups.new(name='SW_Torso')
vg_pelvis = cage.vertex_groups.new(name='SW_Pelvis')
vg_arm_l = cage.vertex_groups.new(name='SW_Arm_L')
vg_arm_r = cage.vertex_groups.new(name='SW_Arm_R')

# Define regions using world coordinates of the raw Roblox cage
for i, v in enumerate(wv):
    x, y, z = v.x, v.y, v.z
    
    # Arms: outside torso boundary
    # In world coords: +X is character's Left, -X is character's Right
    if z > 0.65 and z < 1.60:
        if x > 0.16:
            # Smooth weight falloff near shoulder seam (0.16 to 0.22)
            w = min(1.0, (x - 0.16) / 0.06)
            vg_arm_l.add([i], w, 'REPLACE')
        elif x < -0.16:
            w = min(1.0, (abs(x) - 0.16) / 0.06)
            vg_arm_r.add([i], w, 'REPLACE')
    
    # Torso: central body between pelvis and neck
    if z >= 0.88 and z <= 1.55:
        # Full weight in middle, falloff towards shoulders (|x| > 0.14)
        if abs(x) <= 0.15:
            vg_torso.add([i], 1.0, 'REPLACE')
        elif abs(x) < 0.22:
            w = 1.0 - (abs(x) - 0.15) / 0.07
            vg_torso.add([i], max(0.0, w), 'REPLACE')
            
    # Pelvis: below torso
    if z >= 0.75 and z < 0.92 and abs(x) <= 0.16:
        w = 1.0 if z < 0.88 else (0.92 - z) / 0.04
        vg_pelvis.add([i], max(0.0, w), 'REPLACE')

report['step4'] = 'Vertex groups created'

# ----------------------------------------------------
# 5. Apply Native Shrinkwrap Modifiers with Safe Offset
# ----------------------------------------------------
OFFSET = 0.022  # 2.2 cm offset ensures cubes never pierce cage

# 1. Torso Shrinkwrap
sw_t = cage.modifiers.new(name='SW_Torso', type='SHRINKWRAP')
sw_t.target = torso
sw_t.vertex_group = 'SW_Torso'
sw_t.wrap_method = 'NEAREST_SURFACEPOINT'
sw_t.offset = OFFSET

# 2. Pelvis Shrinkwrap
sw_p = cage.modifiers.new(name='SW_Pelvis', type='SHRINKWRAP')
sw_p.target = pelvis
sw_p.vertex_group = 'SW_Pelvis'
sw_p.wrap_method = 'NEAREST_SURFACEPOINT'
sw_p.offset = 0.018

# 3. Left Arm Shrinkwrap
sw_al = cage.modifiers.new(name='SW_Arm_L', type='SHRINKWRAP')
sw_al.target = target_arm_l
sw_al.vertex_group = 'SW_Arm_L'
sw_al.wrap_method = 'NEAREST_SURFACEPOINT'
sw_al.offset = OFFSET

# 4. Right Arm Shrinkwrap
sw_ar = cage.modifiers.new(name='SW_Arm_R', type='SHRINKWRAP')
sw_ar.target = target_arm_r
sw_ar.vertex_group = 'SW_Arm_R'
sw_ar.wrap_method = 'NEAREST_SURFACEPOINT'
sw_ar.offset = OFFSET

# 5. Smooth Modifier to eliminate sharp seams and kinks
sm = cage.modifiers.new(name='Smooth_Relax', type='SMOOTH')
sm.factor = 0.6
sm.iterations = 4

bpy.context.view_layer.update()
report['step5'] = 'Shrinkwraps and Smooth modifier configured'

# ----------------------------------------------------
# 6. Setup Jacket and Bind via SurfaceDeform
# ----------------------------------------------------
# Position jacket in Roblox A-pose alignment
jacket.parent = None
jacket.location = (0.0, 0.015, 1.16)
jacket.rotation_euler = (math.radians(90), 0.0, math.radians(180))
jacket.scale = (0.52, 0.56, 0.44)

# Ensure material is 100% opaque
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

# Bind SurfaceDeform to conformed cage
sd_mod = jacket.modifiers.new(name='SurfaceDeform', type='SURFACE_DEFORM')
sd_mod.target = cage
try:
    bpy.ops.object.surfacedeform_bind(modifier=sd_mod.name)
    report['jacket_bound'] = sd_mod.is_bound
except Exception as e:
    report['jacket_bind_error'] = str(e)

# Hide cage from render
cage.hide_render = True
jacket.hide_render = False

# ----------------------------------------------------
# 7. Render Front, 3/4 and Side Views
# ----------------------------------------------------
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 800
scene.render.resolution_y = 1200
scene.render.film_transparent = False

cam = scene.camera
cam.data.lens = 70

output_dirs = [
    r'D:\blender\assets\renders',
    r'C:\Users\Henrique\Documents\GitHub\Isometricon\assets\renders'
]
for d in output_dirs:
    os.makedirs(d, exist_ok=True)

shots = [
    ('clean_front.png', (0.0, -3.5, 0.95), (math.radians(90), 0.0, 0.0)),
    ('clean_34.png', (2.2, -2.4, 1.15), (math.radians(78), 0.0, math.radians(45))),
    ('clean_side.png', (3.2, 0.0, 0.95), (math.radians(90), 0.0, math.radians(90))),
]

for filename, loc, rot in shots:
    cam.location = loc
    cam.rotation_euler = rot
    for d in output_dirs:
        scene.render.filepath = os.path.join(d, filename)
        bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_mainfile()
report['status'] = 'SUCCESS'
print("STANDARD_CAGE_DONE:" + json.dumps(report, indent=2))
