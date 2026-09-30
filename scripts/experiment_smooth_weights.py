"""Smooth bone weights shared by body and clothes: 3 smoothness variants vs the current runtime.

python scripts/experiment_smooth_weights.py
Never imported by the runtime. Output: artifacts/smooth_weights/<outfit>.png, one row per
pose (rest, walk, arms raised 90 degrees), one column per variant.

Every vertex keeps its current bone (its body part); around each joint a band of the given
width blends the joint's two bones by position along the limb, on both sides (the torso
too). Skin and cloth use the same rule, so at the same place they move the same way. The
middle of each part stays 100%. Head, hair and neck keep the runtime binding.
(Diffusing weights along the body cage failed: the Roblox cage is open at the shoulders.)
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import RIGID_PARTS, CharacterAnimator
from src.clothing.character_model import MODELS_DIR, CharacterModel, parse_character_cli_args
from src.clothing.hsr import engine_to_body_mesh
from src.clothing.skeleton import CAGE_PART_BONES, rest_rotations, skin, walk_rotations
from src.clothing.wear_engine import BODY_CAGES, load_r15_cages
from src.rendering.shader import Shader

OUT = ROOT / "artifacts" / "smooth_weights"
SIZE = 300
# Diffusion steps on the cage graph: more steps, wider transition around each joint.
# Width (m) of the transition band centred on every joint, shared by skin and cloth.
VARIANTS = [("mesmos pesos, faixa 5 cm", 0.05), ("mesmos pesos, faixa 10 cm", 0.10),
            ("roupa copia a pele, faixa 5 cm", -0.05)]
OUTFITS = [("masculino_sueter", "--male", "9240757332"),
           ("feminino_regata_basquete", "--female", "97346273111638"),
           ("feminino_cropped", "--female", "110977031470293")]
EYE, TARGET = [-1.35, 1.25, 1.55], [0.0, 1.0, 0.0]
KEEP = set(RIGID_PARTS) | {"neck"}


def cage_graph(body):
    """Body cage points (mesh coordinates), their bone and neighbours, seams welded."""
    cages = load_r15_cages(os.path.join(MODELS_DIR, BODY_CAGES[body]))
    points, parts, edges, offset = [], [], [], 0
    for part in CAGE_PART_BONES:
        verts = engine_to_body_mesh(cages[part]["verts"])
        faces = np.asarray(cages[part]["faces"]) + offset
        points.append(verts)
        parts += [part] * len(verts)
        edges += [faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]
        offset += len(verts)
    points = np.vstack(points)
    # Weld coincident points (the seams between parts) so weights can cross them.
    key = {}
    weld = np.array([key.setdefault(tuple(np.round(p, 3)), i) for i, p in enumerate(points)])
    edges = weld[np.vstack(edges)]
    edges = np.unique(np.sort(edges[edges[:, 0] != edges[:, 1]], axis=1), axis=0)
    return points, np.array(parts), weld, edges


def diffused_weights(skeleton, parts, weld, edges, steps):
    """(P, B) weights: one-hot part bones smoothed ``steps`` times over the cage graph."""
    count = len(parts)
    weights = np.zeros((count, len(skeleton.names)))
    weights[np.arange(count), [skeleton.index(CAGE_PART_BONES[p]) for p in parts]] = 1.0
    # Welded copies share one value (the average of the parts meeting there).
    total = np.zeros_like(weights)
    np.add.at(total, weld, weights)
    shared = np.bincount(weld, minlength=count)[:, None]
    for _ in range(steps + 1):
        weights = (total / np.maximum(shared, 1))[weld]
        if _ == steps:
            break
        neighbour = np.zeros_like(weights)
        degree = np.zeros(count)
        np.add.at(neighbour, edges[:, 0], weights[edges[:, 1]])
        np.add.at(neighbour, edges[:, 1], weights[edges[:, 0]])
        np.add.at(degree, edges[:, 0], 1)
        np.add.at(degree, edges[:, 1], 1)
        smoothed = 0.5 * weights + 0.5 * neighbour / np.maximum(degree, 1)[:, None]
        total = np.zeros_like(weights)
        np.add.at(total, weld, smoothed)
    return weights / weights.sum(1, keepdims=True)


def sample(points, own_bones, skeleton, cage_points, cage_bones, cage_weights, k=4):
    """Weights at ``points`` from the k nearest cage points of their bone and neighbour bones."""
    neighbours = {b: {b, int(skeleton.parents[b])} | {c for c in range(len(skeleton.names))
                                                      if skeleton.parents[c] == b}
                  for b in range(len(skeleton.names))}
    dense = np.zeros((len(points), len(skeleton.names)))
    for bone in np.unique(own_bones):
        rows = np.flatnonzero(own_bones == bone)
        allowed = np.flatnonzero(np.isin(cage_bones, list(neighbours[int(bone)])))
        if not len(allowed):
            dense[rows, bone] = 1.0
            continue
        for start in range(0, len(rows), 2048):
            chunk = rows[start:start + 2048]
            distance = np.linalg.norm(points[chunk, None] - cage_points[allowed][None], axis=2)
            nearest = np.argsort(distance, axis=1)[:, :k]
            d = np.take_along_axis(distance, nearest, 1)
            inverse = 1.0 / (d + 1e-3) ** 2
            inverse /= inverse.sum(1, keepdims=True)
            dense[chunk] = np.einsum("nk,nkb->nb", inverse, cage_weights[allowed][nearest])
    order = np.argsort(-dense, axis=1)[:, :4]
    top = np.take_along_axis(dense, order, 1)
    return order, top / top.sum(1, keepdims=True)


def band_weights(skeleton, points, bones, width):
    """(indices, weights) (N, 2): the vertex's bone, blended with the other bone of a joint
    within ``width`` / 2 of it along the child's axis, on both sides of every joint.

    The blend depends only on the position and on which of the joint's two bones the vertex
    belongs to, so skin and cloth at the same place get the same weights.
    """
    half = width / 2
    indices = np.stack([bones, bones], axis=1)
    weights = np.zeros((len(points), 2))
    weights[:, 0] = 1.0
    axes = skeleton.tails - skeleton.heads
    axes = axes / np.linalg.norm(axes, axis=1)[:, None]
    for child in range(len(skeleton.names)):
        parent = skeleton.parents[child]
        if parent < 0 or skeleton.names[child] in ("Neck", "Head"):
            continue
        mine = (bones == child) | (bones == parent)
        if not mine.any():
            continue
        offset = points - skeleton.heads[child]
        along = offset @ axes[child]
        radial = np.linalg.norm(offset - along[:, None] * axes[child], axis=1)
        limb = bones == child
        reach = 1.5 * np.percentile(radial[limb], 90) if limb.any() else 0.12
        near = mine & (np.abs(along) < half) & (radial < reach)
        t = np.clip((along[near] + half) / width, 0.0, 1.0)
        t = t * t * (3 - 2 * t)
        rows = np.flatnonzero(near)
        indices[rows] = np.stack([np.full(len(rows), child), np.full(len(rows), parent)], axis=1)
        weights[rows] = np.stack([t, 1 - t], axis=1)
    return indices, weights


def skin_bones(points, own, skeleton, cage_points, cage_bones):
    """Bone of the nearest body cage point among the vertex's bone and its neighbours."""
    result = own.copy()
    for bone in np.unique(own):
        allowed = {int(bone), int(skeleton.parents[bone])} | {c for c in range(len(skeleton.names))
                                                              if skeleton.parents[c] == bone}
        candidates = np.flatnonzero(np.isin(cage_bones, list(allowed)))
        rows = np.flatnonzero(own == bone)
        if not len(candidates):
            continue
        distance = np.linalg.norm(points[rows, None] - cage_points[candidates][None], axis=2)
        result[rows] = cage_bones[candidates][distance.argmin(1)]
    return result


