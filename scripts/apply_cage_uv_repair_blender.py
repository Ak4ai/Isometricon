"""Run inside Blender. Preserve original scene in a backup and save a work copy."""
import bpy
import bmesh
import json
from pathlib import Path
from datetime import datetime

root=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon')
out=root/'artifacts/clothing_audit'
plan=json.loads((out/'uv_repair_plan.json').read_text())
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
backup=root/'assets/models'/f'female_cage_before_uv_{stamp}.blend'
working=root/'assets/models'/f'female_cage_working_{stamp}.blend'
assert not backup.exists() and not working.exists()
old_active=bpy.context.view_layer.objects.active
was_edit=bpy.context.mode=='EDIT_MESH'
# Save the actual current scene, including unsaved user changes, before mutation.
bpy.ops.wm.save_as_mainfile(filepath=str(backup),copy=True)
if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')

# Check the whole plan before making any edits.
for name,p in plan.items():
    obj=bpy.data.objects[name]
    assert [list(f.vertices) for f in obj.data.polygons]==p['faces'],name
    assert len(obj.data.uv_layers.active.data)==len(p['uv']),name
    for v,expected in zip(obj.data.vertices,p['verts']):
        assert max(abs(a-b) for a,b in zip(obj.matrix_world@v.co,expected))<1e-6,name
    for loop,expected in zip(obj.data.uv_layers.active.data,p['old_uv']):
        assert max(abs(a-b) for a,b in zip(loop.uv,expected))<1e-6,name

before={o.name:[tuple(v.co) for v in o.data.vertices] for o in bpy.data.objects if o.type=='MESH' and o.name.endswith('_OuterCage')}
for name,p in plan.items():
    obj=bpy.data.objects[name]
    for loop,uv in zip(obj.data.uv_layers.active.data,p['uv']):loop.uv=uv
    obj.data.update()

head=bpy.data.objects['Head_OuterCage']
used={v for edge in head.data.edges for v in edge.vertices}|{v for face in head.data.polygons for v in face.vertices}
loose=[v.index for v in head.data.vertices if v.index not in used]
assert loose==[335] or loose==[],loose
if loose:
    bm=bmesh.new()
    bm.from_mesh(head.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[bm.verts[i] for i in loose],context='VERTS')
    bm.to_mesh(head.data)
    bm.free()
    head.data.update()
for name,coords in before.items():
    after=[tuple(v.co) for v in bpy.data.objects[name].data.vertices]
    assert after==(coords[:335] if name=='Head_OuterCage' and loose else coords),name

if was_edit and old_active:
    bpy.context.view_layer.objects.active=old_active
    bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.wm.save_as_mainfile(filepath=str(working))
result={'backup':str(backup),'working':str(working),'uv_repaired':list(plan),'removed_loose_head_vertices':loose,'remaining_vertex_positions_unchanged':True}
(out/'stage1_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
