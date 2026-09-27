"""Locate penetration before/after residual for unmixed radial/prism supports."""
from pathlib import Path
import json
import sys
import hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_blocky_radial_influences import INPUT,OUT,KEY
from scripts.radial_validation_metrics import body_penetration
from scripts.audit_blocky_clearance_witness import body_parts


def main():
    d=dict(np.load(INPUT/(KEY+'.npz')));b=dict(np.load(INPUT/(KEY+'_binding.npz')))
    x=dict(np.load(OUT/'outputs.npz'))
    f=b['faces'][b['face_ids']];labels=x['labels'];names=x['part_names']
    own=x['part_weights'][np.arange(len(labels)),np.searchsorted(names,labels)]
    unmixed=np.einsum('ij,ij->i',b['bary'],1-own[f])<1e-9
    _,inside,_=body_penetration(x['radial_previous'],d['body'],d['body_faces'],return_samples=True)
    selected=np.flatnonzero(unmixed&inside)
    inner=np.einsum('ij,ijk->ik',b['bary'],d['target_body'][f])
    outer=np.einsum('ij,ijk->ik',b['bary'],x['radial_shell'][f])
    middle=(1-b['levels'][:,None])*inner+b['levels'][:,None]*outer
    stages=dict(inner=inner,outer=outer,prism_without_residual=middle,final=x['radial_previous'])
    masks={}
    for name,points in stages.items():
        _,mask,_=body_penetration(points[selected],d['body'],d['body_faces'],return_samples=True)
        masks[name]=mask
    report=dict(unmixed_penetrating_vertices=len(selected),
        stage_inside_counts={k:int(sum(v)) for k,v in masks.items()},
        enters_only_after_residual=int(sum(~masks['prism_without_residual']&masks['final'])),
        body_scope='union of closed components of frozen Blocky body',witnesses=[])
    parts=body_parts()
    for vertex in (93,377,1486):
        points=np.array([a[vertex] for a in stages.values()])
        hits={}
        for name,(v,faces) in parts.items():
            _,hit,_=body_penetration(points,v,faces,return_samples=True)
            if hit.any():hits[name]=hit.tolist()
        report['witnesses'].append(dict(vertex=vertex,region=str(labels[f[vertex,0]]),
            stages={k:a[vertex].tolist() for k,a in stages.items()},stage_order=list(stages),body_parts_hit=hits,
            source_residual=float(np.linalg.norm(b['residual'][vertex])),unmixed=bool(unmixed[vertex])))
    files=[Path(__file__),INPUT/(KEY+'.npz'),INPUT/(KEY+'_binding.npz'),OUT/'outputs.npz',
           ROOT/'scripts/audit_blocky_clearance_witness.py',ROOT/'scripts/radial_validation_metrics.py']
    report['sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'UNMIXED_STAGES.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('witnesses','sha256')},indent=2))
    print(json.dumps(report['witnesses'],indent=2))


if __name__=='__main__':main()
