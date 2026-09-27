"""Compare cached visible garments to their authored reference cages."""
from pathlib import Path
import json
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine
from src.clothing.wrap_layer_fit import read_wrap_layer

engine=RobloxWearEngine(body_type='female')
items=[('Office','133331049150205','80307990380242'),
       ('Sweater','16185652164','16184891193')]
if len(sys.argv)>1:
    items=[]
    for asset_id in sys.argv[1:]:
        rbxm=next((ROOT/'assets/models/clothing').glob(f'*_{asset_id}.rbxm'))
        items.append((asset_id,asset_id,read_wrap_layer(str(rbxm))['reference_id']))
W,H=310,410
canvas=Image.new('RGB',(W*4,(H+30)*len(items)),'white')
draw=ImageDraw.Draw(canvas)
report={}
for row,(name,asset_id,reference_id) in enumerate(items):
    src=next((ROOT/'assets/models/clothing').glob(f'*_{asset_id}.obj'))
    rbxm=next((ROOT/'assets/models/clothing').glob(f'*_{asset_id}.rbxm'))
    garment,garment_faces,*_=engine.load_obj(str(src))
    reference,reference_faces,*_=engine.load_obj(str(ROOT/f'assets/models/clothing/wrap_cages/{reference_id}.obj'))
    wrap=read_wrap_layer(str(rbxm))
    rotation,origin=wrap['cage_origin']
    ref_rotation,ref_origin=wrap['reference_origin']
    # Both meshes must be in the authored outer cage's frame. The previous
    # diagnostic image left the reference mesh in its own local frame.
    reference=(reference@ref_rotation.T+ref_origin-origin)@rotation
    garment=(garment-origin)@rotation
    report[asset_id]={"reference_origin_minus_cage_origin":(ref_origin-origin).tolist(),
                      "reference_rotation":ref_rotation.tolist(),"cage_rotation":rotation.tolist(),
                      "views":{}}
    garment_only_masks={}
    for col,(label,front) in enumerate([('front mesh',True),('back mesh',False),('front with cage',True),('back with cage',False)]):
        include_cage=col>=2
        zbuf=np.full((H,W),-np.inf)
        colors=np.full((H,W,3),255,dtype=np.uint8)
        for verts,faces,color in ([(reference,reference_faces,[213,174,150])] if include_cage else [])+[(garment,garment_faces,[50,105,160])]:
            screen=np.stack([(verts[:,0]+2.4)/4.8*(W-1),(2.8-verts[:,1])/5.6*(H-1)],axis=1)
            depths=-verts[:,2] if front else verts[:,2]
            for face in faces:
                p=screen[face];z=depths[face]
                x0=max(0,int(np.floor(p[:,0].min())));x1=min(W-1,int(np.ceil(p[:,0].max())))
                y0=max(0,int(np.floor(p[:,1].min())));y1=min(H-1,int(np.ceil(p[:,1].max())))
                if x1<x0 or y1<y0:continue
                ax,ay=p[0];bx,by=p[1];cx,cy=p[2]
                den=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
                if abs(den)<1e-10:continue
                yy,xx=np.mgrid[y0:y1+1,x0:x1+1]
                u=((by-cy)*(xx-cx)+(cx-bx)*(yy-cy))/den
                v=((cy-ay)*(xx-cx)+(ax-cx)*(yy-cy))/den
                w=1-u-v
                valid=(u>=0)&(v>=0)&(w>=0)
                depth=u*z[0]+v*z[1]+w*z[2]
                patch=zbuf[y0:y1+1,x0:x1+1]
                update=valid&(depth>patch)
                patch[update]=depth[update]
                colors[y0:y1+1,x0:x1+1][update]=color
        canvas.paste(Image.fromarray(colors),(col*W,row*(H+30)+30))
        draw.text((col*W+8,row*(H+30)+8),f'{name} {label}',fill='black')
        garment_blue=np.all(colors==np.array([50,105,160],dtype=np.uint8),axis=2)
        if not include_cage:
            garment_only_masks[front]=garment_blue
        else:
            reference_beige=np.all(colors==np.array([213,174,150],dtype=np.uint8),axis=2)
            source_silhouette=garment_only_masks[front]
            report[asset_id]['views']['front' if front else 'back']={
                'garment_only_pixels':int(source_silhouette.sum()),
                'reference_visible_over_garment_projection':int((reference_beige&source_silhouette).sum()),
                'reference_visible_over_garment_fraction':float((reference_beige&source_silhouette).sum()/max(source_silhouette.sum(),1))}
out=(ROOT/'artifacts/clothing_audit/source_garments_additional_corrected.png' if len(sys.argv)>1 else
     ROOT/'artifacts/clothing_audit/office_shirt_wraplayer/source_garments_depth_corrected.png')
canvas.save(out)
old=out.with_name(out.stem.replace('_corrected','')+'.png')
if old.exists():
    old_pixels=np.asarray(Image.open(old).convert('RGB'))
    new_pixels=np.asarray(canvas)
    if old_pixels.shape==new_pixels.shape:
        comparison=Image.new('RGB',(W*4,(H+30)*len(items)),'white')
        comp_draw=ImageDraw.Draw(comparison)
        for row,(_,asset_id,_) in enumerate(items):
            y=row*(H+30)
            short_name='dress' if asset_id=='114590471167431' else ('jeans' if asset_id=='109837605892174' else asset_id)
            for col,(version,front,source) in enumerate((('old',True,old_pixels),('old',False,old_pixels),
                                                         ('corrected',True,new_pixels),('corrected',False,new_pixels))):
                source_col=2 if front else 3
                pixels=source[y+30:y+30+H,source_col*W:(source_col+1)*W]
                comparison.paste(Image.fromarray(pixels),(col*W,y+30))
                comp_draw.text((col*W+8,y+8),f'{short_name} {version} {"front" if front else "back"}',fill='black')
                source_mask=np.all(source[y+30:y+30+H,(0 if front else 1)*W:(1 if front else 2)*W]
                                   ==np.array([50,105,160],dtype=np.uint8),axis=2)
                beige=np.all(pixels==np.array([213,174,150],dtype=np.uint8),axis=2)
                report[asset_id]['views']['front' if front else 'back'][version+'_reference_over_garment_pixels']=int((source_mask&beige).sum())
        comparison.save(out.with_name('source_overlay_before_after.png'))
(out.with_suffix('.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(out)
