"""Offline area-weighted local similarity field on a refined reference cage.

Not Roblox code. Uniform midpoint subdivision supplies paired quadrature
points; Gaussian weights blend face polar rotations and a common RMS scale.
Bandwidth is fixed from the UNREFINED source for density comparisons. No
prisms, nearest-face assignment, clothing-specific settings or runtime hook.
"""
import numpy as np
from .experimental_canonical_radial import canonical_cages, similarity_scale


def barycentric_samples(level):
    triangles = np.eye(3)[None]
    for _ in range(level):
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        ab, bc, ca = (a+b)/2, (b+c)/2, (c+a)/2
        triangles = np.concatenate([np.stack(v, axis=1) for v in
                                    ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
    return triangles.mean(axis=1)


class RefinedReferenceField:
    def __init__(self, source, target, faces, uv_ids, parity=1, level=2):
        if parity not in (-1, 1) or level not in (0, 1, 2, 3, 4):
            raise ValueError('Invalid parity or refinement level')
        source, _, target, faces, _ = canonical_cages(source, source, target, faces, uv_ids)
        self.scale = similarity_scale(source, target)
        s, t = source[faces], target[faces]
        ns, nt = [np.cross(x[:, 1]-x[:, 0], x[:, 2]-x[:, 0]) for x in (s, t)]
        areas, at = np.linalg.norm(ns, axis=1), np.linalg.norm(nt, axis=1)
        valid = (areas > 1e-12*np.linalg.norm(np.ptp(source, axis=0))**2)
        valid &= at > 1e-12*np.linalg.norm(np.ptp(target, axis=0))**2
        if not valid.any():
            raise ValueError('No usable reference faces')
        self.excluded = int(sum(~valid))
        s, t, ns, nt, areas, at = [x[valid] for x in (s, t, ns, nt, areas, at)]
        # Column-vector map; parity compensates for normal pseudovectors.
        sb = np.stack((s[:, 1]-s[:, 0], s[:, 2]-s[:, 0], ns/np.sqrt(areas[:, None])), axis=2)
        tb = np.stack((t[:, 1]-t[:, 0], t[:, 2]-t[:, 0], parity*nt/np.sqrt(at[:, None])), axis=2)
        u, _, vt = np.linalg.svd(tb @ np.linalg.inv(sb))
        self.rotation = u @ vt
        bary = barycentric_samples(level)
        self.samples = np.einsum('ki,fij->fkj', bary, s)
        paired = np.einsum('ki,fij->fkj', bary, t)
        self.offsets = paired-self.scale*np.einsum('fij,fkj->fki', self.rotation, self.samples)
        self.mass = areas/len(bary)
        self.centers = s.mean(1)
        edges = np.unique(np.sort(np.concatenate([faces[valid][:, [0, 1]], faces[valid][:, [1, 2]],
                                                 faces[valid][:, [2, 0]]]), axis=1), axis=0)
        lengths = np.linalg.norm(source[edges[:, 0]]-source[edges[:, 1]], axis=1)
        self.base_width = .5*float(np.median(lengths[lengths > 0]))
        self.level = level

    def evaluate(self, points, return_frames=False):
        points = np.asarray(points, float)
        output, frames = [], []
        for start in range(0, len(points), 16):
            p = points[start:start+16]
            nearest2 = ((p[:, None]-self.centers[None])**2).sum(2).min(1)
            width2 = nearest2+self.base_width**2
            distance2 = ((p[:, None, None]-self.samples[None])**2).sum(3)
            exponent = -distance2/(2*width2[:, None, None])
            exponent -= exponent.max(axis=(1, 2), keepdims=True)
            weights = np.exp(exponent)*self.mass[None, :, None]
            weights /= weights.sum(axis=(1, 2), keepdims=True)
            rotation = np.einsum('qf,fij->qij', weights.sum(2), self.rotation)
            displacement = np.einsum('qfk,fki->qi', weights, self.offsets)
            output.append(self.scale*np.einsum('qij,qj->qi', rotation, p)+displacement)
            frames.append(rotation.transpose(0, 2, 1))
        result = np.concatenate(output)
        return (result, np.concatenate(frames)) if return_frames else result

    def audit(self):
        return dict(level=self.level, samples=int(np.prod(self.samples.shape[:2])),
                    usable_faces=len(self.samples), excluded_faces=self.excluded,
                    scale=self.scale, base_width=self.base_width,
                    weighting='source area quadrature times Gaussian; unrefined source bandwidth',
                    limitations='spatial support can mix body parts; blended rotations can shrink; no collision guarantee')
