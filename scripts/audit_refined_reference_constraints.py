"""Measure whether the reference field actually reaches cage correspondences."""
from pathlib import Path
import json
import sys
import hashlib
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.experimental_refined_reference import RefinedReferenceField
from src.clothing.experimental_canonical_radial import canonical_cages


def main():
    inputs = ROOT/'artifacts/clothing_audit/radial_frames'
    report = {}
    for p in sorted(inputs.glob('*_binding.npz')):
        key = p.name.removesuffix('_binding.npz')
        data_path = inputs/(key+'.npz')
        d = dict(np.load(data_path))
        r, _, target, faces, _ = canonical_cages(d['reference_parent'], d['outer_parent'],
                                                 d['target_body'], d['projection_faces'], d['uv_index'])
        used = np.unique(faces)
        height = np.ptp(d['body'][:, 2])
        _, inv, counts = np.unique(np.round(r[used], 8), axis=0, return_inverse=True, return_counts=True)
        means = np.zeros((len(counts), 3))
        np.add.at(means, inv, target[used])
        spread = np.linalg.norm(target[used]-means[inv]/counts[inv, None], axis=1)/height
        row = {'coincident_source_target_spread_max_over_height': float(spread.max()),
               'input_sha256': hashlib.sha256(data_path.read_bytes()).hexdigest()}
        for level in (0, 2):
            field = RefinedReferenceField(r, target, faces, np.arange(len(r)), int(d['cage_normal_sign']), level)
            error = np.linalg.norm(field.evaluate(r[used])-target[used], axis=1)/height
            worst = np.argsort(error)[-10:][::-1]
            row[str(level)] = dict(max=float(error.max()), p99=float(np.quantile(error, .99)),
                                  median=float(np.median(error)), vertices_over_one_percent=int(sum(error > .01)),
                                  worst_uv_vertex_indices=used[worst].tolist())
        report[key] = row
        print(key, {k: v for k, v in row.items() if k != 'input_sha256'}, flush=True)
    result = dict(cases=report, units='all distances normalized by body height',
                  sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__), ROOT/'src/clothing/experimental_refined_reference.py')})
    out = ROOT/'artifacts/clothing_audit/refined_reference/CAGE_CONSTRAINTS.json'
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
