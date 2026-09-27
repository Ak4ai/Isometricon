"""Body-union clearance trial using frozen radial/prism controls."""
from pathlib import Path
import json
import sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_radial_frames import OUT as INPUT
from scripts.experiment_canonical_radial import bind_source,evaluate_binding
from scripts.radial_validation_metrics import body_components,body_penetration,distortion,seam_report,prism_jacobians
from scripts.test_r15_shirt_transfer import depth_preview
from scripts.audit_canonical_radial_results import binding_jacobians
from src.clothing.experimental_shell_clearance import ClosedBodyUnion,project_shell_clearance
from src.clothing.experimental_prism_constraints import PrismShapeConstraints

OUT=ROOT/'artifacts/clothing_audit/shell_clearance'


def write_comparison(key):
    names=['before','after','cage_before','cage_after']
    labels=['Camisa: radial anterior','Camisa: correcao experimental',
            'Cage anterior: apenas faces usadas pela camisa; recortes da selecao',
            'Cage corrigida: apenas faces usadas pela camisa; recortes da selecao']
    images=[Image.open(OUT/(key+'_'+name+'.png')).convert('RGB') for name in names]
    sheet=Image.new('RGB',(images[0].width,sum(im.height+24 for im in images)),'white')
    y=0
    for i,(label,im) in enumerate(zip(labels,images)):
        ImageDraw.Draw(sheet).text((8,y+4),label,fill='black')
        sheet.paste(im,(0,y+24));y+=im.height+24
        if i==1:sheet.crop((0,0,sheet.width,y)).save(OUT/(key+'_garment_comparison.png'))
    sheet.save(OUT/(key+'_comparison.png'))


def main():
    global OUT
    guarded='--prism-guard' in sys.argv
    if guarded:OUT=ROOT/'artifacts/clothing_audit/prism_clearance'
    OUT.mkdir(exist_ok=True)
    chosen=[arg for arg in sys.argv[1:] if not arg.startswith('--')] or ['blocky_133331049150205']
    for key in chosen:
        d=dict(np.load(INPUT/(key+'.npz')))
        previous=dict(np.load(INPUT/(key+'_outputs.npz')))
        old=json.loads((INPUT/(key+'.json')).read_text())
        binding=bind_source(d,INPUT/(key+'_binding.npz'))
        faces=binding['faces'][np.unique(binding['face_ids'])]
        parts=body_components(d['body'],d['body_faces'])
        closed=[ids for ids,is_closed in parts if is_closed]
        body=ClosedBodyUnion(d['body'],d['body_faces'],closed)
        baseline=previous['radial_previous_shell']
        def factory(x,inverse):
            return PrismShapeConstraints(x,inverse,d['reference_parent'],d['outer_parent'],d['target_body'],faces,
                binding['faces'][binding['face_ids']],binding['bary'],binding['levels'],int(d['cage_normal_sign']))
        print(key,'projection',flush=True)
        corrected,audit=project_shell_clearance(d['outer_parent'],baseline,d['projection_faces'],faces,body,
            margin=float(np.ptp(d['body'][:,2]))*1e-4,local_steps='--global-step' not in sys.argv,
            constraint_factory=factory if guarded else None)
        print(key,'solver',json.dumps({k:v for k,v in audit.items() if k!='history'}),flush=True)
        fitted=evaluate_binding(d,binding,corrected)
        outputs={'before':previous['radial_previous'],'after':fitted}
        shells={'before':baseline,'after':corrected}
        report={'case':key,'solver':audit,'closed_components':len(closed),'open_components':len(parts)-len(closed),'variants':{}}
        shared=np.vstack([d['body'],*outputs.values(),baseline[faces].reshape(-1,3),corrected[faces].reshape(-1,3)])
        for name,mesh in outputs.items():
            print(key,name,'validation',flush=True)
            valid,inverted=binding_jacobians(d,binding,shells[name])
            row=dict(distortion=distortion(d['garment'],mesh,d['garment_faces'],old['common_metric_scale']),
                penetration=body_penetration(np.vstack([mesh,mesh[d['garment_faces']].mean(1)]),d['body'],d['body_faces']),
                cage_centers_penetration=body_penetration(shells[name][faces].mean(1),d['body'],d['body_faces']),
                seams=seam_report(d['outer_parent'],shells[name],d['uv_index']),
                used_prism_jacobians=prism_jacobians(d['reference_parent'],d['outer_parent'],d['target_body'],shells[name],faces,int(d['cage_normal_sign'])),
                binding_inversions=int(inverted.sum()),binding_valid=int(valid.sum()))
            row['visibility']=depth_preview(d['body'],d['body_faces'],mesh,d['garment_faces'],OUT/(key+'_'+name+'.png'),shared_garment_vertices=shared)
            depth_preview(d['body'],d['body_faces'],shells[name],faces,OUT/(key+'_cage_'+name+'.png'),shared_garment_vertices=shared)
            report['variants'][name]=row
        (OUT/(key+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
        np.savez_compressed(OUT/(key+'.npz'),before=outputs['before'],after=fitted,before_shell=baseline,after_shell=corrected)
        write_comparison(key)
        print(key,'DONE',json.dumps({n:{'edges':r['distortion']['historical_length_mask']['over_3'],
            'compressed':r['distortion']['area']['under_tenth'],'penetration':r['penetration']['penetrating_fraction'],
            'cage_centers_inside':r['cage_centers_penetration']['penetrating_samples']} for n,r in report['variants'].items()}),flush=True)

if __name__=='__main__':main()
