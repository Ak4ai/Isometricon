"""Factorial diagnostic: isolate support contamination from global RMS scale.

Only changes experiment object state; never edits the implementation/runtime.
Offsets are recomputed consistently when substituting the measured bulk scale.
"""
from pathlib import Path
import json
import hashlib
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.synthetic_wrap_fixture import make_fixture, GAP
from scripts.experiment_synthetic_wrap import measure, OUT
from src.clothing.experimental_refined_reference import RefinedReferenceField


def main():
    fixtures = {label: make_fixture(neighbor=neighbor) for label, neighbor in [('alone', False), ('neighbor', True)]}
    fields = {label: RefinedReferenceField(d['reference_parent'], d['target_body'], d['projection_faces'],
                                          d['uv_index'], level=2) for label, d in fixtures.items()}
    scales = {label: field.scale for label, field in fields.items()}
    report = dict(scales=scales, variants={})
    outputs = {}
    for label, field in fields.items():
        for scale_label, scale in scales.items():
            old_scale = field.scale
            field.offsets += (old_scale-scale)*np.einsum('fij,fkj->fki', field.rotation, field.samples)
            field.scale = scale
            key = label+'_scale_'+scale_label
            output = field.evaluate(fixtures[label]['garment'])
            outputs[key] = output
            report['variants'][key] = measure(fixtures[label], output)
    for scale_label in scales:
        delta = np.linalg.norm(outputs['alone_scale_'+scale_label]-outputs['neighbor_scale_'+scale_label], axis=1)/GAP
        report['neighbor_change_with_fixed_'+scale_label+'_scale'] = dict(p99_over_gap=float(np.quantile(delta, .99)),
                                                                         max_over_gap=float(delta.max()))
    d, field = fixtures['neighbor'], fields['neighbor']
    error = np.linalg.norm(outputs['neighbor_scale_neighbor']-d['truth'], axis=1)
    report['largest_error_witnesses'] = []
    for vertex in np.argsort(error)[-5:][::-1]:
        point = d['garment'][vertex]
        width2 = ((point-field.centers)**2).sum(1).min()+field.base_width**2
        e = -((point-field.samples)**2).sum(2)/(2*width2)
        w = np.exp(e-e.max())*field.mass[:, None]
        w /= w.sum()
        other = field.centers[:, 0] > .4
        report['largest_error_witnesses'].append(dict(vertex=int(vertex), source=point.tolist(),
            truth=d['truth'][vertex].tolist(), result=outputs['neighbor_scale_neighbor'][vertex].tolist(),
            weight_on_stationary_neighbor=float(w[other].sum()), error_over_gap=float(error[vertex]/GAP)))
    paths = [Path(__file__), ROOT/'scripts/synthetic_wrap_fixture.py', ROOT/'src/clothing/experimental_refined_reference.py']
    report['sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    OUT.mkdir(exist_ok=True)
    (OUT/'NEIGHBOR_ABLATION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    np.savez_compressed(OUT/'neighbor_ablation_outputs.npz', **outputs)
    print({name: row['position_p99_over_gap'] for name, row in report['variants'].items()})
    print({name: value for name, value in report.items() if name.startswith('neighbor_change')})


if __name__ == '__main__':
    main()
