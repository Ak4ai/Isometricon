"""Render HSR skin in the fitting pose, rest pose and four walk phases.

Uses the actual OpenGL runtime in a hidden window and checks topology preservation.
The normal runtime may refresh stale fit caches.
Run from the repository root: python scripts/diagnose_skin_animation.py
"""
from pathlib import Path
import argparse
import json
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CharacterModel, parse_character_cli_args
from src.rendering.shader import Shader

SIZE = 480
OUT = Path('artifacts/skin_animation_diagnosis')


def render(shader, model, eye):
    gl.glClearColor(.18, .19, .22, 1)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4('u_Projection', perspective(38, 1, .1, 50))
    shader.set_mat4('u_View', look_at(eye, [0, 1.15, 0], [0, 1, 0]))
    shader.set_vec3('u_LightDir', .4, 1.2, .8)
    shader.set_vec3('u_LightColor', .85, .85, .85)
    shader.set_vec3('u_AmbientColor', .45, .45, .45)
    shader.set_int('u_TextureAtlas', 0)
    model.draw(shader, np.eye(4, dtype=np.float32))
    gl.glFinish()
    return Image.frombytes('RGBA', (SIZE, SIZE), gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB')


def main():
    if not glfw.init():
        raise RuntimeError('GLFW init failed')
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(SIZE, SIZE, 'Skin diagnosis', None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader('assets/shaders/world_textured.vert', 'assets/shaders/world_textured.frag')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    options, character_args = parser.parse_known_args()
    customization, top, bottom, _, _ = parse_character_cli_args(['--char', '--female', '--top', '101748354579961', '--bottom', '109837605892174'] + character_args)
    views = [[0, 1.25, 1.65], [-1.25, 1.3, 1.25], [0, 1.25, -1.65]]
    report = {}
    modes = ['A-pose HSR', 'rest', 'walk 0', 'walk 1/4', 'walk 1/2', 'walk 3/4']
    sheet = Image.new('RGB', (SIZE * 3, (SIZE + 24) * len(modes)), 'white')
    draw = ImageDraw.Draw(sheet)
    model = CharacterModel(customization=customization, top_id=top, bottom_id=bottom)
    before = {p.name: p.mesh.read_indices() for p in model.parts}
    animator = CharacterAnimator(model, walking=False)
    for row, mode in enumerate(modes):
        if row:
            animator.walking = row >= 2
            animator.walk_time = (row - 2) * np.pi / 2
            animator.update(0)
        after = {p.name: p.mesh.read_indices() for p in model.parts}
        report[mode] = {name: len(faces) // 3 - len(after.get(name, [])) // 3
                        for name, faces in before.items() if not np.array_equal(faces, after.get(name, []))}
        draw.text((5, row * (SIZE + 24) + 5), mode, fill='black')
        for col, eye in enumerate(views):
            sheet.paste(render(shader, model, eye), (col * SIZE, row * (SIZE + 24) + 24))
    model.delete()
    options.output.mkdir(parents=True, exist_ok=True)
    sheet.save(options.output / 'comparison.png')
    (options.output / 'removed_faces.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
    glfw.destroy_window(window)
    glfw.terminate()
    assert not any(report.values()), 'Animation changed the HSR topology'


if __name__ == '__main__':
    main()
