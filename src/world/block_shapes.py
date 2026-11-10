"""Formas dos blocos que não são cubos inteiros (laje, degrau, cerca, alçapão...), sem OpenGL.

Cada bloco do Minecraft (``minecraft:oak_stairs[facing=east,half=bottom,shape=straight]``) vira uma
lista de caixas, no estilo dos modelos de caixas do jogo: coordenadas de 0 a 16 dentro da célula, x para
leste, y para cima, z para o sul. ``shape_for`` devolve ``None`` para o cubo inteiro, que é o caso comum e
segue pelo caminho rápido do malhador.

A textura de cada face vem do atlas pelo nome do bloco; a UV acompanha o recorte da caixa, como no jogo
(uma laje mostra só a metade de baixo da textura nas laterais).
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

Vec = Tuple[float, float, float]
UvLookup = Callable[[str, str], Tuple[float, float, float, float]]

# Cada face: deslocamento do vizinho, normal, grupo de textura e os 4 cantos (sinal -1/+1 por eixo, vistos
# de fora no sentido anti-horário). É a mesma tabela do malhador das construções.
FACES = (
    ((0, 1, 0), (0.0, 1.0, 0.0), "top", ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1))),
    ((0, -1, 0), (0.0, -1.0, 0.0), "bottom", ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    ((0, 0, 1), (0.0, 0.0, 1.0), "north", ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
    ((1, 0, 0), (1.0, 0.0, 0.0), "east", ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1))),
    ((0, 0, -1), (0.0, 0.0, -1.0), "south", ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1))),
    ((-1, 0, 0), (-1.0, 0.0, 0.0), "west", ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
)
FACE_INDEX = {key: i for i, (_, _, key, _) in enumerate(FACES)}


@dataclass(frozen=True)
class Box:
    """Uma caixa da forma, em unidades de 1/16 de bloco dentro da célula.

    ``texture`` troca a textura do bloco por outra, pelo nome (ex.: a metade de cima de uma porta).
    """

    lo: Vec
    hi: Vec
    texture: Optional[str] = None

    def covers_face(self, face: int) -> bool:
        """A face encosta no limite da célula e a preenche por inteiro (então pode ser descartada)."""
        axis = face_axis(face)
        wall = 16.0 if FACES[face][1][axis] > 0 else 0.0
        edge = self.hi[axis] if wall else self.lo[axis]
        if edge != wall:
            return False
        others = [a for a in range(3) if a != axis]
        return all(self.lo[a] == 0.0 and self.hi[a] == 16.0 for a in others)


def face_axis(face: int) -> int:
    normal = FACES[face][1]
    return next(i for i, v in enumerate(normal) if v != 0.0)


# ---------------------------------------------------------------------------------------- geometria
def _box(x0, y0, z0, x1, y1, z1, texture: Optional[str] = None) -> Box:
    return Box((float(x0), float(y0), float(z0)), (float(x1), float(y1), float(z1)), texture)


def _turn(box: Box, turns: int) -> Box:
    """Gira a caixa ``turns`` quartos de volta no sentido horário visto de cima (leste vira sul)."""
    lo, hi = box.lo, box.hi
    for _ in range(turns % 4):
        (x0, z0), (x1, z1) = (lo[0], lo[2]), (hi[0], hi[2])
        # (x, z) -> (16 - z, x)
        nx0, nx1 = 16.0 - z1, 16.0 - z0
        nz0, nz1 = x0, x1
        lo, hi = (nx0, lo[1], nz0), (nx1, hi[1], nz1)
    return Box(lo, hi, box.texture)


def _flip(box: Box) -> Box:
    """Espelha a caixa no eixo y (de baixo para cima)."""
    return Box((box.lo[0], 16.0 - box.hi[1], box.lo[2]), (box.hi[0], 16.0 - box.lo[1], box.hi[2]), box.texture)


TURNS_FROM_EAST = {"east": 0, "south": 1, "west": 2, "north": 3}
TURNS_FROM_NORTH = {"north": 0, "east": 1, "south": 2, "west": 3}


def parse_block(name: str) -> Tuple[str, Dict[str, str]]:
    """'minecraft:oak_stairs[facing=east,half=top]' -> ('oak_stairs', {'facing': 'east', 'half': 'top'})."""
    base = name.split("[")[0].strip()
    if ":" in base:
        base = base.split(":", 1)[1]
    props: Dict[str, str] = {}
    match = re.search(r"\[(.*)\]", name)
    if match:
        for pair in match.group(1).split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                props[key.strip()] = value.strip()
    return base.lower(), props


# ---------------------------------------------------------------------------------------- formas
def _slab(props) -> Optional[List[Box]]:
    kind = props.get("type", "bottom")
    if kind == "double":
        return None
    return [_box(0, 0, 0, 16, 8, 16) if kind == "bottom" else _box(0, 8, 0, 16, 16, 16)]


def _stairs(props) -> List[Box]:
    """Modelo base voltado para leste (a parte alta no lado leste), girado para o ``facing``."""
    shape = props.get("shape", "straight")
    base = _box(0, 0, 0, 16, 8, 16)
    step = _box(8, 8, 0, 16, 16, 16)
    quarter = _box(8, 8, 8, 16, 16, 16)          # o canto sudeste
    inner_extra = _box(0, 8, 8, 8, 16, 16)       # o canto sudoeste, que completa o L
    boxes = {
        "straight": [base, step],
        "outer_right": [base, quarter],
        "outer_left": [base, _turn(quarter, 3)],
        "inner_right": [base, step, inner_extra],
        "inner_left": [_turn(b, 3) for b in (base, step, inner_extra)],
    }.get(shape, [base, step])
    turns = TURNS_FROM_EAST.get(props.get("facing", "east"), 0)
    boxes = [_turn(b, turns) for b in boxes]
    if props.get("half", "bottom") == "top":
        boxes = [_flip(b) for b in boxes]
    return boxes


def _trapdoor(props) -> List[Box]:
    if props.get("open", "false") == "true":
        panel = _box(0, 0, 13, 16, 16, 16)  # com facing=north fica no lado sul
        return [_turn(panel, TURNS_FROM_NORTH.get(props.get("facing", "north"), 0))]
    return [_box(0, 0, 0, 16, 3, 16) if props.get("half", "bottom") == "bottom" else _box(0, 13, 0, 16, 16, 16)]


def _fence(props) -> List[Box]:
    boxes = [_box(6, 0, 6, 10, 16, 10)]
    arms = {
        "east": [_box(10, 6, 7, 16, 9, 9), _box(10, 12, 7, 16, 15, 9)],
        "north": [_box(7, 6, 0, 9, 9, 6), _box(7, 12, 0, 9, 15, 6)],
        "south": [_box(7, 6, 10, 9, 9, 16), _box(7, 12, 10, 9, 15, 16)],
        "west": [_box(0, 6, 7, 6, 9, 9), _box(0, 12, 7, 6, 15, 9)],
    }
    for side, parts in arms.items():
        if props.get(side) == "true":
            boxes += parts
    return boxes


def _fence_gate(props) -> List[Box]:
    boxes = [_box(0, 5, 6, 2, 16, 10), _box(14, 5, 6, 16, 16, 10)]
    if props.get("open", "false") != "true":
        boxes += [_box(2, 6, 7, 14, 9, 9), _box(2, 12, 7, 14, 15, 9)]
    turn = 1 if props.get("facing", "north") in ("east", "west") else 0
    return [_turn(b, turn) for b in boxes]


def _wall(props) -> List[Box]:
    boxes = []
    if props.get("up", "true") != "false":
        boxes.append(_box(4, 0, 4, 12, 16, 12))
    sides = {
        "north": lambda h: _box(5, 0, 0, 11, h, 8),
        "east": lambda h: _box(8, 0, 5, 16, h, 11),
        "south": lambda h: _box(5, 0, 8, 11, h, 16),
        "west": lambda h: _box(0, 0, 5, 8, h, 11),
    }
    for side, make in sides.items():
        height = {"low": 14, "tall": 16, "true": 14}.get(props.get(side, "none"))
        if height:
            boxes.append(make(height))
    return boxes or [_box(4, 0, 4, 12, 16, 12)]


def _bars(props) -> List[Box]:
    boxes = [_box(7, 0, 7, 9, 16, 9)]
    arms = {"north": (7, 0, 0, 9, 16, 7), "south": (7, 0, 9, 9, 16, 16),
            "east": (9, 0, 7, 16, 16, 9), "west": (0, 0, 7, 7, 16, 9)}
    for side, dims in arms.items():
        if props.get(side) == "true":
            boxes.append(_box(*dims))
    return boxes


def _wall_sign(props) -> List[Box]:
    plate = _box(0, 4.5, 14, 16, 12.5, 16)  # com facing=north a placa fica no lado sul
    return [_turn(plate, TURNS_FROM_NORTH.get(props.get("facing", "north"), 0))]


def _button(props) -> List[Box]:
    depth = 1 if props.get("powered", "false") == "true" else 2
    face = props.get("face", "wall")
    facing = props.get("facing", "north")
    if face == "wall":
        plate = _box(5, 6, 16 - depth, 11, 10, 16)  # com facing=north fica no lado sul
        return [_turn(plate, TURNS_FROM_NORTH.get(facing, 0))]
    turn = 1 if facing in ("east", "west") else 0
    floor = _turn(_box(5, 0, 6, 11, depth, 10), turn)
    return [_flip(floor) if face == "ceiling" else floor]


def _pressure_plate(base: str, props) -> List[Box]:
    top = 0.5 if props.get("powered", "false") == "true" or props.get("power", "0") != "0" else 1
    # as placas pesadas e leves são feitas de ferro e de ouro
    texture = {"heavy_weighted_pressure_plate": "iron_block", "light_weighted_pressure_plate": "gold_block"}.get(base)
    return [_box(1, 0, 1, 15, top, 15, texture)]


def _torch(props) -> List[Box]:
    return [_box(7, 0, 7, 9, 10, 9)]


def _wall_torch(props) -> List[Box]:
    standing = _box(7, 3.5, 0, 9, 13.5, 2)  # encostada no lado norte; gira para os outros lados
    towards = {"south": 0, "west": 1, "north": 2, "east": 3}  # facing é o lado para onde a tocha aponta
    return [_turn(standing, towards.get(props.get("facing", "south"), 0))]


def _lantern(props) -> List[Box]:
    lift = 1 if props.get("hanging", "false") == "true" else 0
    return [_box(5, lift, 5, 11, 7 + lift, 11), _box(6, 7 + lift, 6, 10, 9 + lift, 10)]


def _chain(props) -> List[Box]:
    axis = props.get("axis", "y")
    return [{"y": _box(6.5, 0, 6.5, 9.5, 16, 9.5), "x": _box(0, 6.5, 6.5, 16, 9.5, 9.5),
             "z": _box(6.5, 6.5, 0, 9.5, 9.5, 16)}.get(axis, _box(6.5, 0, 6.5, 9.5, 16, 9.5))]


def _candle(props) -> List[Box]:
    return [_box(7, 0, 7, 9, 6, 9)]


def _carpet(base: str, props) -> List[Box]:
    # o tapete usa a textura da lã da mesma cor (o de musgo, a do bloco de musgo)
    material = "moss_block" if base == "moss_carpet" else base[: -len("_carpet")] + "_wool"
    return [_box(0, 0, 0, 16, 1, 16, material)]


def _pot(props) -> List[Box]:
    return [_box(5, 0, 5, 11, 6, 11, "flower_pot")]


def _decorated_pot(props) -> List[Box]:
    return [_box(1, 0, 1, 15, 16, 15, "terracotta")]


def _anvil(props) -> List[Box]:
    """Base, cintura, pescoço e topo; o topo corre ao longo do eixo da bigorna (norte-sul para facing leste/oeste)."""
    boxes = [_box(2, 0, 2, 14, 4, 14), _box(4, 4, 3, 12, 5, 13), _box(6, 5, 4, 10, 10, 12), _box(3, 10, 0, 13, 16, 16)]
    turn = 1 if props.get("facing", "north") in ("north", "south") else 0
    return [_turn(b, turn) for b in boxes]


def _cake(props) -> List[Box]:
    bites = int(props.get("bites", "0") or 0)
    return [_box(1 + 2 * bites, 0, 1, 15, 8, 15)]


def _ladder(props) -> List[Box]:
    plate = _box(0, 0, 14, 16, 16, 16)  # com facing=north fica no lado sul
    return [_turn(plate, TURNS_FROM_NORTH.get(props.get("facing", "north"), 0))]


def _door(base: str, props) -> List[Box]:
    """Painel de 3/16; fechado fica no lado oposto ao ``facing``; aberto gira 90° para o lado da dobradiça."""
    panel = _box(0, 0, 0, 3, 16, 16)  # com facing=east fecha no lado oeste
    facing = TURNS_FROM_EAST.get(props.get("facing", "east"), 0)
    if props.get("open", "false") == "true":
        facing += 1 if props.get("hinge", "left") == "left" else 3
    texture = f"{base}_top" if props.get("half", "lower") == "upper" else f"{base}_bottom"
    boxed = _turn(panel, facing)
    return [Box(boxed.lo, boxed.hi, texture)]


# (teste do nome, construtor). A ordem importa: os mais específicos primeiro.
_RULES: List[Tuple[Callable[[str], bool], Callable]] = [
    (lambda b: b.endswith("_slab"), _slab),
    (lambda b: b.endswith("_stairs"), _stairs),
    (lambda b: b.endswith("_trapdoor"), _trapdoor),
    (lambda b: b.endswith("_fence_gate"), _fence_gate),
    (lambda b: b.endswith("_fence"), _fence),
    (lambda b: b.endswith("_wall_sign"), _wall_sign),
    (lambda b: b.endswith("_wall") and not b.endswith(("_wall_sign", "_wall_torch")), _wall),
    (lambda b: b == "iron_bars" or b.endswith("_pane"), _bars),
    (lambda b: b.endswith("_button"), _button),
    (lambda b: b.endswith("_pressure_plate"), None),  # recebe o nome do bloco (ver shape_for)
    (lambda b: b.endswith("wall_torch"), _wall_torch),
    (lambda b: b.endswith("torch"), _torch),
    (lambda b: b.endswith("lantern"), _lantern),
    (lambda b: b == "chain", _chain),
    (lambda b: b == "candle" or (b.endswith("_candle") and not b.endswith("_candle_cake")), _candle),
    (lambda b: b.endswith("_carpet"), None),  # recebe o nome do bloco (ver shape_for)
    (lambda b: b.startswith("potted_") or b == "flower_pot", _pot),
    (lambda b: b == "decorated_pot", _decorated_pot),
    (lambda b: b == "anvil" or b in ("chipped_anvil", "damaged_anvil"), _anvil),
    (lambda b: b == "cake", _cake),
    (lambda b: b == "ladder", _ladder),
]


@lru_cache(maxsize=4096)
def shape_for(block_name: str) -> Optional[Tuple[Box, ...]]:
    """As caixas do bloco, ou ``None`` se é um cubo inteiro."""
    base, props = parse_block(block_name)
    if base.endswith("_door") and not base.endswith("trapdoor"):
        return tuple(_door(base, props))
    for matches, build in _RULES:
        if matches(base):
            if build is None:  # as que dependem do nome do bloco
                build = (lambda pr: _carpet(base, pr)) if base.endswith("_carpet") else (lambda pr: _pressure_plate(base, pr))
            boxes = build(props)
            return tuple(boxes) if boxes else None
    return None


def is_full_cube(block_name: str) -> bool:
    return shape_for(block_name) is None


# Blocos que enfeitam o espaço sem barrar quem passa (nem selar um cômodo)
_DECORATION_SUFFIXES = ("_button", "_pressure_plate", "_wall_sign", "_sign", "_carpet", "torch", "lantern", "_candle")
_DECORATION_NAMES = ("chain", "ladder", "candle", "flower_pot")


def collides(block_name: str) -> bool:
    """O personagem não atravessa o bloco (tochas, tapetes, placas, botões, velas, vasos... não barram)."""
    base, _ = parse_block(block_name)
    if base.startswith("potted_") or base in _DECORATION_NAMES or base.endswith(_DECORATION_SUFFIXES):
        return False
    return True


# ---------------------------------------------------------------------------------------- malha
def _uv(face_key: str, point: Vec) -> Tuple[float, float]:
    """UV (0 a 1, dentro do ladrilho) de um ponto 0..16 da face, no mesmo sentido do malhador de cubos."""
    x, y, z = (c / 16.0 for c in point)
    if face_key in ("top", "bottom"):
        return x, z
    v = 1.0 - y
    if face_key == "north":
        return x, v
    if face_key == "east":
        return 1.0 - z, v
    if face_key == "south":
        return 1.0 - x, v
    return z, v  # west


def box_face_quad(box: Box, face: int, cell_corner: np.ndarray, rect: Tuple[float, float, float, float]) -> np.ndarray:
    """Os 4 vértices (4, 11) da face ``face`` da caixa, com posição, normal, UV e cor.

    Args:
        box: a caixa, em unidades de 1/16 dentro da célula.
        face: índice em ``FACES``.
        cell_corner: o canto mínimo da célula no espaço da malha.
        rect: (u0, v0, u1, v1) da textura no atlas.
    """
    _, normal, key, corners = FACES[face]
    u0, v0, u1, v1 = rect
    quad = np.empty((4, 11), dtype=np.float32)
    for i, corner in enumerate(corners):
        point = tuple(box.hi[a] if corner[a] > 0 else box.lo[a] for a in range(3))
        u, v = _uv(key, point)
        quad[i, :3] = cell_corner + np.array(point, dtype=np.float32) / 16.0
        quad[i, 3:6] = normal
        quad[i, 6] = u0 + u * (u1 - u0)
        quad[i, 7] = v0 + v * (v1 - v0)
        quad[i, 8:11] = 1.0
    return quad
