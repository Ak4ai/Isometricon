"""Read-only validation of live stage-2 geometry, with baseline comparisons."""
import bpy,bmesh,json
import numpy as np
from pathlib import Path
from collections import defaultdict
from mathutils.bvhtree import BVHTree
from mathutils import Vector

root=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon')
out=root/'artifacts/clothing_audit'
exec((root/'scripts/plan_cage_coverage_blender.py').read_text(encoding='utf-8').split('plan={}')[0])
plan=json.loads((out/'coverage_plan.json').read_text())

def triangulate(v,faces):
    bm=bmesh.new();vs=[bm.verts.new(p) for p in v]
    for i,f in enumerate(faces):bm.faces.new([vs[j] for j in f]).material_index=i
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.verts.index_update()
    triangles=np.array([[x.index for x in f.verts] for f in bm.faces])
    owners=[f.material_index for f in bm.faces]
    bm.free()
    return triangles,owners

def segment_hit(a,b,t):
    direction=b-a;e1=t[1]-t[0];e2=t[2]-t[0];h=np.cross(direction,e2);det=np.dot(e1,h)
    if abs(det)<1e-12:return False
    delta=a-t[0];u=np.dot(delta,h)/det;q=np.cross(delta,e1);w=np.dot(direction,q)/det;s=np.dot(e2,q)/det
    return u>1e-7 and w>1e-7 and u+w<1-1e-7 and 1e-7<s<1-1e-7

def geometry(v,faces):
    v=np.array(v);tri,owners=triangulate(v,faces);xyz=v[tri]
    cross=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0]);areas=np.linalg.norm(cross,axis=1)*.5
    edges=defaultdict(list)
    for fi,f in enumerate(faces):
        for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))].append((fi,a,b))
    winding=[list(k) for k,e in edges.items() if len(e)==2 and e[0][1:]==e[1][1:]]
    tree=BVHTree.FromPolygons(v.tolist(),tri.tolist(),all_triangles=True)
    crossings=set()
    for i,j in tree.overlap(tree):
        if i>=j or owners[i]==owners[j] or set(tri[i])&set(tri[j]):continue
        a,b=xyz[i],xyz[j]
        if any(segment_hit(a[k],a[(k+1)%3],b) or segment_hit(b[k],b[(k+1)%3],a) for k in range(3)):
            crossings.add(tuple(sorted((owners[i],owners[j]))))
    bm=bmesh.new();vs=[bm.verts.new(p) for p in v]
    for f in faces:bm.faces.new([vs[i] for i in f])
    bm.normal_update();original=[(f,f.normal.copy()) for f in bm.faces]
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
    reversed_faces=[i for i,(f,n) in enumerate(original) if f.normal.dot(n)<0]
    bm.free()
    return {'vertices':len(v),'faces':len(faces),'triangles':len(tri),'boundary_edges':sum(len(e)==1 for e in edges.values()),
      'inward_faces_against_closed_orientation':reversed_faces,
      'nonmanifold_edges':sum(len(e)>2 for e in edges.values()),'inconsistent_winding_edges':winding,
      'degenerate_triangles_1e12':np.flatnonzero(areas<1e-12).tolist(),'minimum_triangle_area':float(areas.min()),
      'nonadjacent_surface_crossings':[list(p) for p in sorted(crossings)]}

result={'file':bpy.data.filepath,'parts':{},'coverage':{}}
trees={};boxes={}
for name,p in plan.items():
    current=scene[name+'_OuterCage'];v=np.array(current['verts'])
    faces=current['faces'];uv=np.array(current['uv'])
    row={'current':geometry(v,faces),'before_stage2':geometry(p['old_verts'],p['faces']),
      'faces_unchanged':faces==p['faces'],'uv_unchanged':bool(np.array_equal(uv,np.array(p['uv']))),
      'max_difference_from_applied_plan':float(np.linalg.norm(v-p['verts'],axis=1).max())}
    result['parts'][name]=row
    trees[name]=surface(v,faces)[0];boxes[name]=(v.min(0)-1e-6,v.max(0)+1e-6)
    print(name,json.dumps(row['current']))
for name,body in dict(mapping,Neck='pecoco.001').items():
    pts=samples(scene[body],24)
    uncovered=[]
    for pt in pts:
        if not any(np.all(pt>=boxes[n][0]) and np.all(pt<=boxes[n][1]) and not outside(tree,pt) for n,tree in trees.items()):uncovered.append(pt.tolist())
    result['coverage'][name]={'samples':len(pts),'uncovered':len(uncovered),'points':uncovered}
(out/'stage3_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('COVERAGE',sum(p['samples'] for p in result['coverage'].values()),'UNCOVERED',sum(p['uncovered'] for p in result['coverage'].values()))
