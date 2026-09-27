"""Read-only static placement/clearance audit at frozen Blocky witnesses.

Deliberately supports only the inspected root mesh transforms and X-only
skeleton ancestor rotations. Reject unsupported FBX features rather than
pretend to be a general FBX importer. Does not refit clothing.
"""
from pathlib import Path
import json
import hashlib
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import scripts.inspect_classic_mannequin_fbx as parser
from scripts.test_r15_shirt_transfer import FBX
from scripts.radial_validation_metrics import body_penetration

OUT=ROOT/'artifacts/clothing_audit/blocky_target_placement'
INPUT=ROOT/'artifacts/clothing_audit/radial_frames'


def properties(children):
    return {p[0]:p[4:] for name,_,items in children if name=='Properties70'
            for n,p,_ in items if n=='P'}


def local_matrix(props):
    for key in ('PreRotation','PostRotation','RotationPivot','ScalingPivot','RotationOffset','ScalingOffset',
                'GeometricTranslation','GeometricRotation'):
        if np.linalg.norm(props.get(key,[0,0,0]))>1e-10:
            raise ValueError('Unsupported '+key)
    if not np.allclose(props.get('GeometricScaling',[1,1,1]),1):
        raise ValueError('Unsupported geometric scale')
    r=np.array(props.get('Lcl Rotation',[0,0,0]),float)
    if np.linalg.norm(r[1:])>1e-10:
        raise ValueError('Audit only supports X-axis local rotation')
    angle=np.deg2rad(r[0]); c,s=np.cos(angle),np.sin(angle)
    m=np.eye(4);m[:3,:3]=np.array([[1,0,0],[0,c,-s],[0,s,c]])@np.diag(props.get('Lcl Scaling',[1,1,1]))
    m[:3,3]=props.get('Lcl Translation',[0,0,0])
    return m


def apply(points,m):
    return points@m[:3,:3].T+m[:3,3]


def section_segments(vertices,faces,z):
    segments=[]
    for tri in vertices[faces]:
        points=[]
        for i,j in ((0,1),(1,2),(2,0)):
            a,b=tri[i],tri[j]
            if (a[2]<=z<b[2]) or (b[2]<=z<a[2]):
                t=(z-a[2])/(b[2]-a[2]);points.append((a+t*(b-a))[:2])
        if len(points)==2:segments.append(points)
    return segments


