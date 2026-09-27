"""Measure limb-axis change between a garment reference cage and female target."""
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine

engine=RobloxWearEngine(body_type='female')
ref,_,uv,_=engine.load_obj(str(ROOT/'artifacts/clothing_audit/office_shirt_wraplayer/reference.obj'))
for name in ('UpperTorso','LeftUpperArm','RightUpperArm','LeftLowerArm','RightLowerArm'):
    part=engine.r15_female_cages[name]
    part_uv=np.unique(np.round(np.vstack(part['face_uvs']),6),axis=0)
    match=np.concatenate([((chunk[:,None,:]-uv[None,:,:])**2).sum(2).argmin(1) for chunk in np.array_split(part_uv,20)])
    garment=ref[match]
    target=part['verts']
    src_center=garment.mean(0)
    dst_center=target.mean(0)
    src_axis=np.linalg.svd(garment-src_center,full_matrices=False)[2][0]
    dst_axis=np.linalg.svd(target-dst_center,full_matrices=False)[2][0]
    src_xy=np.abs(src_axis[:2])
    dst_xz=np.abs(dst_axis[[0,2]])
    print(name,'reference arm horizontal/vertical',np.round(src_xy,3),
          'target horizontal/vertical',np.round(dst_xz,3),
          'reference_angle_deg',round(float(np.degrees(np.arctan2(src_xy[0],src_xy[1]))),1),
          'target_angle_deg',round(float(np.degrees(np.arctan2(dst_xz[0],dst_xz[1]))),1),
          'ref UV match max',round(float(np.linalg.norm(part_uv-uv[match],axis=1).max()),7))
