"""Cabelo nudred (afro com "twists" de esponja), feito no Blender para o jogo.

Para rodar: abra no Blender um arquivo salvo em ``assets/models`` (``123.blend``), cole este
script no editor de texto e execute. As cabeças são lidas dos arquivos de corpo do próprio jogo
(``BODIES``), não dos objetos da cena. Ele cria a coleção "Nudred" com o cabelo sobre cada cabeça e grava
``assets/models/clothing/Hair_fitted_900000000001_<corpo>.obj``, o formato de cabelo que o jogo
veste (``/skin cabelo nudred``).

Para só exportar de novo um cabelo editado à mão no Blender, chame ``export`` com o objeto.

Como é feito: uma calota em volta da cabeça, justa na linha do cabelo (o degradê dos lados e da
nuca: cabelo rente, sem twists, de transparente na linha a opaco no alto dele) e cheia em cima, medida a partir da própria cabeça; e no alto dela
os "twists", compridos e largos, cada um um tubinho de quatro anéis que giram um pouco a cada passo.
"""
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HAIR_ID = "900000000001"
# The heads the game itself draws: the object "Export_cabeca" of each body's file (the heads in
# the .blend are not always these: its male one is 2 cm wider, and the hair came out as a helmet).
BODIES = {"male": "character_male_clean_apose.obj", "female": "character_female_clean_apose_stage2.obj"}
CLOTHING = os.path.join(os.path.dirname(bpy.data.filepath), "clothing")  # assets/models/clothing, beside the .blend
UP = Vector((0, 0, 1))
RING_POINTS, RINGS_ROUND, SIDES = 22, 72, 6                           # the cap's grid, and corners around a twist
TIGHT, MIN_FULL = 0.003, 0.010                                        # metres off the head in the fade, and at least in the volume
FADE, FADE_FRONT, BLEND = 0.040, 0.006, 0.045                         # metres of fade above the hairline at the sides and the nape (hair cut to the skin), at the forehead (none: the volume starts at the line), then of passing to the volume
TWISTS, TWIST_GAP, TWIST_FROM = 300, 0.0250, 0.72                     # how many at most, metres between them, and how full the hair must be to have them (the top)
TWIST_LENGTH, TWIST_RADIUS = (0.020, 0.018), 0.0160                   # metres long (the least, and more where the hair is fullest) and wide
OPACITY = "opacidade"                                                 # the UV layer that says how solid each vertex is (its u: 0 clear, 1 solid)
U_CLEAR, U_SOLID = 0.02, 0.98                                         # where clear and solid are on the texture the game makes


def game_head(path: str):
    """(points, faces) of the head in one of the game's body files, in Blender's axes (the game's x, y, z -> x, -z, y)."""
    points, faces, inside = [], [], False
    for line in open(path, encoding="utf-8", errors="ignore"):
        if line.startswith("v "):
            x, y, z = (float(t) for t in line.split()[1:4])
            points.append(Vector((x, -z, y)))
        elif line.startswith(("o ", "g ")):
            inside = line.split(maxsplit=1)[1].strip().startswith("Export_cabeca")
        elif line.startswith("f ") and inside:
            faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    used = sorted({i for face in faces for i in face})
    order = {old: new for new, old in enumerate(used)}
    return [points[i] for i in used], [[order[i] for i in face] for face in faces]


