"""Read-only asset/cache audit plus instrumented actual wear() into artifacts.

No GL session is started. Uses cached asset data, disables optional network
metadata lookup, traces production functions without replacing their math.
"""
from pathlib import Path
import contextlib
import io
import json
import hashlib
import sys
import urllib.request
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.clothing.wear_engine import RobloxWearEngine,closest_point_on_triangle
import src.clothing.wrap_layer_fit as wrap
from src.clothing.character_model import is_valid_v2_obj,parse_obj_as_mesh,transform_hip_vertices
from scripts.radial_validation_metrics import distortion,body_penetration
from scripts.test_r15_shirt_transfer import depth_preview
from scripts.audit_jeans_foot_binding import chart_labels

OUT=ROOT/'artifacts/clothing_audit/female_jeans_runtime'
ASSET='109837605892174'


def main():
    OUT.mkdir(exist_ok=True)
    saved=ROOT/f'assets/models/character_native_{ASSET}_female.obj'
    report=dict(asset=ASSET,body_type='female',cache=dict(path=str(saved),exists=saved.exists(),
        accepted_by_current_application=is_valid_v2_obj(str(saved))),calls=[],scope='actual wear() and CPU mesh parser, not live UI state')
    if saved.exists():
        report['cache'].update(header=saved.read_text().splitlines()[0],sha256=hashlib.sha256(saved.read_bytes()).hexdigest())
    engine=RobloxWearEngine(body_type='female')
    trace={};arrays={};original=wrap.retarget_garment_with_wrap_layer
    def traced(*args,**kwargs):
        kwargs['binding_audit']=trace
        arrays['raw_garment']=np.array(args[1],copy=True)
        result=original(*args,**kwargs)
        arrays['wrap_before_runtime_postprocess']=result[0].copy()
        report['wrap_metrics']=result[1]
        for key,value in trace.items():arrays['trace_'+key]=np.array(value,copy=True)
        report['calls'].append('retarget_garment_with_wrap_layer returned')
        return result
    for method in ('fit_bottom_clothing','deform_bottom_mesh','_fit_asset_wrap_layer'):
        fn=getattr(engine,method)
        def callback(*args,_fn=fn,_name=method,**kwargs):
            result=_fn(*args,**kwargs)
            report['calls'].append(dict(method=_name,returned_none=result is None))
            if isinstance(result,np.ndarray):arrays[_name]=result.copy()
            return result
        setattr(engine,method,callback)
    def offline(*args,**kwargs):raise OSError('Offline audit: use local asset metadata fallback')
    stream=io.StringIO()
    fresh=OUT/'jeans_fresh.obj'
    with contextlib.redirect_stdout(stream),patch.object(wrap,'retarget_garment_with_wrap_layer',traced),patch.object(urllib.request,'urlopen',offline):
        result=engine.wear(ASSET,output_obj=str(fresh))
    (OUT/'runtime.log').write_text(stream.getvalue(),encoding='utf-8')
    print(stream.getvalue(),flush=True)
    arrays['wear_final']=result['verts'].copy()
    faces=np.asarray(result['faces'],int)
    arrays['wear_faces']=faces
    parsed,indices=parse_obj_as_mesh(str(fresh),vertex_transform=lambda v:transform_hip_vertices(v,1.,1.,0.))
    # Convert the GL upload positions back to engine XYZ solely for comparison.
    gl=parsed.reshape(-1,11)[:,:3]
    gl_engine=gl[:,[0,2,1]]*np.array([1,-1,1])
    expected_corners=result['verts'][faces].reshape(-1,3)
    report['export_and_cpu_parser_max_position_error']=float(np.linalg.norm(gl_engine-expected_corners,axis=1).max())
    report['fresh_cache_accepted']=is_valid_v2_obj(str(fresh))
    report['render_customization']='neutral glute=1, width=1, waist_offset=0; current interactive settings unknown'
    if 'wrap_before_runtime_postprocess' in arrays:
        prediction=arrays['wrap_before_runtime_postprocess']*[-1,1,1]
        report['final_vs_wrap_with_documented_x_reflection_max_error']=float(np.linalg.norm(result['verts']-prediction,axis=1).max())
    fixture_path=ROOT/f'artifacts/clothing_audit/radial_frames/female_{ASSET}.npz'
    d=dict(np.load(fixture_path));old=json.loads(fixture_path.with_suffix('.json').read_text())
    report['raw_vs_frozen_max_error']=float(np.linalg.norm(arrays['raw_garment']-d['garment'],axis=1).max())
    report['target_vs_frozen_max_error']=float(np.linalg.norm(arrays['trace_target_body']-d['target_body'],axis=1).max())
    report['wrap_vs_frozen_production_max_error']=float(np.linalg.norm(arrays['wrap_before_runtime_postprocess']-d['baseline'],axis=1).max())
    meshes=dict(wrap_before_postprocess=arrays['wrap_before_runtime_postprocess'],wear_final=arrays['wear_final'])
    if saved.exists():
        previous,_,_,_=engine.load_obj(str(saved))
        if previous.shape==arrays['wear_final'].shape:
            meshes['existing_v5']=previous
            report['existing_vs_fresh_max_position_error']=float(np.linalg.norm(previous-result['verts'],axis=1).max())
    shared=np.vstack([d['body'],*meshes.values()]);report['stages']={}
    panels=[]
    for name,mesh in meshes.items():
        print(name,'validation',flush=True)
        stats=distortion(d['garment'],mesh,d['garment_faces'],old['common_metric_scale'])
        samples=np.vstack((mesh,mesh[d['garment_faces']].mean(1)))
        report['stages'][name]=dict(distortion=stats,penetration=body_penetration(samples,d['body'],d['body_faces']))
        path=OUT/(name+'.png')
        depth_preview(d['body'],d['body_faces'],mesh,d['garment_faces'],path,shared_garment_vertices=shared)
        panels.append(Image.open(path).convert('RGB'))
    sheet=Image.new('RGB',(panels[0].width,sum(p.height+24 for p in panels)),'white');y=0
    for name,panel in zip(meshes,panels):
        ImageDraw.Draw(sheet).text((8,y+4),name,fill='black');sheet.paste(panel,(0,y+24));y+=panel.height+24
    sheet.save(OUT/'comparison.png')
    # Trace both endpoints of the worst five normalized, non-tiny source edges.
    f=d['garment_faces'];edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    source=arrays['raw_garment'];fit=arrays['wrap_before_runtime_postprocess']
    length=np.linalg.norm(source[edges[:,0]]-source[edges[:,1]],axis=1)
    ratio=np.linalg.norm(fit[edges[:,0]]-fit[edges[:,1]],axis=1)/np.maximum(length*old['common_metric_scale'],1e-30)
    ranked=np.flatnonzero(length>=.01);ranked=ranked[np.argsort(ratio[ranked])[-5:][::-1]]
    def evaluate(point,face):
        src=trace['source_outer'][face];dst=trace['target_outer'][face]
        q,u,v,w=closest_point_on_triangle(point,*src)
        bary=np.array([u,v,w]);base=bary@dst
        residual=wrap._local_map(*src,*dst,normal_sign=trace['cage_normal_sign'])@(point-q)
        return base,residual
    report['worst_edges']=[]
    charts,labels=chart_labels(engine,trace)
    for eid in ranked:
        ends=edges[eid];entry=dict(vertices=ends.tolist(),normalized_stretch=float(ratio[eid]),endpoints=[])
        midpoint=trace['source_vertices'][ends].mean(0);mapped=[]
        for vertex in ends:
            face=trace['projection_faces'][trace['face_indices'][vertex]]
            base,residual=evaluate(trace['source_vertices'][vertex],face)
            midbase,midres=evaluate(midpoint,face);mapped.append(midbase+midres)
            entry['endpoints'].append(dict(vertex=int(vertex),source_face=face.tolist(),
                body_chart_majority_label=labels[int(charts[trace['face_indices'][vertex]])],
                source_distance=float(trace['distances'][vertex]),target_outer_point=base.tolist(),
                transported_residual=residual.tolist(),final=fit[vertex].tolist(),
                reconstruction_error=float(np.linalg.norm(base+residual-fit[vertex]))))
        entry['same_midpoint_two_face_predictions_distance']=float(np.linalg.norm(mapped[0]-mapped[1]))
        report['worst_edges'].append(entry)
    vertex=int(np.argmin(fit[:,2]))
    face=trace['projection_faces'][trace['face_indices'][vertex]]
    base,residual=evaluate(trace['source_vertices'][vertex],face)
    report['lowest_vertex']=dict(vertex=vertex,source_face=face.tolist(),
        body_chart_majority_label=labels[int(charts[trace['face_indices'][vertex]])],
        source_point=trace['source_vertices'][vertex].tolist(),
        source_distance=float(trace['distances'][vertex]),
        target_triangle=trace['target_outer'][face].tolist(),
        target_outer_point=base.tolist(),transported_residual=residual.tolist(),
        final=fit[vertex].tolist(),body_min_z=float(d['body'][:,2].min()),
        reconstruction_error=float(np.linalg.norm(base+residual-fit[vertex])))
    paths=[Path(__file__),saved,fresh,fixture_path,ROOT/'src/clothing/wear_engine.py',ROOT/'src/clothing/character_model.py',
           ROOT/'src/clothing/wrap_layer_fit.py',ROOT/'assets/models/female_cages_apose_stage2.obj']
    report['sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}
    report['existing_cache_preserved']=not saved.exists() or hashlib.sha256(saved.read_bytes()).hexdigest()==report['cache']['sha256']
    np.savez_compressed(OUT/'stages.npz',**arrays)
    (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('stages','worst_edges','sha256')},indent=2))


if __name__=='__main__':main()