def copy_skin_weights(bindings, skeleton):
    """Cloth takes the weights of the nearest skin vertex (AutoSkin), among the skin of the
    cloth's own bone and its neighbours, so a wide trouser hem never copies the other leg."""
    skin_rows, skin_indices, skin_weights, skin_own = [], [], [], []
    for part, rows, indices, weights in bindings:
        if part.source_obj is None and part.name not in KEEP:
            skin_rows.append(rows[:, :3])
            skin_indices.append(indices)
            skin_weights.append(weights)
            skin_own.append(indices[np.arange(len(indices)), weights.argmax(1)])
    points = np.vstack(skin_rows).astype(np.float64)
    all_indices, all_weights, own_bones = np.vstack(skin_indices), np.vstack(skin_weights), np.concatenate(skin_own)
    result = []
    for part, rows, indices, weights in bindings:
        if part.source_obj is None:
            result.append((part, rows, indices, weights))
            continue
        cloth = rows[:, :3].astype(np.float64)
        own = indices[np.arange(len(indices)), weights.argmax(1)]
        new_indices, new_weights = indices.copy(), weights.copy()
        for bone in np.unique(own):
            allowed = {int(bone), int(skeleton.parents[bone])} | {c for c in range(len(skeleton.names))
                                                                  if skeleton.parents[c] == bone}
            candidates = np.flatnonzero(np.isin(own_bones, list(allowed)))
            if not len(candidates):
                continue
            rows_of = np.flatnonzero(own == bone)
            for start in range(0, len(rows_of), 1024):
                chunk = rows_of[start:start + 1024]
                distance = np.linalg.norm(cloth[chunk, None] - points[candidates][None], axis=2)
                nearest = candidates[distance.argmin(1)]
                new_indices[chunk] = all_indices[nearest]
                new_weights[chunk] = all_weights[nearest]
        result.append((part, rows, new_indices, new_weights))
    return result


