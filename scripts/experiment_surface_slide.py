"""Surface-binding slide on contacting cylinders, including a closed-ring gate.

No old shell correction is called. The carrier radius and normal offset remain
fixed; only angular surface associations change. This deliberately restricted
control cannot establish support for arbitrary cages or closed garments.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.experimental_surface_slide import slide_open_arc,closed_ring_obstruction
from scripts.synthetic_wrap_fixture import cylinder
from scripts.radial_validation_metrics import normals
from scripts.test_r15_shirt_transfer import depth_preview

OUT=ROOT/'artifacts/clothing_audit/surface_slide'
RADIUS=.29
CARRIER_RADIUS=.24
MARGIN=.002


def strip(theta):
    z=np.linspace(.25,1.75,13)
    vertices=np.array([[RADIUS*np.cos(a),RADIUS*np.sin(a),h] for h in z for a in theta])
    faces=[];n=len(theta)
    for j in range(len(z)-1):
        for i in range(n-1):
            a=j*n+i;faces.extend(((a,a+1,a+n+1),(a,a+n+1,a+n)))
    return vertices,np.array(faces)


def body(distance):
    a,af=cylinder(.2,17,64,closed=True);b,bf=cylinder(.3,17,64,closed=True)
    return np.vstack((a,b+[distance,0,0])),np.vstack((af,bf+len(a)))


def metrics(source,result,faces,distance):
    edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
    lengths=[np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1) for v in (source,result)]
    ratio=lengths[1]/lengths[0]
    samples=np.vstack((result,result[edges].mean(1),result[faces].mean(1)))
    arm=np.linalg.norm(samples[:,:2],axis=1)
    neighbor=np.linalg.norm(samples[:,:2]-[distance,0],axis=1)
    inside=((arm<.2-1e-9)|(neighbor<.3-1e-9))&(samples[:,2]>0)&(samples[:,2]<2)
    a0,a1=[np.linalg.norm(normals(v,faces),axis=1) for v in (source,result)]
    return dict(samples=len(samples),penetrating=int(sum(inside)),minimum_neighbor_clearance=float((neighbor-.3).min()),
                minimum_arm_clearance=float((arm-.2).min()),edge_ratio_min=float(ratio.min()),edge_ratio_max=float(ratio.max()),
                face_area_ratio_min=float((a1/a0).min()),
                maximum_vertex_displacement=float(np.linalg.norm(result-source,axis=1).max()),
                normal_offset_error_max=float(np.abs(np.linalg.norm(result[:,:2],axis=1)-CARRIER_RADIUS-.05).max()),
                note='vertex/edge-midpoint/face-center samples; no continuous collision certificate')


def main():
    OUT.mkdir(exist_ok=True)
    report=dict(method='angular surface-coordinate QP, fixed axial coordinates and normal offset',
                constants=dict(carrier_radius=CARRIER_RADIUS,garment_radius=RADIUS,body_radius=.2,
                               neighbor_radius=.3,clearance_margin=MARGIN,edge_strain_limit=.1),cases={})
    for name,distance in [('open_clear',.8),('open_contact',.5)]:
        theta=np.linspace(.05,.85,17)
        fitted,audit=slide_open_arc(theta,RADIUS,distance,.3,MARGIN)
        source,faces=strip(theta);result,_=strip(fitted);bv,bf=body(distance)
        report['cases'][name]=dict(solver=audit,before=metrics(source,source,faces,distance),
                                  after=metrics(source,result,faces,distance))
        np.savez_compressed(OUT/(name+'.npz'),source=source,fitted=result,faces=faces,
                            original_theta=theta,fitted_theta=fitted,body=bv,body_faces=bf)
        panels=[];shared=np.vstack((bv,source,result))
        for label,mesh in [('initial_binding',source),('slid_binding',result)]:
            path=OUT/(name+'_'+label+'.png')
            depth_preview(bv,bf,mesh,faces,path,shared_garment_vertices=shared)
            panels.append(Image.open(path).convert('RGB'))
        sheet=Image.new('RGB',(panels[0].width,sum(p.height+24 for p in panels)),'white');y=0
        for label,panel in zip(('Correspondencia inicial','Correspondencia deslizada'),panels):
            ImageDraw.Draw(sheet).text((8,y+4),name+' | '+label,fill='black');sheet.paste(panel,(0,y+24));y+=panel.height+24
        sheet.save(OUT/(name+'_comparison.png'))
    # Negative control: whole closed sleeve has nonzero winding around the arm.
    closed,cf=cylinder(RADIUS,13,32,.25,1.75)
    bv,bf=body(.5)
    obstruction=closed_ring_obstruction(RADIUS,.5,.3,MARGIN)
    report['closed_contact']=dict(before=metrics(closed,closed,cf,.5),obstruction=obstruction,
        optimized=False,reason='no admissible continuous degree-one binding exists on this fixed-radius chart')
    depth_preview(bv,bf,closed,cf,OUT/'closed_contact.png',shared_garment_vertices=np.vstack((bv,closed)))
    np.savez_compressed(OUT/'closed_contact.npz',source=closed,faces=cf,body=bv,body_faces=bf)
    report['integration_gate_passed']=False
    paths=[Path(__file__),ROOT/'src/clothing/experimental_surface_slide.py',ROOT/'tests/test_experimental_surface_slide.py',
           ROOT/'scripts/synthetic_wrap_fixture.py',ROOT/'scripts/test_r15_shirt_transfer.py']
    report['sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
