"""O nariz 3D do personagem: a malha do modelo antigo (objeto ``nariz.002``), guardada aqui.

Os corpos atuais (arquivos ``*_clean_apose*.obj``) não trazem o nariz; a malha vem do corpo
masculino antigo, extraída com ``parse_clean_obj_groups`` (posição, normal e UV de cada vértice).
As UVs caem na textura da cabeça, entre os olhos, onde a sombra do nariz é pintada.
"""
import numpy as np

# Each vertex: x, y, z, normal x, y, z, u, v (on the head of the old male body: face at z = 0.133,
# head from y = 1.492 to 1.809).
ROWS = np.array([
    [-0.00548, 1.58016, 0.14455, -0.00000, -0.04880, 0.99880, 0.23380, 0.38695],
    [-0.00548, 1.56624, 0.14387, -0.00000, -0.04880, 0.99880, 0.23380, 0.39867],
    [0.00910, 1.56624, 0.14387, -0.00000, -0.04880, 0.99880, 0.26310, 0.39867],
    [0.00910, 1.58016, 0.14455, -0.00000, -0.04880, 0.99880, 0.26310, 0.38695],
    [-0.00548, 1.56657, 0.12955, -0.00000, -0.99970, -0.02280, 0.23380, 0.40063],
    [0.00910, 1.56657, 0.12955, -0.00000, -0.99970, -0.02280, 0.26310, 0.40063],
    [0.00910, 1.56624, 0.14387, -0.00000, -0.99970, -0.02280, 0.26310, 0.40649],
    [-0.00548, 1.56624, 0.14387, -0.00000, -0.99970, -0.02280, 0.23380, 0.40649],
    [0.00910, 1.58030, 0.12996, -0.00000, 1.00000, 0.00940, 0.26310, 0.37914],
    [-0.00548, 1.58030, 0.12996, -0.00000, 1.00000, 0.00940, 0.23380, 0.37914],
    [-0.00548, 1.58016, 0.14455, -0.00000, 1.00000, 0.00940, 0.23380, 0.38500],
    [0.00910, 1.58016, 0.14455, -0.00000, 1.00000, 0.00940, 0.26310, 0.38500],
    [-0.00548, 1.58030, 0.12996, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [-0.00548, 1.56657, 0.12955, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [-0.00548, 1.56624, 0.14387, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [-0.00548, 1.58016, 0.14455, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [0.00910, 1.56657, 0.12955, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.58030, 0.12996, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.58016, 0.14455, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.56624, 0.14387, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.63615, 0.12988, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.63586, 0.13284, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [0.00910, 1.57982, 0.14038, 1.00000, -0.00000, -0.00000, 0.23185, 0.38695],
    [-0.00548, 1.63615, 0.12988, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [-0.00548, 1.57982, 0.14038, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [-0.00548, 1.63586, 0.13284, -1.00000, -0.00000, -0.00000, 0.22794, 0.38695],
    [0.00910, 1.63615, 0.12988, -0.00000, 0.99530, 0.09730, 0.26310, 0.37914],
    [-0.00548, 1.63615, 0.12988, -0.00000, 0.99530, 0.09730, 0.23380, 0.37914],
    [-0.00548, 1.63586, 0.13284, -0.00000, 0.99530, 0.09730, 0.23380, 0.38500],
    [0.00910, 1.63586, 0.13284, -0.00000, 0.99530, 0.09730, 0.26310, 0.38500],
    [-0.00548, 1.58030, 0.12996, -0.00000, -0.99890, -0.04590, 0.23380, 0.40063],
    [0.00910, 1.58030, 0.12996, -0.00000, -0.99890, -0.04590, 0.26310, 0.40063],
    [0.00910, 1.57982, 0.14038, -0.00000, -0.99890, -0.04590, 0.26310, 0.40649],
    [-0.00548, 1.57982, 0.14038, -0.00000, -0.99890, -0.04590, 0.23380, 0.40649],
    [-0.00548, 1.63586, 0.13284, -0.00000, 0.13340, 0.99110, 0.23380, 0.38695],
    [-0.00548, 1.57982, 0.14038, -0.00000, 0.13340, 0.99110, 0.23380, 0.39867],
    [0.00910, 1.57982, 0.14038, -0.00000, 0.13340, 0.99110, 0.26310, 0.39867],
    [0.00910, 1.63586, 0.13284, -0.00000, 0.13340, 0.99110, 0.26310, 0.38695],
])
TRIANGLES = np.array([
    [0, 1, 2],
    [0, 2, 3],
    [4, 5, 6],
    [4, 6, 7],
    [8, 9, 10],
    [8, 10, 11],
    [12, 13, 14],
    [12, 14, 15],
    [16, 17, 18],
    [16, 18, 19],
    [17, 20, 21],
    [17, 21, 22],
    [23, 12, 24],
    [23, 24, 25],
    [26, 27, 28],
    [26, 28, 29],
    [30, 31, 32],
    [30, 32, 33],
    [34, 35, 36],
    [34, 36, 37],
], dtype=np.uint32)
# Where the old head put it: the bottom of the head and the plane of the face.
HEAD_BOTTOM, FACE_FRONT = 1.492, 0.133


# ---------------------------------------------------------------------------------------------
# Formatos de nariz: a mesma ideia do nariz antigo (um dorso que sai do rosto e termina numa
# ponta), gerada por parâmetros para poder curvar a ponte, alargar a ponta ou as narinas.
# ---------------------------------------------------------------------------------------------
from dataclasses import dataclass, replace
from typing import Dict, Mapping, Optional

SECTIONS = 6          # cortes ao longo do dorso, da ponte à ponta
EMBED = 0.003         # metres the base goes into the face (no gap on a rounded head)
HUMP = 0.005          # metres a fully curved bridge rises (or sinks) at its middle
TIP_LIFT = 0.006      # metres a fully upturned tip rises
NOSE_BOTTOM = float(ROWS[:, 1].min())  # under the tip, on the old head: every shape ends here, above the mouth
# Where on the head atlas the nose takes its colour: the patch the old nose used, between the eyes,
# but stopping short of the mouth (the old one ran into its upper edge and came out pink underneath).
UV_CENTRE, UV_SPAN = (0.2455, 0.379), (1.2, 0.014)


@dataclass(frozen=True)
class NoseShape:
    """Medidas de um nariz, em metros (curve e tip_lift de -1 a 1)."""
    length: float = 0.066         # from the top of the bridge down to the tip
    under: float = 0.004          # from the tip down to where the nose meets the face
    bridge_base: float = 0.010    # width on the face, at the top
    bridge_ridge: float = 0.005   # width of the ridge, at the top
    bridge_depth: float = 0.003   # how far the top of the bridge stands out
    tip_width: float = 0.012      # width of the ridge at the tip
    nostril_width: float = 0.016  # width on the face at the bottom (the nostrils)
    tip_depth: float = 0.015      # how far the tip stands out
    curve: float = 0.0            # bridge: + curved outwards (aquiline), - inwards
    tip_lift: float = 0.0         # tip: + turned up, - turned down
    flare: float = 0.45           # how far down the nose (0 to 1) it starts to widen to the nostrils
    wing_width: float = 0.0       # the wings of the nostrils: a block on each side of the tip,
    wing_height: float = 0.0      # this wide, this tall
    wing_depth: float = 0.0       # and standing this far out of the face
    wing_lift: float = 0.0        # how far above the bottom of the nose the wings start (negative: below it)


BASE = NoseShape()  # the measures of the old nose: 7 cm long, a 1.5 cm tip, as wide as its tip box
NOSE_STYLES: Dict[str, NoseShape] = {
    "padrao": BASE,
    "projetado": replace(BASE, tip_depth=0.023, bridge_depth=0.007),
    "ponta_larga": replace(BASE, tip_width=0.020, nostril_width=0.022),
    "narinas_largas": replace(BASE, nostril_width=0.028, tip_width=0.013),
    "aquilino": replace(BASE, curve=1.0, tip_lift=-0.6, tip_depth=0.018, length=0.070),
    "arrebitado": replace(BASE, curve=-0.7, tip_lift=1.0, length=0.058, tip_depth=0.016, under=0.006),
    "fino": replace(BASE, bridge_base=0.007, bridge_ridge=0.0035, tip_width=0.008, nostril_width=0.011),
    "largo": replace(BASE, bridge_base=0.014, bridge_ridge=0.008, tip_width=0.018, nostril_width=0.024),
    "botao": replace(BASE, length=0.038, tip_depth=0.012, bridge_depth=0.002, tip_lift=0.5, tip_width=0.013),
    "longo": replace(BASE, length=0.084, tip_depth=0.017),
    # Short and wide, from the button nose, with the wings of the nostrils as blocks beside the tip.
    "botao_largo": replace(BASE, length=0.038, tip_depth=0.012, bridge_depth=0.002, tip_lift=0.5, tip_width=0.016,
                           nostril_width=0.020, wing_width=0.005, wing_height=0.010, wing_depth=0.007),
    "botao_arrebitado": replace(BASE, length=0.036, tip_depth=0.013, bridge_depth=0.002, tip_lift=1.0, curve=-0.5,
                                under=0.006, tip_width=0.014, nostril_width=0.018, wing_width=0.004, wing_height=0.009,
                                wing_depth=0.007),
    "narinas_grandes": replace(BASE, length=0.046, tip_depth=0.013, bridge_depth=0.002, bridge_base=0.013,
                               bridge_ridge=0.007, tip_width=0.018, nostril_width=0.022, flare=0.30,
                               wing_width=0.009, wing_height=0.013, wing_depth=0.010),
    "achatado": replace(BASE, length=0.050, tip_depth=0.009, bridge_depth=0.0015, bridge_base=0.014, bridge_ridge=0.008,
                        tip_width=0.020, nostril_width=0.024, flare=0.30, wing_width=0.008, wing_height=0.011,
                        wing_depth=0.007),
    "batata": replace(BASE, length=0.050, tip_depth=0.017, bridge_depth=0.003, tip_width=0.021, nostril_width=0.022,
                      flare=0.35, wing_width=0.006, wing_height=0.012, wing_depth=0.011),
    "aberto": replace(BASE, length=0.060, tip_depth=0.014, bridge_depth=0.003, tip_width=0.015, nostril_width=0.022,
                      flare=0.35, wing_width=0.008, wing_height=0.012, wing_depth=0.009),
}
BLOCK = "bloco"  # the old mesh itself, as it was
BLOCK_WINGS = "bloco_narinas"  # and with the wings of the nostrils of the "batata" nose beside its tip
BLOCKS = (BLOCK, BLOCK_WINGS)  # meshes of their own: changing to or from one rebuilds the nose
STYLE_NAMES = tuple(NOSE_STYLES) + BLOCKS
# The flat front of the face on the 512 px head atlas: the column of x = 0 and pixels per metre
# across, the row of the top of that face, its height above the bottom of the head, pixels per metre down.
FACE_PIXELS = (128.25, 1092.5, 35.0, 0.2735, 801.0)
# With the computed shadow the whole nose takes its colour from this one point of the atlas, under
# the nose itself, which that shadow leaves clear (the patch between the eyes is in the shadow).
PLAIN_UV = (128.0 / 512.0, 186.0 / 512.0)


def _smooth(low: float, high: float, t: float) -> float:
    x = min(max((t - low) / (high - low), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def build(shape: NoseShape) -> np.ndarray:
    """Vértices (N, 8: posição, normal, UV) de um nariz, três por triângulo, com o rosto em z = 0 e
    o ponto sob a ponta em y = 0. Todos os formatos têm os mesmos triângulos, na mesma ordem."""
    top = shape.under + shape.length
    sections = []  # each: left on the face, left of the ridge, right of the ridge, right on the face, and t
    for k in range(SECTIONS):
        t = k / (SECTIONS - 1)
        y = top - shape.length * t + TIP_LIFT * shape.tip_lift * _smooth(0.6, 1.0, t)
        depth = shape.bridge_depth + (shape.tip_depth - shape.bridge_depth) * t + HUMP * shape.curve * np.sin(np.pi * t)
        base = shape.bridge_base + (shape.nostril_width - shape.bridge_base) * _smooth(shape.flare, 1.0, t)
        ridge = shape.bridge_ridge + (shape.tip_width - shape.bridge_ridge) * _smooth(0.3, 1.0, t)
        sections.append(([-base / 2, y, 0.0], [-ridge / 2, y, depth], [ridge / 2, y, depth], [base / 2, y, 0.0], t))
    inside = np.array([0.0, shape.under + shape.length / 2, 0.0])
    quads = []  # (four corners, t of each, a point inside the solid they close)
    first, last = sections[0], sections[-1]
    quads.append(((first[0], first[1], first[2], first[3]), (0.0,) * 4, inside))              # top of the bridge
    for a, b in zip(sections, sections[1:]):
        for i in range(3):                                                                    # left wall, ridge, right wall
            quads.append(((a[i], b[i], b[i + 1], a[i + 1]), (a[4], b[4], b[4], a[4]), inside))
    left, right = [-shape.nostril_width / 2, 0.0, 0.0], [shape.nostril_width / 2, 0.0, 0.0]   # under the tip, on the face
    quads.append(((last[1], left, right, last[2]), (1.0,) * 4, inside))                       # underside of the tip
    # The wings of the nostrils: a block on each side, from inside the base of the nose outwards,
    # a little less deep at its outer edge. With no width or height they are flat, hidden in the nose.
    for side in (-1.0, 1.0):
        x0, x1 = side * shape.nostril_width * 0.42, side * (shape.nostril_width / 2 + shape.wing_width)
        y0, z0, z1 = shape.wing_lift, shape.wing_depth, shape.wing_depth * 0.7
        y1 = y0 + shape.wing_height
        centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2, z0 / 2])
        for corners in (([x0, y0, z0], [x1, y0, z1], [x1, y1, z1], [x0, y1, z0]),      # front
                        ([x1, y0, 0.0], [x1, y0, z1], [x1, y1, z1], [x1, y1, 0.0]),    # outer side
                        ([x0, y1, 0.0], [x0, y1, z0], [x1, y1, z1], [x1, y1, 0.0]),    # top
                        ([x0, y0, 0.0], [x1, y0, 0.0], [x1, y0, z1], [x0, y0, z0])):   # underside
            quads.append((corners, (1.0,) * 4, centre))
    triangles = []
    for corners, ts, within in quads:
        triangles += [((corners[0], corners[1], corners[2]), (ts[0], ts[1], ts[2]), within),
                      ((corners[0], corners[2], corners[3]), (ts[0], ts[2], ts[3]), within)]
    triangles += [((last[0], last[1], left), (1.0,) * 3, inside), ((last[3], right, last[2]), (1.0,) * 3, inside)]  # sides of the nostrils
    rows = np.zeros((len(triangles) * 3, 8))
    for k, (corners, ts, inside) in enumerate(triangles):
        p = np.array(corners, dtype=np.float64)
        ts = np.array(ts, dtype=np.float64)
        normal = np.cross(p[1] - p[0], p[2] - p[0])
        length = np.linalg.norm(normal)
        normal = normal / length if length > 1e-12 else np.array([0.0, 0.0, 1.0])
        if normal @ (p.mean(0) - inside) < 0:  # facing out of the nose
            p, ts, normal = p[::-1], ts[::-1], -normal
        rows[3 * k:3 * k + 3, :3] = p
        rows[3 * k:3 * k + 3, 3:6] = normal
        rows[3 * k:3 * k + 3, 6] = UV_CENTRE[0] + UV_SPAN[0] * p[:, 0]
        rows[3 * k:3 * k + 3, 7] = UV_CENTRE[1] + UV_SPAN[1] * ts
    return rows


def _place(rows8: np.ndarray, head_rows: np.ndarray) -> np.ndarray:
    """Rows of 11 floats of a nose given on the old head, moved to the head given by its vertex
    rows: as far above the bottom of the head, and on the plane of this face."""
    head = np.asarray(head_rows, dtype=np.float64).reshape(-1, 11)[:, :3]
    lift = head[:, 1].min() - HEAD_BOTTOM
    low, high = rows8[:, 1].min() + lift, rows8[:, 1].max() + lift
    face = head[(np.abs(head[:, 0]) < 0.05) & (head[:, 1] > low - 0.03) & (head[:, 1] < high + 0.03)]
    rows = np.ones((len(rows8), 11), dtype=np.float32)  # colour (the last three) stays white
    rows[:, :8] = rows8
    rows[:, 1] += lift
    rows[:, 2] += (face[:, 2].max() if len(face) else head[:, 2].max()) - FACE_FRONT
    return rows


# Adjustments that change the measures of a shape (the old block nose has none of them), and how
# much each does at 1: widths as a share, the height of the bridge in metres, where the base starts.
PARAMETRIC = ("nariz_ponta_largura", "nariz_ponte_largura", "nariz_ponte_altura", "nariz_base_largura", "nariz_base_altura",
              "nariz_narinas_altura", "nariz_ponta_projecao")
PART_WIDTH, BRIDGE_HEIGHT, BASE_HEIGHT = 0.6, 0.006, 0.6
TIP_REACH = 0.010  # metres the tip alone comes out of the face or goes back (the wings of the nostrils stay)
WING_LIFT = 0.008  # metres the wings of the nostrils go up or down the nose
# The colour of the tip: what the skin is multiplied by at its pinkest, and at its darkest.
TIP_PINK, TIP_DARK = (1.0, 0.70, 0.72), (0.80, 0.72, 0.68)


def _amount(adjust: Optional[Mapping[str, float]], name: str) -> float:
    try:
        return min(max(float((adjust or {}).get(name, 0.0)), -1.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def parametric(adjust: Optional[Mapping[str, float]]) -> bool:
    return any(_amount(adjust, name) for name in PARAMETRIC)


def adjusted(shape: NoseShape, adjust: Optional[Mapping[str, float]]) -> NoseShape:
    """As medidas de um formato com os ajustes de cada parte: a ponta, a ponte e a base (as narinas e
    suas asas) mudam cada uma por si."""
    tip, bridge = 1.0 + PART_WIDTH * _amount(adjust, "nariz_ponta_largura"), 1.0 + PART_WIDTH * _amount(adjust, "nariz_ponte_largura")
    base, tall = 1.0 + PART_WIDTH * _amount(adjust, "nariz_base_largura"), _amount(adjust, "nariz_base_altura")
    return replace(shape, tip_width=shape.tip_width * tip,
                   tip_depth=max(0.003, shape.tip_depth + TIP_REACH * _amount(adjust, "nariz_ponta_projecao")),
                   bridge_base=shape.bridge_base * bridge, bridge_ridge=shape.bridge_ridge * bridge,
                   bridge_depth=max(0.0005, shape.bridge_depth + BRIDGE_HEIGHT * _amount(adjust, "nariz_ponte_altura")),
                   nostril_width=shape.nostril_width * base, wing_width=shape.wing_width * base,
                   wing_height=shape.wing_height * (1.0 + BASE_HEIGHT * tall),
                   wing_lift=shape.wing_lift + WING_LIFT * _amount(adjust, "nariz_narinas_altura"),
                   under=max(0.001, shape.under * (1.0 + BASE_HEIGHT * tall)),
                   flare=min(max(shape.flare - 0.3 * tall, 0.05), 0.85))


def tip_colours(rows: np.ndarray, adjust: Optional[Mapping[str, float]]) -> np.ndarray:
    """Cor (N, 3) de cada vértice do nariz: a pele como está na ponte e, na ponta e nas asas, mais
    rosada (ajuste positivo) ou mais escura (negativo). Multiplica a textura."""
    much = _amount(adjust, "nariz_ponta_cor")
    y = np.asarray(rows[:, 1], dtype=np.float64)
    down = (y.max() - y) / max(float(np.ptp(y)), 1e-9)
    t = np.clip((down - 0.50) / 0.40, 0.0, 1.0)
    weight = (t * t * (3 - 2 * t))[:, None] * abs(much)
    return 1.0 + weight * (np.array(TIP_PINK if much > 0 else TIP_DARK) - 1.0)


BLOCK_FRONT = 0.1305  # a vertex of the block further out than this is on its front, not on the face


def _block(adjust: Optional[Mapping[str, float]]) -> np.ndarray:
    """The old block nose with the adjustments of its parts: the block has two levels, the tip
    box and the top of the bridge. The front of the tip takes the width of the tip, its back
    (on the face) the width of the base, the top the width and the height of the bridge, and the
    tip box grows taller with the height of the base."""
    rows = ROWS.copy()
    if not parametric(adjust):
        return rows
    tip, bridge = 1.0 + PART_WIDTH * _amount(adjust, "nariz_ponta_largura"), 1.0 + PART_WIDTH * _amount(adjust, "nariz_ponte_largura")
    base, tall = 1.0 + PART_WIDTH * _amount(adjust, "nariz_base_largura"), _amount(adjust, "nariz_base_altura")
    centre = (ROWS[:, 0].min() + ROWS[:, 0].max()) / 2
    lower, front = ROWS[:, 1] < (ROWS[:, 1].min() + ROWS[:, 1].max()) / 2, ROWS[:, 2] > BLOCK_FRONT
    rows[:, 0] = centre + (ROWS[:, 0] - centre) * np.where(lower, np.where(front, tip, base), bridge)
    rows[lower, 1] = NOSE_BOTTOM + (ROWS[lower, 1] - NOSE_BOTTOM) * (1.0 + BASE_HEIGHT * tall)
    out = lower & front  # the front of the tip box, and the foot of the bridge on it
    rows[out, 2] = np.maximum(ROWS[out, 2] + TIP_REACH * _amount(adjust, "nariz_ponta_projecao"), FACE_FRONT + 0.003)
    top = ~lower & front
    rows[top, 2] = np.maximum(ROWS[top, 2] + BRIDGE_HEIGHT * _amount(adjust, "nariz_ponte_altura"), FACE_FRONT + 0.0005)
    return rows


def _block_wings(block: np.ndarray, adjust: Optional[Mapping[str, float]] = None) -> np.ndarray:
    """Rows (N, 8), three to a triangle, of the wings of the nostrils beside the tip of the block
    nose given: the blocks of the "batata" nose, against the sides of the tip, with the width and
    the height of the base and the place of the nostrils."""
    wing = NOSE_STYLES["batata"]
    tip = block[block[:, 1] < (block[:, 1].min() + block[:, 1].max()) / 2]
    low, high = float(tip[:, 0].min()), float(tip[:, 0].max())
    width = wing.wing_width * (1.0 + PART_WIDTH * _amount(adjust, "nariz_base_largura"))
    y0 = NOSE_BOTTOM + WING_LIFT * _amount(adjust, "nariz_narinas_altura")
    y1, back = y0 + wing.wing_height * (1.0 + BASE_HEIGHT * _amount(adjust, "nariz_base_altura")), FACE_FRONT - EMBED
    z0, z1 = FACE_FRONT + wing.wing_depth, FACE_FRONT + wing.wing_depth * 0.7
    rows = []
    for side, edge in ((-1.0, low), (1.0, high)):
        x0, x1 = edge - side * 0.001, edge + side * width
        centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (back + z0) / 2])
        for corners in (([x0, y0, z0], [x1, y0, z1], [x1, y1, z1], [x0, y1, z0]),        # front
                        ([x1, y0, back], [x1, y0, z1], [x1, y1, z1], [x1, y1, back]),    # outer side
                        ([x0, y1, back], [x0, y1, z0], [x1, y1, z1], [x1, y1, back]),    # top
                        ([x0, y0, back], [x1, y0, back], [x1, y0, z1], [x0, y0, z0])):   # underside
            for trio in ((0, 1, 2), (0, 2, 3)):
                p = np.array([corners[k] for k in trio], dtype=np.float64)
                normal = np.cross(p[1] - p[0], p[2] - p[0])
                normal /= max(np.linalg.norm(normal), 1e-12)
                if normal @ (p.mean(0) - centre) < 0:  # facing out of the wing
                    p, normal = p[::-1], -normal
                for point in p:
                    rows.append([*point, *normal, UV_CENTRE[0] + UV_SPAN[0] * point[0], UV_CENTRE[1] + UV_SPAN[1]])
    return np.array(rows)


def model_rows(style: str = "padrao", adjust: Optional[Mapping[str, float]] = None):
    """(rows of 8 floats, triangles) of the nose of a style where the old head had it (HEAD_BOTTOM,
    FACE_FRONT), with the adjustments of its parts. An unknown style is the default one."""
    if style == BLOCK:
        return _block(adjust), TRIANGLES.copy()
    if style == BLOCK_WINGS:
        block = _block(adjust)
        wings = _block_wings(block, adjust)
        extra = np.arange(len(wings), dtype=np.uint32).reshape(-1, 3) + len(block)
        return np.concatenate([block, wings]), np.concatenate([TRIANGLES, extra])
    rows8 = build(adjusted(NOSE_STYLES.get(style, BASE), adjust))
    rows8[:, 1] += NOSE_BOTTOM   # where the old nose ended, above the mouth
    rows8[:, 2] += FACE_FRONT - EMBED
    return rows8, np.arange(len(rows8), dtype=np.uint32).reshape(-1, 3)


def styled_rows(head_rows: np.ndarray, style: str = "padrao", adjust: Optional[Mapping[str, float]] = None,
                plain: bool = False):
    """(vertex rows, triangles) of the nose of a style on a head, with the adjustments of its parts.
    ``plain``: the whole nose in the colour of one clear point of the skin (PLAIN_UV)."""
    rows8, triangles = model_rows(style, adjust)
    if plain:
        rows8[:, 6:8] = PLAIN_UV
    return _place(rows8, head_rows), triangles


def face_pixels(points: np.ndarray) -> np.ndarray:
    """Where points of the nose (on the old head) are on the 512 px head atlas, seen from the front."""
    points = np.asarray(points, dtype=np.float64)
    middle, across, top, height, down = FACE_PIXELS
    return np.stack([middle + across * points[..., 0], top + down * (HEAD_BOTTOM + height - points[..., 1])], axis=-1)
