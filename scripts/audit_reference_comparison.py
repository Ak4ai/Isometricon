"""Compare garment reference meshes by cage UV and vertex positions."""
from pathlib import Path
import sys
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine

engine=RobloxWearEngine(body_type='female')
paths={'office':ROOT/'artifacts/clothing_audit/office_shirt_wraplayer/reference.obj'}
for name in ('bomber','sweater','pants'):
    paths[name]=ROOT/f'artifacts/clothing_audit/reference_comparison/{name}_reference.obj'

def unique_uv_positions(v,uv):
    seen={}
    for pos,tex in zip(v,uv):seen.setdefault(tuple(np.round(tex,6)),pos)
    return np.asarray(list(seen)),np.asarray(list(seen.values()))

office=engine.load_obj(str(paths['office']))
base_uv,base_xyz=unique_uv_positions(office[0],office[2])
report={}
for name,path in paths.items():
    vertices,faces,uv,_=engine.load_obj(str(path))
    compare_uv,compare_xyz=unique_uv_positions(vertices,uv)
    match=np.concatenate([((chunk[:,None,:]-compare_uv[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(base_uv,30)])
    errors=np.linalg.norm(base_uv-compare_uv[match],axis=1)
    positions=np.linalg.norm(base_xyz-compare_xyz[match],axis=1)
    report[name]={'vertices':len(vertices),'faces':len(faces),'distinct_uv':len(compare_uv),
                  'uv_error_max':float(errors.max()),
                  'position_delta_median':float(np.median(positions)),
                  'position_delta_p90':float(np.quantile(positions,.9)),
                  'position_delta_max':float(positions.max())}
print(json.dumps(report,indent=2))
(ROOT/'artifacts/clothing_audit/reference_comparison/report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
