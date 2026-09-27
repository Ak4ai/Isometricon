"""Controlled proximity sweep; isolates radial influences from prism binding.

This uses two disconnected analytic volumes, not a stitched human shoulder.
Component-separated output is an oracle diagnostic, not a proposed runtime fix.
"""
from pathlib import Path
import json
import hashlib
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.synthetic_wrap_fixture import make_fixture, GAP, NEIGHBOR_X, analytic_penetration
from scripts.experiment_synthetic_wrap import measure, LIMITS
from scripts.experiment_canonical_radial import bind_source, evaluate_binding
from scripts.test_r15_shirt_transfer import depth_preview
from src.clothing.multi_influence_shell import transfer_outer_cage_radial

OUT = ROOT/'artifacts/clothing_audit/synthetic_contact'
DISTANCES = (.80, .76, .74, .72, .70, .68, .64, .60)


def fixture(distance):
    d = make_fixture(neighbor=True)
    n = len(d['reference_parent'])//2
    for name in ('reference_parent', 'outer_parent', 'target_body', 'truth_outer'):
        d[name][n:, 0] += distance-NEIGHBOR_X
    d['body'][len(d['body'])//2:, 0] += distance-NEIGHBOR_X
    d['neighbor_distance'] = np.array(distance)
    return d


def metrics(d, result):
    # Existing measurements with independent analytic contact at the NEW location.
    arm_only = dict(d, neighbor=np.array(False))
    row = measure(arm_only, result)
    points = np.vstack((result, result[d['garment_faces']].mean(1)))
    torso_points = points + [NEIGHBOR_X-float(d['neighbor_distance']), 0, 0]
    delta = torso_points-np.array([NEIGHBOR_X, 0, 0])
    inside_torso = (np.linalg.norm(delta[:, :2], axis=1)<.30-1e-9)&(delta[:, 2]>1e-9)&(delta[:, 2]<2-1e-9)
    arm = analytic_penetration(points, float(d['angle']))
    row['penetration'] = dict(arm_inside=arm['inside'], neighbor_inside=int(sum(inside_torso)), samples=len(points))
    row['passes_diagnostic_gate'] &= not inside_torso.any()
    return row


def cross_weights(reference, outer, n):
    """Reconstruct the exact radial selection/normalization, no rotations needed."""
    total = np.zeros(len(outer)); cross = np.zeros(len(outer)); pairs = 0
    for i, p in enumerate(reference):
        distance = np.linalg.norm(outer-p, axis=1)
        selected = np.flatnonzero(distance <= max(np.linalg.norm(outer[i]-p), 1e-8))
        if i not in selected:
            selected = np.append(selected, i)
        w = 1/np.maximum(distance[selected], 1e-6); w /= w.sum()
        foreign = (selected<n) != (i<n)
        np.add.at(total, selected, w)
        np.add.at(cross, selected[foreign], w[foreign])
        pairs += int(sum(foreign))
    return cross/total, pairs


def main():
    OUT.mkdir(exist_ok=True)
    arm = make_fixture()
    oracle_binding = bind_source(arm, OUT/'arm_binding.npz')
    report = dict(limits=LIMITS, distances=list(DISTANCES), cases={})
    saved = {}
    for distance in DISTANCES:
        key = f'd{distance:.2f}'
        d = fixture(distance); n = len(d['reference_parent'])//2
        np.savez_compressed(OUT/(key+'_input.npz'), **d)
        print(key, 'binding', flush=True)
        binding = bind_source(d, OUT/(key+'_binding.npz'))
        args = [d[k] for k in ('reference_parent', 'outer_parent', 'target_body', 'projection_faces')]
        shell, audit = transfer_outer_cage_radial(*args, radius_factor=1, return_audit=True)
        separated = np.empty_like(shell)
        for start in (0, n):
            faces = d['projection_faces']; mask = (faces[:, 0]>=start)&(faces[:, 0]<start+n)
            separated[start:start+n] = transfer_outer_cage_radial(
                *[d[k][start:start+n] for k in ('reference_parent', 'outer_parent', 'target_body')],
                faces[mask]-start, radius_factor=1, bulk_scale=audit['bulk_scale'])
        meshes = dict(truth=d['truth'], radial_full=evaluate_binding(d, binding, shell),
            radial_arm_binding=evaluate_binding(d, oracle_binding, shell),
            separated_influences=evaluate_binding(d, binding, separated),
            exact_outer=evaluate_binding(d, binding, d['truth_outer']))
        weights, pairs = cross_weights(d['reference_parent'], d['outer_parent'], n)
        bad_binding = binding['faces'][binding['face_ids']][:, 0] >= n
        row = dict(variants={name: metrics(d, mesh) for name, mesh in meshes.items()}, radial=audit,
            cross_component_pairs=pairs, arm_outer_vertices_with_foreign_weight=int(sum(weights[:n]>0)),
            maximum_foreign_weight_on_arm=float(weights[:n].max()),
            foreign_bound_garment_vertices=int(sum(bad_binding)),
            source_body_surface_gap=distance-.5, source_sleeve_neighbor_body_gap=distance-.59,
            source_outer_surface_gap=distance-.74,
            source_binding_residual_p99_over_gap=float(np.quantile(np.linalg.norm(binding['residual'],axis=1),.99)/GAP),
            arm_outer_position_error_p99_over_gap=float(np.quantile(np.linalg.norm(shell[:n]-d['truth_outer'][:n],axis=1),.99)/GAP))
        worst = np.argsort(np.linalg.norm(meshes['radial_full']-d['truth'], axis=1))[-5:][::-1]
        row['witnesses'] = [dict(vertex=int(i), source=d['garment'][i].tolist(), truth=d['truth'][i].tolist(),
            result=meshes['radial_full'][i].tolist(), cage_face=binding['faces'][binding['face_ids'][i]].tolist(),
            face_foreign_weights=weights[binding['faces'][binding['face_ids'][i]]].tolist()) for i in worst]
        report['cases'][key] = row
        saved[key] = (d, meshes)
        np.savez_compressed(OUT/(key+'_outputs.npz'), **meshes, shell=shell, separated_shell=separated, cross_weights=weights)
        print(key, 'cross', pairs, 'foreign_binding', int(sum(bad_binding)),
              {k: round(v['position_p99_over_gap'],3) for k,v in row['variants'].items()}, flush=True)
    # Show separated, first failing distance, and closest stress case; common scale for entire sweep.
    failing = [k for k, row in report['cases'].items() if not row['variants']['radial_full']['passes_diagnostic_gate']]
    selected = list(dict.fromkeys(['d0.80', *(failing[:1]), 'd0.60']))
    shared = np.vstack([v for d, meshes in saved.values() for v in [d['body'], *meshes.values()]])
    for key in selected:
        d, meshes = saved[key]; panels = []
        for name, mesh in meshes.items():
            path = OUT/(key+'_'+name+'.png')
            depth_preview(d['body'], d['body_faces'], mesh, d['garment_faces'], path, shared_garment_vertices=shared)
            panels.append(Image.open(path).convert('RGB'))
        sheet = Image.new('RGB', (panels[0].width, sum(im.height+24 for im in panels)), 'white'); y=0
        for name, panel in zip(meshes, panels):
            ImageDraw.Draw(sheet).text((8,y+4), key+' | '+name, fill='black')
            sheet.paste(panel,(0,y+24)); y+=panel.height+24
        sheet.save(OUT/(key+'_comparison.png'))
    report['rendered_cases'] = selected
    paths = [Path(__file__), ROOT/'scripts/synthetic_wrap_fixture.py', ROOT/'scripts/experiment_synthetic_wrap.py',
        ROOT/'scripts/experiment_canonical_radial.py', ROOT/'scripts/experiment_dual_cage_prism.py',
        ROOT/'src/clothing/multi_influence_shell.py', ROOT/'src/clothing/wrap_layer_fit.py']+list(OUT.glob('*_input.npz'))
    report['sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
