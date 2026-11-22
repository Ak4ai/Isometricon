"""Formas dos blocos que não são cubos inteiros (laje, degrau, cerca, alçapão...), sem OpenGL.

Cada bloco do Minecraft (``minecraft:oak_stairs[facing=east,half=bottom,shape=straight]``) vira uma
lista de caixas, no estilo dos modelos de caixas do jogo: coordenadas de 0 a 16 dentro da célula, x para
leste, y para cima, z para o sul. ``shape_for`` devolve ``None`` para o cubo inteiro, que é o caso comum e
segue pelo caminho rápido do malhador.

A textura de cada face vem do atlas pelo nome do bloco; a UV acompanha o recorte da caixa, como no jogo
(uma laje mostra só a metade de baixo da textura nas laterais).
"""

import os
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
    ``face_uv`` tira a UV de uma região fixa da textura, em pixels (x0, y0, x1, y1) de 0 a 16, por face ("top",
    "bottom" ou "side"), em vez de recortar pela posição da caixa: as texturas que são folhas de modelo (a
    lanterna) têm cada peça num canto da imagem.
    """

    lo: Vec
    hi: Vec
    texture: Optional[str] = None
    face_uv: Optional[Tuple[Tuple[str, Tuple[float, float, float, float]], ...]] = None

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


Rgb = Tuple[float, float, float]
# A tinta da folhagem: a mesma do topo da grama do terreno (as texturas de capim e samambaia vêm em cinza)
GRASS_TINT: Rgb = (0.38, 0.76, 0.24)
DRY_TINT: Rgb = (0.66, 0.52, 0.30)   # folhas secas no chão (leaf_litter, também cinza)

# UV dos cantos de um plano em pé, na ordem baixo-esquerda, baixo-direita, cima-direita, cima-esquerda
# (v = 0 no alto da textura, como nas faces das caixas).
_PLANE_UV = ((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0))


@dataclass(frozen=True)
class Quad:
    """Um plano sem espessura (planta em cruz, trilho, cipó), visto dos dois lados.

    ``corners`` em 1/16 de bloco dentro da célula, no sentido anti-horário visto da frente; ``uvs`` (0 a 1, v = 0 no
    alto) de cada canto. ``tint`` multiplica a cor (folhagem cinza ganha verde).
    """

    corners: Tuple[Vec, Vec, Vec, Vec]
    texture: Optional[str] = None
    uvs: Tuple[Tuple[float, float], ...] = _PLANE_UV
    tint: Optional[Rgb] = None

    def covers_face(self, face: int) -> bool:
        return False  # um plano nunca fecha a face da célula: não esconde o vizinho nem ganha tampa

    @property
    def lo(self) -> Vec:
        """O canto mínimo da caixa que contém o plano (como ``Box.lo``)."""
        return tuple(min(c[a] for c in self.corners) for a in range(3))

    @property
    def hi(self) -> Vec:
        return tuple(max(c[a] for c in self.corners) for a in range(3))


def _quad_turn(quad: Quad, turns: int) -> Quad:
    """Gira o plano ``turns`` quartos de volta no sentido horário visto de cima (como ``_turn``)."""
    corners = quad.corners
    for _ in range(turns % 4):
        corners = tuple((16.0 - z, y, x) for x, y, z in corners)
    return Quad(tuple(tuple(float(c) for c in p) for p in corners), quad.texture, quad.uvs, quad.tint)


def quad_vertices(quad: Quad, cell_corner: np.ndarray, rect: Tuple[float, float, float, float],
                  color: Rgb = (1.0, 1.0, 1.0)) -> np.ndarray:
    """Os 8 vértices (8, 11) do plano: a frente (4) e as costas (4, na ordem inversa e com a normal oposta).

    Os dois lados saem como quads separados (índices 0-1-2 2-3-0 de cada grupo de 4), porque o OpenGL descarta a
    face de trás.
    """
    u0, v0, u1, v1 = rect
    points = np.asarray(quad.corners, dtype=np.float32) / 16.0
    normal = np.cross(points[1] - points[0], points[2] - points[0])
    length = float(np.linalg.norm(normal))
    normal = normal / length if length > 1e-9 else np.array([0.0, 1.0, 0.0], dtype=np.float32)
    tint = np.asarray(quad.tint or (1.0, 1.0, 1.0), dtype=np.float32) * np.asarray(color, dtype=np.float32)
    out = np.empty((8, 11), dtype=np.float32)
    for side, order, sign in ((0, (0, 1, 2, 3), 1.0), (1, (1, 0, 3, 2), -1.0)):
        for i, k in enumerate(order):
            row = out[side * 4 + i]
            row[:3] = cell_corner + points[k]
            row[3:6] = normal * sign
            u, v = quad.uvs[k]
            row[6] = u0 + u * (u1 - u0)
            row[7] = v0 + v * (v1 - v0)
            row[8:11] = tint
    return out


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
    return Box(lo, hi, box.texture, box.face_uv)


def _flip(box: Box) -> Box:
    """Espelha a caixa no eixo y (de baixo para cima)."""
    return Box((box.lo[0], 16.0 - box.hi[1], box.lo[2]), (box.hi[0], 16.0 - box.lo[1], box.hi[2]), box.texture,
               box.face_uv)


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


# A textura da lanterna é uma folha de modelo (como no jogo): o corpo de lado em (0,2)-(6,9), o topo e o fundo em
# (0,9)-(6,15), o pescoço de lado em (1,0)-(5,2) e a alça (um arco de 3x3) em (11,1)-(14,4).
_LANTERN_BODY_UV = (("side", (0.0, 2.0, 6.0, 9.0)), ("top", (0.0, 9.0, 6.0, 15.0)), ("bottom", (0.0, 9.0, 6.0, 15.0)))
_LANTERN_NECK_UV = (("side", (1.0, 0.0, 5.0, 2.0)), ("top", (1.0, 10.0, 5.0, 14.0)), ("bottom", (1.0, 10.0, 5.0, 14.0)))
_LANTERN_HANDLE_UV = ((11 / 16, 4 / 16), (14 / 16, 4 / 16), (14 / 16, 1 / 16), (11 / 16, 1 / 16))


def _lantern(props) -> List:
    lift = 1 if props.get("hanging", "false") == "true" else 0
    body = Box((5.0, lift, 5.0), (11.0, 7.0 + lift, 11.0), None, _LANTERN_BODY_UV)
    neck = Box((6.0, 7.0 + lift, 6.0), (10.0, 9.0 + lift, 10.0), None, _LANTERN_NECK_UV)
    # a alça: dois arcos em X por cima do pescoço
    y0, y1 = 9.0 + lift, 12.0 + lift
    a, b = 8.0 - 1.06, 8.0 + 1.06       # 3 pixels de largura na diagonal
    handle = [Quad(((a, y0, a), (b, y0, b), (b, y1, b), (a, y1, a)), None, _LANTERN_HANDLE_UV),
              Quad(((a, y0, b), (b, y0, a), (b, y1, a), (a, y1, b)), None, _LANTERN_HANDLE_UV)]
    return [body, neck, *handle]


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


_OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _ladder(props) -> List[Quad]:
    """Um plano fino a 0,8/16 da parede em que a escada está presa (com facing=north, a parede do sul)."""
    gap = 0.8
    wall = Quad(((16.0, 0.0, gap), (0.0, 0.0, gap), (0.0, 16.0, gap), (16.0, 16.0, gap)), "ladder")  # lado norte
    side = _OPPOSITE.get(props.get("facing", "north"), "south")
    return [_quad_turn(wall, TURNS_FROM_NORTH[side])]


def _door(base: str, props) -> List[Box]:
    """Painel de 3/16; fechado fica no lado oposto ao ``facing``; aberto gira 90° para o lado da dobradiça."""
    panel = _box(0, 0, 0, 3, 16, 16)  # com facing=east fecha no lado oeste
    facing = TURNS_FROM_EAST.get(props.get("facing", "east"), 0)
    if props.get("open", "false") == "true":
        facing += 1 if props.get("hinge", "left") == "left" else 3
    texture = f"{base}_top" if props.get("half", "lower") == "upper" else f"{base}_bottom"
    boxed = _turn(panel, facing)
    return [Box(boxed.lo, boxed.hi, texture)]


def _cross(texture: str, tint: Optional[Rgb] = None, height: float = 16.0) -> List[Quad]:
    """Dois planos em X na diagonal da célula, como as plantas do Minecraft (de 0,8 a 15,2)."""
    a, b = 0.8, 15.2
    return [
        Quad(((a, 0.0, a), (b, 0.0, b), (b, height, b), (a, height, a)), texture, tint=tint),
        Quad(((a, 0.0, b), (b, 0.0, a), (b, height, a), (a, height, b)), texture, tint=tint),
    ]


def _flat(texture: str, height: float = 0.25, tint: Optional[Rgb] = None, turns: int = 0) -> Quad:
    """Um plano deitado a ``height``/16 do chão (trilho, vitória-régia, pétalas), virado para cima."""
    uvs = ((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0))  # u = x, v = z, como o topo das caixas
    quad = Quad(((0.0, height, 16.0), (16.0, height, 16.0), (16.0, height, 0.0), (0.0, height, 0.0)),
                texture, uvs, tint)
    return _quad_turn(quad, turns)


# Plantas altas de dois blocos: a metade de cima e a de baixo têm texturas próprias
_DOUBLE_PLANTS = ("tall_grass", "large_fern", "lilac", "rose_bush", "peony", "sunflower", "tall_seagrass")
_TINTED_PLANTS = ("short_grass", "grass", "fern", "tall_grass", "large_fern", "bush")
_CROSS_NAMES = frozenset({
    "short_grass", "grass", "fern", "dead_bush", "bush", "firefly_bush", "short_dry_grass", "tall_dry_grass",
    "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower", "lily_of_the_valley",
    "wither_rose", "torchflower", "open_eyeblossom", "closed_eyeblossom", "cactus_flower",
    "brown_mushroom", "red_mushroom", "nether_sprouts", "cobweb", "sugar_cane",
    "kelp", "kelp_plant", "seagrass", "hanging_roots", "weeping_vines", "weeping_vines_plant",
    "twisting_vines", "twisting_vines_plant", "cave_vines", "cave_vines_plant",
    "wheat", "carrots", "potatoes", "beetroots", "nether_wart", "sweet_berry_bush", "torchflower_crop",
    "fire", "soul_fire", *_DOUBLE_PLANTS,
})
_CROSS_SUFFIXES = ("_sapling", "_tulip", "_fungus", "_coral", "_coral_fan")
# Estágio de crescimento (age) -> número da textura, nas plantações que têm menos texturas que estágios
_CROP_STAGES = {
    "wheat": (0, 1, 2, 3, 4, 5, 6, 7), "carrots": (0, 0, 1, 1, 2, 2, 2, 3), "potatoes": (0, 0, 1, 1, 2, 2, 2, 3),
    "beetroots": (0, 1, 2, 3), "nether_wart": (0, 1, 1, 2), "sweet_berry_bush": (0, 1, 2, 3),
    "torchflower_crop": (0, 1, 1),
}


def is_cross_plant(base: str) -> bool:
    """O bloco (nome sem namespace nem propriedades) é desenhado como dois planos em X."""
    if base in _CROSS_NAMES:
        return True
    if base.endswith("_roots") and "mangrove" not in base:
        return True                     # raízes carmesim e distorcidas (as de mangue são um bloco)
    return base.endswith(_CROSS_SUFFIXES)


def _plant_texture(base: str, props) -> str:
    if base in _DOUBLE_PLANTS:
        return f"{base}_{'top' if props.get('half', 'lower') == 'upper' else 'bottom'}"
    if base == "grass":
        return "short_grass"            # o nome antigo do capim
    if base in _CROP_STAGES:
        stages = _CROP_STAGES[base]
        age = min(max(int(props.get("age", "0") or 0), 0), len(stages) - 1)
        return f"{base}_stage{stages[age]}"
    if base in ("cave_vines", "cave_vines_plant") and props.get("berries") == "true":
        return f"{base}_lit"
    if base in ("fire", "soul_fire"):
        return f"{base}_0"              # o primeiro quadro da animação
    return base


def _plant(base: str, props) -> List[Quad]:
    tint = GRASS_TINT if base in _TINTED_PLANTS else None
    return _cross(_plant_texture(base, props), tint)


def _rail(base: str, props) -> List[Quad]:
    """Trilho deitado a 1/16 do chão; nas rampas (ascending_*) sobe um bloco inteiro até o lado indicado."""
    shape = props.get("shape", "north_south")
    texture = base + ("_on" if base != "rail" and props.get("powered") == "true" else "")
    if shape.startswith("ascending_"):
        quad = Quad(((0.0, 1.0, 16.0), (16.0, 1.0, 16.0), (16.0, 17.0, 0.0), (0.0, 17.0, 0.0)), texture,
                    ((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)))  # sobe para o norte
        return [_quad_turn(quad, TURNS_FROM_NORTH.get(shape[len("ascending_"):], 0))]
    corners = {"south_east": 0, "south_west": 1, "north_west": 2, "north_east": 3}
    if base == "rail" and shape in corners:
        return [_flat("rail_corner", 1, turns=corners[shape])]
    return [_flat(texture, 1, turns=1 if shape == "east_west" else 0)]


def _vine(base: str, props) -> List[Quad]:
    """Cipó e líquen: um plano encostado em cada lado marcado (north=true...), a 0,8/16 da parede."""
    gap = 0.8
    wall = Quad(((16.0, 0.0, gap), (0.0, 0.0, gap), (0.0, 16.0, gap), (16.0, 16.0, gap)), base)  # no lado norte
    quads = [_quad_turn(wall, TURNS_FROM_NORTH[side]) for side in ("north", "east", "south", "west")
             if props.get(side) == "true"]
    if props.get("up") == "true":
        top = 16.0 - gap
        quads.append(Quad(((0.0, top, 0.0), (16.0, top, 0.0), (16.0, top, 16.0), (0.0, top, 16.0)), base))
    if props.get("down") == "true":
        quads.append(_flat(base, gap))
    return quads or [wall]


def _campfire(base: str, props) -> List:
    """Quatro toras cruzadas e, acesa, o fogo em cruz por cima."""
    lit = props.get("lit", "true") == "true"
    log = f"{base}_log_lit" if lit else "campfire_log"
    logs = [_box(1, 0, 0, 5, 4, 16, log), _box(11, 0, 0, 15, 4, 16, log),
            _box(0, 3, 1, 16, 7, 5, log), _box(0, 3, 11, 16, 7, 15, log)]
    turn = 1 if props.get("facing", "north") in ("east", "west") else 0
    parts: List = [_turn(b, turn) for b in logs]
    if lit:
        parts += _cross(f"{base}_fire")
    return parts


def _flat_cover(base: str, props) -> List[Quad]:
    """Coisas finas deitadas no chão: vitória-régia, pétalas, folhas secas, fio de armadilha."""
    if base == "leaf_litter":
        return [_flat(base, 0.25, DRY_TINT)]
    if base == "tripwire":
        return [_flat(base, 1.5, turns=1 if props.get("east") == "true" or props.get("west") == "true" else 0)]
    return [_flat(base, 0.25)]


def _snow(props) -> Optional[List[Box]]:
    layers = min(max(int(props.get("layers", "1") or 1), 1), 8)
    return None if layers == 8 else [_box(0, 0, 0, 16, 2 * layers, 16)]


def _end_rod(props) -> List[Box]:
    facing = props.get("facing", "up")
    if facing in ("up", "down"):
        return [_box(7, 0, 7, 9, 16, 9)]
    return [_box(0, 7, 7, 16, 9, 9) if facing in ("east", "west") else _box(7, 7, 0, 9, 9, 16)]


def _sea_pickle(props) -> List[Box]:
    count = min(max(int(props.get("pickles", "1") or 1), 1), 4)
    spots = ((6, 6), (2, 9), (9, 2), (9, 9))[:count]
    return [_box(x, 0, z, x + 4, 6, z + 4) for x, z in spots]


# Blocos inteiros com "lantern" no nome (não são a lanterna pequena)
_FULL_LANTERNS = ("sea_lantern", "jack_o_lantern")

# Baús, faixas e camas são desenhados pelo jogo como entidades (a textura fica em ``textures/entity``, que o Bare
# Bones de blocos não traz): ganham a forma e uma textura de bloco que lembra, a madeira do baú e a lã da cor.
TURNS_FROM_SOUTH = {"south": 0, "west": 1, "north": 2, "east": 3}


# Os ladrilhos do baú (``chest_<variante>_<tipo>_<peça>.png``) saem de ``textures/entity/chest`` do jogo pelo
# ``scripts/make_chest_tiles.py`` e ficam fora do git (arte da Mojang); sem eles o baú volta à caixa de tábuas.
_CHEST_TILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "assets", "textures", "blocks")


@lru_cache(maxsize=None)
def _chest_tile_exists(name: str) -> bool:
    return os.path.isfile(os.path.join(_CHEST_TILES_DIR, name + ".png"))


def _chest(base: str, props) -> List[Box]:
    kind = props.get("type", "single")
    if base == "ender_chest":
        variant, kind = "ender", "single"
    elif base == "trapped_chest":
        variant = "trapped"
    else:
        variant = "normal"
    # O baú duplo se estende para o lado do parceiro. No jogo o parceiro de uma metade "left" fica no sentido horário do
    # facing (com facing=south, a oeste) e o da "right" no anti-horário (a leste); as folhas de textura concordam: o
    # aro da "left" está na borda de leste, o da "right" na de oeste, e a junção fica sem aro.
    lo_x, hi_x = 1.0, 15.0
    if kind == "left":
        lo_x = 0.0
    elif kind == "right":
        hi_x = 16.0
    turns = TURNS_FROM_SOUTH.get(props.get("facing", "south"), 0)
    prefix = f"chest_{variant}_{kind if kind in ('left', 'right') else 'single'}_"
    if not all(_chest_tile_exists(prefix + part) for part in ("body", "lid", "top")):
        texture = "obsidian" if base == "ender_chest" else "oak_planks"
        return [_turn(_box(lo_x, 0, 1, hi_x, 14, 15, texture), turns)]
    # a arte da folha do baú: o corpo (14 de largura, 10 de altura), a tampa (14x5) e o topo (14x14); no ladrilho de
    # 16 ela fica encostada onde a caixa começa (a metade do baú duplo que encosta no parceiro vai até a borda)
    x0, x1 = lo_x, hi_x
    body_art, lid_art, top_art = (x0, 1, x1, 10), (x0, 0, x1, 5), (x0, 1, x1, 15)
    inner_art = (x0, 1, x1, 15)
    # o corpo termina um pouco antes do alto e a tampa começa um pouco depois do fundo: no vão ficam chapas finas com o
    # interior (a boca do baú e a face de baixo da tampa), que só aparecem com a tampa levantada
    boxes = [
        Box((lo_x, 0.0, 1.0), (hi_x, 8.9, 15.0), prefix + "body",
            (("side", body_art), ("top", body_art), ("bottom", body_art))),
        Box((lo_x, 9.1, 1.0), (hi_x, 13.9, 15.0), prefix + "lid",
            (("side", lid_art), ("top", lid_art), ("bottom", lid_art))),
        # o topo da tampa: uma chapa fina por cima, que leva a arte do alto (que não cabe no mesmo ladrilho das laterais)
        Box((lo_x, 13.9, 1.0), (hi_x, 14.0, 15.0), prefix + "top",
            (("side", (x0, 1, x1, 2)), ("top", top_art), ("bottom", top_art))),
    ]
    if _chest_tile_exists(prefix + "bodyin") and _chest_tile_exists(prefix + "lidin"):
        boxes.insert(1, Box((lo_x, 8.9, 1.0), (hi_x, 9.0, 15.0), prefix + "bodyin",
                            (("side", (x0, 1, x1, 2)), ("top", inner_art), ("bottom", inner_art))))
        boxes.insert(3, Box((lo_x, 9.0, 1.0), (hi_x, 9.1, 15.0), prefix + "lidin",
                            (("side", (x0, 1, x1, 2)), ("top", inner_art), ("bottom", inner_art))))
    if _chest_tile_exists(prefix + "lock"):
        if kind == "single":
            lock, art = Box((7.0, 7.0, 15.0), (9.0, 11.0, 16.0)), (1, 1, 3, 5)
        else:   # o duplo tem um fecho no meio: um pedaço de 1 em cada metade, na junção
            edge = lo_x if kind == "left" else hi_x - 1.0
            lock, art = Box((edge, 7.0, 15.0), (edge + 1.0, 11.0, 16.0)), (1, 1, 2, 5)
        boxes.append(Box(lock.lo, lock.hi, prefix + "lock",
                         (("side", art), ("top", (art[0], art[1], art[2], art[1] + 1)),
                          ("bottom", (art[0], art[1], art[2], art[1] + 1)))))
    return [_turn(box, turns) for box in boxes]


_LID_PARTS = ("lidin", "lid", "top", "lock")


def is_chest_lid(box) -> bool:
    """A caixa é uma peça da tampa do baú (a que gira ao abrir): a tampa, a chapa de cima, a de baixo e o fecho."""
    texture = getattr(box, "texture", None) or ""
    return texture.startswith("chest_") and texture.rsplit("_", 1)[-1] in _LID_PARTS


def chest_hinge(block_name: str) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """A dobradiça da tampa de um baú: (ponto em 1/16 de bloco dentro da célula, eixo). Fica na borda de trás, no
    fundo da tampa (y = 9), e o eixo corre pela largura do baú; os dois giram com o ``facing`` como a forma."""
    turns = TURNS_FROM_SOUTH.get(parse_block(block_name)[1].get("facing", "south"), 0)
    point, axis = (8.0, 9.0, 1.0), (1.0, 0.0, 0.0)
    for _ in range(turns % 4):                 # a mesma volta de ``_turn``: (x, z) -> (16 - z, x); o eixo, (x, z) -> (-z, x)
        point = (16.0 - point[2], point[1], point[0])
        axis = (-axis[2], axis[1], axis[0])
    return point, axis


def _banner(base: str, props) -> List[Box]:
    texture = base.split("_")[0] + "_wool"
    if base.endswith("_wall_banner"):
        plate = _box(1, 0, 15, 15, 16, 16, texture)  # com facing=north fica no lado sul
        return [_turn(plate, TURNS_FROM_NORTH.get(props.get("facing", "north"), 0))]
    return [_box(1, 0, 7.5, 15, 16, 8.5, texture)]


# (teste do nome, construtor). A ordem importa: os mais específicos primeiro.
_RULES: List[Tuple[Callable[[str], bool], Callable]] = [
    (is_cross_plant, _plant),
    (lambda b: b == "rail" or b.endswith("_rail"), _rail),
    (lambda b: b in ("vine", "glow_lichen"), _vine),
    (lambda b: b in ("campfire", "soul_campfire"), _campfire),
    (lambda b: b in ("lily_pad", "pink_petals", "wildflowers", "leaf_litter", "tripwire"), _flat_cover),
    (lambda b: b == "snow", _snow),
    (lambda b: b == "end_rod", _end_rod),
    (lambda b: b == "sea_pickle", _sea_pickle),
    (lambda b: b.endswith("_slab"), _slab),
    (lambda b: b.endswith("_stairs"), _stairs),
    (lambda b: b.endswith("_trapdoor"), _trapdoor),
    (lambda b: b.endswith("_fence_gate"), _fence_gate),
    (lambda b: b.endswith("_fence"), _fence),
    (lambda b: b.endswith("_wall_sign"), _wall_sign),
    (lambda b: b in ("chest", "trapped_chest", "ender_chest"), _chest),
    (lambda b: b.endswith("_banner"), _banner),
    (lambda b: b.endswith("_wall") and not b.endswith(("_wall_sign", "_wall_torch")), _wall),
    (lambda b: b == "iron_bars" or b.endswith("_pane"), _bars),
    (lambda b: b.endswith("_button"), _button),
    (lambda b: b.endswith("_pressure_plate"), _pressure_plate),
    (lambda b: b.endswith("wall_torch"), _wall_torch),
    (lambda b: b.endswith("torch"), _torch),
    (lambda b: b.endswith("lantern") and b not in _FULL_LANTERNS, _lantern),
    (lambda b: b == "chain", _chain),
    (lambda b: b == "candle" or (b.endswith("_candle") and not b.endswith("_candle_cake")), _candle),
    (lambda b: b.endswith("_carpet"), _carpet),
    (lambda b: b.startswith("potted_") or b == "flower_pot", _pot),
    (lambda b: b == "decorated_pot", _decorated_pot),
    (lambda b: b == "anvil" or b in ("chipped_anvil", "damaged_anvil"), _anvil),
    (lambda b: b == "cake", _cake),
    (lambda b: b == "ladder", _ladder),
]


# Blocos em que o modelo do jogo, quando existe, vale mais que a regra daqui (a regra fica de reserva): a placa de
# parede do jogo é um pouco mais fina (1,33/16) que a que eu tinha medido (2/16)
_PREFER_MODELS = ("_wall_sign",)

# Os construtores que recebem também o nome do bloco
_NEEDS_NAME = (_plant, _rail, _vine, _campfire, _flat_cover, _carpet, _pressure_plate, _chest, _banner)


@lru_cache(maxsize=4096)
def shape_for(block_name: str) -> Optional[Tuple]:
    """As partes do bloco (caixas ``Box`` e planos ``Quad``), ou ``None`` se é um cubo inteiro."""
    base, props = parse_block(block_name)
    if base.endswith("_door") and not base.endswith("trapdoor"):
        return tuple(_door(base, props))
    if base.endswith(_PREFER_MODELS):
        from_models = _shape_from_models(block_name)
        if from_models is not None:
            return from_models
    for matches, build in _RULES:
        if matches(base):
            boxes = build(base, props) if build in _NEEDS_NAME else build(props)
            return tuple(boxes) if boxes else None
    return _shape_from_models(block_name)


@lru_cache(maxsize=1)
def _models():
    """Os modelos do Minecraft (a cópia local ou o jar), se existem; ``False`` se não."""
    try:
        from src.rendering.mc_models import MinecraftModels

        return MinecraftModels.find() or False
    except Exception:  # sem os modelos o jogo segue com os cubos de sempre
        return False


def _shape_from_models(block_name: str) -> Optional[Tuple]:
    """As caixas do bloco lidas do blockstate e do modelo do Minecraft, para os que não têm regra aqui."""
    models = _models()
    if not models:
        return None
    boxes = models.boxes(block_name)
    if not boxes:
        return None
    base, _ = parse_block(block_name)
    texture = base[: -len("_bed")] + "_wool" if base.endswith("_bed") else None  # a cama é textura de entidade
    return tuple(Box(lo, hi, texture) for lo, hi in boxes)


def is_full_cube(block_name: str) -> bool:
    return shape_for(block_name) is None


SHADOW_BOXES = 8    # até quantas caixas de um bloco a sombra do sol leva (as maiores)


@lru_cache(maxsize=4096)
def shadow_boxes(block_name: str) -> Tuple[Tuple[Vec, Vec], ...]:
    """As caixas do bloco em blocos (0 a 1 dentro da célula), para a sombra do sol: ``(lo, hi)`` de cada uma, as
    ``SHADOW_BOXES`` maiores. Vazio para o cubo inteiro e para o que só tem planos (planta, escada de mão)."""
    shape = shape_for(block_name)
    boxes = [part for part in shape or () if isinstance(part, Box)]
    boxes.sort(key=lambda b: -(b.hi[0] - b.lo[0]) * (b.hi[1] - b.lo[1]) * (b.hi[2] - b.lo[2]))
    return tuple((tuple(v / 16.0 for v in b.lo), tuple(v / 16.0 for v in b.hi)) for b in boxes[:SHADOW_BOXES])


@lru_cache(maxsize=4096)
def shadow_plant(block_name: str) -> Optional[Tuple[str, float, float]]:
    """Os planos em X de uma planta (muda, flor, capim, cogumelo), para a sombra do sol: ``(textura, y0, y1)``, a
    textura deles e a altura de baixo e de cima em blocos; None se o bloco não é planta em cruz. A sombra sai do
    desenho da textura (o transparente deixa o sol passar)."""
    if parse_block(block_name)[0] in ("fire", "soul_fire"):
        return None                                            # o fogo é luz, não faz sombra
    shape = shape_for(block_name)
    if not shape or any(isinstance(part, Box) for part in shape):
        return None
    crossed = [part for part in shape if isinstance(part, Quad)
               and len({c[0] for c in part.corners}) > 1 and len({c[2] for c in part.corners}) > 1
               and len({c[1] for c in part.corners}) > 1]           # de pé e na diagonal (não cipó, trilho, escada)
    if not crossed or not crossed[0].texture:
        return None
    ys = [c[1] for part in crossed for c in part.corners]
    return crossed[0].texture, min(ys) / 16.0, max(ys) / 16.0


# Blocos que enfeitam o espaço sem barrar quem passa (nem selar um cômodo)
_DECORATION_SUFFIXES = ("_button", "_pressure_plate", "_wall_sign", "_sign", "_carpet", "torch", "lantern", "_candle",
                        "_rail", "_banner")
_DECORATION_NAMES = ("chain", "ladder", "candle", "flower_pot", "rail", "vine", "glow_lichen", "lily_pad",
                     "pink_petals", "wildflowers", "leaf_litter", "tripwire", "end_rod", "sea_pickle")


# Os detalhes de dentro de uma casa (móveis, enfeites): o corte da casa de bonecas não os tira, mesmo encostados
# na parede da frente; só o corredor de visão, se ficam na frente do personagem
_DETAIL_WORDS = ("barrel", "chest", "shulker_box", "furnace", "smoker", "bookshelf", "crafting_table", "lectern",
                 "cartography_table", "fletching_table", "smithing_table", "enchanting_table", "loom", "stonecutter",
                 "grindstone", "anvil", "cauldron", "composter", "brewing_stand", "jukebox", "note_block", "beehive",
                 "bee_nest", "_bed", "flower_pot", "potted_", "decorated_pot", "candle", "lantern", "banner",
                 "campfire", "bell", "skull", "_head", "sign", "hay_block", "target", "chain", "end_rod",
                 "lightning_rod", "_trapdoor", "_fence", "dispenser", "dropper", "hopper", "crafter", "_carpet",
                 "torch", "button", "pressure_plate", "ladder", "scaffolding", "cake", "beacon", "conduit",
                 "respawn_anchor", "lodestone", "vault", "trial_spawner", "spawner", "armor_stand", "item_frame")


def is_room_detail(block_name: str) -> bool:
    """O bloco é um detalhe de dentro da casa (móvel, enfeite), não parede: fica no corte da casa de bonecas."""
    base, _ = parse_block(block_name)
    if base.endswith("_fence_gate"):
        return True
    return any(word in base for word in _DETAIL_WORDS)


def collides(block_name: str) -> bool:
    """O personagem não atravessa o bloco (tochas, tapetes, placas, botões, velas, vasos, plantas, trilhos e fogo
    não barram)."""
    base, props = parse_block(block_name)
    if base in _FULL_LANTERNS:
        return True
    if base.startswith("potted_") or base in _DECORATION_NAMES or base.endswith(_DECORATION_SUFFIXES):
        return False
    if is_cross_plant(base):
        return False
    if base == "snow" and int(props.get("layers", "1") or 1) < 8:
        return False  # a neve fina não barra (como o tapete)
    if base.endswith("_door") and not base.endswith("trapdoor") and props.get("open") == "true":
        return False  # a porta aberta deixa passar (a colisão é por célula inteira)
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
    points = [tuple(box.hi[a] if corner[a] > 0 else box.lo[a] for a in range(3)) for corner in corners]
    uvs = [_uv(key, point) for point in points]
    region = dict(box.face_uv).get(key if key in ("top", "bottom") else "side") if box.face_uv else None
    if region is not None:
        # a face inteira cobre a região da folha (em pixels), no mesmo sentido do recorte normal
        us, vs = [u for u, _ in uvs], [v for _, v in uvs]
        span_u, span_v = (max(us) - min(us)) or 1.0, (max(vs) - min(vs)) or 1.0
        x0, y0, x1, y1 = (c / 16.0 for c in region)
        uvs = [(x0 + (u - min(us)) / span_u * (x1 - x0), y0 + (v - min(vs)) / span_v * (y1 - y0)) for u, v in uvs]
    quad = np.empty((4, 11), dtype=np.float32)
    for i, (point, (u, v)) in enumerate(zip(points, uvs)):
        quad[i, :3] = cell_corner + np.array(point, dtype=np.float32) / 16.0
        quad[i, 3:6] = normal
        quad[i, 6] = u0 + u * (u1 - u0)
        quad[i, 7] = v0 + v * (v1 - v0)
        quad[i, 8:11] = 1.0
    return quad
