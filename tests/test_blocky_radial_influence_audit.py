import numpy as np
from scripts.audit_blocky_radial_influences import replay
from scripts.experiment_synthetic_contact import fixture
from src.clothing.multi_influence_shell import transfer_outer_cage_radial


def test_replay_matches_radial_and_weights_sum_to_one():
    d = fixture(.72)
    args = [d[k] for k in ('reference_parent', 'outer_parent', 'target_body', 'projection_faces')]
    n = len(args[0])//2
    labels = np.array(['arm']*n+['neighbor']*n)
    full, ablated, weights, names = replay(*args, labels, 1., 1)
    expected = transfer_outer_cage_radial(*args, radius_factor=1, bulk_scale=1.)
    np.testing.assert_allclose(full, expected, atol=1e-14)
    np.testing.assert_allclose(weights.sum(1), 1., atol=1e-14)
    assert np.linalg.norm(full[:n]-ablated[:n], axis=1).max() > .1
    assert np.any(weights[:n, np.flatnonzero(names=='neighbor')[0]] > .1)


def test_single_part_ablation_is_noop():
    d = fixture(.72)
    args = [d[k] for k in ('reference_parent', 'outer_parent', 'target_body', 'projection_faces')]
    full, ablated, weights, _ = replay(*args, np.array(['same']*len(args[0])), 1., 1)
    np.testing.assert_allclose(full, ablated, atol=1e-14)
    np.testing.assert_allclose(weights, 1., atol=1e-14)
