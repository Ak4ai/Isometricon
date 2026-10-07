"""Robustness battery: every local Roblox garment, on both bodies, through a set of poses.

python scripts/audit_animation_robustness.py [--limit N] [--only ID ...] [--bodies female male] [--output DIR]
python scripts/audit_animation_robustness.py --report DIR [DIR ...]     (rebuild the report, merging runs)
Output: relatorio.json (raw measurements), relatorio.md and falhas.png (the failing cases, marked).

For each garment, worn alone (and a few whole outfits), and each pose it measures,
without looking at images:
  pele furando   area (cm2) of drawn skin with cloth just beneath it and none over it (the body
                 pierces the garment), minus what already pierces in the fitting pose
  esticado       area (cm2) of the tested garment's triangles with an edge past 2.5x its fitted
                 length and at least 2 cm longer
  buraco         area (cm2) of skin that HSR removed although it can be seen from outside
                 (fitting pose): nothing drawn blocks a third of the directions around it
                 and nothing drawn lies just beneath it (cloth that shows through)
The measurements are stored raw. The verdict (ok, atenção, falha) comes from the limits in LIMITS,
applied when the report is written, over the poses the game shows (GAME_POSES); the other poses
stress the garment and are reported apart. Garments that cannot be worn are listed with the error.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import time

import glfw
import numpy as np
import OpenGL.GL as gl
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_female_tests import look_at, perspective
from src.clothing.character_animation import CharacterAnimator
from src.clothing.character_model import CLOTHING_DIR, MODELS_DIR, CharacterModel, is_valid_v2_obj
from src.clothing.customization import AvatarCustomization, BodyType
from src.clothing.hsr import closest_on_surface, subdivide
from src.clothing.layer_clearance import _farthest_hits, fitted_asset_type
from src.clothing.skeleton import rest_rotations, rotation_x, skin
from src.clothing.wear_engine import RobloxWearEngine, body_parts_path
from src.rendering.shader import Shader

OUT = ROOT / "artifacts" / "robustness"
JEANS, TANK = 109837605892174, 137915688957785
TOP_TYPES, BOTTOM_TYPES, DRESS = {64, 65, 67, 68}, {66, 69}, 72
SKIN = ("arm_left", "arm_right", "forearm_left", "forearm_right", "trunk_skin", "legs_skin")
# (attention, failure) past these, set by looking at the marked thumbnails of the whole catalogue:
# up to the first nothing shows at the game's distance (a knit sweater stretches ~400 cm2 under the
# arms when walking); past the second the garment is visibly torn, pierced or open.
LIMITS = {"pele_furando_cm2": (100.0, 400.0), "esticado_cm2": (600.0, 4000.0), "buraco_cm2": (100.0, 500.0)}
POKE_DEPTH, POKE_COVER = 0.04, 0.075  # cloth this deep under the skin pierces; cloth this far over it covers
STRETCH_RATIO, STRETCH_GROWTH = 2.5, 0.02
HOLE_RAYS, HOLE_OPEN, HOLE_REACH = 26, 0.3, 3.0
HOLE_BEHIND = 0.03  # hidden skin with something drawn this close beneath it shows that, not a hole
MARKS = {"pele_furando_cm2": (255, 40, 40), "esticado_cm2": (255, 220, 0), "buraco_cm2": (255, 0, 255)}
LAYERED = [("camisa + bomber", 133331049150205, 72628400373948), ("regata + moletom", TANK, 7192553841),
           ("camisa + sobretudo", 133331049150205, 133273151439383)]
COMBINED = [("regata + jeans", TANK), ("suéter + jeans", 9240757332), ("cropped + jeans", 101748354579961),
            ("regata de basquete + jeans", 97346273111638)]
SHOES = [("tênis", "101914651386350,131149613284268"), ("botas", "80102743203860,87917823878878")]
SIZE = 300
# The poses the game shows today; the others stress the garment and are reported apart.
GAME_POSES = ("descanso", "andar 1", "andar 2", "andar 3", "andar 4")


def poses(animator):
    rest = animator.rest
    yield "descanso", dict(rest), (0, 0, 0)
    for k, phase in enumerate(np.linspace(0, 2 * math.pi, 4, endpoint=False)):
        yield (f"andar {k + 1}", *animator.walk_pose(phase))
    yield "braços 90° lado", rest_rotations(animator.skeleton, math.pi / 2), (0, 0, 0)
    forward = dict(rest)
    for side in "LR":
        forward[f"UpperArm_{side}"] = rotation_x(-math.pi / 3) @ forward[f"UpperArm_{side}"]
    yield "braços 60° frente", forward, (0, 0, 0)
    seated = dict(rest)
    for side in "LR":
        seated[f"UpperLeg_{side}"] = rotation_x(-math.radians(80))
        seated[f"LowerLeg_{side}"] = rotation_x(math.radians(80))
    yield "sentar", seated, (0, 0, 0)


def triangle_area(points, faces):
    a, b, c = points[faces[:, 0]], points[faces[:, 1]], points[faces[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def any_hit(origins, directions, far, triangles):
    """Whether each ray meets a triangle within ``far``."""
    if not len(origins) or not len(triangles):
        return np.zeros(len(origins), dtype=bool)
    return ~np.isnan(_farthest_hits(origins, directions, np.full(len(origins), far / 2), triangles, far / 2))


def poking(animator, matrices, cloth_triangles):
    """(area in m2, their centres) of the drawn skin that pierces the cloth: cloth lies just
    beneath it and none over it.

    Each skin triangle is probed at three inner points, straight in and out of its own plane
    (a smoothed vertex normal would cut the corner of a blocky body and find the cloth that
    rightly covers the next face); the triangle counts by its share of piercing probes.
    """
    total, centres = 0.0, []
    for part, rows, indices, weights in animator._bindings:
        if part.name not in SKIN:
            continue
        faces = part.mesh.read_indices().reshape(-1, 3)
        if not len(faces):
            continue
        posed = skin(rows, indices, weights, matrices)
        corners = posed[:, :3].astype(np.float64)[faces]
        normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        areas = 0.5 * np.linalg.norm(normals, axis=1)
        solid = areas > 1e-10
        corners, areas = corners[solid], areas[solid]
        normals = normals[solid] / (2 * areas[:, None])
        normals *= np.sign((normals * posed[:, 3:6][faces[solid]].sum(1)).sum(1))[:, None]
        centre = corners.mean(1)
        probes = (0.5 * (corners + centre[:, None])).reshape(-1, 3)
        along = np.repeat(normals, 3, axis=0)
        pierce = any_hit(probes - along * 1e-4, -along, POKE_DEPTH, cloth_triangles)
        pierce[pierce] = ~any_hit(probes[pierce] + along[pierce] * 1e-3, along[pierce], POKE_COVER, cloth_triangles)
        share = pierce.reshape(-1, 3).mean(1)
        total += float((areas * share).sum())
        centres.append(centre[share > 0])
    return total, (np.vstack(centres) if centres else np.zeros((0, 3)))


def stretching(rows, posed, faces):
    """(area in m2, their centres, longest growth in m) of triangles torn by the pose."""
    torn, growth = np.zeros(len(faces), dtype=bool), 0.0
    for i, j in ((0, 1), (1, 2), (2, 0)):
        before = np.linalg.norm(rows[faces[:, i], :3] - rows[faces[:, j], :3], axis=1)
        after = np.linalg.norm(posed[faces[:, i], :3] - posed[faces[:, j], :3], axis=1)
        torn |= (before > 1e-5) & (after > STRETCH_RATIO * before) & (after - before > STRETCH_GROWTH)
        growth = max(growth, float((after - before).max()))
    points = posed[:, :3].astype(np.float64)
    return float(triangle_area(points, faces)[torn].sum()), points[faces[torn]].mean(1), growth


def naked_samples(body):
    """Centres, areas and normals of the whole (subdivided) skin of a body, hands, head and feet aside."""
    from src.clothing.character_model import parse_clean_obj_groups
    clean_obj = os.path.join(MODELS_DIR, f"character_{body.value}_clean_apose_stage2.obj" if body.value == "female"
                             else "character_male_clean_apose.obj")
    hip_tf = arm_tf = None
    groups = [("trunk_skin", ["Export_torso", "Export_pelve"], hip_tf),
              ("legs_skin", ["Export_coxa_esquerda", "Export_coxa_direita", "Export_canela_esquerda",
                             "Export_canela_direita", "Export_pe_esquerdo", "Export_pe_direito"], hip_tf)]
    for side, pt_side in (("left", "esquerdo"), ("right", "direito")):
        groups += [(f"arm_{side}", [f"Export_braco_superior_{pt_side}"], arm_tf),
                   (f"forearm_{side}", [f"Export_antebraco_{pt_side}"], arm_tf)]
    centres, areas, normals = [], [], []
    for name, prefixes, transform in groups:
        data = parse_clean_obj_groups(clean_obj, prefixes, default_color=[1, 1, 1], vertex_transform=transform)
        if not data:
            continue
        v, ind = data
        rows, faces = subdivide(v.reshape(-1, 11), ind.reshape(-1, 3), levels=2)
        pts = rows[:, :3].astype(np.float64)
        centres.append(pts[faces].mean(1))
        areas.append(triangle_area(pts, faces))
        normal = rows[:, 3:6].astype(np.float64)[faces].mean(1)
        normals.append(normal / np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9))
    return np.vstack(centres), np.concatenate(areas), np.vstack(normals)


def hemisphere(normals, count):
    """(N, count, 3) directions spread over the hemisphere around each normal."""
    k = np.arange(count) + 0.5
    polar, turn = np.arccos(1 - k / count * 0.95), k * math.pi * (3 - math.sqrt(5))
    local = np.stack([np.sin(polar) * np.cos(turn), np.sin(polar) * np.sin(turn), np.cos(polar)], axis=1)
    helper = np.where(np.abs(normals[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
    u = np.cross(normals, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    v = np.cross(normals, u)
    return (local[None, :, 0, None] * u[:, None] + local[None, :, 1, None] * v[:, None]
            + local[None, :, 2, None] * normals[:, None])


def holes(animator, samples):
    """(area in m2, their centres) of skin that is not drawn but can be seen from outside (fitting pose)."""
    centres, areas, normals = samples
    drawn = [(part, rows) for part, rows, _, _ in animator._bindings if part.mesh.index_count]
    everything = np.concatenate([rows[:, :3][part.mesh.read_indices().reshape(-1, 3)] for part, rows in drawn]).astype(np.float64)
    skin_drawn = [(part, rows) for part, rows in drawn if part.name in SKIN]
    visible = np.zeros(len(centres), dtype=bool)
    if skin_drawn:
        tri = np.concatenate([rows[:, :3][part.mesh.read_indices().reshape(-1, 3)] for part, rows in skin_drawn]).astype(np.float64)
        best, bary = closest_on_surface(centres, tri[:, 0], tri[:, 1], tri[:, 2])
        closest = (bary[:, :, None] * tri[best]).sum(1)
        visible = np.linalg.norm(closest - centres, axis=1) < 4e-3
    hidden = np.flatnonzero(~visible)
    hidden = hidden[~any_hit(centres[hidden] + normals[hidden] * 2e-3, normals[hidden], HOLE_REACH, everything)]
    hidden = hidden[~any_hit(centres[hidden] + normals[hidden] * 2e-3, -normals[hidden], HOLE_BEHIND, everything)]
    if not len(hidden):
        return 0.0, np.zeros((0, 3))
    directions = hemisphere(normals[hidden], HOLE_RAYS)
    origins = np.repeat(centres[hidden] + normals[hidden] * 2e-3, HOLE_RAYS, axis=0)
    blocked = any_hit(origins, directions.reshape(-1, 3), HOLE_REACH, everything).reshape(len(hidden), HOLE_RAYS)
    opened = hidden[(~blocked).mean(1) >= HOLE_OPEN]
    return float(areas[opened].sum()), centres[opened]


VIEW = dict(eye=(-1.9, 1.1, 2.3), target=(0.0, 0.9, 0.0), fov=34.0)


def render(shader, model):
    gl.glClearColor(0.18, 0.19, 0.22, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    shader.use()
    shader.set_mat4("u_Projection", perspective(VIEW["fov"], 1.0, 0.05, 50.0))
    shader.set_mat4("u_View", look_at(list(VIEW["eye"]), list(VIEW["target"]), [0.0, 1.0, 0.0]))
    shader.set_vec3("u_LightDir", 0.4, 1.2, 0.8)
    shader.set_vec3("u_LightColor", 0.85, 0.85, 0.85)
    shader.set_vec3("u_AmbientColor", 0.45, 0.45, 0.45)
    shader.set_int("u_TextureAtlas", 0)
    model.draw(shader, np.identity(4, dtype=np.float32))
    gl.glFinish()
    pixels = gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    depth = np.frombuffer(gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT), dtype=np.float32)
    image = Image.frombytes("RGBA", (SIZE, SIZE), pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")
    return image, depth.reshape(SIZE, SIZE)[::-1]


def mark(image, depth, points, colour):
    """Dots on the thumbnail where ``points`` are, the ones in sight only."""
    if not len(points):
        return
    matrix = (np.asarray(perspective(VIEW["fov"], 1.0, 0.05, 50.0), dtype=np.float64)
              @ np.asarray(look_at(list(VIEW["eye"]), list(VIEW["target"]), [0.0, 1.0, 0.0]), dtype=np.float64))
    clip = np.c_[points, np.ones(len(points))] @ matrix.T
    ndc = clip[:, :3] / clip[:, 3:]
    x = np.round((ndc[:, 0] * 0.5 + 0.5) * (SIZE - 1)).astype(int)
    y = np.round((0.5 - ndc[:, 1] * 0.5) * (SIZE - 1)).astype(int)
    inside = (x >= 0) & (x < SIZE) & (y >= 0) & (y < SIZE) & (clip[:, 3] > 0)
    draw = ImageDraw.Draw(image)
    for px, py, z in zip(x[inside], y[inside], ndc[inside, 2]):
        if z * 0.5 + 0.5 <= depth[py, px] + 2e-4:
            draw.point((px, py), fill=colour)


def audit(shader, label, body, samples, tested=(), **ids):
    """Raw measurements of one outfit on one body, per pose, and a marked thumbnail of its worst pose."""
    model = CharacterModel(customization=AvatarCustomization(body_type=body), **ids)
    animator = CharacterAnimator(model, walking=False)
    animator.update(0.0)
    cloth = [b for b in animator._bindings if b[0].source_obj is not None]
    if not cloth:
        model.delete()
        raise RuntimeError("nenhuma peça foi vestida")
    cloth_faces = [part.mesh.read_indices().reshape(-1, 3) for part, *_ in cloth]
    rest_triangles = np.concatenate([rows[:, :3][faces] for (_, rows, _, _), faces in zip(cloth, cloth_faces)]).astype(np.float64)
    base_poke, _ = poking(animator, animator.skeleton.pose({}), rest_triangles)
    hole, hole_points = holes(animator, samples)
    tested_area = sum(float(triangle_area(rows[:, :3].astype(np.float64), faces).sum())
                      for (part, rows, _, _), faces in zip(cloth, cloth_faces) if not tested or part.name.startswith(tested))
    result = {"roupa": label, "corpo": body.value, "ids": {k: str(v) for k, v in ids.items()},
              "encaixe_pela_cage": all(os.path.exists(body_parts_path(part.source_obj)) for part, *_ in cloth),
              "area_da_peca_cm2": round(tested_area * 1e4), "buraco_cm2": round(hole * 1e4, 1),
              "fura_na_pose_de_vestir_cm2": round(base_poke * 1e4, 1),
              "balanco_dos_bracos": animator.arm_swing, "poses": {}}
    kept = {}
    for name, rotations, root in poses(animator):
        matrices = animator.skeleton.pose(rotations, root)
        posed = [skin(rows, indices, weights, matrices) for _, rows, indices, weights in cloth]
        triangles = np.concatenate([p[:, :3][faces] for p, faces in zip(posed, cloth_faces)]).astype(np.float64)
        stretched, stretch_points, growth = 0.0, [np.zeros((0, 3))], 0.0
        for (part, rows, _, _), p, faces in zip(cloth, posed, cloth_faces):
            if tested and not part.name.startswith(tested):
                continue
            area, points, longest = stretching(rows, p, faces)
            stretched, growth = stretched + area, max(growth, longest)
            stretch_points.append(points)
        poke, poke_points = poking(animator, matrices, triangles)
        result["poses"][name] = {"pele_furando_cm2": round(max(poke - base_poke, 0.0) * 1e4, 1),
                                 "esticado_cm2": round(stretched * 1e4, 1), "maior_alongamento_cm": round(growth * 100, 1)}
        kept[name] = (matrices, poke_points, np.vstack(stretch_points))
    worst = max(GAME_POSES, key=lambda n: max(result["poses"][n][k] / LIMITS[k][1] for k in ("pele_furando_cm2", "esticado_cm2")))
    result["pior_pose"] = worst
    matrices, poke_points, stretch_points = kept[worst]
    for part, rows, indices, weights in animator._bindings:
        part.mesh.update_vertices(skin(rows, indices, weights, matrices))
    thumbnail, depth = render(shader, model)
    mark(thumbnail, depth, stretch_points, MARKS["esticado_cm2"])
    mark(thumbnail, depth, poke_points, MARKS["pele_furando_cm2"])
    mark(thumbnail, depth, hole_points, MARKS["buraco_cm2"])
    model.delete()
    return result, thumbnail


def verdict(result, level):
    """What a measured case exceeds at a level of LIMITS (0 attention, 1 failure), in the game's poses."""
    found = {f"{pose}: {key}" for pose in GAME_POSES for key in ("pele_furando_cm2", "esticado_cm2")
             if result["poses"][pose][key] > LIMITS[key][level]}
    if result["buraco_cm2"] > LIMITS["buraco_cm2"][level]:
        found.add("buraco")
    return sorted(found)


