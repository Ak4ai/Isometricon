import numpy as np
from scripts.experiment_synthetic_contact import fixture, metrics, cross_weights, DISTANCES


def test_proximity_sweep_keeps_arm_and_answer_fixed_and_collision_free():
    reference = fixture(.8)
    n = len(reference['reference_parent'])//2
    for distance in DISTANCES:
        d = fixture(distance)
        np.testing.assert_array_equal(d['reference_parent'][:n], reference['reference_parent'][:n])
        np.testing.assert_array_equal(d['target_body'][:n], reference['target_body'][:n])
        np.testing.assert_array_equal(d['truth'], reference['truth'])
        assert distance-.59 > 0  # Sleeve is outside the neighboring body in the source.
        row = metrics(d, d['truth'])
        assert row['passes_diagnostic_gate']
        assert row['penetration']['neighbor_inside'] == 0


def test_penetration_uses_shifted_neighbor_location():
    d = fixture(.6)
    moved = d['truth'].copy()
    moved[0] = [.6, 0, 1]
    assert metrics(d, moved)['penetration']['neighbor_inside'] >= 1


def test_radial_weight_audit_distinguishes_separate_and_close_shells():
    d = fixture(.8); n = len(d['reference_parent'])//2
    weight, pairs = cross_weights(d['reference_parent'], d['outer_parent'], n)
    assert pairs == 0
    assert np.all(weight == 0)
    d = fixture(.72)
    weight, pairs = cross_weights(d['reference_parent'], d['outer_parent'], n)
    assert pairs > 0
    assert np.any(weight[:n] > .1)
    assert np.all((weight >= 0) & (weight <= 1))
