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
from typing import Dict

SECTIONS = 6          # cortes ao longo do dorso, da ponte à ponta
EMBED = 0.003         # metres the base goes into the face (no gap on a rounded head)
HUMP = 0.005          # metres a fully curved bridge rises (or sinks) at its middle
TIP_LIFT = 0.006      # metres a fully upturned tip rises
NOSE_BOTTOM = float(ROWS[:, 1].min())  # under the tip, on the old head: every shape ends here, above the mouth
UV_CENTRE, UV_SPAN = (0.2455, 0.379), (1.2, 0.0275)  # the patch of the head atlas the old nose used


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
}
BLOCK = "bloco"  # the old mesh itself, as it was
STYLE_NAMES = tuple(NOSE_STYLES) + (BLOCK,)


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
        base = shape.bridge_base + (shape.nostril_width - shape.bridge_base) * _smooth(0.45, 1.0, t)
        ridge = shape.bridge_ridge + (shape.tip_width - shape.bridge_ridge) * _smooth(0.3, 1.0, t)
        sections.append(([-base / 2, y, 0.0], [-ridge / 2, y, depth], [ridge / 2, y, depth], [base / 2, y, 0.0], t))
    quads = []  # (four corners, t of each)
    first, last = sections[0], sections[-1]
    quads.append(((first[0], first[1], first[2], first[3]), (0.0,) * 4))                      # top of the bridge
    for a, b in zip(sections, sections[1:]):
        for i in range(3):                                                                    # left wall, ridge, right wall
            quads.append(((a[i], b[i], b[i + 1], a[i + 1]), (a[4], b[4], b[4], a[4])))
    left, right = [-shape.nostril_width / 2, 0.0, 0.0], [shape.nostril_width / 2, 0.0, 0.0]   # under the tip, on the face
    quads.append(((last[1], left, right, last[2]), (1.0,) * 4))                               # underside of the tip
    triangles = []
    for corners, ts in quads:
        triangles += [((corners[0], corners[1], corners[2]), (ts[0], ts[1], ts[2])),
                      ((corners[0], corners[2], corners[3]), (ts[0], ts[2], ts[3]))]
    triangles += [((last[0], last[1], left), (1.0,) * 3), ((last[3], right, last[2]), (1.0,) * 3)]  # sides of the nostrils
    inside = np.array([0.0, shape.under + shape.length / 2, 0.0])
    rows = np.zeros((len(triangles) * 3, 8))
    for k, (corners, ts) in enumerate(triangles):
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


def styled_rows(head_rows: np.ndarray, style: str = "padrao"):
    """(vertex rows, triangles) of the nose of a style on a head. An unknown style is the default one."""
    if style == BLOCK:
        return _place(ROWS, head_rows), TRIANGLES.copy()
    rows8 = build(NOSE_STYLES.get(style, BASE))
    rows8[:, 1] += NOSE_BOTTOM   # where the old nose ended, above the mouth
    rows8[:, 2] += FACE_FRONT - EMBED
    rows = _place(rows8, head_rows)
    return rows, np.arange(len(rows), dtype=np.uint32).reshape(-1, 3)
