import bpy
import mathutils
import math
import os

def render_female_outfits():
    scene = bpy.context.scene
    base_dir = r"C:\Users\Henrique\Documents\GitHub\Isometricon"
    artifact_dir = r"C:\Users\Henrique\.gemini\antigravity-cli\brain\b12a4ec6-59d8-4b95-b402-045e7dddf299"

    # 1. Camera & Lighting setup
    cam = bpy.data.objects.get('Crotch_Cam')
    if not cam:
        cam_data = bpy.data.cameras.new('Crotch_Cam')
        cam = bpy.data.objects.new('Crotch_Cam', cam_data)
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.hide_render = False

    for l_name in ['KeyLight', 'FillLight', 'RimLight']:
        light = bpy.data.objects.get(l_name)
        if light:
            light.hide_render = False

    scene.render.resolution_x = 800
    scene.render.resolution_y = 900
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = True

    # Skin material
    skin_mat = bpy.data.materials.get("Skin_Material_Female")
    if not skin_mat:
        skin_mat = bpy.data.materials.new("Skin_Material_Female")
        skin_mat.use_nodes = True
        bsdf = skin_mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.88, 0.82, 0.76, 1.0) # Character skin tone
            bsdf.inputs["Roughness"].default_value = 0.5

    col6 = bpy.data.collections.get('Collection 6')

    outfits = [
        {
            "name": "Sweater_and_Jeans",
            "top_id": "9240757332",
            "top_obj": os.path.join(base_dir, "assets", "models", "character_native_9240757332_female.obj"),
            "top_png": os.path.join(base_dir, "assets", "models", "clothing", "Knit_Sweater_-_Black_9240757332.png"),
            "bot_id": "109837605892174",
            "bot_obj": os.path.join(base_dir, "assets", "models", "character_native_109837605892174_female.obj"),
            "bot_png": os.path.join(base_dir, "assets", "models", "clothing", "Black_Distressed_Designer_Jeans_w__Boots_109837605892174.png"),
            "is_long": True,
        },
        {
            "name": "Shirt_and_Jeans",
            "top_id": "133331049150205",
            "top_obj": os.path.join(base_dir, "assets", "models", "character_native_133331049150205_female.obj"),
            "top_png": os.path.join(base_dir, "assets", "models", "clothing", "-_office_shirt__BLACK_133331049150205.png"),
            "bot_id": "109837605892174",
            "bot_obj": os.path.join(base_dir, "assets", "models", "character_native_109837605892174_female.obj"),
            "bot_png": os.path.join(base_dir, "assets", "models", "clothing", "Black_Distressed_Designer_Jeans_w__Boots_109837605892174.png"),
            "is_long": False,
        }
    ]

    for outfit in outfits:
        outfit_name = outfit["name"]
        top_id = outfit["top_id"]
        is_long = outfit["is_long"]

        # Clean up previously imported dynamic objects
        for o in list(bpy.data.objects):
            if o.name.startswith("DYN_"):
                bpy.data.objects.remove(o, do_unlink=True)

        # Hide all objects in scene by default
        for o in bpy.data.objects:
            o.hide_render = True
            o.hide_viewport = True

        # Show camera & lights
        cam.hide_render = False
        for l_name in ['KeyLight', 'FillLight', 'RimLight']:
            l_obj = bpy.data.objects.get(l_name)
            if l_obj:
                l_obj.hide_render = False

        # Collection 6 configuration:
        # Head, neck, face are visible
        # Torso, pelvis, legs are hidden (covered by clothing)
        # Arms are managed via sliced HSR meshes
        if col6:
            col6.hide_render = False
            for o in col6.objects:
                name_l = o.name.lower()
                if any(k in name_l for k in ['cabeca', 'rosto', 'pecoco']):
                    o.hide_render = False
                    o.hide_viewport = False
                elif 'antebraco' in name_l and not is_long:
                    # Short sleeves: forearms are completely visible
                    o.hide_render = False
                    o.hide_viewport = False
                else:
                    o.hide_render = True
                    o.hide_viewport = True

        def load_obj_with_tex(filepath, texpath, obj_name, mat_name):
            if not os.path.exists(filepath):
                print(f"File not found: {filepath}")
                return None
            bpy.ops.wm.obj_import(filepath=filepath, forward_axis='Y', up_axis='Z')
            imported = bpy.context.selected_objects
            if not imported:
                return None
            obj = imported[0]
            obj.name = obj_name
            obj.hide_render = False
            obj.hide_viewport = False

            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bsdf and os.path.exists(texpath):
                tex_img = mat.node_tree.nodes.new('ShaderNodeTexImage')
                tex_img.image = bpy.data.images.load(texpath, check_existing=True)
                mat.node_tree.links.new(tex_img.outputs['Color'], bsdf.inputs['Base Color'])
                bsdf.inputs['Roughness'].default_value = 0.8
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            return obj

        def load_arm_obj(filepath, obj_name):
            if not os.path.exists(filepath):
                return None
            # Check if file has vertices
            with open(filepath, "r") as f:
                content = f.read()
            if "v " not in content:
                return None
            bpy.ops.wm.obj_import(filepath=filepath, forward_axis='Y', up_axis='Z')
            imported = bpy.context.selected_objects
            if not imported:
                return None
            obj = imported[0]
            obj.name = obj_name
            obj.hide_render = False
            obj.hide_viewport = False
            obj.data.materials.clear()
            obj.data.materials.append(skin_mat)
            return obj

        # Load Top and Bottom
        load_obj_with_tex(outfit["top_obj"], outfit["top_png"], f"DYN_{outfit_name}_Top", f"Mat_{outfit_name}_Top")
        load_obj_with_tex(outfit["bot_obj"], outfit["bot_png"], f"DYN_{outfit_name}_Bot", f"Mat_{outfit_name}_Bot")

        # Load Sliced Arms
        if is_long:
            # Long sleeve: load sliced hands/wrists emerging from sleeves
            load_arm_obj(os.path.join(base_dir, "assets", "models", f"character_native_forearm_left_{top_id}_female.obj"), f"DYN_{outfit_name}_Forearm_L")
            load_arm_obj(os.path.join(base_dir, "assets", "models", f"character_native_forearm_right_{top_id}_female.obj"), f"DYN_{outfit_name}_Forearm_R")
        else:
            # Short sleeve: load sliced upper arms
            load_arm_obj(os.path.join(base_dir, "assets", "models", f"character_native_arm_left_{top_id}_female.obj"), f"DYN_{outfit_name}_Arm_L")
            load_arm_obj(os.path.join(base_dir, "assets", "models", f"character_native_arm_right_{top_id}_female.obj"), f"DYN_{outfit_name}_Arm_R")

        target = mathutils.Vector((0.0, 0.0, 0.95))

        # 1. Front View (facing character at negative Y)
        cam.location = mathutils.Vector((0.0, -2.3, 0.95))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(artifact_dir, f"female_dressed_{outfit_name}_front.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered Front: {scene.render.filepath}")

        # 2. 3/4 Perspective View
        cam.location = mathutils.Vector((1.5, -1.8, 1.15))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(artifact_dir, f"female_dressed_{outfit_name}_3quarter.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered 3/4: {scene.render.filepath}")

        # 3. Back View (facing character at positive Y)
        cam.location = mathutils.Vector((0.0, 2.3, 0.95))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(artifact_dir, f"female_dressed_{outfit_name}_back.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered Back: {scene.render.filepath}")

    print("SUCCESS: All female outfit renders completed!")

render_female_outfits()
