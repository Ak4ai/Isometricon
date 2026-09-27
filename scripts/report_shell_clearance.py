"""Write reproducible rejection evidence for the Blocky clearance trial."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.experiment_shell_clearance import INPUT,OUT
from scripts.audit_canonical_radial_results import binding_jacobians
from scripts.radial_validation_metrics import normals
from src.clothing.experimental_prism_constraints import determinants


def main():
    global OUT
    if '--prism-guard' in sys.argv:OUT=ROOT/'artifacts/clothing_audit/prism_clearance'
    key='blocky_133331049150205'
    d=dict(np.load(INPUT/(key+'.npz')))
    b=dict(np.load(INPUT/(key+'_binding.npz')))
    x=dict(np.load(OUT/(key+'.npz')))
    _,before=binding_jacobians(d,b,x['before_shell'])
    _,after=binding_jacobians(d,b,x['after_shell'])
    new=np.flatnonzero(after&~before)
    fixed=np.flatnonzero(before&~after)
    n0,n1=[normals(x[name],d['projection_faces']) for name in ['before_shell','after_shell']]
    a0,a1=np.linalg.norm(n0,axis=1),np.linalg.norm(n1,axis=1)
    good=a0>np.linalg.norm(np.ptp(x['before_shell'],axis=0))**2*1e-10
    cosine=np.einsum('ij,ij->i',n0[good],n1[good])/(a0[good]*a1[good])
    witnesses=[dict(vertex=int(i),face=b['faces'][b['face_ids'][i]].tolist(),
        level=float(b['levels'][i]),barycentric=b['bary'][i].tolist(),
        before=x['before'][i].tolist(),after=x['after'][i].tolist()) for i in new[:20]]
    audit=dict(new_inverted_binding_vertices=len(new),recovered_binding_vertices=len(fixed),
        minimum_surface_normal_cosine=float(cosine.min()),minimum_surface_area_ratio=float((a1[good]/a0[good]).min()),
        maximum_shell_displacement_over_body_height=float(np.linalg.norm(x['after_shell']-x['before_shell'],axis=1).max()/np.ptp(d['body'][:,2])),
        all_new_inverted_vertex_ids=new.tolist(),examples=witnesses)
    used=b['faces'][np.unique(b['face_ids'])]
    audit['cells_with_mixed_determinant_sign']={}
    for label,low,high in [('source',d['reference_parent'],d['outer_parent']),
                           ('target_before',d['target_body'],x['before_shell']),
                           ('target_after',d['target_body'],x['after_shell'])]:
        values=np.stack([determinants(low[used],high[used],np.tile(q,(len(used),1)),np.full(len(used),t))
                         for q in ([1/3]*3,[1,0,0],[0,1,0],[0,0,1]) for t in (0.,.5,1.)])
        epsilon=1e-12*np.linalg.norm(np.ptp(low,axis=0))**3
        ids=np.flatnonzero((values.min(0)<-epsilon)&(values.max(0)>epsilon))
        audit['cells_with_mixed_determinant_sign'][label]=dict(total=len(used),count=len(ids),faces=used[ids].tolist())
    (OUT/'FAILURE_WITNESSES.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    names=['src/clothing/experimental_shell_clearance.py','src/clothing/experimental_prism_constraints.py','scripts/experiment_shell_clearance.py',
           'scripts/report_shell_clearance.py','scripts/radial_validation_metrics.py','scripts/experiment_canonical_radial.py',
           'src/clothing/wrap_layer_fit.py','tests/test_experimental_shell_clearance.py']
    paths=[ROOT/name for name in names]+[INPUT/(key+suffix) for suffix in ['.npz','_outputs.npz','_binding.npz']]
    (OUT/'MANIFEST_SHA256.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['all_new_inverted_vertex_ids','examples','cells_with_mixed_determinant_sign']},indent=2))
    print({k:v['count'] for k,v in audit['cells_with_mixed_determinant_sign'].items()})

if __name__=='__main__':main()
