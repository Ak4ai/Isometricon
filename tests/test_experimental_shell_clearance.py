import numpy as np
from src.clothing.experimental_shell_clearance import ClosedBodyUnion,project_shell_clearance


def cube(low=(-1,-1,-1),high=(1,1,1)):
    v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
    v=np.asarray(low)+(np.asarray(high)-low)*v
    f=np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
    return v,f


def test_union_boundary_does_not_exit_into_neighboring_body_part():
    a,f=cube((-1,-1,-1),(0,1,1));b,_=cube((0,-1,-1),(1,1,1))
    body=ClosedBodyUnion(np.vstack((a,b)),np.vstack((f,f+8)),[np.arange(12),np.arange(12,24)])
    p=np.array([[.01,0,.8]])
    assert body.contains(p)[0]
    target=body.exterior_targets(p,.001)
    assert not body.contains(target)[0]
    np.testing.assert_allclose(target,[[.01,0,1.001]],atol=1e-10)


def test_clearance_moves_a_sheet_outside_without_compressing_its_faces():
    v,f=cube();body=ClosedBodyUnion(v,f,[np.arange(len(f))])
    shell=np.array([[-.3,-.3,.8],[.3,-.3,.8],[.3,.3,.8],[-.3,.3,.8]])
    faces=np.array([[0,1,2],[0,2,3]])
    result,audit=project_shell_clearance(shell,shell,faces,faces,body,margin=.001)
    assert audit['remaining_penetrating_samples']==0
    assert (result[:,2]>1).all()
    np.testing.assert_allclose(result[:,:2],shell[:,:2],atol=1e-10)


def test_clear_shell_is_unchanged():
    v,f=cube();body=ClosedBodyUnion(v,f,[np.arange(len(f))])
    shell=np.array([[-.3,-.3,1.2],[.3,-.3,1.2],[.3,.3,1.2]])
    faces=np.array([[0,1,2]])
    result,audit=project_shell_clearance(shell,shell,faces,faces,body,margin=.001)
    np.testing.assert_array_equal(result,shell)
    assert audit['reason']=='sampled_surface_clear'


def test_export_split_copies_remain_coincident():
    v,f=cube();body=ClosedBodyUnion(v,f,[np.arange(len(f))])
    shell=np.array([[-.3,-.3,.8],[.3,-.3,.8],[.3,.3,.8],[-.3,-.3,.8]])
    faces=np.array([[0,1,2],[3,1,2]])
    result,_=project_shell_clearance(shell,shell,faces,faces,body,margin=.001)
    np.testing.assert_array_equal(result[0],result[3])


def test_linked_garment_sample_moves_its_driving_shell_vertex():
    v,f=cube();body=ClosedBodyUnion(v,f,[np.arange(len(f))])
    shell=np.array([[-.3,-.3,1.2],[.3,-.3,1.2],[0.,.3,1.2]])
    faces=np.array([[0,1,2]])
    linked=dict(indices=np.array([[0]]),weights=np.array([[1.]]),
                offsets=np.array([[0.,0.,-.4]]))
    result,audit=project_shell_clearance(
        shell,shell,faces,np.empty((0,3),int),body,margin=.001,
        linked_samples=linked,
    )
    assert result[0,2]>1.0
    assert audit['linked_sample_count']==1
    assert audit['remaining_penetrating_linked_samples']==0
