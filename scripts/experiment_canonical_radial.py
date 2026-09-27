"""Fixed six-case comparison; production stays untouched.

Run audit_radial_frames.py first, then this script. Cached source prism
bindings are invalidated by a digest of their geometry and implementation.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_radial_frames import OUT
from scripts.experiment_dual_cage_prism import closest_prism_binding
from scripts.test_r15_shirt_transfer import depth_preview
from scripts.radial_validation_metrics import distortion,seam_report,body_penetration,prism_jacobians,normals
from src.clothing.wrap_layer_fit import _local_map
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from src.clothing.experimental_canonical_radial import canonical_cages,normal_frames,similarity_scale,transfer_canonical_radial


def bind_source(data, path):
    i,o,f=data['reference_parent'],data['outer_parent'],data['projection_faces']
    valid=(np.linalg.norm(normals(i,f),axis=1)>1e-8)&(np.linalg.norm(normals(o,f),axis=1)>1e-8)
    f=f[valid]
    digest=hashlib.sha256()
    for x in (i,o,f,data['garment']): digest.update(x.tobytes())
    digest.update((ROOT/'scripts/experiment_dual_cage_prism.py').read_bytes())
    fingerprint=digest.hexdigest()
    if path.exists():
        cache=dict(np.load(path))
        if str(cache['fingerprint'])==fingerprint: return cache
    six=np.concatenate((i[f],o[f]),axis=1)
    lo,hi=six.min(1),six.max(1)
    ids=[]; levels=[]; barys=[]; residuals=[]
    for p in data['garment']:
        _,(face,t,bary,residual)=closest_prism_binding(p,i,o,f,lo,hi)
        ids.append(face);levels.append(t);barys.append(bary);residuals.append(residual)
    cache=dict(faces=f,face_ids=np.array(ids),levels=np.array(levels),bary=np.array(barys),
               residual=np.array(residuals),fingerprint=np.array(fingerprint))
    np.savez_compressed(path,**cache)
    return cache


def evaluate_binding(data,binding,shell):
    result=np.empty_like(data['garment'],dtype=float)
    parity=int(data['cage_normal_sign'])
    for v,(fid,t,b,residual) in enumerate(zip(binding['face_ids'],binding['levels'],binding['bary'],binding['residual'])):
        f=binding['faces'][fid]
        i,o,ti,to=data['reference_parent'][f],data['outer_parent'][f],data['target_body'][f],shell[f]
        section=(1-t)*i+t*o; target=(1-t)*ti+t*to
        transform=_local_map(*section,*target,normal_sign=parity)
        if transform is None: transform=_local_map(*i,*ti,normal_sign=parity)
        if transform is None: transform=_local_map(*o,*to,normal_sign=parity)
        if transform is None: raise ValueError('No usable prism residual frame')
        result[v]=b@target+transform@residual
    return result


def main():
    selected=[x for x in sys.argv[1:] if not x.startswith('--')]
    for path in sorted(OUT.glob('*.npz')):
        if path.stem.endswith(('_binding','_outputs')): continue
        if selected and path.stem not in selected: continue
        key=path.stem; d=dict(np.load(path)); p=int(d['cage_normal_sign'])
        args=[d[k] for k in ('reference_parent','outer_parent','target_body','projection_faces')]
        candidate,audit=transfer_canonical_radial(*args,d['uv_index'],parity=p,return_audit=True)
        legacy,old_audit=transfer_outer_cage_radial(*args,parity=p,radius_factor=1,return_audit=True)
        r,o,t,f,inverse=canonical_cages(*args,d['uv_index'])
        scale=similarity_scale(r,t)
        # Controlled re-encoding audit: same physical cages, logical indexing only.
        old_canonical=transfer_outer_cage_radial(r,o,t,f,parity=p,radius_factor=1,
                                                bulk_scale=old_audit['bulk_scale'])[inverse]
        change=np.linalg.norm(legacy-old_canonical,axis=1)
        report=dict(candidate=audit,legacy=old_audit,
                    old_encoding_dependence=dict(max=float(change.max()),p99=float(np.quantile(change,.99))),
                    common_metric_scale=scale,source_binding={})
        print(key,'binding',flush=True)
        binding=bind_source(d,OUT/(key+'_binding.npz'))
        report['source_binding']=dict(residual_p99=float(np.quantile(np.linalg.norm(binding['residual'],axis=1),.99)),
                                     vertices_outside_1e_minus_4=int(sum(np.linalg.norm(binding['residual'],axis=1)>1e-4)))
        shells=dict(production=d['reference_order_target_outer'],radial_previous=legacy,canonical_candidate=candidate)
        outputs=dict(production=d['baseline'],radial_previous=evaluate_binding(d,binding,legacy),
                     canonical_candidate=evaluate_binding(d,binding,candidate))
        # Common independent reference orientation for ALL variants (proxy, not a proof).
        frames,_=normal_frames(r,t,f,p)
        vertex_frames=frames[inverse][binding['faces'][binding['face_ids']]].mean(1)
        shared=np.vstack([d['body'],*outputs.values()])
        report['variants']={}
        for name,mesh in outputs.items():
            print(key,name,'metrics/render',flush=True)
            image_path=OUT/(key+'_'+name+'.png')
            samples=np.vstack((mesh,mesh[d['garment_faces']].mean(1)))
            row=dict(distortion=distortion(d['garment'],mesh,d['garment_faces'],scale,vertex_frames,p),
                     penetration=body_penetration(samples,d['body'],d['body_faces']),
                     seams=seam_report(d['outer_parent'],shells[name],d['uv_index']),
                     prism_jacobians=prism_jacobians(d['reference_parent'],d['outer_parent'],d['target_body'],shells[name],d['projection_faces'],p),
                     visibility=depth_preview(d['body'],d['body_faces'],mesh,d['garment_faces'],image_path,shared_garment_vertices=shared),
                     image=str(image_path.relative_to(ROOT)))
            report['variants'][name]=row
        np.savez_compressed(OUT/(key+'_outputs.npz'),**outputs,**{k+'_shell':v for k,v in shells.items()})
        panels=[Image.open(OUT/(key+'_'+name+'.png')).convert('RGB') for name in outputs]
        sheet=Image.new('RGB',(panels[0].width,sum(x.height+24 for x in panels)),'white')
        y=0
        for name,panel in zip(outputs,panels):
            ImageDraw.Draw(sheet).text((8,y+4),key+' | '+name,fill='black')
            sheet.paste(panel,(0,y+24));y+=panel.height+24
        sheet.save(OUT/(key+'_comparison.png'))
        (OUT/(key+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(key,'DONE',json.dumps({name:dict(edges=row['distortion']['historical_length_mask']['over_3'],
            compressed=row['distortion']['area']['under_tenth'],penetration=row['penetration']['penetrating_fraction']) for name,row in report['variants'].items()}),flush=True)

if __name__=='__main__': main()
