"""Experimental WrapLayer cage-to-body mapping for the cached office shirt."""
from pathlib import Path
import sys
import json
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.clothing.wear_engine import RobloxWearEngine, closest_point_on_triangle, decode_roblox_float_be

ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'artifacts/clothing_audit/office_shirt_wraplayer'
engine=RobloxWearEngine(body_type='female')
shirt,faces,uvs,face_uvs=engine.load_obj(str(ROOT/'assets/models/clothing/-_office_shirt__BLACK_133331049150205.obj'))
rbxm=(ROOT/'assets/models/clothing/-_office_shirt__BLACK_133331049150205.rbxm').read_bytes()
def origin(name):
    key=name.encode('ascii')
    at=rbxm.index(key)+len(key)
    assert rbxm[at:at+2]==b'\x10\x02'
    return np.array([decode_roblox_float_be(rbxm[at+2+i*4:at+6+i*4]) for i in range(3)])
cage_origin=origin('CageOrigin')
reference_origin=origin('ReferenceOrigin')
shirt=shirt.copy()
shirt[:,1]-=cage_origin[1]
src,src_faces,src_uv,_=engine.load_obj(str(DIR/'reference.obj'))
cage,cage_faces,cage_uv,_=engine.load_obj(str(DIR/'cage.obj'))
dst_uv=[];dst_xyz=[]
for name,part in engine.r15_female_cages.items():
    if name.endswith('Forearm'):continue
    for face,tri_uv in zip(part['faces'],part['face_uvs']):
        for idx,uv in zip(face,tri_uv):
            dst_uv.append(uv);dst_xyz.append(part['verts'][idx])
unique={tuple(np.round(u,5)):p for u,p in zip(dst_uv,dst_xyz)}
target_uv=np.asarray(list(unique));target_xyz=np.asarray(list(unique.values()))
lookup=np.concatenate([((chunk[:,None,:]-target_uv[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(src_uv,50)])
uv_error=np.linalg.norm(src_uv-target_uv[lookup],axis=1)
assert uv_error.max()<2e-5,uv_error.max()
dst=target_xyz[lookup]
cage_lookup=np.concatenate([((chunk[:,None,:]-cage_uv[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(src_uv,50)])
assert np.linalg.norm(src_uv-cage_uv[cage_lookup],axis=1).max()<2e-5
cage_aligned=cage[cage_lookup]
delta=cage_aligned-src
scale=0.4456
outer=dst+delta[:,[0,2,1]]*np.array([-scale,scale,scale])
a,b,c=cage_aligned[src_faces[:,0]],cage_aligned[src_faces[:,1]],cage_aligned[src_faces[:,2]]
da,db,dc=outer[src_faces[:,0]],outer[src_faces[:,1]],outer[src_faces[:,2]]
centroids=(a+b+c)/3
output=np.empty_like(shirt)
distances=[]
for i,p in enumerate(shirt):
    candidate=np.argpartition(((centroids-p)**2).sum(1),min(40,len(centroids)-1))[:40]
    best=(float('inf'),None)
    for t in candidate:
        q,u,v,w=closest_point_on_triangle(p,a[t],b[t],c[t])
        dist=float(np.linalg.norm(p-q))
        if dist<best[0]:best=(dist,(t,q,u,v,w))
    dist,(t,q,u,v,w)=best
    distances.append(dist)
    src_n=np.cross(b[t]-a[t],c[t]-a[t]);src_n/=max(np.linalg.norm(src_n),1e-12)
    dst_n=np.cross(db[t]-da[t],dc[t]-da[t]);dst_n/=max(np.linalg.norm(dst_n),1e-12)
    # The signed offset is scaled from Roblox units to the target's metres.
    signed=np.dot(p-q,src_n)
    output[i]=u*da[t]+v*db[t]+w*dc[t]+signed*0.4456*dst_n

path=DIR/'shirt_reference_to_body.obj'
with path.open('w',encoding='utf-8') as fp:
    for p in output:fp.write(f'v {p[0]:.9f} {p[2]:.9f} {-p[1]:.9f}\n')
    for uv in uvs:fp.write(f'vt {uv[0]:.9f} {uv[1]:.9f}\n')
    for face,tri_uv in zip(faces,face_uvs):
        fp.write('f '+' '.join(f'{i+1}/{j+1}' for i,j in zip(face,tri_uv))+'\n')
report={'uv_error_max':float(uv_error.max()),'source_distance_quantiles':np.quantile(distances,[0,.5,.9,.99,1]).tolist(),
        'cage_origin':cage_origin.tolist(),'reference_origin':reference_origin.tolist(),
        'output_bounds':{'min':output.min(0).tolist(),'max':output.max(0).tolist()},'finite':bool(np.isfinite(output).all())}
(DIR/'mapping_test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
