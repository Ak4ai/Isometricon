"""Compare an actual clothing WrapLayer reference/cage to the R15 body cage by UV."""
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.clothing.wear_engine import RobloxWearEngine

ROOT = Path(__file__).resolve().parents[1]
engine = RobloxWearEngine(body_type="female")
base = ROOT / "artifacts/clothing_audit/office_shirt_wraplayer"
ref_v, ref_f, ref_uv, _ = engine.load_obj(str(base / "reference.obj"))
cage_v, cage_f, cage_uv, _ = engine.load_obj(str(base / "cage.obj"))

def uv_key(uv):
    return tuple(np.round(uv, 5))

def uv_map_obj(v, uv):
    out = {}
    for p, tex in zip(v, uv):
        out.setdefault(uv_key(tex), p)
    return out

ref_map = uv_map_obj(ref_v, ref_uv)
cage_map = uv_map_obj(cage_v, cage_uv)
body_map = {}
for name, part in engine.r15_source_cages.items():
    if name.endswith("Forearm"):
        continue
    for face, face_uv in zip(part["faces"], part["face_uvs"]):
        for i, uv in zip(face, face_uv):
            body_map.setdefault(uv_key(uv), part["verts"][i])

keys = sorted(set(ref_map) & set(cage_map) & set(body_map))
print("shared UV keys", len(keys), "reference", len(ref_map), "cage", len(cage_map), "body", len(body_map))
print("samples",list(ref_map)[:5],list(body_map)[:5])
if not keys:
    a=np.asarray(list(ref_map)); b=np.asarray(list(body_map))
    for label,t in [('raw',a),('flip_v',a*[1,-1]+[0,1]),('flip_u',a*[-1,1]+[1,0]),('flip_both',a*[-1,-1]+[1,1])]:
        d=np.concatenate([np.sqrt(((chunk[:,None,:]-b[None,:,:])**2).sum(2)).min(1) for chunk in np.array_split(t,20)])
        print(label,'UV nearest',np.quantile(d,[0,.5,.9,.99,1]),'matches <.001',sum(d<.001))
    indices=np.concatenate([((chunk[:,None,:]-b[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(a,20)])
    keys=list(ref_map)
    garment=np.stack([ref_map[k] for k in keys])
    body=np.stack([body_map[list(body_map)[j]] for j in indices])
else:
    garment = np.stack([ref_map[k] for k in keys])
    body = np.stack([body_map[k] for k in keys])
for label, transformed in [("x,-z,y",garment[:,[0,2,1]] * [1,-1,1]),
                           ("x,z,y",garment[:,[0,2,1]]),
                           ("-x,-z,y",garment[:,[0,2,1]] * [-1,-1,1])]:
    delta = transformed - body
    print(label, "median shift", np.round(np.median(delta,axis=0),4),
          "median error", round(float(np.median(np.linalg.norm(delta,axis=1))),4),
          "p90 error", round(float(np.quantile(np.linalg.norm(delta,axis=1),.9)),4))
X=np.column_stack((garment,np.ones(len(garment))))
matrix=np.linalg.lstsq(X,body,rcond=None)[0]
error=np.linalg.norm(X@matrix-body,axis=1)
print('least squares matrix rows x,y,z,translation to body XYZ',np.round(matrix,4))
print('residual',np.round(np.quantile(error,[0,.5,.9,.99,1]),4))
src_uvs=np.asarray(list(ref_map))
body_uvs=np.asarray(list(body_map))
src_to_body=np.concatenate([((chunk[:,None,:]-body_uvs[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(src_uvs,20)])
src_keys=list(ref_map); body_keys=list(body_map)
src_uv_to_body={src_keys[i]:body_keys[j] for i,j in enumerate(src_to_body)}
def garment_face_keys(v,faces,uv):
    return {tuple(sorted(src_uv_to_body[uv_key(uv[i])] for i in face)) for face in faces}
ref_tris=garment_face_keys(ref_v,ref_f,ref_uv)
body_tris=set()
for name,part in engine.r15_source_cages.items():
    if name.endswith('Forearm'): continue
    body_tris.update(tuple(sorted(uv_key(t) for t in tri)) for tri in part['face_uvs'])
print('triangles',len(ref_tris),len(body_tris),'shared',len(ref_tris&body_tris))
