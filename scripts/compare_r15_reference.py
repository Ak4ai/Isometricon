"""Compare live cage topology/UVs with original local FBX, without importing it."""
import json
import sys
from collections import Counter
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.blender_client import execute_blender_code

OUT=ROOT/'artifacts/clothing_audit'
code='''
import json
from io_scene_fbx import parse_fbx
root,version=parse_fbx.parse(FBX_PATH)
objects=next(e for e in root.elems if e.id==b'Objects')
connections=next(e for e in root.elems if e.id==b'Connections')
models={e.props[0]:e.props[1].split(b'\\x00')[0].decode() for e in objects.elems if e.id==b'Model'}
parents={e.props[1]:e.props[2] for e in connections.elems if e.id==b'C' and e.props[0]==b'OO'}
result={}
for e in objects.elems:
    if e.id!=b'Geometry':continue
    name=models.get(parents.get(e.props[0]),'')
    if 'Cage' not in name:continue
    children={c.id:c for c in e.elems}
    uv={c.id:c.props for c in children[b'LayerElementUV'].elems}
    result[name]={'verts':list(children[b'Vertices'].props[0]),'indices':list(children[b'PolygonVertexIndex'].props[0]),'uv':list(uv[b'UV'][0]),'uv_indices':list(uv[b'UVIndex'][0]) if b'UVIndex' in uv else None,'mapping':str(uv[b'MappingInformationType'][0]),'reference':str(uv[b'ReferenceInformationType'][0])}
print(json.dumps(result))
'''
code='FBX_PATH='+repr(str(ROOT/'ClassicMannequin_With-Cages.fbx'))+'\n'+code
response=execute_blender_code(code)
ref=json.loads(response['result']['result'])
(OUT/'r15_reference_snapshot.json').write_text(json.dumps(ref),encoding='utf-8')
scene=json.loads((OUT/'scene_snapshot.json').read_text())['objects']

def canonical(seq):
    seq=tuple(seq)
    reverse=tuple(reversed(seq))
    return min([seq[i:]+seq[:i] for i in range(len(seq))]+[reverse[i:]+reverse[:i] for i in range(len(seq))])

def uv_faces(faces,loop_uv):
    result=[];offset=0
    for f in faces:
        result.append(canonical([tuple(round(float(c),5) for c in uv) for uv in loop_uv[offset:offset+len(f)]]))
        offset+=len(f)
    return Counter(result)

report={}
for name,p in ref.items():
    if name not in scene:continue
    faces=[];face=[]
    for idx in p['indices']:
        face.append(idx if idx>=0 else -idx-1)
        if idx<0:faces.append(face);face=[]
    uv=np.array(p['uv']).reshape(-1,2)
    loops=uv[p['uv_indices']] if p['uv_indices'] is not None else uv
    s=scene[name]
    a=uv_faces(faces,loops);b=uv_faces(s['faces'],s['uv'])
    # Also compare unoriented face indices; this does not assume coordinate equality.
    fa=Counter(canonical(f) for f in faces);fb=Counter(canonical(f) for f in s['faces'])
    used=set(i for f in s['faces'] for i in f)
    report[name]={'reference_vertices':len(p['verts'])//3,'scene_vertices':len(s['verts']),
      'reference_faces':len(faces),'scene_faces':len(s['faces']),
      'face_indices_equal':fa==fb,'uv_face_layout_equal_1e5':a==b,
      'reference_uv_faces_missing':sum((a-b).values()),'scene_uv_faces_extra':sum((b-a).values()),
      'scene_unused_vertices':sorted(set(range(len(s['verts'])))-used),
      'reference_uv_mapping':p['mapping']}
    distance=np.linalg.norm(np.array(s['uv'])[:,None]-uv[None],axis=2).min(axis=1)
    report[name]['uv_loops_without_reference_match_1e6']=int((distance>1e-6).sum())
    report[name]['max_nearest_uv_distance']=float(distance.max())
    if name.startswith('Right'):
        left=ref[name.replace('Right','Left')]
        left_uv=np.array(left['uv']).reshape(-1,2)[left['uv_indices']]
        left_faces=[];face=[]
        for idx in left['indices']:
            face.append(idx if idx>=0 else -idx-1)
            if idx<0:left_faces.append(face);face=[]
        report[name]['uv_faces_match_left_reference']=uv_faces(left_faces,left_uv)==b
    if name=='LowerTorso_OuterCage':
        mismatches=[];offset=0
        for fi,face in enumerate(s['faces']):
            for li,vi in enumerate(face):
                if distance[offset+li]>1e-6:
                    mismatches.append({'face':fi,'vertex':vi,'uv':s['uv'][offset+li]})
            offset+=len(face)
        report[name]['uv_mismatches']=mismatches
(OUT/'r15_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
