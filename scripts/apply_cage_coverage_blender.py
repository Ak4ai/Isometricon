"""Apply validated stage-2 positions and prepare the viewport for review."""
import bpy
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from mathutils import Vector,Quaternion

root=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon')
out=root/'artifacts/clothing_audit'
plan=json.loads((out/'coverage_plan.json').read_text())
validation=json.loads((out/'coverage_dense_validation.json').read_text())
assert all(p['uncovered']==0 for p in validation.values())
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
backup=root/'assets/models'/f'female_cage_before_coverage_{stamp}.blend'
working=root/'assets/models'/f'female_cage_stage2_{stamp}.blend'
assert not backup.exists() and not working.exists()
bpy.ops.wm.save_as_mainfile(filepath=str(backup),copy=True)
if bpy.context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
for name,p in plan.items():
    o=bpy.data.objects[name+'_OuterCage']
    assert [list(f.vertices) for f in o.data.polygons]==p['faces']
    assert np.max(np.abs(np.array([o.matrix_world@v.co for v in o.data.vertices])-p['old_verts']))<1e-6
    assert np.max(np.abs(np.array([l.uv[:] for l in o.data.uv_layers.active.data])-p['uv']))<1e-6
    a=np.array(p['old_verts']);b=np.array(p['verts'])
    for face in p['faces']:
        for i in range(1,len(face)-1):
            ix=[face[0],face[i],face[i+1]];x=a[ix];y=b[ix]
            assert np.dot(np.cross(x[1]-x[0],x[2]-x[0]),np.cross(y[1]-y[0],y[2]-y[0]))>=0,name

changes={}
for name,p in plan.items():
    o=bpy.data.objects[name+'_OuterCage'];inverse=o.matrix_world.inverted()
    distances=np.linalg.norm(np.array(p['verts'])-p['old_verts'],axis=1)
    moved=np.flatnonzero(distances>1e-7).tolist()
    if moved:
        group=o.vertex_groups.get('REVISAO_ETAPA2') or o.vertex_groups.new(name='REVISAO_ETAPA2')
        group.add(moved,1.0,'REPLACE')
        for v,position in zip(o.data.vertices,p['verts']):v.co=inverse@Vector(position)
        o.data.update()
        changes[name]={'vertices':moved,'max_displacement_mm':float(distances.max()*1000)}
    assert [list(f.vertices) for f in o.data.polygons]==p['faces']
    assert np.max(np.abs(np.array([l.uv[:] for l in o.data.uv_layers.active.data])-p['uv']))<1e-6

snapshot=json.loads((out/'scene_snapshot.json').read_text())['objects']
body_names={n for n in snapshot if not n.endswith('_OuterCage')}
for name in body_names:
    o=bpy.data.objects.get(name)
    if o and o.type=='MESH':assert np.max(np.abs(np.array([o.matrix_world@v.co for v in o.data.vertices])-snapshot[name]['verts']))<1e-6,name
visible=body_names|{name+'_OuterCage' for name in plan}
def reveal(layer):
    layer.exclude=False;layer.hide_viewport=False
    for child in layer.children:reveal(child)
reveal(bpy.context.view_layer.layer_collection)
for o in bpy.context.view_layer.objects:
    o.hide_set(o.name not in visible)
    o.select_set(False)
    if o.name in visible:
        o.hide_viewport=False
        o.show_in_front=False
        o.display_type='WIRE' if o.name.endswith('_OuterCage') else 'SOLID'
        o.color=(0.05,0.8,1.0,1.0) if o.name.endswith('_OuterCage') else (0.55,0.34,0.22,1.0)
active=bpy.data.objects['LeftUpperArm_OuterCage']
active.select_set(True);bpy.context.view_layer.objects.active=active
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.type='SOLID';space.shading.color_type='OBJECT';space.shading.show_xray=False
            space.overlay.show_extras=False
            space.region_3d.view_rotation=Quaternion((0.70710678,0.70710678,0,0))
            space.region_3d.view_perspective='ORTHO'
            space.region_3d.view_location=Vector((0,0,0.95));space.region_3d.view_distance=2.5
bpy.ops.wm.save_as_mainfile(filepath=str(working))
result={'working':str(working),'backup':str(backup),'changes':changes,'validated_samples':sum(p['samples'] for p in validation.values()),'uncovered_samples':0,'uv_and_faces_preserved':True,'body_positions_unchanged':True}
(out/'stage2_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
