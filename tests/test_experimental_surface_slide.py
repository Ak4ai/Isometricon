import numpy as np
import pytest
from src.clothing.experimental_surface_slide import quadratic_active_set,slide_open_arc,closed_ring_obstruction


def test_qp_active_constraint_and_coupling():
    h=np.array([[2.,-1],[-1,2]])
    x,audit=quadratic_active_set(h,np.zeros(2),np.array([[1.,0]]),np.array([1.]),np.ones(2))
    np.testing.assert_allclose(x,[1,.5],atol=1e-9)
    assert audit['converged']


def test_reject_infeasible_initialization():
    with pytest.raises(ValueError):
        quadratic_active_set(np.eye(1),np.zeros(1),np.eye(1),np.ones(1),np.zeros(1))


def test_slide_obeys_contact_and_edge_constraints():
    source=np.linspace(.05,.85,17)
    theta,audit=slide_open_arc(source,.29,.5,.3,.002)
    distance=np.sqrt(.29**2+.5**2-2*.29*.5*np.cos(theta))
    assert distance.min()>=.302-1e-10
    ratio=np.diff(theta)/np.diff(source)
    assert ratio.min()>=.9-1e-9 and ratio.max()<=1.1+1e-9
    assert audit['converged']
    assert audit['energy']<=audit['initial_penalized_displacement_energy']+1e-9


def test_clear_case_stays_fixed_and_closed_contact_is_obstructed():
    source=np.linspace(.05,.85,17)
    theta,_=slide_open_arc(source,.29,.8,.3,.002)
    np.testing.assert_allclose(theta,source,atol=1e-12)
    assert not closed_ring_obstruction(.29,.8,.3,.002)['obstructed']
    assert closed_ring_obstruction(.29,.5,.3,.002)['obstructed']