def main():
    OUT.mkdir(exist_ok=True)
    parser.DATA=FBX.read_bytes();root=parser.nodes(27,len(parser.DATA))
    objects=next(c for n,p,c in root if n=='Objects');connections=next(c for n,p,c in root if n=='Connections')
    models={p[0]:(p[1].split('\x00')[0],properties(c)) for n,p,c in objects if n=='Model'}
    # A bone also connects to skin clusters. Those OO links are NOT parents.
    parents={p[1]:p[2] for n,p,c in connections if n=='C' and p[0]=='OO' and (p[2] in models or p[2]==0)}
    ids={name:i for i,(name,_) in models.items()}
    world_cache={0:np.eye(4)}
    def world(i):
        if i not in world_cache:
            world_cache[i]=world(parents.get(i,0))@local_matrix(models[i][1])
        return world_cache[i]
    wanted=('UpperTorso','LeftUpperArm','LeftLowerArm','RightUpperArm','RightLowerArm')
    parts={};uv={};transforms={}
    for n,p,c in objects:
        if n!='Geometry':continue
        mid=parents.get(p[0]);name=models.get(mid,('',{}))[0]
        if name not in [part+suffix for part in wanted for suffix in ('_Geo','_OuterCage')]:continue
        if parents.get(mid)!=0:raise ValueError('Selected mesh is not a root child')
        fields={nn:pp[0] for nn,pp,_ in c if nn in ('Vertices','PolygonVertexIndex')}
        raw=np.array(fields['Vertices']).reshape(-1,3);m=world(mid)
        transformed=apply(raw,m)[:,[0,2,1]]
        transforms[name]=dict(parent=0,properties=models[mid][1],
            max_ignored_displacement=float(np.linalg.norm(apply(raw,m)-raw,axis=1).max()))
        indices=fields['PolygonVertexIndex'];poly=[];faces=[]
        for encoded in indices:
            poly.append(encoded if encoded>=0 else -encoded-1)
            if encoded<0:
                faces.extend((poly[0],poly[j],poly[j+1]) for j in range(1,len(poly)-1));poly=[]
        if name.endswith('_Geo'):
            parts[name]=(transformed,np.array(faces))
        else:
            layer=next(cc for nn,pp,cc in c if nn=='LayerElementUV')
            fields_uv={nn:pp[0] for nn,pp,_ in layer if nn in ('UV','UVIndex')}
            coords=np.array(fields_uv['UV']).reshape(-1,2)
            for encoded,ui in zip(indices,fields_uv['UVIndex']):
                vi=encoded if encoded>=0 else -encoded-1
                uv[tuple(np.round(coords[ui],5))]=(raw[vi,[0,2,1]],transformed[vi])
    # Compare current skeleton globals with ALL stored bind poses for these bones.
    bind_errors={part:[] for part in wanted}
    for n,p,c in objects:
        if n!='Pose':continue
        for nn,pp,cc in c:
            if nn!='PoseNode':continue
            data={a:b[0] for a,b,_ in cc}
            name=models.get(data.get('Node'),('',{}))[0]
            if name in wanted:
                matrix=np.array(data['Matrix']).reshape(4,4).T
                bind_errors[name].append(float(np.abs(world(data['Node'])-matrix).max()))
    d=dict(np.load(INPUT/'blocky_133331049150205.npz'));b=dict(np.load(INPUT/'blocky_133331049150205_binding.npz'))
    old=json.loads((ROOT/'artifacts/clothing_audit/blocky_influences/UNMIXED_STAGES.json').read_text())
    matched=[(i,uv[tuple(np.round(t,5))]) for i,t in enumerate(d['target_uv'][d['uv_index']]) if tuple(np.round(t,5)) in uv]
    report=dict(mesh_transforms=transforms,
        skeleton_current_vs_bind_pose_max_matrix_error={k:max(v) if v else None for k,v in bind_errors.items()},
        compared_cage_entries=len(matched),
        frozen_cage_vs_raw_fbx_max_error=max(float(np.linalg.norm(d['target_body'][i]-v[0])) for i,v in matched),
        ignored_cage_transform_max_error=max(float(np.linalg.norm(d['target_body'][i]-v[1])) for i,v in matched),witnesses=[])
    panels=[];colors=[(46,98,160),(205,126,40)]
    for witness in old['witnesses']:
        vertex=witness['vertex'];f=b['faces'][b['face_ids'][vertex]]
        corrected=np.array([uv[tuple(np.round(d['target_uv'][d['uv_index'][i]],5))][1] for i in f])
        inner=b['bary'][vertex]@corrected
        raw_inner=np.array(witness['stages']['inner']);outer=np.array(witness['stages']['outer'])
        direction=outer-raw_inner; direction/=np.linalg.norm(direction)
        distances=np.array([-.04,-.01,-.005,-.001,0,.001,.005,.01,.04])
        query=inner+distances[:,None]*np.array([1.,0,0])
        pair=([witness['region']+'_Geo',next(iter(witness['body_parts_hit']))])
        pair=list(dict.fromkeys(pair));hits={}
        for name in pair:
            verts,faces=parts[name]
            _,hit,_=body_penetration(query,verts,faces,return_samples=True)
            _,out_hit,_=body_penetration(inner+np.array([.001,.005,.01,.04])[:,None]*direction,verts,faces,return_samples=True)
            hits[name]=dict(x_probe_inside=hit.tolist(),transport_direction_inside=out_hit.tolist())
        row=dict(vertex=vertex,corrected_inner=inner.tolist(),correction=float(np.linalg.norm(inner-raw_inner)),
                 x_offsets=distances.tolist(),transport_direction=direction.tolist(),
                 transport_offsets=[.001,.005,.01,.04],hits=hits)
        report['witnesses'].append(row)
        panel=Image.new('RGB',(600,540),'white');draw=ImageDraw.Draw(panel)
        draw.text((12,10),f'Vertice {vertex} | corte XY em Z={inner[2]:.4f}',fill='black')
        def screen(p):return (300+(p[0]-inner[0])*500,290-(p[1]-inner[1])*500)
        for name,color in zip(pair,colors):
            verts,faces=parts[name]
            for a,z in section_segments(verts,faces,inner[2]):draw.line([screen(a),screen(z)],fill=color,width=3)
            draw.text((12,34+18*pair.index(name)),name,fill=color)
        draw.line([screen(inner),screen(inner+direction*.2)],fill=(170,30,40),width=3)
        x,y=screen(inner);draw.ellipse((x-5,y-5,x+5,y+5),fill=(170,30,40))
        draw.text((12,510),'Vermelho: inner corrigida e direcao do transporte (projecao XY).',fill='black')
        panels.append(panel)
    sheet=Image.new('RGB',(600*len(panels),540),'white')
    for i,panel in enumerate(panels):sheet.paste(panel,(600*i,0))
    sheet.save(OUT/'sections.png')
    files=[Path(__file__),FBX,INPUT/'blocky_133331049150205.npz',INPUT/'blocky_133331049150205_binding.npz',
           ROOT/'scripts/inspect_classic_mannequin_fbx.py',ROOT/'artifacts/clothing_audit/blocky_influences/UNMIXED_STAGES.json']
    report['sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('mesh_transforms','sha256')},indent=2))


if __name__=='__main__':main()
