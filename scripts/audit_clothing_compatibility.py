"""Read-only geometry audit; writes evidence only under artifacts/clothing_audit."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.blender_client import execute_blender_code
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages

OUT = ROOT / 'artifacts' / 'clothing_audit'
OUT.mkdir(exist_ok=True)


def read_obj(path):
    parts, vertices, current = {}, [], None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('o '):
            current = line[2:]
            parts[current] = {'verts': [], 'faces': [], 'offset': len(vertices)}
        elif line.startswith('v '):
            v = list(map(float, line.split()[1:4]))
            vertices.append(v)
            parts[current]['verts'].append(v)
        elif line.startswith('f '):
            parts[current]['faces'].append([int(t.split('/')[0])-1-parts[current]['offset'] for t in line.split()[1:]])
    for p in parts.values():
        a = np.array(p['verts'])
        p['verts'] = a[:, [0, 2, 1]] * [1, -1, 1]
    return parts


code = '''
import bpy,json,bmesh
result={'file':bpy.data.filepath,'objects':{}}
for o in bpy.data.objects:
    if o.type!='MESH' or not ('OuterCage' in o.name or o.name.startswith('Export_') or o.name in ['cabeca.001','pecoco.001','pe_direito.003','pe_esquerdo.003']): continue
    result['objects'][o.name]={'verts':[list(o.matrix_world @ v.co) for v in o.data.vertices], 'faces':[list(p.vertices) for p in o.data.polygons], 'uv':[list(d.uv) for d in o.data.uv_layers.active.data] if o.data.uv_layers.active else [], 'parent_type':o.parent_type,'parent_bone':o.parent_bone,'groups':[g.name for g in o.vertex_groups], 'modifiers':[m.type for m in o.modifiers]}
    if o.data.is_editmode:
        bm=bmesh.from_edit_mesh(o.data)
        indices={v:i for i,v in enumerate(bm.verts)}
        uv=bm.loops.layers.uv.active
        result['objects'][o.name].update(verts=[list(o.matrix_world @ v.co) for v in bm.verts],faces=[[indices[v] for v in f.verts] for f in bm.faces],uv=[list(l[uv].uv) for f in bm.faces for l in f.loops] if uv else [])
print(json.dumps(result))
'''
response = execute_blender_code(code, timeout=20)
scene = json.loads(response['result']['result'])
(OUT / 'scene_snapshot.json').write_text(json.dumps(scene), encoding='utf-8')
source = load_r15_female_cages(str(ROOT/'assets/models/clothing/roblox_source_cages.obj'), True)
raw = load_r15_female_cages(str(ROOT/'assets/models/clothing/female_cages_apose.obj'))
engine = RobloxWearEngine(body_type='female')
body = read_obj(ROOT/'assets/models/character_female_clean_apose.obj')
mapping = {'UpperTorso':'Export_torso','LowerTorso':'Export_pelve','Head':'Export_cabeca',
 'LeftUpperArm':'Export_braco_superior_esquerdo','RightUpperArm':'Export_braco_superior_direito',
 'LeftLowerArm':'Export_antebraco_esquerdo','RightLowerArm':'Export_antebraco_direito',
 'LeftHand':'Export_mao_esquerda','RightHand':'Export_mao_direita',
 'LeftUpperLeg':'Export_coxa_esquerda','RightUpperLeg':'Export_coxa_direita',
 'LeftLowerLeg':'Export_canela_esquerda','RightLowerLeg':'Export_canela_direita',
 'LeftFoot':'Export_pe_esquerdo','RightFoot':'Export_pe_direito'}
report = {'parts':{}, 'body_scene_differences':{}, 'body_names':list(body)}
for name, p in raw.items():
    if name.endswith('Forearm'): continue
    sv=source[name]['verts']; v=p['verts']; f=p['faces']; repaired=engine.r15_female_cages[name]['verts']
    obj=scene['objects'].get(name+'_OuterCage',{})
    bv=np.array(obj.get('verts',[]))
    displacement=np.linalg.norm(repaired-v,axis=1)
    edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    def lengths(a): return np.linalg.norm(a[edges[:,0]]-a[edges[:,1]],axis=1)
    row={'source_vertices':len(sv),'export_vertices':len(v),'scene_vertices':len(bv),
         'faces_equal_to_source':bool(np.array_equal(f,source[name]['faces'])),
         'scene_uv_loops':len(obj.get('uv',[])),
         'scene_export_max_delta':float(np.linalg.norm(bv-v,axis=1).max()) if bv.shape==v.shape else None,
         'repair_changed_vertices':np.flatnonzero(displacement>1e-6).tolist(),
         'repair_max_delta':float(displacement.max()),
         'max_edge_before':float(lengths(v).max()),'max_edge_after':float(lengths(repaired).max())}
    distances=np.linalg.norm(bv[:,None]-v[None],axis=2)
    row['scene_export_hausdorff']=float(max(distances.min(axis=0).max(),distances.min(axis=1).max()))
    for label,target in [('raw',v),('repaired',repaired)]:
        nearest=np.linalg.norm(bv[:,None]-target[None],axis=2).argmin(axis=1)
        scene_edges={tuple(sorted((int(nearest[face[i]]),int(nearest[face[(i+1)%len(face)]])))) for face in obj['faces'] for i in range(len(face))}
        row[label+'_scene_edges_missing_in_export']=len(scene_edges-set(map(tuple,edges)))
    row['scene_reordered_vertices']=int((distances.argmin(axis=1)!=np.arange(len(bv))).sum()) if len(bv)==len(v) else None
    if mapping.get(name) in body:
        points=body[mapping[name]]['verts']
        for label, cage in [('raw',v),('repaired',repaired),('scene',bv)]:
            excess=np.maximum(np.maximum(cage.min(axis=0)-points,points-cage.max(axis=0)),0)
            row[label+'_body_vertices_outside_bbox']=int((excess.max(axis=1)>0.001).sum())
            row[label+'_max_bbox_excess']=float(excess.max())
        row['body_vertices']=len(points)
    report['parts'][name]=row
for name,p in body.items():
    candidate=name+'.001'
    if name=='Export_cabeca':candidate='cabeca.001'
    if name=='Export_pecoco':candidate='pecoco.001'
    if name=='Export_pe_esquerdo':candidate='pe_esquerdo.003'
    if name=='Export_pe_direito':candidate='pe_direito.003'
    if candidate in scene['objects']:
        bv=np.array(scene['objects'][candidate]['verts'])
        report['body_scene_differences'][name]=float(np.linalg.norm(bv-p['verts'],axis=1).max()) if bv.shape==p['verts'].shape else 'vertex_count_differs'
(OUT/'metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

# Orthographic technical comparison. Green: exported body, cyan: cage.
from PIL import Image, ImageDraw
im=Image.new('RGB',(1500,1000),'#161922'); draw=ImageDraw.Draw(im)
for col,(title,parts) in enumerate([('EXPORTED CAGE',raw),('RUNTIME REPAIRED CAGE',engine.r15_female_cages),('CURRENT BLENDER CAGE',None)]):
    draw.text((col*500+20,12),title,fill='white')
    for row,axes in enumerate([(0,2),(1,2)]):
        def screen(v):return (col*500+250+float(v[axes[0]])*235,row*490+470-float(v[axes[1]])*235)
        for p in body.values():
            for face in p['faces']:
                pts=[screen(p['verts'][i]) for i in face]
                draw.line(pts+[pts[0]],fill='#426c42',width=1)
        for name in mapping:
            if parts is None:
                p=scene['objects'].get(name+'_OuterCage')
                if p is None:continue
            else:p=parts[name]
            for face in p['faces']:
                pts=[screen(p['verts'][i]) for i in face]
                draw.line(pts+[pts[0]],fill='#44cddd',width=1)
im.save(OUT/'comparison.png')
