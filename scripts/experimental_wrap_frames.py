"""Offline candidate local maps for cage-transfer comparisons.

None of these are selected by the clothing runtime. The benchmark supplies
them through private experiment hooks in the otherwise unchanged fitter.
"""
import numpy as np


def affine_map(sa, sb, sc, ta, tb, tc, normal_sign=1):
    """Exact tangent map with bounded singular values."""
    source_edges = np.column_stack((sb - sa, sc - sa))
    target_edges = np.column_stack((tb - ta, tc - ta))
    source_cross = np.cross(source_edges[:, 0], source_edges[:, 1])
    target_cross = np.cross(target_edges[:, 0], target_edges[:, 1])
    source_area2 = float(np.linalg.norm(source_cross))
    target_area2 = float(np.linalg.norm(target_cross))
    if source_area2 < 1e-9 or target_area2 < 1e-9:
        return None
    source_normal = source_cross / source_area2
    target_normal = target_cross / target_area2
    tangent = target_edges @ np.linalg.pinv(source_edges, rcond=1e-10)
    normal_scale = np.sqrt(target_area2 / source_area2)
    full_map = tangent + normal_sign * normal_scale * np.outer(target_normal, source_normal)
    u, singular_values, vt = np.linalg.svd(full_map)
    return (u * np.clip(singular_values, 0.08, 1.5)) @ vt


def rotation_map(sa, sb, sc, ta, tb, tc, normal_sign=1):
    """Rotate shell offsets without stretching their thickness."""
    source_edges = np.column_stack((sb - sa, sc - sa))
    target_edges = np.column_stack((tb - ta, tc - ta))
    source_cross = np.cross(source_edges[:, 0], source_edges[:, 1])
    target_cross = np.cross(target_edges[:, 0], target_edges[:, 1])
    source_area2 = float(np.linalg.norm(source_cross))
    target_area2 = float(np.linalg.norm(target_cross))
    if source_area2 < 1e-9 or target_area2 < 1e-9:
        return None
    source_normal = source_cross / source_area2
    target_normal = target_cross / target_area2
    tangent = target_edges @ np.linalg.pinv(source_edges, rcond=1e-10)
    full_map = tangent + normal_sign * np.outer(target_normal, source_normal)
    u, _, vt = np.linalg.svd(full_map)
    return u @ vt


def normalized_edges_map(sa, sb, sc, ta, tb, tc, normal_sign=1):
    """Frame with unit-length triangle edges and area-weighted use."""
    def frame(a, b, c):
        first = b - a
        second = c - a
        normal = np.cross(first, second)
        lengths = (np.linalg.norm(first), np.linalg.norm(second),
                   np.linalg.norm(normal))
        if min(lengths) < 1e-9:
            return None
        return np.column_stack((first / lengths[0], second / lengths[1],
                                normal / lengths[2]))

    source = frame(sa, sb, sc)
    target = frame(ta, tb, tc)
    if source is None or target is None:
        return None
    target[:, 2] *= normal_sign
    return target @ np.linalg.inv(source)
