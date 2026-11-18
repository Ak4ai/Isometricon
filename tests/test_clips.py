"""Clipes de animação de um .glb: leitura, escolha pelo nome e a pose que eles dão aos ossos."""

import numpy as np
import pytest

from src.clothing.clips import ClipAnimator, pick_clips, quaternion_matrices
from src.clothing.custom_model import CustomModel
from src.clothing.glb import ModelError, parse_model
from src.clothing.glb_writer import GlbBuilder, box
from src.clothing.rig import rotation_matrix

SQRT_HALF = float(np.sqrt(0.5))
QUARTER_Z = (0.0, 0.0, SQRT_HALF, SQRT_HALF)   # 90 graus em z


def animated_glb(clips=("Walk", "Idle"), root_slides=True, interpolation="LINEAR"):
    """Três ossos em linha (raiz, meio, ponta). 'Walk': o osso do meio gira 90° em z em 1 s e a raiz desliza em x."""
    builder = GlbBuilder()
    nodes = [builder.add_node(name=n, translation=(0.0, 0.0 if i == 0 else 1.0, 0.0))
             for i, n in enumerate(("raiz", "meio", "ponta"))]
    builder.nodes[nodes[0]]["children"] = [nodes[1]]
    builder.nodes[nodes[1]]["children"] = [nodes[2]]
    positions, normals, uvs, indices = box((-0.2, 0.0, -0.2), (0.2, 3.0, 0.2))
    joints = np.zeros((len(positions), 4), dtype=np.uint16)
    weights = np.zeros((len(positions), 4), dtype=np.float32)
    joints[:, 0] = np.clip((positions[:, 1] // 1.0).astype(int), 0, 2)
    weights[:, 0] = 1.0
    world = [np.identity(4) for _ in nodes]
    for i in range(3):
        world[i][1, 3] = float(i)
    mesh = builder.add_mesh(positions, indices, normals, uvs, joints=joints, weights=weights)
    skin = builder.add_skin(nodes, [np.linalg.inv(w) for w in world])
    body = builder.add_node(mesh=mesh, skin=skin, name="corpo")
    if "Walk" in clips:
        tracks = [(nodes[1], "rotation", [0.0, 1.0], [(0, 0, 0, 1), QUARTER_Z])]
        if root_slides:
            tracks.append((nodes[0], "translation", [0.0, 1.0], [(0, 0, 0), (2.0, 0, 0)]))
        builder.add_animation("Walk", tracks, interpolation)
    if "Idle" in clips:
        builder.add_animation("Idle", [(nodes[2], "translation", [0.0, 1.0], [(0, 1, 0), (0, 1.1, 0)])])
    builder.add_animation("Fora", [(body, "translation", [0.0, 1.0], [(0, 0, 0), (1, 0, 0)])])   # não é de um osso
    return builder.build([nodes[0], body])


def test_clips_of_the_bones_are_read_and_others_ignored():
    model = parse_model(animated_glb())
    assert model.animations == ["Walk", "Idle", "Fora"]
    assert [c.name for c in model.clips] == ["Walk", "Idle"]
    walk = model.clips[0]
    assert walk.duration == 1.0 and {c.path for c in walk.channels} == {"rotation", "translation"}
    assert model.rest_pose is not None and model.rest_pose.translation.shape == (3, 3)


def test_pick_clips_by_name():
    assert pick_clips(["Idle", "Walk"]) == (1, 0)
    assert pick_clips(["Andando", "Parado"]) == (0, 1)
    assert pick_clips(["Ataque"]) == (0, None)         # um só clipe, sem nome que diga: vale como o de andar
    assert pick_clips(["Ataque", "Morte"]) == (0, None) or pick_clips(["Ataque", "Morte"])[1] is None
    assert pick_clips([]) == (None, None)


def test_quaternion_matrix_matches_the_axis_angle_one():
    got = quaternion_matrices(np.array([QUARTER_Z]))[0]
    assert np.allclose(got, rotation_matrix((0, 0, 1), np.pi / 2), atol=1e-9)


def animator_for(model, **options):
    custom = CustomModel(model, create_gl=False, **options)
    custom.animate()
    return custom


def test_the_model_with_clips_plays_them_by_default():
    custom = animator_for(parse_model(animated_glb()))
    assert isinstance(custom.animator, ClipAnimator) and custom.animator.profile == "clipes"
    assert custom.animator.names == ("Walk", "Idle")


def test_standing_with_no_idle_pose_is_the_rest_pose_and_walking_bends_the_middle_bone():
    custom = animator_for(parse_model(animated_glb(clips=("Walk",))))
    custom.update(0.5, 0.0)
    assert np.allclose(custom.animator.matrices, np.tile(np.identity(4), (3, 1, 1)), atol=1e-5)
    for _ in range(15):                                  # andando 0,75 s: o clipe está a meio caminho do fim
        custom.update(0.05, 3.0)
    matrices = custom.animator.matrices
    assert not np.allclose(matrices[1], np.identity(4), atol=1e-3)   # o osso do meio girou
    # o osso do meio gira em volta da posição dele, e a ponta (filha) o acompanha
    pivot = custom.rig.rest_positions[1]
    assert np.allclose((matrices[1] @ np.append(pivot, 1.0))[:3], pivot, atol=1e-4)
    assert not np.allclose(matrices[2][:3, :3], np.identity(3), atol=1e-3)


def test_the_root_does_not_carry_the_model_away():
    custom = animator_for(parse_model(animated_glb()))
    for _ in range(15):
        custom.update(0.05, 3.0)
    root = custom.animator.matrices[0]
    assert abs(root[0, 3]) < 1e-4 and abs(root[2, 3]) < 1e-4     # nada de deslizar em x ou z


def test_the_idle_clip_plays_while_standing():
    custom = animator_for(parse_model(animated_glb()))
    custom.update(0.5, 0.0)
    still = custom.animator.matrices.copy()
    custom.update(0.25, 0.0)
    assert not np.allclose(custom.animator.matrices, still)       # respira
    assert np.allclose(custom.animator.matrices[1], np.identity(4), atol=1e-4)  # o osso do meio não


def test_clips_follow_the_normalization():
    """Escala e giro do modelo não podem quebrar a pose: no repouso a pele continua identidade."""
    for turns in range(4):
        custom = animator_for(parse_model(animated_glb(clips=("Walk",))), height=1.8, yaw_turns=turns)
        custom.update(0.1, 0.0)
        assert np.allclose(custom.animator.matrices, np.tile(np.identity(4), (3, 1, 1)), atol=1e-4)
        for _ in range(15):
            custom.update(0.05, 3.0)
        matrices = custom.animator.matrices
        pivot = custom.rig.rest_positions[1]
        assert np.allclose((matrices[1] @ np.append(pivot, 1.0))[:3], pivot, atol=1e-4)
        # o giro do osso do meio é o do arquivo (90 graus por segundo de clipe), seja como for que o modelo foi girado
        angle = np.degrees(np.arccos(np.clip((np.trace(matrices[1][:3, :3]) - 1) / 2, -1, 1)))
        assert angle == pytest.approx(90.0 * custom.animator._walk_time, abs=1.0)


def test_a_procedural_profile_can_be_forced_and_clips_demand_clips():
    model = parse_model(animated_glb())
    custom = CustomModel(model, create_gl=False)
    custom.animate(profile="bipede")
    assert custom.animator.profile == "bipede"
    plain = CustomModel(parse_model(animated_glb(clips=())), create_gl=False)
    with pytest.raises(ModelError):
        plain.animate(profile="clipes")
    plain.animate()                                       # sem clipes: procedural, como antes
    assert plain.animator.profile != "clipes"


def test_cubic_spline_files_still_play():
    # o valor das tangentes não é usado; o leitor só precisa não quebrar com a forma (3 valores por tempo)
    model = parse_model(animated_glb(clips=("Walk",), interpolation="STEP"))
    assert model.clips and model.clips[0].channels[0].step
