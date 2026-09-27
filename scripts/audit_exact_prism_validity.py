"""Audit frozen six-case fixtures without fitting or rendering again."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.experimental_prism_validity import determinant_bounds

INPUT = ROOT / 'artifacts/clothing_audit/radial_frames'
OUT = ROOT / 'artifacts/clothing_audit/prism_clearance'


def measure(low, high, faces):
    minimum, maximum, corner, depth = determinant_bounds(low[faces], high[faces])
    epsilon = 1e-12 * np.linalg.norm(np.ptp(low, axis=0)) ** 3
    mixed = (minimum < -epsilon) & (maximum > epsilon)
    singular = (minimum <= epsilon) & (maximum >= -epsilon)
    ids = np.flatnonzero(mixed)
    return dict(cells=len(faces), mixed_sign_cells=int(mixed.sum()),
                zero_or_near_zero_cells_including_mixed=int(singular.sum()),
                strictly_positive_cells=int(sum(minimum > epsilon)),
                strictly_negative_cells=int(sum(maximum < -epsilon)),
                tolerance=float(epsilon), mixed_face_ids=ids.tolist(),
                witnesses=[dict(face=faces[i].tolist(), minimum=float(minimum[i]),
                                maximum=float(maximum[i]), minimum_corner=int(corner[i]),
                                minimum_depth=float(depth[i])) for i in ids[:10]])


def main():
    report = {'scope': 'Exact extrema of each paired linear wedge Jacobian up to roundoff; '
              'not global injectivity, seam validity or collision certification.', 'cases': {}, 'sha256': {}}
    for path in sorted(INPUT.glob('*_binding.npz')):
        key = path.name.removesuffix('_binding.npz')
        files = [path, INPUT / (key + '.npz'), INPUT / (key + '_outputs.npz')]
        b, d, outputs = [dict(np.load(p)) for p in files]
        faces = b['faces'][np.unique(b['face_ids'])]
        row = {'source': measure(d['reference_parent'], d['outer_parent'], faces),
               'radial_target': measure(d['target_body'], outputs['radial_previous_shell'], faces)}
        guarded = OUT / (key + '.npz')
        if guarded.exists():
            row['guarded_target'] = measure(d['target_body'], np.load(guarded)['after_shell'], faces)
            files.append(guarded)
        report['cases'][key] = row
        for p in files:
            report['sha256'][str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
        print(key, {k: (v['mixed_sign_cells'], v['zero_or_near_zero_cells_including_mixed'])
                    for k, v in row.items()})
    for p in [Path(__file__), ROOT / 'src/clothing/experimental_prism_validity.py']:
        report['sha256'][str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'EXACT_PRISM_VALIDITY.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
