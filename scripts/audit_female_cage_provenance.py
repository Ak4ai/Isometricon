"""Read-only current-loader provenance and frozen target correspondence audit.

Does not validate live UI caches, visible garment assignment or final fitting.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import src.clothing.wear_engine as wear
from src.clothing.wrap_layer_fit import _unique_uv_positions,_match_reference_to_body_uv


def main():
    package_path=ROOT/'assets/models/female_clothing_package_stage2.json'
    package=json.loads(package_path.read_text())
    calls=[];original=wear.load_r15_cages
    def traced(path,*args,**kwargs):
        resolved=Path(path).resolve()
        calls.append(dict(path=str(resolved),sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
                          is_source_cage=kwargs.get('is_source_cage',False)))
        return original(path,*args,**kwargs)
    wear.load_r15_cages=traced
    try:engine=wear.RobloxWearEngine(body_type='female')
    finally:wear.load_r15_cages=original
    expected=original(str(ROOT/'assets/models'/package['cage_obj']),is_source_cage=False)
    differences={name:float(np.linalg.norm(engine.body_cages[name]['verts']-part['verts'],axis=1).max())
                 for name,part in expected.items() if not name.endswith('Forearm')}
    uv,pos=_unique_uv_positions(engine.body_cages)
    rows={}
    for path in sorted((ROOT/'artifacts/clothing_audit/radial_frames').glob('female_*_binding.npz')):
        key=path.name.removesuffix('_binding.npz');data_path=path.with_name(key+'.npz')
        d=dict(np.load(data_path))
        ids=_match_reference_to_body_uv(d['reference_uv'],uv)
        current=pos[ids]
        rows[key]=dict(target_entries=len(current),max_target_position_difference=float(np.linalg.norm(current-d['target_body'],axis=1).max()),
                       frozen_input_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest())
    report=dict(loader_calls=calls,expected_target=package['cage_obj'],runtime_vs_export_by_part=differences,
                frozen_female_cases_vs_current_target=rows,
                limits=['Direct female engine initialization; not a running UI session or fitted-clothing cache audit.',
                        'Checks loaded cage and UV target mapping, not garment influence correctness.',
                        'Does not prove the current Blender scene equals the exported OBJ.'])
    out=ROOT/'artifacts/clothing_audit/FEMALE_CAGE_PROVENANCE_CURRENT.json'
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
