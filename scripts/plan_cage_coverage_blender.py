"""Compute coverage candidates without modifying scene objects (run in Blender)."""
import json
from pathlib import Path
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

out=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon\artifacts\clothing_audit')
scene=json.loads((out/'scene_snapshot.json').read_text())['objects']
mapping={'UpperTorso':'Export_torso.001','LowerTorso':'Export_pelve.001',
'LeftUpperArm':'Export_braco_superior_esquerdo.001','RightUpperArm':'Export_braco_superior_direito.001',
'LeftLowerArm':'Export_antebraco_esquerdo.001','RightLowerArm':'Export_antebraco_direito.001',
'LeftLowerLeg':'Export_canela_esquerda.001','RightLowerLeg':'Export_canela_direita.001',
'LeftUpperLeg':'Export_coxa_esquerda.001','RightUpperLeg':'Export_coxa_direita.001',
'LeftHand':'Export_mao_esquerda.001','RightHand':'Export_mao_direita.001',
'LeftFoot':'pe_esquerdo.003','RightFoot':'pe_direito.003','Head':'cabeca.001'}

def surface(vertices,faces):
    bm=bmesh.new()
    vs=[bm.verts.new(v) for v in vertices]
    for index,f in enumerate(faces):
        face=bm.faces.new([vs[i] for i in f]);face.material_index=index+1
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:
        caps=bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
        for face in caps['faces']:face.material_index=0
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.verts.index_update()
    polygons=[[v.index for v in f.verts] for f in bm.faces]
    ids=[f.material_index-1 for f in bm.faces]
    tree=BVHTree.FromPolygons([v.co.copy() for v in bm.verts],polygons,all_triangles=True)
    bm.free()
    return tree,ids,polygons

def samples(p,divisions=16):
    v=np.array(p['verts']);result=list(v)
    for f in p['faces']:
        for i in range(1,len(f)-1):
            a,b,c=v[[f[0],f[i],f[i+1]]]
            for j in range(divisions+1):
                for k in range(divisions+1-j):result.append(a+(b-a)*j/divisions+(c-a)*k/divisions)
    return np.unique(np.round(result,9),axis=0)

def outside(tree,p):
    votes=0
    for direction in [(1,.371,.217),(.193,1,.417),(.319,.237,1)]:
        origin=Vector(p);ray=Vector(direction).normalized();hits=0
        for _ in range(80):
            q,n,fi,d=tree.ray_cast(origin,ray)
            if q is None:break
            hits+=1;origin=q+ray*0.0000005
        votes+=hits%2==0
    return votes>=2

def assess(v,faces,points):
    tree,ids,_=surface(v,faces)
    signed=[]
    for p in points:
        q,n,fi,d=tree.find_nearest(Vector(p))
        if ids[fi]<0:continue
        signed.append(d if outside(tree,p) else -d)
    signed=np.array(signed)
    return {'outside_samples':int((signed>0.00001).sum()),'max_signed_distance':float(signed.max()),'samples':len(points),'surface_samples':len(signed)}

plan={}
for name,body in mapping.items():
    cage=scene[name+'_OuterCage'];v=np.array(cage['verts']);p=samples(scene[body]);before=assess(v,cage['faces'],p)
    after=before;candidate=v.copy();margin=0
    if before['outside_samples']:
        for step in range(100):
            tree,ids,_=surface(candidate,cage['faces'])
            shifts=[[] for _ in candidate]
            for point in p:
                q,n,fi,d=tree.find_nearest(Vector(point))
                index=ids[fi]
                if index<0:continue  # temporary joint caps are not exported surfaces
                is_out=outside(tree,point)
                signed=d if is_out else -d
                if signed>-0.001:
                    direction=(Vector(point)-q) if is_out else (q-Vector(point))
                    if direction.length<1e-8:direction=n
                    delta=np.array(direction.normalized())*(signed+0.001)
                    for vi in cage['faces'][index]:shifts[vi].append(delta)
            if not any(shifts):break
            for vi,ss in enumerate(shifts):
                if ss:candidate[vi]+=np.mean(ss,axis=0)*0.85
            after=assess(candidate,cage['faces'],p)
            if after['max_signed_distance']<=-0.0005:break
        margin=float(np.linalg.norm(candidate-v,axis=1).max())
    plan[name]={'before':before,'after':after,'radial_offset':margin,'verts':candidate.tolist(),'old_verts':v.tolist(),'faces':cage['faces'],'uv':cage['uv']}
    print(name,before,'offset',margin,'after',after)
points_by_part={name:samples(scene[body]) for name,body in mapping.items()}
points_by_part['UpperTorso']=np.vstack([points_by_part['UpperTorso'],samples(scene['pecoco.001'],48)])
for iteration in range(40):
    surfaces={name:surface(p['verts'],p['faces']) for name,p in plan.items()}
    boxes={name:(np.min(p['verts'],axis=0)-1e-6,np.max(p['verts'],axis=0)+1e-6) for name,p in plan.items()}
    corrections={}
    total=0
    for name,points in points_by_part.items():
        uncovered=[]
        for point in points:
            covered=False
            for other,(tree,_,_) in surfaces.items():
                lo,hi=boxes[other]
                if np.all(point>=lo) and np.all(point<=hi) and not outside(tree,point):covered=True;break
            if covered:continue
            uncovered.append(point.tolist());total+=1
            target=name
            if name=='UpperTorso':
                target=min(['UpperTorso','Head'],key=lambda k:surfaces[k][0].find_nearest(Vector(point))[3])
            tree,ids,tris=surfaces[target]
            q,n,fi,d=tree.find_nearest(Vector(point))
            direction=Vector(point)-q
            if direction.length<1e-8:direction=n
            delta=np.array(direction.normalized())*(d+0.001)
            for vi in tris[fi]:corrections.setdefault((target,vi),[]).append(delta)
        plan[name]['uncovered_by_union']=uncovered
    if total==0:break
    for (name,vi),deltas in corrections.items():
        plan[name]['verts'][vi]=(np.array(plan[name]['verts'][vi])+np.mean(deltas,axis=0)).tolist()
for name,p in plan.items():
    p['after']=assess(p['verts'],p['faces'],samples(scene[mapping[name]]))
    p['max_vertex_displacement']=float(np.linalg.norm(np.array(p['verts'])-p['old_verts'],axis=1).max())
    print('UNION',name,len(p['uncovered_by_union']),'max displacement',p['max_vertex_displacement'])
(out/'coverage_plan.json').write_text(json.dumps(plan),encoding='utf-8')
