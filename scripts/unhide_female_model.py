from blender_client import execute_blender_code

code = '''
import bpy

def unhide_collection_recursive(layer_coll, target_names):
    if layer_coll.name in target_names:
        layer_coll.hide_viewport = False
        layer_coll.exclude = False
    for child in layer_coll.children:
        unhide_collection_recursive(child, target_names)

# Target collections for female character and cages
target_colls = ["Collection 6", "Cages_Feminino", "Cages_Feminino_Unificada"]

# Unhide in ViewLayer
unhide_collection_recursive(bpy.context.view_layer.layer_collection, target_colls)

# Unhide data collections and their objects
unhidden_objs = []
for coll_name in target_colls:
    coll = bpy.data.collections.get(coll_name)
    if coll:
        coll.hide_viewport = False
        coll.hide_render = False
        for obj in coll.all_objects:
            obj.hide_viewport = False
            obj.hide_set(False)
            unhidden_objs.append(obj.name)

# Also ensure Armature_Character.001 is unhidden
arm = bpy.data.objects.get("Armature_Character.001")
if arm:
    arm.hide_viewport = False
    arm.hide_set(False)

print(f"Successfully unhidden {len(unhidden_objs)} objects across {target_colls}")
'''

res = execute_blender_code(code)
print(res)
