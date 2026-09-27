"""Representation invariants that the previous radial prototype did not test."""
import numpy as np
import pytest
from src.clothing.experimental_canonical_radial import transfer_canonical_radial
from src.clothing.multi_influence_shell import transfer_outer_cage_radial
from scripts.radial_validation_metrics import body_penetration, prism_jacobians


def fixture():
    r=np.array([[0.,0,0],[2,0,0],[2,1,0],[0,1,0],[.4,.3,1.7]])
    o=r+np.array([[-.1,-.1,-.2],[.2,0,-.1],[.1,.1,0],[0,.1,-.1],[0,0,.3]])
    f=np.array([[0,1,4],[1,2,4],[2,3,4],[3,0,4]])
    return r,o,f


@pytest.mark.parametrize('parity',[-1,1])
@pytest.mark.parametrize('scale',[.23,1.,2.7])
def test_automatic_scale_arbitrary_coordinate_rotation(parity,scale):
    r,o,f=fixture()
    q,_=np.linalg.qr(np.array([[.3,.7,.4],[-.6,.2,.8],[.9,.1,.3]]))
    q[:,0]*=parity*np.linalg.det(q)
    t=scale*r@q+[3,4,-1]
    actual=transfer_canonical_radial(r,o,t,f,np.arange(len(r)),parity=parity)
    np.testing.assert_allclose(actual,scale*o@q+[3,4,-1],atol=1e-10)


def test_split_uv_normal_export_does_not_change_result():
    r,o,f=fixture(); t=r.copy(); t[4]+=[.5,.7,.2]
    base=transfer_canonical_radial(r,o,t,f,np.arange(len(r)))
    ids=f.ravel(); split_faces=np.arange(len(ids)).reshape(-1,3)
    split=transfer_canonical_radial(r[ids],o[ids],t[ids],split_faces,ids)
    np.testing.assert_allclose(split,base[ids],atol=1e-12)
    old=transfer_outer_cage_radial(r,o,t,f,radius_factor=1,bulk_scale=1)
    old_split=transfer_outer_cage_radial(r[ids],o[ids],t[ids],split_faces,radius_factor=1,bulk_scale=1)
    assert np.max(np.abs(old_split-old[ids]))>1e-3


def test_corner_and_face_order_do_not_change_normal_frames():
    r,o,f=fixture();t=r.copy();t[4]+=[.5,.7,.2]
    base=transfer_canonical_radial(r,o,t,f,np.arange(len(r)))
    other=transfer_canonical_radial(r,o,t,f[::-1, [1,2,0]],np.arange(len(r)))
    np.testing.assert_allclose(other,base,atol=1e-10)


def test_conflicting_uv_positions_fail_instead_of_silent_welding():
    r,o,f=fixture()
    with pytest.raises(ValueError,match='Conflicting'):
        transfer_canonical_radial(r,o,r,f,np.zeros(len(r)))


def test_unused_obj_rows_do_not_influence_physical_surface():
    r,o,f=fixture(); t=r.copy();t[4]+=[.5,.7,.2]
    base=transfer_canonical_radial(r,o,t,f,np.arange(len(r)))
    extra=transfer_canonical_radial(np.vstack((r,[100,100,100])),
        np.vstack((o,o[0])),np.vstack((t,[400,300,200])),f,np.arange(len(r)+1))
    np.testing.assert_allclose(extra[:-1],base,atol=1e-10)


def test_closed_body_penetration_and_distances():
    v=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,0,1]])
    f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    result=body_penetration(np.array([[.1,.1,.1],[2,2,2],[0,0,0]]),v,f)
    assert result['closed_components']==1
    assert result['penetrating_samples']==1
    assert result['depth_max_over_body_height']==pytest.approx(.1)


def test_touching_body_parts_do_not_become_nonmanifold_by_global_welding():
    v=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,0,1]])
    f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    body=np.vstack((v,v*[1,1,-1]))
    faces=np.vstack((f,f[:,::-1]+4))
    result=body_penetration(np.array([[.1,.1,.1],[.1,.1,-.1],[2,2,2]]),body,faces)
    assert result['closed_components']==2
    assert result['penetrating_samples']==2


def test_prism_jacobian_distinguishes_reflection_from_inversion():
    i=np.array([[0.,0,0],[1,0,0],[0,1,0]])
    o=i+[0,0,1];f=np.array([[0,1,2]])
    q=np.diag([-1,1,1])
    assert prism_jacobians(i,o,i@q,o@q,f,-1)['inverted_samples']==0
    assert prism_jacobians(i,o,i,i-[0,0,1],f,1)['inverted_samples']==12
