"""Malha colada: triângulos que esticam quando as partes se mexem de modos diferentes."""

import numpy as np

from src.clothing.custom_model import CustomModel
from src.clothing.glb import parse_model
from src.clothing.mesh_repair import sample_poses, stretched_triangles, without
from tests.test_procedural import skinned_glb


def model():
    return parse_model(skinned_glb()[0]).normalize(1.8)


def pose_with_bone_moved(count, bone, offset):
    pose = np.tile(np.identity(4), (count, 1, 1))
    pose[bone, :3, 3] = offset
    return pose


def test_no_triangle_is_stretched_in_the_rest_pose():
    sub = model().submeshes[0]
    rest = np.tile(np.identity(4), (3, 1, 1))
    assert not stretched_triangles(sub, [rest]).any()


def test_a_bone_that_flies_off_stretches_the_triangles_that_join_it_to_the_rest():
    sub = model().submeshes[0]
    far = pose_with_bone_moved(3, 2, (6.0, 0.0, 0.0))
    bad = stretched_triangles(sub, [far])
    assert bad.any() and not bad.all()
    kept = without(sub, bad)
    assert len(kept) == 3 * int((~bad).sum()) and kept.dtype == sub.indices.dtype


def test_repair_cuts_and_can_be_undone_on_a_custom_model():
    custom = CustomModel(parse_model(skinned_glb()[0]), create_gl=False)
    custom.animate()
    whole = custom.triangles
    assert custom.repair_stretch(False) == 0 and custom.triangles == whole
    custom.repair_stretch(True)
    assert custom.triangles <= whole
    custom.repair_stretch(False)
    assert custom.triangles == whole


def test_a_normal_walk_cuts_nothing_from_a_well_made_model():
    custom = CustomModel(parse_model(skinned_glb()[0]), create_gl=False)
    custom.animate()
    assert custom.repair_stretch() == 0         # o procedural não estica uma caixa bem pesada
    assert len(sample_poses(custom.animator)) == 36