def poses(animator):
    yield "descanso", dict(animator.rest), (0, 0, 0)
    for phase in (0.0, math.pi):
        walk, root = walk_rotations(phase)
        rotations = dict(animator.rest)
        for bone, rotation in walk.items():
            rotations[bone] = rotation @ rotations[bone] if bone in rotations else rotation
        yield f"andando {int(phase / math.pi) + 1}", rotations, root
    yield "braços a 90°", rest_rotations(animator.skeleton, math.pi / 2), (0, 0, 0)


def render(shader, model):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(34.0, 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(EYE, TARGET, [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")


def run(shader, name, body_flag, top):
    customization, top_id, bottom_id, _, _ = parse_character_cli_args(["--char", body_flag, "--top", top])
    model = CharacterModel(customization=customization, top_id=top_id, bottom_id=bottom_id)
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    skeleton = animator.skeleton
    bindings = {"atual": [(p, r, i, w) for p, r, i, w in animator._bindings]}
    cage_points, cage_parts, _, _ = cage_graph(model.body)
    cage_bones = np.array([skeleton.index(CAGE_PART_BONES[p]) for p in cage_parts])
    for label, width in VARIANTS:
        copy_skin = width < 0
        width = abs(width)
        variant = []
        for part, rows, indices, weights in animator._bindings:
            if part.name in KEEP:
                variant.append((part, rows, indices, weights))
                continue
            own = indices[np.arange(len(indices)), weights.argmax(1)]
            if part.source_obj is None:
                # Skin: the body cage part under it (its bone, parent or children), as cloth
                # takes the cage part it was bound to: both pick the bone the same way.
                own = skin_bones(rows[:, :3].astype(np.float64), own, skeleton, cage_points, cage_bones)
            new_indices, new_weights = band_weights(skeleton, rows[:, :3].astype(np.float64), own, width)
            variant.append((part, rows, new_indices, new_weights))
        if copy_skin:
            variant = copy_skin_weights(variant, skeleton)
        bindings[label] = variant
    pose_list = list(poses(animator))
    columns = ["atual"] + [label for label, _ in VARIANTS]
    sheet = Image.new("RGB", (SIZE * len(columns) + 110, (SIZE + 20) * len(pose_list) + 20), "white")
    draw = ImageDraw.Draw(sheet)
    for c, label in enumerate(columns):
        draw.text((110 + c * SIZE + 6, 4), label, fill="black")
    for r, (pose_name, rotations, root) in enumerate(pose_list):
        matrices = skeleton.pose(rotations, root)
        draw.text((6, 20 + r * (SIZE + 20) + SIZE // 2), pose_name, fill="black")
        for c, label in enumerate(columns):
            for part, rows, indices, weights in bindings[label]:
                part.mesh.update_vertices(skin(rows, indices, weights, matrices))
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
    window = glfw.create_window(SIZE, SIZE, "Weights", None, None)
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
