"""Analytic nonlinear arm benchmark. No real assets or runtime mutations."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.synthetic_wrap_fixture import make_fixture, unbend, analytic_penetration, GAP, BODY_RADIUS, LENGTH
from scripts.experiment_canonical_radial import bind_source, evaluate_binding
from scripts.radial_validation_metrics import normals
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.experimental_refined_reference import RefinedReferenceField
from src.clothing.multi_influence_shell import transfer_outer_cage_radial

OUT = ROOT/'artifacts/clothing_audit/synthetic_arm'
# Preregistered diagnostic thresholds, NOT Roblox requirements.
LIMITS = dict(position_p99_over_gap=.1, position_max_over_gap=.25,
              edge_relative_error_p99=.1, neighbor_error_increase_over_gap=.1)


def measure(d, result):
    truth, faces = d['truth'], d['garment_faces']
    error = np.linalg.norm(result-truth, axis=1)/GAP
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1), axis=0)
    lengths = [np.linalg.norm(v[edges[:, 0]]-v[edges[:, 1]], axis=1) for v in (truth, result)]
    edge_error = np.abs(lengths[1]/lengths[0]-1)
    nt, nr = normals(truth, faces), normals(result, faces)
    area_ratio = np.linalg.norm(nr, axis=1)/np.linalg.norm(nt, axis=1)
    points = np.vstack((result, result[faces].mean(1)))
    collision = analytic_penetration(points, float(d['angle']), bool(d['neighbor']))
    clearance = np.linalg.norm(unbend(result, float(d['angle']))[:, :2], axis=1)-BODY_RADIUS
    displacement_error = (result-truth)[edges[:, 1]]-(result-truth)[edges[:, 0]]
    row = dict(position_p99_over_gap=float(np.quantile(error, .99)), position_max_over_gap=float(error.max()),
               position_rms_over_gap=float(np.sqrt(np.mean(error**2))),
               edge_relative_error_p99=float(np.quantile(edge_error, .99)),
               area_ratio_min=float(area_ratio.min()), area_ratio_p99=float(np.quantile(area_ratio, .99)),
               faces_below_tenth_truth_area=int(sum(area_ratio < .1)),
               normals_over_90_degrees_from_truth=int(sum(np.einsum('ij,ij->i', nt, nr) < 0)),
               clearance_over_expected_gap_quantiles=np.quantile(clearance/GAP, [0, .01, .5, .99, 1]).tolist(),
               neighboring_error_difference_over_edge_p99=float(np.quantile(np.linalg.norm(displacement_error, axis=1)/lengths[0], .99)),
               penetration=collision)
    row['passes_diagnostic_gate'] = (row['position_p99_over_gap'] <= LIMITS['position_p99_over_gap']
        and row['position_max_over_gap'] <= LIMITS['position_max_over_gap']
        and row['edge_relative_error_p99'] <= LIMITS['edge_relative_error_p99']
        and collision['inside'] == 0 and row['faces_below_tenth_truth_area'] == 0
        and row['normals_over_90_degrees_from_truth'] == 0)
    return row


def main():
    OUT.mkdir(exist_ok=True)
    summary = dict(limits=LIMITS, cases={})
    variants_by_case = {}
    cases = [('identity', 9, 16, 0., False), ('bend_coarse', 9, 16, np.pi/2, False),
             ('bend_dense', 17, 32, np.pi/2, False), ('bend_neighbor', 9, 16, np.pi/2, True)]
    for key, rings, sides, angle, neighbor in cases:
        d = make_fixture(rings, sides, angle, neighbor)
        np.savez_compressed(OUT/(key+'_input.npz'), **d)
        print(key, 'binding', flush=True)
        cache_name = 'neighbor' if neighbor else ('dense' if rings == 17 else 'coarse')
        binding = bind_source(d, OUT/(cache_name+'_binding.npz'))
        shell, audit = transfer_outer_cage_radial(d['reference_parent'], d['outer_parent'], d['target_body'],
            d['projection_faces'], parity=1, radius_factor=1, return_audit=True)
        variants = dict(truth=d['truth'], radial_prism=evaluate_binding(d, binding, shell),
                        prism_exact_outer=evaluate_binding(d, binding, d['truth_outer']))
        fields = {}
        for level in (0, 2):
            field = RefinedReferenceField(d['reference_parent'], d['target_body'], d['projection_faces'], d['uv_index'], level=level)
            name = 'reference_level_'+str(level)
            variants[name] = field.evaluate(d['garment'])
            ce = np.linalg.norm(field.evaluate(d['reference_parent'])-d['target_body'], axis=1)/GAP
            fields[name] = dict(**field.audit(), cage_position_error_p99_over_gap=float(np.quantile(ce, .99)))
        row = dict(radial_audit=audit, fields=fields,
                   source_binding_residual_p99_over_gap=float(np.quantile(np.linalg.norm(binding['residual'], axis=1), .99)/GAP),
                   outer_error_p99_over_gap=float(np.quantile(np.linalg.norm(shell-d['truth_outer'], axis=1), .99)/GAP),
                   variants={name: measure(d, mesh) for name, mesh in variants.items()})
        # Compare reference constraints over ARM vertices only to exclude neighbor size.
        row['geometry'] = dict(arm_length=LENGTH, clearance=GAP, cage_rings=rings, cage_sides=sides,
                               angle_degrees=float(np.rad2deg(angle)), neighbor=neighbor)
        np.savez_compressed(OUT/(key+'_outputs.npz'), **variants, radial_shell=shell)
        shared = np.vstack([d['body'], *variants.values()])
        panels = []
        for name, mesh in variants.items():
            path = OUT/(key+'_'+name+'.png')
            depth_preview(d['body'], d['body_faces'], mesh, d['garment_faces'], path, shared_garment_vertices=shared)
            panels.append(Image.open(path).convert('RGB'))
        sheet = Image.new('RGB', (panels[0].width, sum(im.height+24 for im in panels)), 'white')
        y = 0
        for name, panel in zip(variants, panels):
            ImageDraw.Draw(sheet).text((8, y+4), key+' | '+name, fill='black')
            sheet.paste(panel, (0, y+24)); y += panel.height+24
        sheet.save(OUT/(key+'_comparison.png'))
        (OUT/(key+'.json')).write_text(json.dumps(row, indent=2), encoding='utf-8')
        summary['cases'][key] = row
        variants_by_case[key] = variants
        print(key, {name: (round(v['position_p99_over_gap'], 4), v['penetration']['inside'], v['passes_diagnostic_gate'])
                    for name, v in row['variants'].items()}, flush=True)
    summary['neighbor_effect'] = {}
    for name in variants_by_case['bend_coarse']:
        delta = np.linalg.norm(variants_by_case['bend_neighbor'][name]-variants_by_case['bend_coarse'][name], axis=1)/GAP
        summary['neighbor_effect'][name] = dict(p99_over_gap=float(np.quantile(delta, .99)), max_over_gap=float(delta.max()))
    files = [Path(__file__), ROOT/'scripts/synthetic_wrap_fixture.py', ROOT/'scripts/experiment_canonical_radial.py',
             ROOT/'scripts/experiment_dual_cage_prism.py', ROOT/'src/clothing/multi_influence_shell.py',
             ROOT/'src/clothing/experimental_refined_reference.py', ROOT/'src/clothing/wrap_layer_fit.py',
             ROOT/'src/clothing/experimental_canonical_radial.py', ROOT/'tests/test_synthetic_wrap_fixture.py']
    files += list(OUT.glob('*_input.npz'))
    summary['sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('neighbor_effect', summary['neighbor_effect'], flush=True)


if __name__ == '__main__':
    main()
