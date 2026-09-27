"""Export the reviewed Blender snapshot and verify the R15 cage mapping."""
import json
import shutil
import subprocess
import sys
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'/'clothing_audit'
MODELS=ROOT/'assets'/'models'
scene=json.loads((OUT/'scene_snapshot.json').read_text())['objects']
reference=json.loads((OUT/'r15_reference_snapshot.json').read_text())
names=[n for n in reference if n.endswith('_OuterCage') and n in scene]

def parse_faces(indices):
    faces=[];face=[]
    for i in indices:
        face.append(i if i>=0 else -i-1)
        if i<0:faces.append(face);face=[]
    assert not face
    return faces

def canon(seq):
    seq=tuple(seq);rev=seq[::-1]
    return min([seq[i:]+seq[:i] for i in range(len(seq))]+[rev[i:]+rev[:i] for i in range(len(seq))])

def uv_corners(part):
    uv=np.asarray(part['uv'],dtype=float).reshape(-1,2)
    return uv[np.asarray(part['uv_indices'],dtype=int)]

def canonical_uv_mesh(name):
    ref=reference[name];obj=scene[name]
    rf=parse_faces(ref['indices']);ruv=uv_corners(ref)
    ref_signatures=[[] for _ in range(len(ref['verts'])//3)]
    scene_signatures=[[] for _ in obj['verts']]
    offset=0
    for face in rf:
        for vi,uv in zip(face,ruv[offset:offset+len(face)]):ref_signatures[vi].append(tuple(np.round(uv,5)))
        offset+=len(face)
    offset=0
    for face in obj['faces']:
        for vi,uv in zip(face,obj['uv'][offset:offset+len(face)]):scene_signatures[vi].append(tuple(np.round(uv,5)))
        offset+=len(face)
    ref_by_signature={tuple(sorted(sig)):i for i,sig in enumerate(ref_signatures)}
    assert len(ref_by_signature)==len(ref_signatures),(name,'duplicate reference UV signatures')
    mapping={i:ref_by_signature.get(tuple(sorted(sig))) for i,sig in enumerate(scene_signatures)}
    assert None not in mapping.values() and len(set(mapping.values()))==len(mapping),(name,'vertex map is not bijective')
    scene_face_maps=[[mapping[i] for i in face] for face in obj['faces']]
    assert len(mapping)==len(ref['verts'])//3 and len(set(mapping.values()))==len(mapping),(name,'vertex mapping not bijective')
    assert Counter(canon(f) for f in scene_face_maps)==Counter(canon(f) for f in rf),(name,'canonical topology mismatch')
    world=np.asarray(obj['verts'],dtype=float)
    ordered=np.empty((len(mapping),3))
    for scene_i,ref_i in mapping.items():ordered[ref_i]=world[scene_i]
    comparison=json.loads((OUT/'r15_comparison.json').read_text())
    return ordered,rf,ruv,comparison[name]['max_nearest_uv_distance']


def write_cages(path):
    lines=['# Isometricon female R15 outer cages, stage 2 validated','']
    global_v=global_uv=0;report={}
    for name in names:
        verts,faces,uv,error=canonical_uv_mesh(name)
        raw_uv=np.asarray(reference[name]['uv'],dtype=float).reshape(-1,2)
        uv_indices=np.asarray(reference[name]['uv_indices'],dtype=int)
        lines.append('o '+name)
        for x,y,z in verts:lines.append(f'v {x:.9f} {z:.9f} {-y:.9f}')
        for u,v in raw_uv:lines.append(f'vt {u:.9f} {v:.9f}')
        loop_offset=0
        for face in faces:
            toks=[]
            for i in range(len(face)):
                toks.append(f'{global_v+face[i]+1}/{global_uv+uv_indices[loop_offset+i]+1}')
            loop_offset+=len(face)
            lines.append('f '+' '.join(toks))
        report[name]={'vertices':len(verts),'faces':len(faces),'uv_loops':len(uv),'max_uv_error':error}
        global_v+=len(verts);global_uv+=len(raw_uv)
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


def write_body(path):
    # Body geometry did not change during stages 1-3. Reuse its established
    # export so body UVs, normals and materials remain exactly intact.
    source=MODELS/'character_female_clean_apose.obj'
    shutil.copy2(source,path)
    body_report=json.loads((OUT/'metrics.json').read_text())['body_scene_differences']
    assert all(isinstance(value,float) and value<1e-5 for value in body_report.values()),body_report
    return {'copied_from':source.name,'body_scene_max_position_delta':max(body_report.values())}
    # Kept as a reference implementation for when body geometry is edited.
    body_order=['Export_cabeca','Export_pecoco','Export_torso','Export_pelve',
      'Export_braco_superior_esquerdo','Export_antebraco_esquerdo','Export_mao_esquerda',
      'Export_braco_superior_direito','Export_antebraco_direito','Export_mao_direita',
      'Export_coxa_esquerda','Export_canela_esquerda','Export_pe_esquerdo',
      'Export_coxa_direita','Export_canela_direita','Export_pe_direito']
    source_names={'Export_cabeca':'cabeca.001','Export_pecoco':'pecoco.001','Export_pe_esquerdo':'pe_esquerdo.003','Export_pe_direito':'pe_direito.003'}
    lines=['# Isometricon female body, stage 2 validated']
    vo=uo=0;manifest={}
    for name in body_order:
        obj=scene[source_names.get(name,name+'.001')]
        verts=np.asarray(obj['verts']);faces=obj['faces'];uv=np.asarray(obj['uv'])
        assert len(uv)==sum(len(f) for f in faces),(name,'body UV missing')
        lines.append('o '+name)
        for x,y,z in verts:lines.append(f'v {x:.9f} {z:.9f} {-y:.9f}')
        for u,v in uv:lines.append(f'vt {u:.9f} {v:.9f}')
        off=0
        for face in faces:
            lines.append('f '+' '.join(f'{vo+i+1}/{uo+off+j+1}' for j,i in enumerate(face)))
            off+=len(face)
        manifest[name]={'vertices':len(verts),'faces':len(faces),'uv_loops':len(uv)}
        vo+=len(verts);uo+=len(uv)
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return manifest


cage_path=MODELS/'female_cages_apose_stage2.obj'
body_path=MODELS/'character_female_clean_apose_stage2.obj'
if cage_path.exists():
    assert cage_path.read_text(encoding='utf-8').startswith('# Isometricon female R15 outer cages, stage 2 validated')
if body_path.exists():
    assert body_path.read_bytes()==(MODELS/'character_female_clean_apose.obj').read_bytes()
cages=write_cages(cage_path);body=write_body(body_path)
reference_cage_path=MODELS/'roblox_reference_cages.obj'
subprocess.run([sys.executable,str(ROOT/'scripts'/'export_r15_reference_cages.py')],check=True)
manifest={'schema':'isometricon.roblox-r15-clothing-package.v1','source_blend':json.loads((OUT/'scene_snapshot.json').read_text())['file'],
 'coordinates':'OBJ X=Blender X, OBJ Y=Blender Z (up), OBJ Z=-Blender Y (depth); metres',
 'cage_topology':'vertex and face indices canonicalized to ClassicMannequin_With-Cages.fbx using per-corner UVs',
 'reference_fbx':'ClassicMannequin_With-Cages.fbx','reference_cage_obj':reference_cage_path.name,
 'cage_obj':cage_path.name,'body_obj':body_path.name,
 'runtime_integration':'Reference and target triangles are paired corner-by-corner using their FBX UV coordinates. Runtime rejects missing or ambiguous UV bindings instead of assuming vertex/face indices match.',
 'body_export':body,'cages':cages,'body_parts':16}
(MODELS/'female_clothing_package_stage2.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'cage_file':str(cage_path),'body_file':str(body_path),'manifest':str(MODELS/'female_clothing_package_stage2.json'),'cages':len(cages),'body_parts':16,'max_uv_error':max(x['max_uv_error'] for x in cages.values())},indent=2))
