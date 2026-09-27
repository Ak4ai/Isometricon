"""Independent denser surface sampling of the proposed cages, including neck."""
from pathlib import Path
root=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon')
exec((root/'scripts/plan_cage_coverage_blender.py').read_text(encoding='utf-8').split('plan={}')[0])
plan=json.loads((out/'coverage_plan.json').read_text())
trees={n:surface(p['verts'],p['faces'])[0] for n,p in plan.items()}
boxes={n:(np.min(p['verts'],axis=0)-1e-6,np.max(p['verts'],axis=0)+1e-6) for n,p in plan.items()}
result={}
for name,body in dict(mapping,Neck='pecoco.001').items():
    points=samples(scene[body],24)
    uncovered=[]
    for pt in points:
        if not any(np.all(pt>=boxes[k][0]) and np.all(pt<=boxes[k][1]) and not outside(t,pt) for k,t in trees.items()):uncovered.append(pt.tolist())
    result[name]={'samples':len(points),'uncovered':len(uncovered),'points':uncovered}
(out/'coverage_dense_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({n:{k:v for k,v in p.items() if k!='points'} for n,p in result.items()}))
