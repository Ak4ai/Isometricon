"""Locate concrete Blocky collisions before visible-mesh residual transport."""
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_radial_frames import OUT
from scripts.radial_validation_metrics import body_penetration
from scripts.test_r15_shirt_transfer import FBX
from src.clothing.wear_engine import RobloxWearEngine
import scripts.inspect_classic_mannequin_fbx as fbx


def body_parts():
    fbx.DATA=FBX.read_bytes()
    root=fbx.nodes(27,len(fbx.DATA))
    objects=next(c for n,p,c in root if n=='Objects')
    connections=next(c for n,p,c in root if n=='Connections')
    models={p[0]:p[1].split('\x00')[0] for n,p,c in objects if n=='Model'}
    parents={p[1]:p[2] for n,p,c in connections if n=='C' and p[0]=='OO'}
    result={}
    for n,p,c in objects:
        name=models.get(parents.get(p[0]),'') if n=='Geometry' else ''
        if not name.endswith('_Geo'):continue
        fields={n:p[0] for n,p,_ in c if n in ('Vertices','PolygonVertexIndex')}
        v=np.asarray(fields['Vertices']).reshape(-1,3)[:,[0,2,1]]
        faces=[];poly=[]
        for encoded in fields['PolygonVertexIndex']:
            poly.append(encoded if encoded>=0 else -encoded-1)
            if encoded<0:
                faces.extend((poly[0],poly[j],poly[j+1]) for j in range(1,len(poly)-1));poly=[]
        result[name]=(v,np.array(faces))
    return result


def main():
    key='blocky_133331049150205'
    d=dict(np.load(OUT/(key+'.npz')));b=dict(np.load(OUT/(key+'_binding.npz')))
    outputs=dict(np.load(OUT/(key+'_outputs.npz')))
    mesh=outputs['canonical_candidate'];shell=outputs['canonical_candidate_shell']
    _,mask,dist=body_penetration(mesh,d['body'],d['body_faces'],return_samples=True)
    # Select deepest and highest penetrating samples, not a garment-specific fix.
    available=np.flatnonzero(mask)
    selected=np.unique(np.r_[available[np.argsort(dist[available])[-8:]],
                             available[np.argsort(mesh[available,2])[-8:]]])
    engine=RobloxWearEngine(body_type='female')
    uv_parts={tuple(np.round(uv,5)):name for name,part in engine.r15_source_cages.items()
              if not name.endswith('Forearm') for uv in part['face_uvs'].reshape(-1,2)}
    cage_parts=np.array([uv_parts.get(tuple(np.round(uv,5)),'unknown') for uv in d['target_uv'][d['uv_index']]])
    regions=cage_parts[b['faces'][b['face_ids']][:,0]]
    for region in np.unique(regions):
        ids=np.flatnonzero(mask&(regions==region))
        selected=np.unique(np.r_[selected,ids[np.argsort(dist[ids])[-3:]],ids[np.argsort(mesh[ids,2])[-3:]]])
    report=[]; parts=body_parts()
    for index in selected:
        f=b['faces'][b['face_ids'][index]];bary=b['bary'][index];t=float(b['levels'][index])
        inner=bary@d['target_body'][f];outer=bary@shell[f]
        middle=(1-t)*inner+t*outer
        points=np.array([inner,outer,middle,mesh[index]])
        hits={}
        for name,(v,faces) in parts.items():
            _,hit,_=body_penetration(points,v,faces,return_samples=True)
            if hit.any():hits[name]=hit.tolist()
        report.append(dict(vertex=int(index),binding_region=str(regions[index]),source=d['garment'][index].tolist(),
                           target_inner=inner.tolist(),target_outer=outer.tolist(),
                           prism_without_residual=middle.tolist(),final=mesh[index].tolist(),
                           t=t,source_residual=float(np.linalg.norm(b['residual'][index])),
                           distance_to_body_surface=float(dist[index]),
                           hit_order=['target_inner','target_outer','prism_without_residual','final'],body_part_hits=hits))
    (OUT/'BLOCKY_CLEARANCE_WITNESSES.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(witnesses=len(report),by_binding_region={r:sum(x['binding_region']==r for x in report) for r in np.unique(regions)})))

if __name__=='__main__':main()
