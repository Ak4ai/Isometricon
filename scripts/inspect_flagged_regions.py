"""Close-ups of what the robustness battery marks as skin poking through (pele furando) or holes (buraco).

python scripts/inspect_flagged_regions.py REPORT.json [--names NAME ...] [--max N] [--output DIR]

For each chosen case it measures again, groups the marked points into regions and, for the biggest
regions, draws the view that sees most of them twice: plain and marked (red = poking, magenta = hole).
Poking is shown in the game pose the battery found worst; holes in the fitting pose, where they are measured.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_animation_robustness import GAME_POSES, LIMITS, holes, naked_samples, poking, poses, stretching
from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CharacterModel
from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.skeleton import skin
from src.rendering.shader import Shader

SIZE, FOV, DISTANCE = 360, 30.0, 0.75
REGION = 0.12  # points this close belong to one region
COLOURS = {"furando": (255, 40, 40), "buraco": (255, 0, 255), "esticado": (255, 220, 0)}


def regions(points, count):
    """(centre, points) of the ``count`` biggest groups of points."""
    left, found = points.copy(), []
    while len(left) and len(found) < count:
        sample = left[:: max(1, len(left) // 2000)]
        seed = sample[np.argmax((np.linalg.norm(sample[:, None] - sample[None], axis=2) < REGION).sum(1))]
        for _ in range(3):
            near = np.linalg.norm(left - seed, axis=1) < REGION
            seed = left[near].mean(0)
        found.append((seed, left[near]))
        left = left[~near]
    return sorted(found, key=lambda r: -len(r[1]))


def matrices_for(eye, target):
    return (np.asarray(perspective(FOV, 1.0, 0.02, 20.0), dtype=np.float64),
            np.asarray(look_at(list(eye), list(target), [0.0, 1.0, 0.0]), dtype=np.float64))


def render(shader, model, eye, target):
    projection, view = matrices_for(eye, target)
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(FOV, 1.0, 0.02, 20.0))
    shader.set_mat4("u_View", look_at(list(eye), list(target), [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    depth = np.frombuffer(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT), dtype=np.float32)
    image = Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")
    return image, depth.reshape(SIZE, SIZE)[::-1], projection @ view


def in_sight(points, depth, matrix):
    """Pixel (x, y) of each point and whether it is the nearest thing drawn there."""
    clip = np.c_[points, np.ones(len(points))] @ matrix.T
    ndc = clip[:, :3] / clip[:, 3:]
    x = np.round((ndc[:, 0] * 0.5 + 0.5) * (SIZE - 1)).astype(int)
    y = np.round((0.5 - ndc[:, 1] * 0.5) * (SIZE - 1)).astype(int)
    inside = (x >= 0) & (x < SIZE) & (y >= 0) & (y < SIZE) & (clip[:, 3] > 0)
    seen = np.zeros(len(points), dtype=bool)
    seen[inside] = ndc[inside, 2] * 0.5 + 0.5 <= depth[y[inside], x[inside]] + 3e-4
    return x, y, seen


def best_view(shader, model, centre, points):
    """(plain image, marked image, share in sight) from the direction that sees most of ``points``."""
    best = None
    for tilt in (0.0, 0.5, -0.5):
        for k in range(8):
            turn = k * math.pi / 4
            direction = np.array([math.sin(turn), tilt, math.cos(turn)])
            eye = centre + DISTANCE * direction / np.linalg.norm(direction)
            image, depth, matrix = render(shader, model, eye, centre)
            x, y, seen = in_sight(points, depth, matrix)
            if best is None or seen.mean() > best[0]:
                best = (seen.mean(), image, x, y, seen)
    share, image, x, y, seen = best
    return image, (x, y, seen), share


def mark(image, spots, colour):
    marked = image.copy()
    draw = ImageDraw.Draw(marked)
    x, y, seen = spots
    for px, py in zip(x[seen], y[seen]):
        draw.ellipse((px - 1, py - 1, px + 1, py + 1), fill=colour)
    return marked


def ids_of(result):
    ids = {}
    for key, value in result["ids"].items():
        if key == "tested":
            continue
        ids[key] = None if value == "None" else value if key == "shoes_id" else int(value)
    return ids


def inspect(shader, result, samples, count):
    """[(title, plain, marked)] for the biggest marked regions of one case."""
    body = BodyType.FEMALE if result["corpo"] == "female" else BodyType.MALE
    model = CharacterModel(customization=AvatarCustomization(body_type=body), **ids_of(result))
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    cloth = [b for b in animator._bindings if b[0].source_obj is not None]
    faces = [part.mesh.read_indices().reshape(-1, 3) for part, *_ in cloth]
    views = []
    shown = {"buraco": None, "furando": None, "esticado": None}
    if result["buraco_cm2"] > 0:
        matrices = animator.skeleton.pose({})
        shown["buraco"] = (matrices, holes(animator, samples)[1], "vestir")
    worst = max(GAME_POSES, key=lambda n: result["poses"][n]["pele_furando_cm2"])
    if result["poses"][worst]["pele_furando_cm2"] > 0:
        _, base = poking(animator, animator.skeleton.pose({}),
                         np.concatenate([rows[:, :3][f] for (_, rows, _, _), f in zip(cloth, faces)]).astype(np.float64))
        for name, rotations, root in poses(animator):
            if name == worst:
                matrices = animator.skeleton.pose(rotations, root)
                triangles = np.concatenate([skin(rows, i, w, matrices)[:, :3][f]
                                            for (_, rows, i, w), f in zip(cloth, faces)]).astype(np.float64)
                points = poking(animator, matrices, triangles)[1]
                # what already pierced in the fitting pose is not counted by the battery either
                if len(base) and len(points):
                    gap = np.min(np.linalg.norm(points[:, None] - base[None], axis=2), axis=1)
                    points = points[gap > 0.01]
                shown["furando"] = (matrices, points, worst)
    stretched = max(GAME_POSES, key=lambda n: result["poses"][n]["esticado_cm2"])
    if result["poses"][stretched]["esticado_cm2"] > LIMITS["esticado_cm2"][0]:
        for name, rotations, root in poses(animator):
            if name == stretched:
                matrices = animator.skeleton.pose(rotations, root)
                points = np.vstack([stretching(rows, skin(rows, i, w, matrices), f)[1]
                                    for (_, rows, i, w), f in zip(cloth, faces)])
                shown["esticado"] = (matrices, points, stretched)
    for kind, entry in shown.items():
        if entry is None or not len(entry[1]):
            continue
        matrices, points, pose = entry
        for part, rows, indices, weights in animator._bindings:
            part.mesh.update_vertices(skin(rows, indices, weights, matrices))
        for k, (centre, members) in enumerate(regions(points, count)):
            plain, spots, share = best_view(shader, model, centre, members)
            title = f"{kind} {k + 1}: {len(members)} pts, {share:.0%} à vista, pose {pose}"
            views.append((title, plain, mark(plain, spots, COLOURS[kind])))
    model.delete()
    return views


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--names", nargs="*", default=[])
    parser.add_argument("--max", type=int, default=3, help="regions per kind and case")
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "inspecao"))
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    chosen = [r for r in report["resultados"]
              if (r["roupa"] in args.names if args.names else
                  r["veredito"] == "falha")]

    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(SIZE, SIZE, "Inspect", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")
    samples = {}
    for index, result in enumerate(chosen):
        body = result["corpo"]
        if body not in samples:
            samples[body] = naked_samples(BodyType.FEMALE if body == "female" else BodyType.MALE)
        views = inspect(shader, result, samples[body], args.max)
        if not views:
            continue
        sheet = Image.new("RGB", (SIZE * 2, (SIZE + 18) * len(views) + 20), "white")
        draw = ImageDraw.Draw(sheet)
        draw.text((4, 4), f"{result['roupa']} ({body}) | buraco {result['buraco_cm2']:.0f} | "
                          f"furando {max(result['poses'][p]['pele_furando_cm2'] for p in GAME_POSES):.0f}", fill="black")
        for row, (title, plain, marked) in enumerate(views):
            y = 20 + row * (SIZE + 18)
            draw.text((4, y + 2), title, fill="black")
            sheet.paste(plain, (0, y + 18))
            sheet.paste(marked, (SIZE, y + 18))
        name = f"{index:02d}_{body}_{''.join(c if c.isalnum() else '_' for c in result['roupa'])[:40]}.png"
        sheet.save(out / name)
        print(f"[{index + 1}/{len(chosen)}] {result['roupa']} ({body}): {len(views)} regiões -> {name}", flush=True)
    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
