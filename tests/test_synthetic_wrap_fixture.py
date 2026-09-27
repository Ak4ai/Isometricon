import numpy as np
from scripts.synthetic_wrap_fixture import make_fixture, bend, unbend, analytic_penetration, GAP, BODY_RADIUS
from scripts.radial_validation_metrics import body_components


def test_bend_inverse_and_positive_jacobian():
    points = np.random.default_rng(4).uniform([-.4, -.4, 0], [.4, .4, 2], (100, 3))
    np.testing.assert_allclose(unbend(bend(points)), points, atol=1e-14)
    h = 1e-6
    j = np.stack([(bend(points+np.eye(3)[i]*h)-bend(points-np.eye(3)[i]*h))/(2*h)
                  for i in range(3)], axis=2)
    np.testing.assert_allclose(np.linalg.det(j), 1+np.pi/4*points[:, 0], atol=1e-9)
    assert np.all(np.linalg.det(j) > 0)


def test_ground_truth_clearance_and_body_mesh_closure():
    for neighbor in (False, True):
        d = make_fixture(neighbor=neighbor)
        recovered = unbend(d['truth'])
        np.testing.assert_allclose(np.linalg.norm(recovered[:, :2], axis=1)-BODY_RADIUS, GAP, atol=1e-14)
        samples = np.vstack((d['truth'], d['truth'][d['garment_faces']].mean(1)))
        assert analytic_penetration(samples, float(d['angle']), neighbor)['inside'] == 0
        components = body_components(d['body'], d['body_faces'])
        assert len(components) == 1+neighbor
        assert all(closed for _, closed in components)


def test_penetration_detects_arm_and_neighbor_interior():
    points = np.vstack((bend(np.array([[0., 0, 1]])), [.8, 0, 1]))
    assert analytic_penetration(points, np.pi/2, True)['inside'] == 2