def write_report(out, runs):
    """relatorio.json/.md and falhas.png in ``out`` from the measurements of one or more runs."""
    results, skipped, seconds = [], [], 0
    for folder in runs:
        data = json.loads((Path(folder) / "medidas.json").read_text(encoding="utf-8"))
        for r in data["resultados"]:
            r["miniatura"] = str(Path(folder) / r["miniatura"])
        results += data["resultados"]
        skipped += data["nao_vestidas"]
        seconds = max(seconds, data["segundos"])
    for r in results:
        r["falhas"], r["atencao"] = verdict(r, 1), verdict(r, 0)
        r["veredito"] = "falha" if r["falhas"] else "atenção" if r["atencao"] else "ok"
        r["jogo"] = {key: max(r["poses"][pose][key] for pose in GAME_POSES) for key in ("pele_furando_cm2", "esticado_cm2")}
        r["extras"] = {key: max(m[key] for pose, m in r["poses"].items() if pose not in GAME_POSES)
                       for key in ("pele_furando_cm2", "esticado_cm2")}
    count = {v: sum(r["veredito"] == v for r in results) for v in ("ok", "atenção", "falha")}
    report = {"limites": LIMITS, "poses_do_jogo": GAME_POSES, "contagem": count, "resultados": results,
              "nao_vestidas": skipped, "segundos": seconds}
    (out / "relatorio.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = ["# Bateria de robustez das roupas", "",
             f"{len(results)} combinações testadas: {count['ok']} ok, {count['atenção']} atenção, {count['falha']} falha; "
             f"{len(skipped)} fora do teste.", "",
             f"O veredito vale para as poses do jogo ({', '.join(GAME_POSES)}). Limites (atenção, falha) em cm²: "
             + "; ".join(f"{k.replace('_cm2', '').replace('_', ' ')} {int(a)}/{int(b)}" for k, (a, b) in LIMITS.items())
             + ". As colunas “extra” são o pior valor nas poses que o jogo ainda não usa (braços abertos, braços à frente, sentar).", "",
             "| Veredito | Roupa | Corpo | Buraco | Pele furando | Esticado | Pior pose do jogo | Furando (extra) | Esticado (extra) | Motivo |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    order = {"falha": 0, "atenção": 1, "ok": 2}
    for r in sorted(results, key=lambda r: (order[r["veredito"]], -r["jogo"]["esticado_cm2"], r["roupa"])):
        lines.append(f"| {r['veredito']} | {r['roupa']} | {r['corpo']} | {r['buraco_cm2']:.0f} | {r['jogo']['pele_furando_cm2']:.0f} | "
                     f"{r['jogo']['esticado_cm2']:.0f} | {r['pior_pose']} | {r['extras']['pele_furando_cm2']:.0f} | "
                     f"{r['extras']['esticado_cm2']:.0f} | {'; '.join(r['falhas'] or r['atencao']) or '-'} |")
    lines += ["", "## Fora do teste", ""] + [f"- {s['roupa']} ({s['corpo']}): {s['motivo']}" for s in skipped]
    (out / "relatorio.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name, wanted in (("falhas.png", "falha"), ("atencao.png", "atenção")):
        chosen = sorted((r for r in results if r["veredito"] == wanted), key=lambda r: -r["jogo"]["esticado_cm2"])
        if not chosen:
            continue
        columns = 8
        sheet = Image.new("RGB", (SIZE * columns, (SIZE + 40) * math.ceil(len(chosen) / columns)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, r in enumerate(chosen):
            x, y = (i % columns) * SIZE, (i // columns) * (SIZE + 40)
            sheet.paste(Image.open(r["miniatura"]), (x, y + 40))
            draw.text((x + 3, y + 1), f"{r['roupa'][:38]} ({r['corpo'][0]})", fill="black")
            draw.text((x + 3, y + 13), f"{r['pior_pose']} | buraco {r['buraco_cm2']:.0f}", fill="black")
            draw.text((x + 3, y + 25), f"fura {r['jogo']['pele_furando_cm2']:.0f} | esticado {r['jogo']['esticado_cm2']:.0f}", fill="black")
        sheet.save(out / name)
    print(f"[OK] {len(results)} testadas: {count} | {len(skipped)} fora do teste -> {out}")


def local_garments():
    """(asset id, name) of every garment downloaded to assets/models/clothing."""
    found = {}
    for path in sorted(Path(CLOTHING_DIR).glob("*.rbxm")):
        match = re.search(r"_(\d{6,})$", path.stem)
        if match and "hair" not in path.stem.lower():
            found[match.group(1)] = path.stem[:match.start()].replace("_", " ").strip()
    return found


def slot_of(asset_id, body_name):
    """('top' | 'bottom' | 'dress' | None, error): fits the garment on first use."""
    path = os.path.join(MODELS_DIR, f"character_native_{asset_id}_{body_name}.obj")
    if not is_valid_v2_obj(path):
        try:
            RobloxWearEngine(body_type=body_name).wear(asset_id, output_obj=path)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
    asset_type = fitted_asset_type(path)
    if asset_type in TOP_TYPES:
        return "top", None
    if asset_type in BOTTOM_TYPES:
        return "bottom", None
    if asset_type == DRESS:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            heights = [float(line.split()[3]) for line in handle if line.startswith("v ")]
        return ("dress" if max(heights) > 1.2 else "bottom"), None
    return None, f"tipo de asset {asset_type} fora do teste (sapato, acessório...)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--bodies", nargs="*", default=["female", "male"])
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--report", nargs="*", default=None)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.report is not None:
        write_report(out, args.report or [out])
        return
    garments = local_garments()
    if args.only:
        garments = {k: v for k, v in garments.items() if k in args.only}
    if args.limit:
        garments = dict(list(garments.items())[:args.limit])
    (out / "miniaturas").mkdir(exist_ok=True)

    glfw.init()
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    window = glfw.create_window(SIZE, SIZE, "Robustness", None, None)
    glfw.make_context_current(window)
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glViewport(0, 0, SIZE, SIZE)
    shader = Shader("assets/shaders/world_textured.vert", "assets/shaders/world_textured.frag")

    results, skipped = [], []
    started = time.perf_counter()
    for body_name in args.bodies:
        body = BodyType.FEMALE if body_name == "female" else BodyType.MALE
        samples = naked_samples(body)
        cases = []
        for asset_id, name in garments.items():
            slot, error = slot_of(asset_id, body_name)
            if slot is None:
                skipped.append({"roupa": name, "id": asset_id, "corpo": body_name, "motivo": error})
            elif slot == "bottom":
                cases.append((name, dict(tested=("bottom",), top_id=None, bottom_id=int(asset_id))))
            else:
                cases.append((name, dict(tested=("top",), top_id=int(asset_id), bottom_id=None)))
        if not args.only and not args.limit:
            cases += [(label, dict(tested=("top", "bottom"), top_id=top, bottom_id=JEANS)) for label, top in COMBINED]
            cases += [(label, dict(tested=("outer_top",), top_id=top, bottom_id=JEANS, outer_top_id=outer))
                      for label, top, outer in LAYERED]
            cases += [(f"jeans + {label}", dict(tested=("shoe",), top_id=TANK, bottom_id=JEANS, shoes_id=ids))
                      for label, ids in SHOES]
        for index, (label, ids) in enumerate(cases):
            try:
                result, thumbnail = audit(shader, label, body, samples, **ids)
            except Exception as exc:
                skipped.append({"roupa": label, "corpo": body_name, "motivo": f"{type(exc).__name__}: {exc}"})
                continue
            result["miniatura"] = f"miniaturas/{body_name}_{index:03d}.png"
            thumbnail.save(out / result["miniatura"])
            results.append(result)
            failed = verdict(result, 1)
            print(f"[{body_name} {index + 1}/{len(cases)}] {label}: {'FALHA ' + '; '.join(failed) if failed else 'ok'}", flush=True)
            measurements = {"resultados": results, "nao_vestidas": skipped, "segundos": round(time.perf_counter() - started)}
            (out / "medidas.json").write_text(json.dumps(measurements, indent=1, ensure_ascii=False), encoding="utf-8")
    glfw.destroy_window(window)
    glfw.terminate()
    write_report(out, [out])


if __name__ == "__main__":
    main()
