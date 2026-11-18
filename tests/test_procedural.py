"""Testes do esqueleto, dos papéis dos ossos e da animação procedural (sem OpenGL)."""

import json

import numpy as np
import pytest

from src.clothing import glb as glb_module
from src.clothing.glb import ModelError, parse_model
from src.clothing.glb_writer import GlbBuilder, box
from src.clothing.procedural import (
    LEFT,
    PROFILE_NAMES,
    PROFILES,
    RIGHT,
    ProceduralAnimator,
    Roles,
    RolesError,
    auto_roles,
    suggest_profile,
)
from src.clothing.rig import MAX_BONES, Rig, rotation_matrix


def make_rig(bones):
    """Um Rig só de translações: ``bones`` é uma lista de (nome, pai, posição de montagem no mundo)."""
    names = [b[0] for b in bones]
    parents = np.array([-1 if b[1] is None else names.index(b[1]) for b in bones])
    world = np.tile(np.identity(4), (len(bones), 1, 1))
    for i, b in enumerate(bones):
        world[i][:3, 3] = b[2]
    local = np.array([world[i] if parents[i] < 0 else np.linalg.inv(world[parents[i]]) @ world[i]
                      for i in range(len(bones))])
    return Rig(names, parents, local, np.array([np.linalg.inv(w) for w in world]))


def biped():
    """Um humanoide de 1,8 m: quadril com duas pernas e a coluna; no peito, a cabeça e dois braços."""
    return make_rig([
        ("quadril", None, (0, 0.95, 0)),
        ("coxa_e", "quadril", (0.12, 0.9, 0)), ("joelho_e", "coxa_e", (0.12, 0.5, 0.02)),
        ("pe_e", "joelho_e", (0.12, 0.1, 0.05)),
        ("coxa_d", "quadril", (-0.12, 0.9, 0)), ("joelho_d", "coxa_d", (-0.12, 0.5, 0.02)),
        ("pe_d", "joelho_d", (-0.12, 0.1, 0.05)),
        ("coluna", "quadril", (0, 1.15, 0)), ("peito", "coluna", (0, 1.4, 0)),
        ("pescoco", "peito", (0, 1.55, 0)), ("cabeca", "pescoco", (0, 1.7, 0.03)),
        ("ombro_e", "peito", (0.2, 1.45, 0)), ("cotovelo_e", "ombro_e", (0.3, 1.15, 0)),
        ("mao_e", "cotovelo_e", (0.32, 0.85, 0.05)),
        ("ombro_d", "peito", (-0.2, 1.45, 0)), ("cotovelo_d", "ombro_d", (-0.3, 1.15, 0)),
        ("mao_d", "cotovelo_d", (-0.32, 0.85, 0.05)),
    ])


def quadruped():
    """Um bicho de quatro patas, de frente para +z, com cabeça e rabo."""
    return make_rig([
        ("quadril", None, (0, 0.6, -0.5)),
        ("coxa_te", "quadril", (0.15, 0.55, -0.5)), ("joelho_te", "coxa_te", (0.15, 0.3, -0.45)),
        ("pata_te", "joelho_te", (0.15, 0.05, -0.5)),
        ("coxa_td", "quadril", (-0.15, 0.55, -0.5)), ("joelho_td", "coxa_td", (-0.15, 0.3, -0.45)),
        ("pata_td", "joelho_td", (-0.15, 0.05, -0.5)),
        ("lombo", "quadril", (0, 0.65, -0.1)), ("peito", "lombo", (0, 0.68, 0.4)),
        ("pata_fe_a", "peito", (0.15, 0.55, 0.45)), ("pata_fe_b", "pata_fe_a", (0.15, 0.3, 0.5)),
        ("pata_fe_c", "pata_fe_b", (0.15, 0.05, 0.45)),
        ("pata_fd_a", "peito", (-0.15, 0.55, 0.45)), ("pata_fd_b", "pata_fd_a", (-0.15, 0.3, 0.5)),
        ("pata_fd_c", "pata_fd_b", (-0.15, 0.05, 0.45)),
        ("pescoco", "peito", (0, 0.8, 0.6)), ("cabeca", "pescoco", (0, 0.85, 0.85)),
        ("rabo_a", "quadril", (0, 0.65, -0.8)), ("rabo_b", "rabo_a", (0, 0.7, -1.0)),
    ])


