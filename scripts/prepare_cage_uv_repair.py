"""Prepare and validate per-corner UV transfers before touching Blender."""
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/clothing_audit'
scene=json.loads((OUT/'scene_snapshot.json').read_text())['objects']
reference=json.loads((OUT/'r15_reference_snapshot.json').read_text())
plan={}
for name in reference:
    if not (name.startswith('Right') or name=='LowerTorso_OuterCage'):continue
    p=reference[name];faces=[];face=[]
    for index in p['indices']:
        face.append(index if index>=0 else -index-1)
        if index<0:faces.append(face);face=[]
    uv=np.array(p['uv']).reshape(-1,2)[p['uv_indices']]
    ref_faces=[];offset=0
    for face in faces:
        ref_faces.append(uv[offset:offset+len(face)])
        offset+=len(face)
    obj=scene[name];offset=0;used=[];new_uv=[];mapping={};max_error=0
    for face in obj['faces']:
        old=np.array(obj['uv'][offset:offset+len(face)])
        offset+=len(face)
        guess=old.copy()
        if name=='RightFoot_OuterCage':guess[:,0]-=2
        elif name.startswith('Right'):guess[:,0]=7-guess[:,0]
        candidates=[]
        for fi,ruv in enumerate(ref_faces):
            if len(ruv)!=len(face):continue
            for rev in [False,True]:
                order=np.arange(len(face))
                if rev:order=order[::-1]
                for shift in range(len(face)):
                    perm=np.roll(order,shift)
                    error=float(np.sum((guess-ruv[perm])**2))
                    candidates.append((error,fi,perm))
        error,fi,perm=min(candidates,key=lambda x:x[0])
        assert fi not in used,(name,'non-bijective face',fi)
        used.append(fi)
        for vi,ri in zip(face,perm):
            target=faces[fi][ri]
            assert vi not in mapping or mapping[vi]==target,(name,'inconsistent vertex',vi)
            mapping[vi]=target
        new_uv.extend(ref_faces[fi][perm].tolist())
        max_error=max(max_error,float(np.linalg.norm(guess-ref_faces[fi][perm],axis=1).max()))
    assert len(set(mapping.values()))==len(mapping),(name,'non-bijective vertices')
    assert len(used)==len(faces)
    plan[name]={'uv':new_uv,'old_uv':obj['uv'],'faces':obj['faces'],'verts':obj['verts'],'max_matching_error':max_error}
    print(name,'validated faces',len(used),'vertices',len(mapping),'max UV matching distance',max_error)
(OUT/'uv_repair_plan.json').write_text(json.dumps(plan),encoding='utf-8')
