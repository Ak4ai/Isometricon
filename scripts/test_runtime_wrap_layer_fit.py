"""Renderable static-pose preview of the asset-specific WrapLayer fitter."""
from pathlib import Path
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer

asset_id=sys.argv[1] if len(sys.argv)>1 else '133331049150205'
directory=ROOT/'assets/models/clothing'
source=next(directory.glob(f'*_{asset_id}.obj'))
rbxm=next(directory.glob(f'*_{asset_id}.rbxm'))
out=ROOT/f'artifacts/clothing_audit/wrap_layer_{asset_id}.obj'
engine=RobloxWearEngine(body_type='female')
vertices,faces,uvs,face_uvs=engine.load_obj(str(source))
fitted,diagnostics=retarget_garment_with_wrap_layer(engine,vertices,str(rbxm),directory/'wrap_cages')
fitted[:,0]*=-1  # Match the production female OBJ orientation.
with out.open('w',encoding='utf-8') as f:
    for x,y,z in fitted:f.write(f'v {x:.9f} {z:.9f} {-y:.9f}\n')
    for u,v in uvs:f.write(f'vt {u:.9f} {v:.9f}\n')
    for face,uv_face in zip(faces,face_uvs):
        f.write('f '+' '.join(f'{i+1}/{j+1}' for i,j in zip(face[::-1],uv_face[::-1]))+'\n')
print(json.dumps({'source':source.name,'output':str(out),'vertices':len(vertices),
                  'bounds':{'min':fitted.min(0).tolist(),'max':fitted.max(0).tolist()},
                  'diagnostics':diagnostics},indent=2))
