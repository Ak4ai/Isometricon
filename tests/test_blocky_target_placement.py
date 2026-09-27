import numpy as np
import pytest
from scripts.audit_blocky_target_placement import local_matrix, apply, section_segments


def test_supported_local_transform():
    m=local_matrix({'Lcl Translation':[1,2,3],'Lcl Rotation':[90,0,0],'Lcl Scaling':[2,2,2]})
    np.testing.assert_allclose(apply(np.array([[0.,1,0]]),m),[[1,2,5]],atol=1e-14)


@pytest.mark.parametrize('props',[{'Lcl Rotation':[0,90,0]},{'RotationPivot':[1,0,0]}])
def test_unsupported_transform_is_explicit(props):
    with pytest.raises(ValueError):local_matrix(props)


def test_section_interpolates_triangle_at_height():
    points=np.array([[0.,0,0],[2,0,2],[0,2,2]])
    segments=section_segments(points,np.array([[0,1,2]]),1.)
    np.testing.assert_allclose(sorted(map(tuple,segments[0])),[(0,1),(1,0)])
