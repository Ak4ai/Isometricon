"""Orthographic depth-buffer audit using the project's +Z front convention."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
PANTS_MODE='pants' in sys.argv
VALIDATED_MODE='validated' in sys.argv
EXPERIMENT_MODE='experiment' in sys.argv
PART_AFFINE_MODE='part_affine' in sys.argv
MATRIX_MODE='matrix' in sys.argv
JERSEY_MODE='jersey' in sys.argv
FALLBACK_MODE='fallback' in sys.argv
COHERENT_MODE='coherent' in sys.argv
OUT=ROOT/('artifacts/clothing_audit/pants_four_view_depth.png' if PANTS_MODE else
          'artifacts/clothing_audit/dress_jeans_coherent_four_view.png' if COHERENT_MODE else
          'artifacts/clothing_audit/dress_jeans_fallback_four_view.png' if FALLBACK_MODE else
          'artifacts/clothing_audit/jersey_compare_four_view.png' if JERSEY_MODE else
          'artifacts/clothing_audit/compatibility_four_view.png' if MATRIX_MODE else
          'artifacts/clothing_audit/part_affine_four_view.png' if PART_AFFINE_MODE else
          'artifacts/clothing_audit/experiment_binding_four_view.png' if EXPERIMENT_MODE else
          'artifacts/clothing_audit/validated_four_view_depth.png' if VALIDATED_MODE else
          'artifacts/clothing_audit/office_shirt_wraplayer/four_view_depth_audit.png')
W,H=280,350
XMIN,XMAX=-0.45,0.45
YMIN,YMAX=(-0.1,1.72) if (PANTS_MODE or MATRIX_MODE or FALLBACK_MODE or COHERENT_MODE) else (0.72,1.72)

def load(path):
    v=[];f=[]
    for line in path.open(encoding='utf-8'):
        if line.startswith('v '):v.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):
            ids=[int(t.split('/')[0])-1 for t in line.split()[1:]]
            f.extend([[ids[0],ids[i],ids[i+1]] for i in range(1,len(ids)-1)])
    return np.asarray(v),np.asarray(f,dtype=int)

def load_engine(path):
    vertices, faces = load(path)
    return np.column_stack((vertices[:, 0], vertices[:, 2], -vertices[:, 1])), faces

def depth_buffer(vertices,faces,camera):
    zbuf=np.full((H,W),-np.inf)
    xy=np.empty((len(vertices),2))
    dx,dz=np.asarray(camera,dtype=float)/np.linalg.norm(camera)
    horizontal=dz*vertices[:,0]-dx*vertices[:,2]
    xy[:,0]=(horizontal-XMIN)/(XMAX-XMIN)*(W-1)
    xy[:,1]=(YMAX-vertices[:,1])/(YMAX-YMIN)*(H-1)
    depth=dx*vertices[:,0]+dz*vertices[:,2]
    for face in faces:
        points=xy[face]; depths=depth[face]
        left=max(0,int(np.floor(points[:,0].min())))
        right=min(W-1,int(np.ceil(points[:,0].max())))
        top=max(0,int(np.floor(points[:,1].min())))
        bottom=min(H-1,int(np.ceil(points[:,1].max())))
        if right<left or bottom<top:continue
        x1,y1=points[0];x2,y2=points[1];x3,y3=points[2]
        denom=(y2-y3)*(x1-x3)+(x3-x2)*(y1-y3)
        if abs(denom)<1e-10:continue
        yy,xx=np.mgrid[top:bottom+1,left:right+1]
        u=((y2-y3)*(xx-x3)+(x3-x2)*(yy-y3))/denom
        v=((y3-y1)*(xx-x3)+(x1-x3)*(yy-y3))/denom
        w=1-u-v
        valid=(u>=-1e-7)&(v>=-1e-7)&(w>=-1e-7)
        z=u*depths[0]+v*depths[1]+w*depths[2]
        current=zbuf[top:bottom+1,left:right+1]
        np.maximum(current,z,out=current,where=valid)
    return zbuf

body=load(ROOT/'assets/models/character_female_clean_apose_stage2.obj')
shirts={
    'Atual':load(ROOT/'artifacts/clothing_audit/office_shirt_stage2_fitted.obj'),
    'WrapLayer experimental':load(ROOT/'artifacts/clothing_audit/office_shirt_wraplayer/shirt_reference_to_body.obj'),
    'Frame local':load(ROOT/'artifacts/clothing_audit/wrap_layer_133331049150205.obj'),
    'Bomber frame local':load(ROOT/'artifacts/clothing_audit/wrap_layer_72628400373948.obj'),
    'Sweater frame local':load(ROOT/'artifacts/clothing_audit/wrap_layer_16185652164.obj')
}
if PANTS_MODE:
    pants=load(ROOT/'artifacts/clothing_audit/wrap_layer_16899958482.obj')
    top=load(ROOT/'artifacts/clothing_audit/wrap_layer_133331049150205.obj')
    outfit=(np.vstack((pants[0],top[0])),np.vstack((pants[1],top[1]+len(pants[0]))))
    shirts={'Cargo pants frame local':pants,'Office shirt + cargo pants':outfit}
elif VALIDATED_MODE:
    shirts={'Office anterior':load(ROOT/'artifacts/clothing_audit/office_shirt_stage2_fitted.obj'),
            'Office com WrapLayer':load(ROOT/'artifacts/clothing_audit/wrap_layer_133331049150205.obj'),
            'Jaqueta com WrapLayer':load(ROOT/'artifacts/clothing_audit/wrap_layer_72628400373948.obj')}
elif EXPERIMENT_MODE:
    shirts={'Sweater nearest':load(ROOT/'artifacts/clothing_audit/wrap_layer_16185652164.obj'),
            'Sweater coherent':load(ROOT/'artifacts/clothing_audit/experiment_binding_16185652164.obj'),
            'Office coherent':load(ROOT/'artifacts/clothing_audit/experiment_binding_133331049150205.obj'),
            'Bomber coherent':load(ROOT/'artifacts/clothing_audit/experiment_binding_72628400373948.obj')}
elif PART_AFFINE_MODE:
    shirts={'Sweater nearest':load(ROOT/'artifacts/clothing_audit/wrap_layer_16185652164.obj'),
            'Sweater part affine':load(ROOT/'artifacts/clothing_audit/experiment_part_affine_16185652164.obj'),
            'Office part affine':load(ROOT/'artifacts/clothing_audit/experiment_part_affine_133331049150205.obj'),
            'Bomber part affine':load(ROOT/'artifacts/clothing_audit/experiment_part_affine_72628400373948.obj')}
elif MATRIX_MODE:
    shirts={'Bikini WrapLayer':load_engine(ROOT/'assets/models/character_native_96314281401899_female.obj'),
            'Dress WrapLayer':load_engine(ROOT/'assets/models/character_native_114590471167431_female.obj'),
            'Jeans WrapLayer':load_engine(ROOT/'assets/models/character_native_109837605892174_female.obj'),
            'Jersey fallback':load_engine(ROOT/'assets/models/character_native_97346273111638_female.obj')}
elif JERSEY_MODE:
    shirts={'Jersey fallback':load_engine(ROOT/'assets/models/character_native_97346273111638_female.obj'),
            'Jersey WrapLayer direct':load(ROOT/'artifacts/clothing_audit/wrap_layer_97346273111638.obj')}
elif FALLBACK_MODE:
    shirts={'Dress WrapLayer':load_engine(ROOT/'assets/models/character_native_114590471167431_female.obj'),
            'Dress fallback':load_engine(ROOT/'artifacts/clothing_audit/dress_fallback.obj'),
            'Jeans WrapLayer':load_engine(ROOT/'assets/models/character_native_109837605892174_female.obj'),
            'Jeans fallback':load_engine(ROOT/'artifacts/clothing_audit/jeans_fallback.obj')}
elif COHERENT_MODE:
    shirts={'Dress WrapLayer':load_engine(ROOT/'assets/models/character_native_114590471167431_female.obj'),
            'Dress coherent':load(ROOT/'artifacts/clothing_audit/experiment_binding_114590471167431.obj'),
            'Jeans WrapLayer':load_engine(ROOT/'assets/models/character_native_109837605892174_female.obj'),
            'Jeans coherent':load(ROOT/'artifacts/clothing_audit/experiment_binding_109837605892174.obj')}
views=[('Frente +Z',(0,1)),('Lado +X',(1,0)),('Costas -Z',(0,-1)),('3/4',(.7,.7))]
canvas=Image.new('RGB',(W*4,(H+40)*len(shirts)),'white')
draw=ImageDraw.Draw(canvas)
report={}
for row,(label,shirt) in enumerate(shirts.items()):
    for col,(view_name,camera) in enumerate(views):
        bd=depth_buffer(*body,camera)
        sd=depth_buffer(*shirt,camera)
        skin=np.isfinite(bd)
        clothing=np.isfinite(sd)&((sd>=bd-1e-5)|~skin)
        img=np.full((H,W,3),255,dtype=np.uint8)
        img[skin]=[215,174,150]
        img[clothing]=[50,105,160]
        canvas.paste(Image.fromarray(img),(col*W,row*(H+40)+40))
        roi=(np.arange(W)[None,:]>W*.34)&(np.arange(W)[None,:]<W*.66)&(np.arange(H)[:,None]>H*.30)&(np.arange(H)[:,None]<H*.62)
        rate=float((skin&clothing&roi).sum()/max((skin&roi).sum(),1))
        report[f'{label}_{view_name}']=rate
        draw.text((col*W+8,row*(H+40)+12),f'{label} - {view_name}',fill='black')
canvas.save(OUT)
print(OUT)
print(report)
