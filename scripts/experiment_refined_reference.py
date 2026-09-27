"""Frozen six-case ablation: old radial/prism vs reference field at levels 0/2."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.experimental_refined_reference import RefinedReferenceField
from src.clothing.experimental_canonical_radial import canonical_cages, normal_frames
from scripts.radial_validation_metrics import distortion, body_penetration, seam_report
from scripts.test_r15_shirt_transfer import depth_preview

INPUT = ROOT/'artifacts/clothing_audit/radial_frames'
OUT = ROOT/'artifacts/clothing_audit/refined_reference'


def main():
    OUT.mkdir(exist_ok=True)
    selected = sys.argv[1:]
    for path in sorted(INPUT.glob('*_binding.npz')):
        key = path.name.removesuffix('_binding.npz')
        if selected and key not in selected:
            continue
        files = [INPUT/(key+'.npz'), INPUT/(key+'_outputs.npz'), path, INPUT/(key+'.json')]
        d, previous, binding = [dict(np.load(p)) for p in files[:3]]
        old = json.loads(files[3].read_text())
        parity = int(d['cage_normal_sign'])
        meshes = {'radial_prism': previous['radial_previous']}
        report = dict(case=key, method='refined reference similarity field; fixed source-space support', variants={})
        for level in (0, 2):
            print(key, 'fit', level, flush=True)
            field = RefinedReferenceField(d['reference_parent'], d['target_body'], d['projection_faces'],
                                          d['uv_index'], parity, level)
            name = 'reference_level_'+str(level)
            meshes[name] = field.evaluate(d['garment'])
            report[name] = field.audit()
        r, o, t, f, inverse = canonical_cages(d['reference_parent'], d['outer_parent'],
                                             d['target_body'], d['projection_faces'], d['uv_index'])
        frames, _ = normal_frames(r, t, f, parity)
        vertex_frames = frames[inverse][binding['faces'][binding['face_ids']]].mean(1)
        shared = np.vstack([d['body'], *meshes.values()])
        for name, mesh in meshes.items():
            print(key, name, 'measure/render', flush=True)
            penetration = (old['variants']['radial_previous']['penetration'] if name == 'radial_prism' else
                           body_penetration(np.vstack([mesh, mesh[d['garment_faces']].mean(1)]), d['body'], d['body_faces']))
            image_path = OUT/(key+'_'+name+'.png')
            report['variants'][name] = dict(
                distortion=distortion(d['garment'], mesh, d['garment_faces'], old['common_metric_scale'], vertex_frames, parity),
                penetration=penetration,
                visibility=depth_preview(d['body'], d['body_faces'], mesh, d['garment_faces'], image_path,
                                         shared_garment_vertices=shared),
                image=str(image_path.relative_to(ROOT)))
        delta = np.linalg.norm(meshes['reference_level_2']-meshes['reference_level_0'], axis=1)/np.ptp(d['body'][:, 2])
        report['refinement_displacement_over_body_height'] = dict(max=float(delta.max()), p99=float(np.quantile(delta, .99)))
        report['unchanged_radial_outer_seams'] = seam_report(d['outer_parent'], previous['radial_previous_shell'], d['uv_index'])
        report['limitations'] = ['Outer cage unchanged; its known penetration remains a layering blocker.',
            'Orientation metric is a common transported-frame proxy, not certified self-intersection detection.',
            'Penetration uses vertices and face centers, not area coverage.',
            'Linear refinement only adds quadrature points; no new geometric curvature.',
            'Prism Jacobian is not a validity metric for this field.']
        files += [Path(__file__), ROOT/'src/clothing/experimental_refined_reference.py',
                  ROOT/'scripts/radial_validation_metrics.py', ROOT/'src/clothing/experimental_canonical_radial.py']
        report['sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        np.savez_compressed(OUT/(key+'.npz'), **meshes)
        panels = [Image.open(OUT/(key+'_'+name+'.png')).convert('RGB') for name in meshes]
        sheet = Image.new('RGB', (panels[0].width, sum(im.height+24 for im in panels)), 'white')
        y = 0
        for name, panel in zip(meshes, panels):
            ImageDraw.Draw(sheet).text((8, y+4), key+' | '+name, fill='black')
            sheet.paste(panel, (0, y+24)); y += panel.height+24
        sheet.save(OUT/(key+'_comparison.png'))
        (OUT/(key+'.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(key, {k: (v['distortion']['historical_length_mask']['over_3'], v['penetration']['penetrating_fraction'])
                    for k, v in report['variants'].items()}, flush=True)


if __name__ == '__main__':
    main()
