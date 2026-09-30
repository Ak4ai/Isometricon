"""Run a cached shirt through the female wrap using the validated stage-2 cages."""
import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine,load_r15_cages

OUT=ROOT/'artifacts/clothing_audit'
engine=RobloxWearEngine(body_type='female')
engine.body_cages=load_r15_cages(str(ROOT/'assets/models/female_cages_apose_stage2.obj'))
# The stage-2 cage is paired against the FBX reference by its per-corner UVs.
engine._init_dual_cage()
assert engine.dual_cage_ready

shirt=ROOT/'assets/models/clothing/-_office_shirt__BLACK_133331049150205.obj'
verts,faces,uvs,face_uvs=engine.load_obj(str(shirt))
sleeves,torso=engine.analyze_topology(verts,faces)
src=engine.r15_source_cages['UpperTorso']['verts'];dst=engine.body_cages['UpperTorso']['verts']
scale=np.ptp(dst[:,2])/(np.ptp(src[:,2])+1e-8)
z_shift=dst[:,2].max()-src[:,2].max()*scale
y_shift=dst[:,1].mean()-src[:,1].mean()*scale
canonical=np.empty_like(verts)
canonical[:,0]=verts[:,0]*scale
canonical[:,1]=verts[:,2]*scale+y_shift
canonical[:,2]=(verts[:,1]+1.222)*scale+z_shift
fitted=engine.deform_dual_cage(canonical,faces,sleeves,torso)
assert np.isfinite(fitted).all()

path=OUT/'office_shirt_stage2_fitted.obj'
with path.open('w',encoding='utf-8') as f:
    f.write('# Cached office shirt fitted using stage-2 female R15 cages\n')
    for v in fitted:f.write(f'v {v[0]:.9f} {v[2]:.9f} {-v[1]:.9f}\n')
    for uv in uvs:f.write(f'vt {uv[0]:.9f} {uv[1]:.9f}\n')
    for i,face in enumerate(faces):
        if len(face_uvs)>i:f.write('f '+' '.join(f'{face[j]+1}/{face_uvs[i][j]+1}' for j in range(len(face)))+'\n')
        else:f.write('f '+' '.join(str(i+1) for i in face)+'\n')
report={'asset':shirt.name,'vertices':len(verts),'faces':len(faces),'sleeve_vertices':len(sleeves),'torso_vertices':len(torso),
 'all_output_positions_finite':True,'output_bounds_engine_xyz':{'min':fitted.min(0).tolist(),'max':fitted.max(0).tolist()},
 'tested_stage2_cage_package':'assets/models/female_cages_apose_stage2.obj','fitted_preview_obj':path.name,
 'reference_cage':'assets/models/roblox_reference_cages.obj',
 'binding':'per-triangle/per-corner UV correspondence; no vertex-index assumption'}
(OUT/'runtime_clothing_test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
