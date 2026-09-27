"""Exact replay and fixed-weight cross-part ablation of the frozen Blocky fit.

Diagnostic only: source weights, rotations, bulk scale and garment bindings stay
fixed. Remove cross-part pairs and normalize surviving weights per destination.
This is not a universal part filter and is never called by production.
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clothing.multi_influence_shell import _neighborhoods, _rotation
from src.clothing.wear_engine import RobloxWearEngine
from scripts.experiment_canonical_radial import evaluate_binding
from scripts.radial_validation_metrics import body_penetration, distortion, seam_report
from scripts.audit_canonical_radial_results import binding_jacobians
from scripts.test_r15_shirt_transfer import depth_preview

INPUT = ROOT/'artifacts/clothing_audit/radial_frames'
OUT = ROOT/'artifacts/clothing_audit/blocky_influences'
KEY = 'blocky_133331049150205'


def labels_for(d):
    engine = RobloxWearEngine(body_type='female')
    lookup = defaultdict(set)
    for name, part in engine.r15_source_cages.items():
        if name.endswith('Forearm'):
            continue
        for uv in part['face_uvs'].reshape(-1, 2):
            lookup[tuple(np.round(uv, 5))].add(name)
    labels = []
    for uv in d['target_uv'][d['uv_index']]:
        names = lookup[tuple(np.round(uv, 5))]
        if len(names) != 1:
            raise ValueError('UV identity must have exactly one body-part label')
        labels.append(next(iter(names)))
    return np.asarray(labels)


def replay(reference, outer, target, faces, labels, scale, parity):
    rotations = np.array([_rotation(reference[ids]-reference[i], target[ids]-target[i], parity)
                          for i, ids in enumerate(_neighborhoods(faces, len(reference), 1))])
    total, own = np.zeros_like(outer), np.zeros_like(outer)
    mass, own_mass = np.zeros(len(outer)), np.zeros(len(outer))
    names = np.unique(labels)
    part_mass = np.zeros((len(outer), len(names)))
    for i, center in enumerate(reference):
        distance = np.linalg.norm(outer-center, axis=1)
        ids = np.flatnonzero(distance <= max(np.linalg.norm(outer[i]-center), 1e-8))
        if i not in ids:
            ids = np.append(ids, i)
        w = 1/np.maximum(distance[ids], 1e-6); w /= w.sum()
        predicted = target[i]+scale*((outer[ids]-center)@rotations[i])
        total[ids] += w[:, None]*predicted; mass[ids] += w
        part_mass[ids, np.searchsorted(names, labels[i])] += w
        keep = labels[ids] == labels[i]
        own[ids[keep]] += w[keep, None]*predicted[keep]; own_mass[ids[keep]] += w[keep]
    if np.any(own_mass <= 0):
        raise ValueError('A destination lost all same-part influences')
    return total/mass[:, None], own/own_mass[:, None], part_mass/mass[:, None], names


def main():
    OUT.mkdir(exist_ok=True)
    paths = [INPUT/(KEY+suffix) for suffix in ('.npz', '_binding.npz', '_outputs.npz', '.json')]
    d, b, cached = [dict(np.load(p)) for p in paths[:3]]
    old = json.loads(paths[3].read_text())
    labels = labels_for(d)
    scale = old['legacy']['bulk_scale']
    shell, own, contributions, names = replay(d['reference_parent'], d['outer_parent'], d['target_body'],
                    d['projection_faces'], labels, scale, int(d['cage_normal_sign']))
    replay_error = float(np.linalg.norm(shell-cached['radial_previous_shell'], axis=1).max())
    if replay_error > 1e-10:
        raise ValueError(f'Replay does not match frozen radial shell: {replay_error}')
    foreign = 1-contributions[np.arange(len(labels)), np.searchsorted(names, labels)]
    binding_faces = b['faces'][b['face_ids']]
    if np.any(labels[binding_faces] != labels[binding_faces[:, 0]][:, None]):
        raise ValueError('Mixed-part binding faces need explicit handling')
    regions = labels[binding_faces[:, 0]]
    support_foreign = np.einsum('ij,ij->i', b['bary'], foreign[binding_faces])
    meshes = dict(radial_previous=cached['radial_previous'], foreign_removed=evaluate_binding(d, b, own))
    report = dict(replay_max_error=replay_error, bulk_scale_frozen=scale, variants={}, witnesses=[],
                  scope='part labels from unambiguous reference UVs; fixed source weights, frames, scale, binding; not runtime')
    masks, depths = {}, {}
    for name, mesh in meshes.items():
        print(name, 'collision audit', flush=True)
        samples = np.vstack((mesh, mesh[d['garment_faces']].mean(1)))
        penetration, inside, distance = body_penetration(samples, d['body'], d['body_faces'], return_samples=True)
        masks[name], depths[name] = inside[:len(mesh)], distance[:len(mesh)]
        out_shell = shell if name == 'radial_previous' else own
        _, inverted = binding_jacobians(d, b, out_shell)
        report['variants'][name] = dict(penetration=penetration,
            distortion=distortion(d['garment'], mesh, d['garment_faces'], old['common_metric_scale']),
            seams=seam_report(d['outer_parent'], out_shell, d['uv_index']),
            binding_inversions=int(sum(inverted)),
            regions={region: dict(vertices=int(sum(regions==region)),
                       penetrating=int(sum(inside[:len(mesh)]&(regions==region))),
                       inverted_bindings=int(sum(inverted&(regions==region)))) for region in np.unique(regions)})
    before, after = masks['radial_previous'], masks['foreign_removed']
    report['penetrating_vertex_transitions'] = dict(recovered=int(sum(before&~after)), newly_inside=int(sum(~before&after)),
                                                   remained_inside=int(sum(before&after)))
    report['foreign_support'] = dict(cage_vertices_with_foreign=int(sum(foreign>1e-9)),
        garment_vertices_with_foreign=int(sum(support_foreign>1e-9)),
        penetrating_vertices_without_foreign=int(sum(before&(support_foreign<1e-9))),
        by_binding_region={region: dict(max=float(support_foreign[regions==region].max()),
                                        mean=float(support_foreign[regions==region].mean())) for region in np.unique(regions)})
    penetrating = np.flatnonzero(before)
    selected = np.unique(np.r_[93, 377, 1486, penetrating[np.argsort(depths['radial_previous'][penetrating])[-8:]]])
    for vertex in selected:
        face = binding_faces[vertex]
        influence = b['bary'][vertex]@contributions[face]
        report['witnesses'].append(dict(vertex=int(vertex), region=str(regions[vertex]),
            support_weight_by_source_part={str(part): float(weight) for part, weight in zip(names, influence) if weight>1e-9},
            level=float(b['levels'][vertex]), residual=float(np.linalg.norm(b['residual'][vertex])),
            before=meshes['radial_previous'][vertex].tolist(), after=meshes['foreign_removed'][vertex].tolist(),
            before_inside=bool(before[vertex]), after_inside=bool(after[vertex]),
            displacement_over_body_height=float(np.linalg.norm(meshes['radial_previous'][vertex]-meshes['foreign_removed'][vertex])/np.ptp(d['body'][:, 2]))))
    shared = np.vstack((d['body'], *meshes.values()))
    panels=[]
    for name, mesh in meshes.items():
        path=OUT/(name+'.png')
        depth_preview(d['body'],d['body_faces'],mesh,d['garment_faces'],path,shared_garment_vertices=shared)
        panels.append(Image.open(path).convert('RGB'))
    sheet=Image.new('RGB',(panels[0].width,sum(p.height+24 for p in panels)),'white'); y=0
    for name,panel in zip(meshes,panels):
        ImageDraw.Draw(sheet).text((8,y+4),name,fill='black');sheet.paste(panel,(0,y+24));y+=panel.height+24
    sheet.save(OUT/'comparison.png')
    np.savez_compressed(OUT/'outputs.npz',**meshes,radial_shell=shell,ablated_shell=own,part_weights=contributions,part_names=names,labels=labels)
    paths += [Path(__file__), ROOT/'src/clothing/multi_influence_shell.py',ROOT/'scripts/experiment_canonical_radial.py',
              ROOT/'src/clothing/wrap_layer_fit.py',ROOT/'scripts/radial_validation_metrics.py']
    report['sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/'SUMMARY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('foreign',report['foreign_support'],flush=True)
    print('transitions',report['penetrating_vertex_transitions'],flush=True)
    print({k:(v['penetration']['penetrating_fraction'],v['distortion']['historical_length_mask']['over_3'],v['binding_inversions'])
           for k,v in report['variants'].items()},flush=True)


if __name__=='__main__':main()
