"""Read-only stage-2 body/cage coverage audit per matching body part."""
from pathlib import Path
import json
import numpy as np
from mathutils import Vector

root=Path(r'C:\Users\Henrique\Documents\GitHub\Isometricon')
out=root/'artifacts/clothing_audit'
exec((root/'scripts/plan_cage_coverage_blender.py').read_text(encoding='utf-8').split('plan={}')[0])
plan=json.loads((out/'coverage_plan.json').read_text(encoding='utf-8'))
rows={}
for name in ('UpperTorso','LowerTorso','LeftUpperArm','RightUpperArm','LeftLowerArm','RightLowerArm','LeftHand','RightHand'):
    body=scene[mapping[name]]
    points=samples(body,4)
    cage=plan[name]
    result=assess(np.asarray(cage['verts']),cage['faces'],points)
    tree,ids,_=surface(cage['verts'],cage['faces'])
    cap_nearest=0
    cap_outside=0
    for p in points:
        q,n,fi,d=tree.find_nearest(Vector(p))
        if ids[fi]<0:
            cap_nearest+=1
            cap_outside+=bool(outside(tree,p))
    result['nearest_to_temporary_cap']=cap_nearest
    result['cap_nearest_outside']=cap_outside
    rows[name]=result
    print(name,result)
(out/'strict_cage_coverage.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
