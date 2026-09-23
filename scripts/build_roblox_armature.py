import bpy
from mathutils import Vector

def create_r15_armature():
    parts = [
        'LowerTorso', 'UpperTorso', 'Head',
        'LeftUpperArm', 'LeftLowerArm', 'LeftHand',
        'RightUpperArm', 'RightLowerArm', 'RightHand',
        'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot',
        'RightUpperLeg', 'RightLowerLeg', 'RightFoot'
    ]
    
    bounds = {}
    for name in parts:
        obj = bpy.data.objects.get(name)
        if not obj:
            print(f"Missing {name}")
            return
        verts = [v.co for v in obj.data.vertices]
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]
        bounds[name] = {
            'min': Vector((min(xs), min(ys), min(zs))),
            'max': Vector((max(xs), max(ys), max(zs))),
            'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
        }

    # Delete existing Armature_Roblox_R15 if present
    old_arm = bpy.data.objects.get('Armature_Roblox_R15')
    if old_arm:
        bpy.data.objects.remove(old_arm, do_unlink=True)
    
    # Create new armature
    arm_data = bpy.data.armatures.new('Armature_Roblox_R15')
    arm_obj = bpy.data.objects.new('Armature_Roblox_R15', arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    
    # Select and make active
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_data.edit_bones

    # 1. Root / LowerTorso (Hips to Waist)
    # LowerTorso center X=0, Y=0
    lt_z_min = bounds['LowerTorso']['min'].z
    lt_z_max = bounds['LowerTorso']['max'].z
    ut_z_min = bounds['UpperTorso']['min'].z
    ut_z_max = bounds['UpperTorso']['max'].z
    waist_z = (lt_z_max + ut_z_min) / 2.0
    hip_z = lt_z_min

    bone_lt = edit_bones.new('LowerTorso')
    bone_lt.head = Vector((0, 0, hip_z))
    bone_lt.tail = Vector((0, 0, waist_z))

    # 2. UpperTorso (Waist to Neck)
    head_z_min = bounds['Head']['min'].z
    neck_z = (ut_z_max + head_z_min) / 2.0
    bone_ut = edit_bones.new('UpperTorso')
    bone_ut.head = Vector((0, 0, waist_z))
    bone_ut.tail = Vector((0, 0, neck_z))
    bone_ut.parent = bone_lt

    # 3. Head (Neck to Head Top)
    head_z_max = bounds['Head']['max'].z
    bone_head = edit_bones.new('Head')
    bone_head.head = Vector((0, 0, neck_z))
    bone_head.tail = Vector((0, 0, head_z_max))
    bone_head.parent = bone_ut

    # Arms helper
    for side, sign in [('Left', 1), ('Right', -1)]:
        ua = f'{side}UpperArm'
        la = f'{side}LowerArm'
        h = f'{side}Hand'
        
        ua_c = bounds[ua]['center']
        la_c = bounds[la]['center']
        h_c = bounds[h]['center']
        
        # Shoulder joint: top of upper arm
        sh_z = bounds[ua]['max'].z - 0.05
        sh_pos = Vector((ua_c.x, ua_c.y, sh_z))
        
        # Elbow joint: between upper arm min and lower arm max
        el_z = (bounds[ua]['min'].z + bounds[la]['max'].z) / 2.0
        el_pos = Vector(((ua_c.x + la_c.x)/2.0, (ua_c.y + la_c.y)/2.0, el_z))
        
        # Wrist joint: between lower arm min and hand max
        wr_z = (bounds[la]['min'].z + bounds[h]['max'].z) / 2.0
        wr_pos = Vector(((la_c.x + h_c.x)/2.0, (la_c.y + h_c.y)/2.0, wr_z))
        
        # Hand tip
        hand_tip = Vector((h_c.x, h_c.y, bounds[h]['min'].z))

        bone_ua = edit_bones.new(ua)
        bone_ua.head = sh_pos
        bone_ua.tail = el_pos
        bone_ua.parent = bone_ut

        bone_la = edit_bones.new(la)
        bone_la.head = el_pos
        bone_la.tail = wr_pos
        bone_la.parent = bone_ua

        bone_h = edit_bones.new(h)
        bone_h.head = wr_pos
        bone_h.tail = hand_tip
        bone_h.parent = bone_la

    # Legs helper
    for side in ['Left', 'Right']:
        ul = f'{side}UpperLeg'
        ll = f'{side}LowerLeg'
        ft = f'{side}Foot'
        
        ul_c = bounds[ul]['center']
        ll_c = bounds[ll]['center']
        ft_c = bounds[ft]['center']
        
        # Hip joint: top of upper leg
        hip_joint_z = bounds[ul]['max'].z
        hip_pos = Vector((ul_c.x, ul_c.y, hip_joint_z))
        
        # Knee joint: between upper leg min and lower leg max
        knee_z = (bounds[ul]['min'].z + bounds[ll]['max'].z) / 2.0
        knee_pos = Vector(((ul_c.x + ll_c.x)/2.0, (ul_c.y + ll_c.y)/2.0, knee_z))
        
        # Ankle joint: between lower leg min and foot max
        ankle_z = (bounds[ll]['min'].z + bounds[ft]['max'].z) / 2.0
        ankle_pos = Vector(((ll_c.x + ft_c.x)/2.0, (ll_c.y + ft_c.y)/2.0, ankle_z))
        
        # Toe tip: front of foot
        toe_tip = Vector((ft_c.x, bounds[ft]['min'].y, bounds[ft]['min'].z))

        bone_ul = edit_bones.new(ul)
        bone_ul.head = hip_pos
        bone_ul.tail = knee_pos
        bone_ul.parent = bone_lt

        bone_ll = edit_bones.new(ll)
        bone_ll.head = knee_pos
        bone_ll.tail = ankle_pos
        bone_ll.parent = bone_ul

        bone_ft = edit_bones.new(ft)
        bone_ft.head = ankle_pos
        bone_ft.tail = toe_tip
        bone_ft.parent = bone_ll

    bpy.ops.object.mode_set(mode='OBJECT')
    print("Armature_Roblox_R15 created with 15 bones.")

    # Now bind each of the 15 body objects with 100% rigid weight to its bone
    for name in parts:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        # Remove any existing vertex groups or armature modifiers
        obj.vertex_groups.clear()
        for mod in list(obj.modifiers):
            if mod.type == 'ARMATURE':
                obj.modifiers.remove(mod)
        
        # Add vertex group matching the bone name
        vg = obj.vertex_groups.new(name=name)
        vert_indices = list(range(len(obj.data.vertices)))
        vg.add(vert_indices, 1.0, 'REPLACE')
        
        # Parent to Armature
        obj.parent = arm_obj
        mod = obj.modifiers.new(name='Armature', type='ARMATURE')
        mod.object = arm_obj

    print("All 15 parts parented and weighted to Armature_Roblox_R15!")

create_r15_armature()