# ---------------------------------------------------------------------------------------------- Rig
def test_rest_pose_gives_identity_skin_matrices():
    rig = biped()
    assert np.allclose(rig.solve(), np.tile(np.identity(4), (len(rig), 1, 1)))
    assert np.allclose(rig.solve(rig.identity_rotations()), np.tile(np.identity(4), (len(rig), 1, 1)))


def test_a_rotation_turns_the_bone_around_its_own_position_and_children_follow():
    rig = biped()
    hip, knee, foot = rig.index("coxa_e"), rig.index("joelho_e"), rig.index("pe_e")
    rotations = rig.identity_rotations()
    rotations[hip] = rotation_matrix((1, 0, 0), np.radians(-90))        # balança a perna para a frente
    skin = rig.solve(rotations)
    pivot = rig.rest_positions[hip]
    for bone in (knee, foot):                                            # o osso que pende vai para +z
        bind = np.append(rig.rest_positions[bone], 1.0)
        moved = (skin[bone] @ bind)[:3]
        expected = rotation_matrix((1, 0, 0), np.radians(-90)) @ (rig.rest_positions[bone] - pivot) + pivot
        assert np.allclose(moved, expected, atol=1e-9)
    assert (skin[foot] @ np.append(rig.rest_positions[foot], 1.0))[2] > 0.3
    other = rig.index("coxa_d")                                          # o outro lado não se mexe
    assert np.allclose(skin[other], np.identity(4))


def test_rotations_in_the_parent_and_the_child_add_up():
    rig = biped()
    hip, knee, foot = rig.index("coxa_e"), rig.index("joelho_e"), rig.index("pe_e")
    rotations = rig.identity_rotations()
    rotations[hip] = rotation_matrix((1, 0, 0), np.radians(-30))
    rotations[knee] = rotation_matrix((1, 0, 0), np.radians(40))
    skin = rig.solve(rotations)
    bind_foot = np.append(rig.rest_positions[foot], 1.0)
    # a mão faz o mesmo à mão: gira o pé em volta do joelho (40°) e depois tudo em volta do quadril (-30°)
    knee_pos, hip_pos = rig.rest_positions[knee], rig.rest_positions[hip]
    step1 = rotation_matrix((1, 0, 0), np.radians(40)) @ (rig.rest_positions[foot] - knee_pos) + knee_pos
    step2 = rotation_matrix((1, 0, 0), np.radians(-30)) @ (step1 - hip_pos) + hip_pos
    assert np.allclose((skin[foot] @ bind_foot)[:3], step2, atol=1e-9)


def test_root_offset_moves_the_whole_body():
    rig = biped()
    skin = rig.solve(None, (0.0, 0.2, 0.0))
    for bone in range(len(rig)):
        assert np.allclose((skin[bone] @ np.append(rig.rest_positions[bone], 1.0))[:3],
                           rig.rest_positions[bone] + (0, 0.2, 0))


def test_a_rig_whose_children_come_before_their_parents_still_solves():
    rig = make_rig([("filho", "pai", (0, 1, 0)), ("pai", None, (0, 0, 0))])
    assert rig.order == [1, 0]
    assert np.allclose(rig.solve(), np.tile(np.identity(4), (2, 1, 1)))
    with pytest.raises(ValueError):
        Rig(["a", "b"], np.array([1, 0]), np.tile(np.identity(4), (2, 1, 1)), np.tile(np.identity(4), (2, 1, 1)))