def nudred(name: str, head_points, head_faces, collection, seed: int = 7):
    """The nudred hair on a head (points and faces of it, in world space), as a new object."""
    bvh = BVHTree.FromPolygons(head_points, head_faces)
    pts = np.array(head_points)
    top, bottom = pts[:, 2].max(), pts[:, 2].min()
    tall = top - bottom
    face_y, back_y, half = pts[:, 1].min(), pts[:, 1].max(), np.abs(pts[:, 0]).max()
    centre = Vector((0.0, (face_y + back_y) / 2 + 0.0025, bottom + 0.656 * tall))
    rx, rz_up, rz_down = half + 0.020, (top - centre.z) + 0.060, 0.150
    ry_front, ry_back = (centre.y - face_y) + 0.032, (back_y - centre.y) + 0.032
    line = bottom + 0.500 * tall            # the hairline at the sides

    def direction(theta, phi):              # theta: 0 at the front (-y); phi: from straight up
        s = math.sin(phi)
        return Vector((s * math.sin(theta), -s * math.cos(theta), math.cos(phi)))

    def r_head(d):
        hit = bvh.ray_cast(centre, d)
        return (hit[0] - centre).length if hit[0] is not None else 0.12

    def r_full(d):
        ry = ry_front if d.y < 0 else ry_back
        rz = rz_up if d.z > 0 else rz_down
        return 1.0 / math.sqrt((d.x / rx) ** 2 + (d.y / ry) ** 2 + (d.z / rz) ** 2)

    def z_low(theta):                       # level at the forehead, a step down at the temples, a taper at the nape
        c = math.cos(theta)
        return line + 0.066 * max(c, 0.0) ** 1.2 - 0.030 * max(-c, 0.0) ** 1.5

    def smooth(t):
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def surface(theta, phi):
        d = direction(theta, phi)
        rh, rf = r_head(d), r_full(d)
        fade = FADE_FRONT + (FADE - FADE_FRONT) * (1.0 - max(math.cos(theta), 0.0) ** 1.2)   # none over the forehead
        full = smooth((centre.z + (rh + rf) / 2 * d.z - z_low(theta) - fade) / BLEND)        # 0 in the fade, 1 in the volume
        point = centre + d * (rh + TIGHT + full * max(rf - rh - TIGHT, MIN_FULL))
        solid = smooth((point.z - z_low(theta)) / fade)                                      # the fade: clear at the hairline, solid at its top
        return point, d, full, solid

    def phi_end(theta):                     # where the surface meets the hairline
        lo, hi = 0.3, math.radians(150)
        for _ in range(40):
            mid = (lo + hi) / 2
            if surface(theta, mid)[0].z > z_low(theta):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    ends = [phi_end(2 * math.pi * i / RINGS_ROUND) for i in range(RINGS_ROUND)]
    verts = [centre + UP * (r_head(UP) + TIGHT + max(r_full(UP) - r_head(UP) - TIGHT, MIN_FULL))]
    solid = [1.0]                           # of each vertex: 0 clear, 1 solid
    faces = []
    for i in range(RINGS_ROUND):
        for j in range(1, RING_POINTS + 1):
            point, _, _, how_solid = surface(2 * math.pi * i / RINGS_ROUND, ends[i] * j / RING_POINTS)
            verts.append(point)
            solid.append(how_solid)
    index = lambda i, j: 1 + (i % RINGS_ROUND) * RING_POINTS + (j - 1)
    for i in range(RINGS_ROUND):
        faces.append((0, index(i, 1), index(i + 1, 1)))
        for j in range(1, RING_POINTS):
            faces.append((index(i, j), index(i, j + 1), index(i + 1, j + 1), index(i + 1, j)))
    cap = len(verts)

    rng = np.random.default_rng(seed)
    spots, tries = [], 0
    while tries < 150000 and len(spots) < TWISTS:
        tries += 1
        theta = rng.uniform(0, 2 * math.pi)
        end = ends[int(theta / (2 * math.pi) * RINGS_ROUND) % RINGS_ROUND]
        p, d, full, _ = surface(theta, math.acos(1 - rng.uniform(0, 1) * (1 - math.cos(end))))
        if full < TWIST_FROM:               # the sides and the nape are a fade: no twists there
            continue
        gap = TWIST_GAP * (0.80 + 0.20 * full)
        if any((p - q).length < gap for q, _, _ in spots):
            continue
        spots.append((p, d, full))
    for p, d, full in spots:
        axis = (d * 0.62 + UP * 0.38 + Vector(rng.normal(0, 0.13, 3))).normalized()   # standing up more than out
        side = axis.cross(UP if abs(axis.z) < 0.9 else Vector((1, 0, 0))).normalized()
        other = axis.cross(side)
        length = (TWIST_LENGTH[0] + TWIST_LENGTH[1] * full) * rng.uniform(0.85, 1.2)
        radius = TWIST_RADIUS * rng.uniform(0.88, 1.12) * (0.75 + 0.25 * full)
        turn, coil = rng.uniform(0, 2 * math.pi), rng.choice((-1.0, 1.0))
        base = len(verts)
        rings = ((0.0, 1.0), (0.32, 0.96), (0.64, 0.84), (0.90, 0.56))
        for k, (t, wide) in enumerate(rings):
            swing = turn + coil * 1.5 * k   # the middle of each ring goes round: a coil
            middle = p - d * 0.006 + axis * length * t + (side * math.cos(swing) + other * math.sin(swing)) * radius * 0.26 * (k > 0)
            for s in range(SIDES):
                a = turn + 2 * math.pi * s / SIDES + coil * 0.6 * k
                verts.append(middle + (side * math.cos(a) + other * math.sin(a)) * radius * wide)
        verts.append(p - d * 0.006 + axis * length * 1.10)
        solid += [1.0] * (len(verts) - len(solid))
        tip = len(verts) - 1
        for k in range(len(rings) - 1):
            for s in range(SIDES):
                a, b = base + k * SIDES + s, base + k * SIDES + (s + 1) % SIDES
                faces.append((a, b, b + SIDES, a + SIDES))
        last = base + (len(rings) - 1) * SIDES
        for s in range(SIDES):
            faces.append((last + s, last + (s + 1) % SIDES, tip))

    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    # Every face turned outwards: the game lights by the faces' own normals.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    of_cap = [f for f in bm.faces if all(v.index < cap for v in f.verts)]
    if sum(f.normal.dot(f.calc_center_median() - centre) for f in of_cap) < 0:
        bmesh.ops.reverse_faces(bm, faces=of_cap)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    layer = mesh.uv_layers.new(name=OPACITY)   # how solid each vertex is, for the game to fade the sides
    for loop in mesh.loops:
        layer.data[loop.index].uv = (U_CLEAR + (U_SOLID - U_CLEAR) * solid[loop.vertex_index], 0.5)
    hair = bpy.data.objects.new(name, mesh)
    collection.objects.link(hair)
    material = bpy.data.materials.get("Nudred_cabelo") or bpy.data.materials.new("Nudred_cabelo")
    material.diffuse_color = (0.035, 0.03, 0.03, 1.0)
    mesh.materials.append(material)
    print(f"{name}: {len(spots)} twists, {len(mesh.vertices)} vértices, {len(mesh.polygons)} triângulos")
    return hair


