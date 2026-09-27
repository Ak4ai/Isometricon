import numpy as np
from src.clothing.experimental_prism_constraints import PrismShapeConstraints


def guard(target_height=1.,parity=1):
    low=np.array([[0.,0,0],[1,0,0],[0,1,0]])
    high=low+[0,0,1]
    target=low.copy();target[:,0]*=parity
    outer=target+[0,0,target_height]
    f=np.array([[0,1,2]])
    g=PrismShapeConstraints(outer,np.arange(3),low,high,target,f,f,
                           np.array([[.2,.3,.5]]),np.array([.37]),parity)
    return outer,g


def test_surface_orientation_alone_does_not_protect_the_prism():
    outer,g=guard()
    inverted=outer.copy();inverted[:,2]=-1
    np.testing.assert_allclose(np.cross(outer[1]-outer[0],outer[2]-outer[0]),
                               np.cross(inverted[1]-inverted[0],inverted[2]-inverted[0]))
    assert not g.accepts(inverted,0)
    assert g.audit()['rejected_trial_moves']['volume']==1
    assert g.audit()['volume_samples']==13  # grid plus actual binding location


def test_reflected_coordinate_system_keeps_valid_initial_prisms():
    outer,g=guard(parity=-1)
    assert all(g.accepts(outer,i) for i in range(3))
    assert g.audit()['initial_inverted_samples']==0


def test_initial_inversion_may_improve_but_cannot_become_worse():
    outer,g=guard(target_height=-1)
    improved=outer.copy();improved[:,2]=-.75
    assert g.accepts(improved,0)
    worse=outer.copy();worse[:,2]=-1.2
    assert not g.accepts(worse,0)


def test_large_translation_without_volume_inversion_is_rejected_by_thickness():
    outer,g=guard()
    shifted=outer+[3,0,0]
    assert not g.accepts(shifted,0)
    assert g.audit()['rejected_trial_moves']['thickness']==1
