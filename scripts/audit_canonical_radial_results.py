"""Recompute validation from saved outputs and localize failures by cage part."""
from pathlib import Path
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_radial_frames import OUT
from scripts.radial_validation_metrics import body_penetration,prism_jacobians
from src.clothing.wear_engine import RobloxWearEngine


def binding_jacobians(d,b,shell):
    f=b['faces'][b['face_ids']]; level=b['levels'][:,None,None]
    determinants=[]
    for low,high in ((d['reference_parent'][f],d['outer_parent'][f]),(d['target_body'][f],shell[f])):
        s=(1-level)*low+level*high
        dz=np.einsum('ni,nij->nj',b['bary'],high-low)
        determinants.append(np.einsum('ni,ni->n',np.cross(s[:,1]-s[:,0],s[:,2]-s[:,0]),dz))
    a,c=determinants
    valid=np.abs(a)>1e-12*float(np.linalg.norm(np.ptp(d['reference_parent'],axis=0)))**3
    inverted=valid&(int(d['cage_normal_sign'])*a*c<0)
    return valid,inverted


def main():
    engine=RobloxWearEngine(body_type='female')
    part_uv={}
    for name,part in engine.r15_source_cages.items():
        if name.endswith('Forearm'): continue
        for uv in part['face_uvs'].reshape(-1,2):part_uv[tuple(np.round(uv,5))]=name
    for path in sorted(OUT.glob('*.json')):
        if path.stem=='INPUT_AUDIT' or not (OUT/(path.stem+'_outputs.npz')).exists(): continue
        d=dict(np.load(OUT/(path.stem+'.npz')))
        outputs=dict(np.load(OUT/(path.stem+'_outputs.npz')))
        b=dict(np.load(OUT/(path.stem+'_binding.npz')))
        report=json.loads(path.read_text())
        parts=np.array([part_uv.get(tuple(np.round(uv,5)),'unmatched') for uv in d['target_uv'][d['uv_index']]])
        regions=parts[b['faces'][b['face_ids']][:,0]]
        for name,row in report['variants'].items():
            mesh=outputs[name]; shell=outputs[name+'_shell']
            samples=np.vstack((mesh,mesh[d['garment_faces']].mean(1)))
            print(path.stem,name,flush=True)
            stats,inside,distance=body_penetration(samples,d['body'],d['body_faces'],return_samples=True)
            row['penetration']=stats
            used=b['faces'][np.unique(b['face_ids'])]
            row['used_prism_jacobians']=prism_jacobians(d['reference_parent'],d['outer_parent'],d['target_body'],shell,used,int(d['cage_normal_sign']))
            row['prism_measurement_scope']=('counterfactual volume from production shell; production does not bind with prisms'
                if name=='production' else 'actual prism cells used by this experimental binding')
            valid,fold=binding_jacobians(d,b,shell)
            row['binding_jacobians']=dict(valid_vertices=int(valid.sum()),inverted_vertices=int(fold.sum()))
            row['regions']={region:dict(vertices=int(sum(regions==region)),
                penetrating_vertices=int(sum(inside[:len(mesh)]&(regions==region))),
                inverted_binding_vertices=int(sum(fold&(regions==region)))) for region in np.unique(regions)}
            if path.stem.startswith('blocky') and name!='production':
                ids=np.flatnonzero(inside[:len(mesh)])
                ids=ids[np.argsort(distance[ids])[-8:][::-1]]
                row['deepest_examples']=[dict(vertex=int(i),part=str(regions[i]),source=d['garment'][i].tolist(),
                    fitted=mesh[i].tolist(),depth=float(distance[i]),t=float(b['levels'][i]),
                    source_prism_residual=float(np.linalg.norm(b['residual'][i])),
                    inverted_binding=bool(fold[i]),cage_face=b['faces'][b['face_ids'][i]].tolist()) for i in ids]
        if path.stem.startswith('blocky'):
            used=b['faces'][np.unique(b['face_ids'])]
            target_inner_centers=d['target_body'][used].mean(1)
            report['target_inner_used_face_centers_inside_body']=body_penetration(target_inner_centers,d['body'],d['body_faces'])
            report['outer_used_face_centers_inside_body']={name:body_penetration(outputs[name+'_shell'][used].mean(1),d['body'],d['body_faces'])
                for name in report['variants']}
        report['measurement_version']=2
        path.write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__=='__main__':main()