def export(hair, path: str, title: str) -> None:
    """Write a mesh as the game's fitted hair: Y up and Z to the front (Blender x, y, z -> x, z, -y),
    triangles (triangulate it first), one texture coordinate a vertex: its u says how solid the hair is
    there (the UV layer OPACITY), and the game draws it in the character's hair colour, fading where it is clear."""
    mesh, world = hair.data, hair.matrix_world
    lines = [f"# Isometricon Native Fitted Hair: {title}"]
    for vertex in mesh.vertices:
        p = world @ vertex.co
        lines.append(f"v {p.x:.6f} {p.z:.6f} {-p.y:.6f}")
    layer = mesh.uv_layers.get(OPACITY)        # with it, u says how solid the vertex is; without, all of it is solid
    u = [U_SOLID] * len(mesh.vertices)
    if layer is not None:
        for loop in mesh.loops:
            u[loop.vertex_index] = layer.data[loop.index].uv[0]
    lines += [f"vt {value:.6f} 0.500000" for value in u]
    for polygon in mesh.polygons:
        assert len(polygon.vertices) == 3, "triangule a malha antes de exportar"
        a, b, c = (i + 1 for i in polygon.vertices)
        lines.append(f"f {a}/{a} {b}/{b} {c}/{c}")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print(f"gravado {path}")


def main() -> None:
    collection = bpy.data.collections.get("Nudred") or bpy.data.collections.new("Nudred")
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)
    models = os.path.dirname(bpy.data.filepath)
    for body, file in BODIES.items():
        points, faces = game_head(os.path.join(models, file))
        name = f"Nudred_ref_cabeca_{body}"       # the game's head, to see the hair on
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(p) for p in points], [], faces)
        mesh.update()
        collection.objects.link(bpy.data.objects.new(name, mesh))
        hair = nudred("Cabelo_Nudred" if body == "male" else f"Cabelo_Nudred_{body}", points, faces, collection)
        export(hair, os.path.join(CLOTHING, f"Hair_fitted_{HAIR_ID}_{body}.obj"), f"{HAIR_ID} (Nudred)")


if __name__ == "__main__":
    main()
