"""Isolated shoulder weight-transfer experiment; never imported by the runtime.

python scripts/experiment_shoulder_surface_transfer.py
Compare current bindings with barycentric weights from the uncut body surface.
Only top-garment weights change. Body geometry, cages, HSR, garment topology and
bind-pose positions stay fixed. No bridge, collision projection or skin culling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.diagnose_skin_animation import render, SIZE
from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator, _nearest
from src.clothing.character_model import (CharacterModel, parse_character_cli_args,
    parse_clean_obj_groups, transform_arm_vertices, transform_hip_vertices)
from src.clothing.hsr import _closest_on_triangles, subdivide
from src.clothing.skeleton import skin, rotation_x, rest_rotations, walk_rotations
from src.rendering.shader import Shader

OUT = ROOT / 'artifacts/shoulder_surface_experiment'
CASES = {'sweater': '9240757332', 'jersey': '97346273111638'}
VIEWS = [('front', [0, 1.25, 1.65]), ('three_quarter', [-1.25, 1.3, 1.25]),
         ('back', [0, 1.25, -1.65])]


def dense_weights(indices, weights, count):
    dense = np.zeros((len(indices), count))
    np.add.at(dense, (np.arange(len(indices))[:, None], indices), weights)
    return dense


def body_reference(model, animator):
    """Full skin BEFORE HSR, with the same transforms, subdivision and weights."""
    def hip(v):
        return transform_hip_vertices(v, model.hip_glute_scale, model.hip_width_scale, model.waist_height_offset)

    def arm(v):
        return transform_arm_vertices(v, model.arm_width_scale, model.arm_length_scale)

    groups = [('trunk_skin', ['Export_torso', 'Export_pelve'], hip, None)]
    for side, pt in [('L', 'esquerdo'), ('R', 'direito')]:
        groups.extend([(f'arm_{side}', [f'Export_braco_superior_{pt}'], arm, f'UpperArm_{side}'),
                       (f'forearm_{side}', [f'Export_antebraco_{pt}'], arm, f'LowerArm_{side}')])
    vertices, faces, weights = [], [], []
    offset = 0
    skeleton = animator.skeleton
    cage_points, cage_bones = animator._cage_binding
    for name, prefixes, transform, bone in groups:
        data = parse_clean_obj_groups(model.clean_obj, prefixes, vertex_transform=transform)
        if data is None:
            raise ValueError(f'Missing reference group: {name}')
        rows, triangles = subdivide(data[0].reshape(-1, 11), data[1].reshape(-1, 3), levels=2)
        if bone:
            bones = np.full(len(rows), skeleton.index(bone))
        else:
            region = np.isin(cage_bones, [skeleton.index('Torso'), skeleton.index('Pelvis')])
            bones = cage_bones[region][_nearest(rows[:, :3], cage_points[region])]
        indices, influence = skeleton.weights(rows[:, :3], bones)
        vertices.append(rows[:, :3])
        faces.append(triangles + offset)
        weights.append(dense_weights(indices, influence, len(skeleton.names)))
        offset += len(rows)
    return np.vstack(vertices), np.vstack(faces), np.vstack(weights)


def transfer_weights(points, vertices, faces, weights, chunk=32):
    """Interpolate existing body weights at the closest point of each triangle.

    No nearest-bone decision and no new coverage mask. This first experiment uses
    only the actual body surface, so its cross-part discontinuities remain visible.
    """
    unique, inverse = np.unique(points, axis=0, return_inverse=True)
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    result = np.empty((len(unique), weights.shape[1]))
    distances = np.empty(len(unique))
    selected = np.empty(len(unique), dtype=int)
    for start in range(0, len(unique), chunk):
        p = unique[start:start + chunk]
        bary = _closest_on_triangles(p, a, b, c)
        closest = bary[..., 0, None] * a + bary[..., 1, None] * b + bary[..., 2, None] * c
        distance = ((closest - p[:, None]) ** 2).sum(-1)
        best = distance.argmin(axis=1)
        row = np.arange(len(p))
        result[start:start + len(p)] = np.einsum('ni,nij->nj', bary[row, best], weights[faces[best]])
        distances[start:start + len(p)] = np.sqrt(distance[row, best])
        selected[start:start + len(p)] = best
    assert np.isfinite(result).all() and result.min() >= -1e-8
    np.testing.assert_allclose(result.sum(axis=1), 1, atol=1e-6)
    return result[inverse], distances[inverse], selected[inverse]


def poses(animator):
    skeleton = animator.skeleton
    yield 'A_pose', {}, (0, 0, 0)
    yield 'rest', animator.rest, (0, 0, 0)
    raised = rest_rotations(skeleton, np.pi / 2)
    yield 'arms_side_90', raised, (0, 0, 0)
    forward = dict(animator.rest)
    for side in 'LR':
        name = f'UpperArm_{side}'
        forward[name] = rotation_x(-np.pi / 3) @ forward[name]
    yield 'arms_front_60', forward, (0, 0, 0)
    overhead = rest_rotations(skeleton, np.radians(140))
    yield 'arms_side_140', overhead, (0, 0, 0)
    for phase in (0, np.pi):
        walk, root = walk_rotations(phase)
        rotations = dict(animator.rest)
        for bone, rotation in walk.items():
            rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
        yield f'walk_{int(phase / np.pi)}', rotations, root


def edge_stretch(rest, posed, faces):
    edges = np.unique(np.sort(np.vstack((faces[:, :2], faces[:, 1:], faces[:, [2, 0]])), axis=1), axis=0)
    lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    valid = lengths > 1e-6
    ratio = np.linalg.norm(posed[edges[:, 0]] - posed[edges[:, 1]], axis=1)[valid] / lengths[valid]
    return {'p01': float(np.percentile(ratio, 1)), 'p99': float(np.percentile(ratio, 99)),
            'max': float(ratio.max()), 'edges_over_2x': int((ratio > 2).sum())}


def fingerprints():
    paths = list((ROOT / 'src/clothing').glob('*.py'))
    paths += list((ROOT / 'assets/models').glob('*.npz'))
    paths += list((ROOT / 'assets/models').glob('rig_*.json'))
    paths += [ROOT / 'assets/models' / name for name in (
        'female_cages_apose_stage2.obj', 'male_cages_apose.obj')]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}


def visible_skin(shader, model, eye):
    """Raw visible upper-arm pixels, NOT a universal penetration/coverage score.

    For a jersey these pixels are expected. Compare only the same body/pose/view.
    Depth and texture-alpha tests match the actual renderer.
    """
    gl.glClearColor(0, 0, 0, 1)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gl.glDisable(gl.GL_CULL_FACE)
    shader.use()
    shader.set_mat4('u_Projection', perspective(38, 1, .1, 50))
    shader.set_mat4('u_View', look_at(eye, [0, 1.15, 0], [0, 1, 0]))
    shader.set_int('u_TextureAtlas', 0)
    colors = {'arm_left': (1, 0, 0), 'arm_right': (0, 1, 0), 'trunk_skin': (0, 0, 1)}
    for part in model.parts:
        shader.set_mat4('u_Model', np.eye(4, dtype=np.float32) if part.transform is None else part.transform)
        shader.set_vec3('u_IdColor', *colors.get(part.name, (0, 0, 0)))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, part.texture_id)
        part.mesh.draw()
    gl.glFinish()
    pixels = np.frombuffer(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE), np.uint8).reshape(SIZE, SIZE, 3)
    return {name: int((pixels[:, :, i] > 127).sum()) for i, name in enumerate(colors)}


def run_case(shader, id_shader, body, garment, directory):
    top_id = CASES[garment]
    customization, top, bottom, _, _ = parse_character_cli_args(
        ['--char', f'--{body}', '--top', top_id, '--bottom', '109837605892174'])
    model = CharacterModel(customization=customization, top_id=top, bottom_id=bottom)
    try:
        animator = CharacterAnimator(model, walking=False)
        animator._bind()
        original = list(animator._bindings)
        top_bindings = [b for b in original if b[0].source_obj and top_id in b[0].source_obj]
        if len(top_bindings) != 1:
            raise ValueError(f'Expected one fitted top, got {len(top_bindings)}')
        top_part, top_rows, _, _ = top_bindings[0]
        original_indices = {id(p): p.mesh.read_indices() for p in model.parts}
        reference = body_reference(model, animator)
        print(f'{body}/{garment}: reference {len(reference[0])} vertices, {len(reference[1])} faces', flush=True)
        weights, distances, selected = transfer_weights(top_rows[:, :3], *reference)
        all_bones = np.broadcast_to(np.arange(len(animator.skeleton.names)), weights.shape)
        variants = {'current': original,
                    'surface_transfer': [(p, rows, all_bones, weights) if p is top_part else (p, rows, ids, w)
                                         for p, rows, ids, w in original]}
        # Both variants must reproduce exactly the same bind-pose positions.
        np.testing.assert_allclose(skin(top_rows, all_bones, weights, animator.skeleton.pose({}))[:, :3], top_rows[:, :3], atol=1e-6)
        report = {'body': body, 'garment': garment, 'asset': top_id,
                  'projection_distance_m': {'median': float(np.median(distances)), 'p99': float(np.percentile(distances, 99))},
                  'topology_unchanged': True, 'body_identical_between_variants': True, 'poses': {}}
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(directory / 'transferred_weights.npz', weights=weights, distance=distances,
                            reference_face=selected, reference_vertices=reference[0], reference_faces=reference[1])
        for pose_name, rotations, root in poses(animator):
            matrices = animator.skeleton.pose(rotations, root)
            sheet = Image.new('RGB', (SIZE * len(VIEWS), (SIZE + 24) * 2), 'white')
            draw = ImageDraw.Draw(sheet)
            metrics = {}
            body_buffers = {}
            for row, (variant, bindings) in enumerate(variants.items()):
                for part, rows, indices, w in bindings:
                    moved = skin(rows, indices, w, matrices)
                    part.mesh.update_vertices(moved)
                    if part is top_part:
                        metrics[variant] = {'edge_stretch': edge_stretch(rows[:, :3], moved[:, :3], original_indices[id(part)].reshape(-1, 3))}
                    elif row == 0:
                        body_buffers[id(part)] = moved.copy()
                    else:
                        np.testing.assert_array_equal(moved, body_buffers[id(part)])
                draw.text((8, row * (SIZE + 24) + 5), f'{body} / {garment} / {pose_name} / {variant}', fill='black')
                for column, (view, eye) in enumerate(VIEWS):
                    sheet.paste(render(shader, model, eye), (column * SIZE, row * (SIZE + 24) + 24))
                    metrics[variant].setdefault('visible_skin_pixels', {})[view] = visible_skin(id_shader, model, eye)
                for part in model.parts:
                    np.testing.assert_array_equal(part.mesh.read_indices(), original_indices[id(part)])
            sheet.save(directory / f'{pose_name}.png')
            report['poses'][pose_name] = metrics
        (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report
    finally:
        model.delete()


def write_gallery(out, reports):
    content = ['<!doctype html><meta charset="utf-8"><title>Shoulder transfer experiment</title>',
               '<style>body{background:#202126;color:#eee;font:16px system-ui;margin:24px}img{width:100%;max-width:1440px}a{color:#8dcaff}section{margin-bottom:40px}</style>',
               '<h1>Experimento separado: transferência de pesos no ombro</h1>',
               '<p>Em cada imagem: método atual em cima; transferência da superfície do corpo embaixo. '
               'Mesma roupa, corpo, HSR e câmera. Nenhum triângulo é acrescentado ou removido. '
               'Este teste não fecha as aberturas da cage e não altera o programa.</p>']
    for case, report in reports.items():
        content.append(f'<h2>{case}</h2><p><a href="{case}/report.json">Métricas</a></p>')
        for pose in report['poses']:
            content.append(f'<section><h3>{pose}</h3><img loading="lazy" src="{case}/{pose}.png"></section>')
    (out / 'index.html').write_text('\n'.join(content), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', choices=['male', 'female', 'both'], default='both')
    parser.add_argument('--garment', choices=[*CASES, 'both'], default='both')
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    before = fingerprints()
    if not glfw.init():
        raise RuntimeError('GLFW initialization failed')
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(SIZE, SIZE, 'Isolated shoulder experiment', None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError('OpenGL context creation failed')
    reports = {}
    try:
        glfw.make_context_current(window)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glViewport(0, 0, SIZE, SIZE)
        shader = Shader(str(ROOT / 'assets/shaders/world_textured.vert'), str(ROOT / 'assets/shaders/world_textured.frag'))
        args.output.mkdir(parents=True, exist_ok=True)
        id_fragment = args.output / 'skin_ids.frag'
        id_fragment.write_text('#version 330 core\nin vec2 v_TexCoord;\nuniform sampler2D u_TextureAtlas;\n'
                               'uniform vec3 u_IdColor;\nout vec4 FragColor;\nvoid main(){\n'
                               'if(texture(u_TextureAtlas,v_TexCoord).a<0.1) discard;\n'
                               'FragColor=vec4(u_IdColor,1.0);\n}', encoding='utf-8')
        id_shader = Shader(str(ROOT / 'assets/shaders/world_textured.vert'), str(id_fragment))
        bodies = ['male', 'female'] if args.body == 'both' else [args.body]
        garments = CASES if args.garment == 'both' else [args.garment]
        for body in bodies:
            for garment in garments:
                key = f'{body}_{garment}'
                reports[key] = run_case(shader, id_shader, body, garment, args.output / key)
                write_gallery(args.output, reports)
                print(f'Completed: {key}', flush=True)
        after = fingerprints()
        assert before == after, 'A monitored production input changed during the experiment'
        (args.output / 'input_hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
        print('Production input hashes unchanged.', flush=True)
    finally:
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == '__main__':
    main()
