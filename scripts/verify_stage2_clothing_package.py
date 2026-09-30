"""Read exported OBJs and compare them to the validated Blender/R15 snapshot."""
import json
import sys
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/clothing_audit';MODELS=ROOT/'assets/models'
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import load_r15_cages, _align_target_faces_by_uv
scene=json.loads((OUT/'scene_snapshot.json').read_text())['objects']
reference=json.loads((OUT/'r15_reference_snapshot.json').read_text())
manifest=json.loads((MODELS/'female_clothing_package_stage2.json').read_text())

def read_obj(path):
    verts=[];uv=[];parts={};current=None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('o '):
            current={'v':[],'vt':[],'f':[]};parts[line[2:]]=current
        elif line.startswith('v '):verts.append(list(map(float,line.split()[1:4])));current['v'].append(len(verts)-1)
        elif line.startswith('vt '):uv.append(list(map(float,line.split()[1:3])));current['vt'].append(len(uv)-1)
        elif line.startswith('f '):
            face=[];tex=[]
            for token in line.split()[1:]:
                bits=token.split('/');face.append(int(bits[0])-1);tex.append(int(bits[1])-1 if len(bits)>1 and bits[1] else None)
            current['f'].append((face,tex))
    return np.array(verts),np.array(uv),parts

def faces(ind):
    result=[];face=[]
    for i in ind:
        face.append(i if i>=0 else -i-1)
        if i<0:result.append(face);face=[]
    assert not face
    return result

cage_v,cage_uv,cage_parts=read_obj(MODELS/manifest['cage_obj'])
report={};voff=uoff=0
for name in [n for n in reference if n.endswith('_OuterCage') and n in scene]:
    p=reference[name];sf=scene[name];part=cage_parts[name];ref_faces=faces(p['indices'])
    rv=np.asarray(p['verts']).reshape(-1,3);source_uv=np.asarray(p['uv']).reshape(-1,2)
    uv_indices=np.asarray(p['uv_indices']);expected_uv=source_uv[uv_indices]
    outv=cage_v[np.array(part['v'])];back=outv[:,[0,2,1]]*np.array([1,-1,1])
    expected_scene=np.empty_like(back)
    # Identity is independently reconstructed from each unique vertex UV signature.
    ref_sig=[[] for _ in rv];scene_sig=[[] for _ in sf['verts']];off=0
    for f in ref_faces:
        for vi,uv in zip(f,expected_uv[off:off+len(f)]):ref_sig[vi].append(tuple(np.round(uv,5)))
        off+=len(f)
    off=0
    for f in sf['faces']:
        for vi,uv in zip(f,sf['uv'][off:off+len(f)]):scene_sig[vi].append(tuple(np.round(uv,5)))
        off+=len(f)
    ref_lookup={tuple(sorted(s)):i for i,s in enumerate(ref_sig)}
    mapping={i:ref_lookup[tuple(sorted(s))] for i,s in enumerate(scene_sig)}
    for si,ri in mapping.items():expected_scene[ri]=sf['verts'][si]
    geom_error=float(np.linalg.norm(back-expected_scene,axis=1).max())
    emitted_faces=[];emitted_uv=[]
    for face,ti in part['f']:
        emitted_faces.append([i-voff for i in face]);emitted_uv.extend(cage_uv[ti])
    uv_error=float(np.max(np.abs(np.asarray(emitted_uv)-expected_uv)))
    assert geom_error<2e-8,(name,geom_error)
    assert emitted_faces==ref_faces,(name,'face connectivity/order changed')
    assert uv_error<2e-8,(name,uv_error)
    report[name]={'vertices':len(outv),'faces':len(emitted_faces),'uv_loops':len(emitted_uv),'max_position_error':geom_error,'max_uv_error':uv_error,'faces_exact':True}
    voff+=len(outv);uoff+=len(expected_uv)
assert len(cage_parts)==15 and len(report)==15
runtime_loaded=load_r15_cages(str(MODELS/manifest['cage_obj']),is_source_cage=False)
reference_loaded=load_r15_cages(str(MODELS/manifest['reference_cage_obj']),is_source_cage=True)
for name in report:
    runtime_name=name.replace('_OuterCage','')
    triangles=[]
    for face in faces(reference[name]['indices']):
        for j in range(1,len(face)-1):triangles.append([face[0],face[j],face[j+1]])
    assert np.array_equal(runtime_loaded[runtime_name]['faces'],np.asarray(triangles)),(name,'runtime loader changed canonical faces')
    report[name]['runtime_loader_topology_exact']=True
    paired_faces=_align_target_faces_by_uv(reference_loaded[runtime_name],runtime_loaded[runtime_name],runtime_name)
    assert paired_faces.shape==reference_loaded[runtime_name]['faces'].shape,(name,'UV triangle binding failed')
    report[name]['reference_target_uv_triangles_paired']=len(paired_faces)
body=MODELS/manifest['body_obj'];source=MODELS/'character_female_clean_apose.obj'
assert body.read_bytes()==source.read_bytes()
result={'cage_parts':report,'total_cage_vertices':voff,'total_cage_uvs':uoff,'runtime_loader_topology_exact':True,
 'reference_target_uv_triangle_binding_exact':True,
 'body_copy_byte_identical_to_previously_validated_obj':True,'cage_obj_bytes':(MODELS/manifest['cage_obj']).stat().st_size,
 'body_obj_bytes':body.stat().st_size,'max_position_error':max(p['max_position_error'] for p in report.values()),
 'max_uv_error':max(p['max_uv_error'] for p in report.values())}
(OUT/'stage4_export_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cage_parts'},indent=2))
