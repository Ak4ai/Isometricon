import json
from blender_client import execute_blender_code

code = '''
import bpy, json

def get_layer_collections(lc):
    res = [{'name': lc.name, 'exclude': lc.exclude, 'hide_viewport': lc.hide_viewport}]
    for child in lc.children:
        res.extend(get_layer_collections(child))
    return res

lcs = get_layer_collections(bpy.context.view_layer.layer_collection)
objs = []
for o in bpy.data.objects:
    objs.append({
        'name': o.name,
        'type': o.type,
        'hide_viewport': o.hide_viewport,
        'hide_get': o.hide_get(),
        'parent': o.parent.name if o.parent else None,
        'colls': [c.name for c in o.users_collection]
    })
print(json.dumps({'collections': lcs, 'objects': objs}))
'''

res = execute_blender_code(code)
if res.get('status') == 'success':
    out = json.loads(res['result']['result'])
    print("=== COLLECTIONS ===")
    for c in out['collections']:
        print(f"Collection: {c['name']} (exclude={c['exclude']}, hide_viewport={c['hide_viewport']})")
    
    print("\n=== OBJECTS ===")
    for o in out['objects']:
        print(f"{o['name']} ({o['type']}) | Parent: {o['parent']} | HideVP: {o['hide_viewport']} | HideGet: {o['hide_get']} | Colls: {o['colls']}")
else:
    print("Error:", res)
