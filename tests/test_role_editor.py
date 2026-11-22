"""Os papéis dos ossos osso por osso: rótulos, refazer as cadeias e achar o osso sob o clique."""

import numpy as np

from src.clothing.procedural import LEFT, RIGHT, Roles, auto_roles
from src.clothing.role_editor import (LABELS, bone_at, labels_from_roles, posed_positions, roles_from_labels,
                                      screen_positions)
from tests.test_procedural import biped, quadruped


def test_labels_cover_every_bone_and_match_the_roles():
    rig = biped()
    roles = auto_roles(rig, 1.8)
    labels = labels_from_roles(rig, roles)
    assert len(labels) == len(rig) and set(labels) <= set(LABELS)
    assert all(labels[b] == "perna" for limb in roles.legs for b in limb.chain)
    assert all(labels[b] == "braco" for limb in roles.arms for b in limb.chain)
    assert all(labels[b] == "cabeca" for b in roles.head)


def test_unchanged_labels_give_back_the_same_roles():
    for make, height in ((biped, 1.8), (quadruped, 1.0)):
        rig = make()
        roles = auto_roles(rig, height)
        again = roles_from_labels(rig, labels_from_roles(rig, roles), roles)
        a, b = again.to_dict(rig), roles.to_dict(rig)
        for key in ("perfil", "pernas", "bracos", "cabeca", "cauda"):   # (a coluna do quadrúpede acha ossos de pata)
            assert a[key] == b[key], key


def test_relabeling_a_leg_bone_as_nothing_shortens_that_leg():
    rig = biped()
    roles = auto_roles(rig, 1.8)
    labels = labels_from_roles(rig, roles)
    leg = roles.legs[0]
    labels[leg.chain[-1]] = "nenhum"
    new = roles_from_labels(rig, labels, roles)
    shortened = next(l for l in new.legs if l.chain[0] == leg.chain[0])
    assert shortened.chain == leg.chain[:-1] and shortened.side == leg.side
    assert len(new.legs) == len(roles.legs)


def test_a_new_limb_gets_its_side_from_where_it_is():
    rig = biped()
    roles = auto_roles(rig, 1.8)
    labels = labels_from_roles(rig, roles)
    arm = roles.arms[0]
    for bone in arm.chain:                  # o braço vira uma perna: o lado continua o do osso
        labels[bone] = "perna"
    new = roles_from_labels(rig, labels, roles)
    assert len(new.legs) == len(roles.legs) + 1 and len(new.arms) == len(roles.arms) - 1
    moved = next(l for l in new.legs if l.chain[0] == arm.chain[0])
    assert moved.side == arm.side and moved.side in (LEFT, RIGHT)


def test_the_profile_follows_the_number_of_legs_only_when_it_changes():
    rig = quadruped()
    roles = auto_roles(rig, 1.0)
    assert roles.profile == "quadrupede"
    labels = labels_from_roles(rig, roles)
    for b in roles.legs[0].chain:
        labels[b] = "nenhum"
    assert roles_from_labels(rig, labels, roles).profile in ("bipede", "quadrupede", "rastejante", "flutuante")
    same = roles_from_labels(rig, labels_from_roles(rig, roles), roles)
    assert same.profile == "quadrupede"


def test_the_posed_position_of_a_bone_follows_the_pose():
    rig = biped()
    assert np.allclose(posed_positions(rig, None), rig.rest_positions)
    assert np.allclose(posed_positions(rig, rig.solve()), rig.rest_positions, atol=1e-9)
    rotations = rig.identity_rotations()
    from src.clothing.rig import rotation_matrix
    child = int(rig.children[rig.roots[0]][0])
    rotations[rig.roots[0]] = rotation_matrix((0, 0, 1), np.pi / 2)
    moved = posed_positions(rig, rig.solve(rotations))
    assert not np.allclose(moved[child], rig.rest_positions[child])
    assert np.allclose(moved[rig.roots[0]], rig.rest_positions[rig.roots[0]])


def test_screen_projection_and_picking_choose_the_nearest_bone():
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    ident = np.identity(4)
    xy, depth = screen_positions(points, ident, ident, ident, (0, 0, 200, 100))
    assert np.allclose(xy[0], [100, 50]) and np.allclose(xy[1], [200, 50])
    depth = np.array([0.0, 0.0, 5.0])
    assert bone_at(xy, depth, 102, 52) == 0
    assert bone_at(xy, depth, 198, 50) == 2          # dois no mesmo ponto: o mais perto da câmera
    assert bone_at(xy, depth, 150, 50) is None
