"""Deterministic, analytic bend benchmark; independent of clothing solvers.

Units are arbitrary. The arm axis is z, cross-sections lie in xy. A circular
bend preserves cross-section radius while its Jacobian determinant is 1+k*x.
It is injective here (positive radial distance and arc shorter than pi).
"""
import numpy as np

LENGTH = 2.0
BODY_RADIUS = .20
INNER_RADIUS = .24
OUTER_RADIUS = .34
SLEEVE_RADIUS = .29
GAP = SLEEVE_RADIUS - BODY_RADIUS
NEIGHBOR_X = .8
NEIGHBOR_RADIUS = .30


def cylinder(radius, rings, sides, zmin=0., zmax=LENGTH, closed=False):
    angle = np.arange(sides)*2*np.pi/sides
    z = np.linspace(zmin, zmax, rings)
    vertices = np.array([[radius*np.cos(a), radius*np.sin(a), h] for h in z for a in angle])
    faces = []
    for ring in range(rings-1):
        for side in range(sides):
            a = ring*sides+side; b = ring*sides+(side+1)%sides
            faces.extend(((a, b, b+sides), (a, b+sides, a+sides)))
    if closed:
        lower, upper = len(vertices), len(vertices)+1
        vertices = np.vstack([vertices, [0, 0, zmin], [0, 0, zmax]])
        for side in range(sides):
            other = (side+1)%sides
            faces.extend(((lower, other, side), (upper, (rings-1)*sides+side, (rings-1)*sides+other)))
    return vertices, np.asarray(faces, int)


def bend(points, angle=np.pi/2):
    points = np.asarray(points, float)
    if abs(angle) < 1e-14:
        return points.copy()
    k = angle/LENGTH
    theta = points[:, 2]*k
    r = 1/k+points[:, 0]
    return np.column_stack((r*np.cos(theta)-1/k, points[:, 1], r*np.sin(theta)))


def unbend(points, angle=np.pi/2):
    points = np.asarray(points, float)
    if abs(angle) < 1e-14:
        return points.copy()
    k = angle/LENGTH
    x = points[:, 0]+1/k
    return np.column_stack((np.hypot(x, points[:, 2])-1/k, points[:, 1],
                            np.arctan2(points[:, 2], x)/k))


def make_fixture(rings=9, sides=16, angle=np.pi/2, neighbor=False):
    inner, faces = cylinder(INNER_RADIUS, rings, sides)
    outer, _ = cylinder(OUTER_RADIUS, rings, sides)
    garment, gf = cylinder(SLEEVE_RADIUS, 17, 32, .15, LENGTH-.15)
    body, bf = cylinder(BODY_RADIUS, 33, 48, closed=True)
    target, truth_outer = bend(inner, angle), bend(outer, angle)
    target_body = bend(body, angle)
    if neighbor:
        ni, nf = cylinder(.34, rings, sides)
        no, _ = cylinder(.40, rings, sides)
        nb, nbf = cylinder(NEIGHBOR_RADIUS, 33, 48, closed=True)
        shift = [NEIGHBOR_X, 0, 0]
        faces = np.vstack((faces, nf+len(inner)))
        inner, outer = np.vstack((inner, ni+shift)), np.vstack((outer, no+shift))
        target, truth_outer = np.vstack((target, ni+shift)), np.vstack((truth_outer, no+shift))
        bf = np.vstack((bf, nbf+len(body)))
        target_body = np.vstack((target_body, nb+shift))
    return dict(reference_parent=inner, outer_parent=outer, target_body=target,
                projection_faces=faces, uv_index=np.arange(len(inner)), cage_normal_sign=np.array(1),
                garment=garment, garment_faces=gf, truth=bend(garment, angle),
                truth_outer=truth_outer, body=target_body, body_faces=bf,
                angle=np.array(angle), neighbor=np.array(neighbor))


def analytic_penetration(points, angle, neighbor=False):
    local = unbend(points, angle)
    depth = np.minimum(BODY_RADIUS-np.linalg.norm(local[:, :2], axis=1),
                       np.minimum(local[:, 2], LENGTH-local[:, 2]))
    if neighbor:
        other = points-np.array([NEIGHBOR_X, 0, 0])
        nd = np.minimum(NEIGHBOR_RADIUS-np.linalg.norm(other[:, :2], axis=1),
                        np.minimum(other[:, 2], LENGTH-other[:, 2]))
        depth = np.maximum(depth, nd)
    return dict(samples=len(points), inside=int(sum(depth > 1e-9)),
                max_interior_margin=float(np.maximum(depth, 0).max(initial=0)))
