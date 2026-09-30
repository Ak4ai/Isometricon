"""Shoulder blend on both sides (as in the first walk) and dual quaternion skinning, vs current.

python scripts/experiment_shoulder_blend_dqs.py
Never imported by the runtime. Output: artifacts/shoulder_blend_dqs/<outfit>.png, one row per
pose (rest, 4 walk phases), one column per variant:
  atual              the runtime: the shoulder blends on the arm's side only
  dois lados         the joint blend of the first walk (commit 4ee3045): 3.5 cm on each side
                     of every joint, the torso included, for skin and cloth
  dois lados + DQS   the same weights, moved by dual quaternion skinning (Kavan et al. 2007),
                     which blends rotations instead of positions and keeps the joint's volume
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_smooth_weights import OUTFITS, KEEP, render, SIZE
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CharacterModel, parse_character_cli_args
from src.clothing.skeleton import BLEND_RADIUS, skin, walk_rotations
from src.rendering.shader import Shader

OUT = ROOT / "artifacts" / "shoulder_blend_dqs"


def both_sides_weights(skeleton, points, bones, blend=BLEND_RADIUS):
    """Skeleton.weights of the first walk (commit 4ee3045): every joint, torso included,
    blends its two bones over ``blend`` on each side along the child's axis."""
    indices = np.stack([bones, bones], axis=1)
    weights = np.zeros((len(points), 2))
    weights[:, 0] = 1.0
    axes = skeleton.tails - skeleton.heads
    axes = axes / np.linalg.norm(axes, axis=1)[:, None]
    for child in range(len(skeleton.names)):
        parent = skeleton.parents[child]
        if parent < 0:
            continue
        mine = (bones == child) | (bones == parent)
        if not mine.any():
            continue
        offset = points - skeleton.heads[child]
        along = offset @ axes[child]
        radial = np.linalg.norm(offset - along[:, None] * axes[child], axis=1)
        own = bones == child
        reach = 1.25 * np.percentile(radial[own], 90) if own.any() else 0.1
        near = mine & (np.abs(along) < blend) & (radial < reach)
        t = np.clip((along[near] + blend) / (2 * blend), 0.0, 1.0)
        t = t * t * (3 - 2 * t)
        rows = np.flatnonzero(near)
        indices[rows] = np.stack([np.full(len(rows), child), np.full(len(rows), parent)], axis=1)
        weights[rows] = np.stack([t, 1 - t], axis=1)
    return indices, weights


def _quat_from_matrix(m):
    """(w, x, y, z) of a 3x3 rotation."""
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    return np.array(q)


def _qmul(a, b):
    w1, x1, y1, z1 = np.moveaxis(a, -1, 0)
    w2, x2, y2, z2 = np.moveaxis(b, -1, 0)
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], axis=-1)


def skin_dqs(rows, indices, weights, matrices):
    """Vertex rows moved by dual quaternion skinning."""
    real = np.array([_quat_from_matrix(m[:3, :3]) for m in matrices])
    translation = np.c_[np.zeros(len(matrices)), matrices[:, :3, 3]]
    dual = 0.5 * _qmul(translation, real)
    r = real[indices]  # (n, k, 4)
    d = dual[indices]
    # Keep every quaternion in the first one's hemisphere (q and -q are the same rotation).
    sign = np.sign(np.einsum("nkq,nq->nk", r, r[:, 0]))
    sign[sign == 0] = 1
    w = weights * sign
    b_real = np.einsum("nk,nkq->nq", w, r)
    b_dual = np.einsum("nk,nkq->nq", w, d)
    norm = np.linalg.norm(b_real, axis=1, keepdims=True)
    b_real, b_dual = b_real / norm, b_dual / norm
    wq, v = b_real[:, :1], b_real[:, 1:]
    wd, vd = b_dual[:, :1], b_dual[:, 1:]
    p = rows[:, :3].astype(np.float64)

    def rotate(vec):
        t = 2 * np.cross(v, vec)
        return vec + wq * t + np.cross(v, t)
    move = 2 * (wq * vd - wd * v + np.cross(v, vd))
    out = rows.copy()
    out[:, :3] = rotate(p) + move
    normals = rotate(rows[:, 3:6].astype(np.float64))
    out[:, 3:6] = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-8)
    return out


def poses(animator):
    yield "descanso", dict(animator.rest), (0, 0, 0)
    for phase in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi):
        walk, root = walk_rotations(phase)
        rotations = dict(animator.rest)
        for bone, rotation in walk.items():
            rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
        yield f"andando {int(phase / (0.5 * math.pi)) + 1}", rotations, root


def run(shader, name, body_flag, top):
    customization, top_id, bottom_id, _, _ = parse_character_cli_args(["--char", body_flag, "--top", top])
    model = CharacterModel(customization=customization, top_id=top_id, bottom_id=bottom_id)
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    skeleton = animator.skeleton
    both = []
    for part, rows, indices, weights in animator._bindings:
        if part.name in KEEP:
            both.append((part, rows, indices, weights))
            continue
        own = indices[np.arange(len(indices)), weights.argmax(1)]
        both.append((part, rows, *both_sides_weights(skeleton, rows[:, :3].astype(np.float64), own)))
    variants = [("atual", animator._bindings, skin), ("dois lados", both, skin), ("dois lados + DQS", both, skin_dqs)]
    pose_list = list(poses(animator))
    sheet = Image.new("RGB", (SIZE * len(variants) + 110, (SIZE + 20) * len(pose_list) + 20), "white")
    draw = ImageDraw.Draw(sheet)
    for c, (label, _, _) in enumerate(variants):
        draw.text((110 + c * SIZE + 6, 4), label, fill="black")
    for r, (pose_name, rotations, root) in enumerate(pose_list):
        matrices = skeleton.pose(rotations, root)
        draw.text((6, 20 + r * (SIZE + 20) + SIZE // 2), pose_name, fill="black")
        for c, (_, bindings, method) in enumerate(variants):
            for part, rows, indices, weights in bindings:
                part.mesh.update_vertices(method(rows, indices, weights, matrices))
            sheet.paste(render(shader, model), (110 + c * SIZE, 20 + r * (SIZE + 20)))
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / f"{name}.png")
    model.delete()
    print("[OK]", OUT / f"{name}.png")


def main():
    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SAMPLES, 4)
    window = glfw.create_window(SIZE, SIZE, "Shoulder", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_MULTISAMPLE)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    for name, body, top in OUTFITS:
        run(shader, name, body, top)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