def test_transforming_the_rig_matches_transforming_the_mesh():
    rig = biped()
    matrix = np.identity(4)
    matrix[:3, :3] = np.diag([2.0, 2.0, 2.0]) @ rotation_matrix((0, 1, 0), np.radians(90))
    matrix[:3, 3] = (0.3, -0.1, 0.5)
    moved = rig.transformed(matrix)
    rotations = rig.identity_rotations()
    rotations[rig.index("cotovelo_e")] = rotation_matrix((1, 0, 0), np.radians(50))
    # a mesma pose, depois de a escala e o giro virem do modelo, tem que dar o mesmo resultado nos vértices
    moved_rotations = moved.identity_rotations()
    moved_rotations[moved.index("cotovelo_e")] = rotation_matrix((1, 0, 0), np.radians(50))
    assert np.allclose(moved.solve(), np.tile(np.identity(4), (len(moved), 1, 1)), atol=1e-9)
    assert np.allclose(moved.rest_positions, (matrix[:3, :3] @ rig.rest_positions.T).T + matrix[:3, 3])
    assert np.isfinite(moved.solve(moved_rotations)).all()


# ---------------------------------------------------------------------------------------------- glb com esqueleto
def skinned_glb(bone_names=("raiz", "meio", "ponta")):
    """Uma caixa alta com três ossos em linha e pesos: embaixo no osso 0, no meio no 1, em cima no 2."""
    builder = GlbBuilder()
    nodes = []
    for i, name in enumerate(bone_names):
        nodes.append(builder.add_node(name=name, translation=(0.0, 0.0 if i == 0 else 1.0, 0.0)))
    for i in range(len(nodes) - 1):
        builder.nodes[nodes[i]]["children"] = [nodes[i + 1]]
    positions, normals, uvs, indices = box((-0.2, 0.0, -0.2), (0.2, 3.0, 0.2))
    joints = np.zeros((len(positions), 4), dtype=np.uint16)
    weights = np.zeros((len(positions), 4), dtype=np.float32)
    joints[:, 0] = np.clip((positions[:, 1] // 1.0).astype(int), 0, len(nodes) - 1)
    weights[:, 0] = 1.0
    world = [np.identity(4) for _ in nodes]
    for i in range(len(nodes)):
        world[i][1, 3] = float(i)
    mesh = builder.add_mesh(positions, indices, normals, uvs, joints=joints, weights=weights)
    skin = builder.add_skin(nodes, [np.linalg.inv(w) for w in world])
    body = builder.add_node(mesh=mesh, skin=skin, name="corpo")
    return builder.build([nodes[0], body]), nodes


def test_the_skeleton_and_the_weights_are_read():
    data, _ = skinned_glb()
    model = parse_model(data)
    rig = model.rig
    assert rig is not None and rig.names == ["raiz", "meio", "ponta"] and list(rig.parents) == [-1, 0, 1]
    assert np.allclose(rig.rest_positions, [(0, 0, 0), (0, 1, 0), (0, 2, 0)])
    assert np.allclose(rig.inverse_bind[2][:3, 3], (0, -2, 0))
    sub = model.submeshes[0]
    assert sub.joints.shape == (24, 4) and sub.weights.shape == (24, 4)
    assert np.allclose(sub.weights.sum(axis=1), 1.0) and sub.joints.max() <= 2
    assert np.allclose(rig.solve(), np.tile(np.identity(4), (3, 1, 1)), atol=1e-6)


def test_normalizing_a_skinned_model_keeps_skin_and_skeleton_in_step():
    data, _ = skinned_glb()
    model = parse_model(data).normalize(1.8, yaw_turns=1)
    assert np.allclose(model.rig.solve(), np.tile(np.identity(4), (3, 1, 1)), atol=1e-6)
    low, high = model.bounds()
    assert low[1] == pytest.approx(0.0) and high[1] == pytest.approx(1.8)
    positions = model.rig.rest_positions
    assert positions[:, 1].max() <= 1.8 + 1e-6 and positions[0, 1] == pytest.approx(0.0, abs=1e-6)


def test_a_posed_vertex_follows_its_bone():
    data, _ = skinned_glb()
    model = parse_model(data)
    rig, sub = model.rig, model.submeshes[0]
    rotations = rig.identity_rotations()
    rotations[1] = rotation_matrix((0, 0, 1), np.radians(90))            # o osso do meio tomba
    skin = rig.solve(rotations)
    index = int(np.argmax((sub.joints[:, 0] == 1) & (sub.vertices[:, 1] > 1.5)))   # um vértice do osso do meio
    bind = np.append(sub.vertices[index, :3], 1.0)
    posed = (sum(sub.weights[index, k] * skin[sub.joints[index, k]] for k in range(4)) @ bind)[:3]
    assert not np.allclose(posed, bind[:3]) and np.isclose(np.linalg.norm(posed - (0, 1, 0)),
                                                           np.linalg.norm(bind[:3] - (0, 1, 0)))


def test_skeleton_limits(monkeypatch):
    data, _ = skinned_glb()
    monkeypatch.setattr(glb_module, "MAX_BONES", 2)
    with pytest.raises(ModelError, match="ossos"):
        parse_model(data)
    monkeypatch.undo()
    builder = GlbBuilder()
    node = builder.add_node(name="so")
    positions, normals, uvs, indices = box((0, 0, 0), (1, 1, 1))
    joints = np.full((24, 4), 5, dtype=np.uint16)                         # aponta para um osso que não existe
    mesh = builder.add_mesh(positions, indices, normals, uvs, joints=joints, weights=np.tile([1.0, 0, 0, 0], (24, 1)))
    skin = builder.add_skin([node])
    body = builder.add_node(mesh=mesh, skin=skin)
    with pytest.raises(ModelError, match="osso"):
        parse_model(builder.build([node, body]))
    assert MAX_BONES == 64


def test_the_shader_has_room_for_the_largest_skeleton():
    with open("assets/shaders/world_textured.vert", encoding="utf-8") as handle:
        assert f"u_Bones[{MAX_BONES}]" in handle.read()


# ---------------------------------------------------------------------------------------------- papéis
def test_auto_roles_for_a_biped():
    rig = biped()
    roles = auto_roles(rig, 1.8)
    names = lambda chain: [rig.names[i] for i in chain]
    assert roles.profile == "bipede" and len(roles.legs) == 2 and len(roles.arms) == 2
    assert names(roles.head) == ["pescoco", "cabeca"] or names(roles.head)[-1] == "cabeca"
    assert names(roles.spine)[0] == "quadril"
    left_leg = next(l for l in roles.legs if l.side == LEFT)
    assert names(left_leg.chain) == ["coxa_e", "joelho_e", "pe_e"]
    assert names(next(l for l in roles.arms if l.side == RIGHT).chain) == ["ombro_d", "cotovelo_d", "mao_d"]


def test_auto_roles_for_a_quadruped_finds_four_legs_the_head_and_the_tail():
    rig = quadruped()
    roles = auto_roles(rig, 1.0)
    assert roles.profile == "quadrupede" and len(roles.legs) == 4
    assert sorted((l.side, l.end) for l in roles.legs) == [(-1, -1), (-1, 1), (1, -1), (1, 1)]   # um de cada canto
    assert rig.names[roles.head[-1]] == "cabeca" and [rig.names[i] for i in roles.tail][0] == "rabo_a"


def test_a_creature_without_legs_floats():
    rig = make_rig([("raiz", None, (0, 1, 0)), ("corpo", "raiz", (0, 1.2, 0)), ("topo", "corpo", (0, 1.5, 0))])
    roles = auto_roles(rig, 1.5)
    assert roles.legs == [] and roles.profile == "flutuante" == suggest_profile(roles)


def test_roles_survive_a_round_trip_through_json(tmp_path):
    rig = biped()
    roles = auto_roles(rig, 1.8)
    path = tmp_path / "boneco.roles.json"
    roles.save(rig, str(path))
    assert json.loads(path.read_text(encoding="utf-8"))["perfil"] == "bipede"
    again = Roles.load(rig, str(path))
    assert again.to_dict(rig) == roles.to_dict(rig)


def test_roles_files_with_mistakes_say_what_is_wrong(tmp_path):
    rig = biped()
    with pytest.raises(RolesError, match="osso_que_nao_existe"):
        Roles.from_dict(rig, {"perna": [], "pernas": [{"ossos": ["osso_que_nao_existe"]}]})
    with pytest.raises(RolesError, match="Perfil"):
        Roles.from_dict(rig, {"perfil": "voador"})
    bad = tmp_path / "ruim.json"
    bad.write_text("{isto nao e json", encoding="utf-8")
    with pytest.raises(RolesError, match="ler"):
        Roles.load(rig, str(bad))
    with pytest.raises(RolesError, match="ler"):
        Roles.load(rig, str(tmp_path / "nao_existe.json"))


# ---------------------------------------------------------------------------------------------- animador
@pytest.mark.parametrize("profile", PROFILE_NAMES)
def test_every_profile_animates_a_biped_without_breaking(profile):
    rig = biped()
    animator = ProceduralAnimator(rig, auto_roles(rig, 1.8), 1.8, profile)
    for step in range(240):
        matrices = animator.update(1 / 60, 3.0)
    assert matrices.shape == (len(rig), 4, 4) and matrices.dtype == np.float32 and np.isfinite(matrices).all()
    assert not np.allclose(matrices, np.tile(np.identity(4), (len(rig), 1, 1)), atol=1e-3)     # há movimento
    assert np.abs(matrices[:, :3, :3]).max() < 1.0001 and np.abs(matrices[:, :3, 3]).max() < 1.5   # nada explode


def test_walking_moves_the_legs_in_opposite_phase_and_standing_still_does_not_walk():
    rig = biped()
    animator = ProceduralAnimator(rig, auto_roles(rig, 1.8), 1.8)
    left, right = rig.index("pe_e"), rig.index("pe_d")
    foot_z = lambda m, b: (m[b] @ np.append(rig.rest_positions[b], 1.0))[2]
    samples = []
    for _ in range(90):
        m = animator.update(1 / 60, 3.0)
        samples.append((foot_z(m, left), foot_z(m, right)))
    samples = np.array(samples[20:])                       # depois de a passada suavizar a entrada
    assert samples[:, 0].max() - samples[:, 0].min() > 0.05                      # o pé balança
    assert np.corrcoef(samples[:, 0], samples[:, 1])[0, 1] < -0.5                # um vai enquanto o outro volta
    still = ProceduralAnimator(rig, auto_roles(rig, 1.8), 1.8)
    for _ in range(120):
        m = still.update(1 / 60, 0.0)
    assert abs(foot_z(m, left) - rig.rest_positions[left][2]) < 0.03             # parado, só respira
    assert still.phase == 0.0


def test_the_walk_fades_in_and_out_smoothly_and_the_cycle_repeats():
    rig = biped()
    animator = ProceduralAnimator(rig, auto_roles(rig, 1.8), 1.8)
    animator.update(1 / 60, 3.0)
    assert 0.0 < animator.walk < 0.5                                             # não pula para o andar inteiro
    for _ in range(60):
        animator.update(1 / 60, 3.0)
    assert animator.walk == 1.0
    phases = []
    for _ in range(200):
        animator.update(1 / 60, 3.0)
        phases.append(animator.phase)
    assert min(phases) < 0.1 and max(phases) > 0.9                               # o ciclo dá a volta
    for _ in range(60):
        animator.update(1 / 60, 0.0)
    assert animator.walk == 0.0


def test_unknown_profiles_and_a_quadruped_with_the_biped_profile():
    rig = biped()
    with pytest.raises(RolesError, match="Perfil"):
        ProceduralAnimator(rig, auto_roles(rig, 1.8), 1.8, "voador")
    quad = quadruped()
    animator = ProceduralAnimator(quad, auto_roles(quad, 1.0), 1.0)
    assert animator.profile == "quadrupede" and set(PROFILES) == set(PROFILE_NAMES)
    for _ in range(60):
        matrices = animator.update(1 / 60, 2.0)
    assert np.isfinite(matrices).all()


def test_a_model_without_a_skeleton_cannot_be_animated():
    from src.clothing.custom_model import CustomModel
    from src.clothing.glb_writer import sample_humanoid

    model = CustomModel.from_bytes(sample_humanoid(), create_gl=False)
    assert model.rig is None
    with pytest.raises(ModelError, match="esqueleto"):
        model.animate()
    data, _ = skinned_glb()
    skinned = CustomModel.from_bytes(data, height=1.8, create_gl=False)
    roles = skinned.animate()
    assert skinned.animator is not None and isinstance(roles, Roles)
    skinned.update(0.016, 2.0)
    assert skinned.animator.matrices.shape == (3, 4, 4)
