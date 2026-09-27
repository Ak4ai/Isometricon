"""Reproducible input/frame audit; caches trace arrays for offline comparisons."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_binding_charts import ASSETS
from scripts.test_r15_shirt_transfer import FBX, CAGE_OBJ, load_classic_body
from scripts.experiment_chart_blend import load_body_for_preview
from src.clothing.wear_engine import RobloxWearEngine, load_r15_female_cages
from src.clothing.wrap_layer_fit import retarget_garment_with_wrap_layer
from src.clothing.multi_influence_shell import _neighborhoods

OUT = ROOT / 'artifacts/clothing_audit/radial_frames'

def main():
    OUT.mkdir(exist_ok=True)
    engine = RobloxWearEngine(body_type='female')
    directory = ROOT / 'assets/models/clothing'
    report = {}
    for body_name, assets in [('female', ASSETS), ('blocky', ASSETS[:1])]:
        if body_name == 'blocky':
            engine.r15_female_cages = load_r15_female_cages(str(CAGE_OBJ), is_source_cage=True)
            body, body_faces, _ = load_classic_body(FBX)
        else:
            body, body_faces = load_body_for_preview(ROOT / 'assets/models/character_female_clean_apose_stage2.obj')
        for asset in assets:
            garment, faces, _, _ = engine.load_obj(str(next(directory.glob(f'*_{asset}.obj'))))
            trace = {}
            baseline, _ = retarget_garment_with_wrap_layer(engine, garment,
                str(next(directory.glob(f'*_{asset}.rbxm'))), directory / 'wrap_cages', binding_audit=trace)
            r, t = trace['reference_parent'], trace['target_body']
            ids = trace['uv_index']
            _, first, inverse = np.unique(ids, return_index=True, return_inverse=True)
            neighborhoods = _neighborhoods(trace['projection_faces'], len(r), 1)
            counts = np.array([len(x) for x in neighborhoods])
            ranks = np.array([np.linalg.matrix_rank(r[x] - r[i], tol=1e-8) for i,x in enumerate(neighborhoods)])
            old_scale = float(np.median(np.ptp(t,axis=0) / np.ptp(r,axis=0)))
            rms_scale = float(np.linalg.norm(t[first]-t[first].mean(0)) / np.linalg.norm(r[first]-r[first].mean(0)))
            row = dict(raw_vertices=len(r), unique_uv=len(first), neighbors_quantiles=np.quantile(counts,[0,.5,1]).tolist(),
                rank_counts={str(k): int(sum(ranks==k)) for k in range(4)}, old_scale=old_scale, rms_scale=rms_scale,
                duplicate_reference_spread=float(np.linalg.norm(r-r[first][inverse],axis=1).max()))
            key = body_name + '_' + asset
            np.savez_compressed(OUT / (key+'.npz'), garment=garment, garment_faces=faces,
                baseline=baseline, body=body, body_faces=body_faces, **trace)
            report[key] = row
            print(key, json.dumps(row), flush=True)
    (OUT / 'INPUT_AUDIT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__ == '__main__':
    main()
