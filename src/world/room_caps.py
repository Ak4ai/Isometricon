"""Tampas dos blocos que ficam à vista quando o bloco da frente é escondido pelo efeito de revelar.

Os malhadores já não geram a face de um bloco que encosta em outro bloco opaco. Quando o shader
esconde o bloco da frente (o teto, a parede de frente, a terra por cima), o bloco que fica à vista
atrás dele está sem a face que encostava, e se vê o vazio por dentro. Este módulo repete, na CPU, a
regra do shader para achar os blocos escondidos e gera só as faces que faltam: as dos blocos à vista
voltadas para um bloco escondido. Sem OpenGL.

As regras são as mesmas de ``world_textured.frag`` (ver ``cut_cells``): a borda do cômodo virada para a
câmera que o tapa, o andar de cima sobre ele (corte do andar) e o corredor entre a câmera e o personagem. As
portas nunca somem.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import numpy as np

from src.world.mesher import _CORNERS, _NORMALS
from src.world.block_shapes import box_face_quad, shape_for
from src.world.room_reveal import INTERIOR, OBJECT, RoomMask
from src.world.structure_mesher import _FACES as _STRUCTURE_FACES

RAY_START = 0.9   # distância do centro em que o raio começa (sai do bloco)
RAY_STEP = 0.5    # passo do raio, em blocos
RAY_STEPS = 64
CAMERA_STEPS = 24  # passos do raio de volta para a câmera (facesCamera no shader)


@dataclass
class StoryCut:
    """O corte do andar como o shader o recebe: teto (célula y), pés, centro do cômodo (x, z) e raio."""

    cut_y: int
    feet_y: int
    center: Tuple[float, float]
    radius: float


@dataclass
class SightCut:
    """O corredor da câmera, no mundo: peito do personagem, olho da câmera, raio e célula y dos pés."""

    target: Tuple[float, float, float]
    camera: Tuple[float, float, float]
    radius: float
    feet_y: int

UvLookup = Callable[[str, str], Tuple[float, float, float, float]]


def _shifted(array: np.ndarray, offset) -> np.ndarray:
    """Para cada célula c, o valor da célula c + offset (False fora da janela)."""
    out = np.zeros_like(array)
    src, dst = [], []
    for d, size in zip(offset, array.shape):
        d = int(d)
        if abs(d) >= size:
            return out
        src.append(slice(d, size) if d >= 0 else slice(0, size + d))
        dst.append(slice(0, size - d) if d >= 0 else slice(-d, size))
    out[tuple(dst)] = array[tuple(src)]
    return out


def _reaches(mask: np.ndarray, direction, steps: int) -> np.ndarray:
    """Para cada célula: o raio que parte do centro dela em ``direction`` encontra ``mask`` em ``steps`` passos."""
    direction = np.asarray(direction, dtype=np.float64)
    offsets = {
        tuple(int(v) for v in np.floor(0.5 + direction * (RAY_START + RAY_STEP * step)))
        for step in range(steps)
    }
    out = np.zeros(mask.shape, dtype=bool)
    for offset in offsets:
        out |= _shifted(mask, offset)
    return out


def cut_cells(room: RoomMask, view_dir, story: Optional[StoryCut] = None,
              sight: Optional[SightCut] = None, center: Optional[Tuple[float, float]] = None) -> np.ndarray:
    """Tudo o que o shader PODE esconder com o cômodo ativo, bool [x, y, z] da janela (um pouco a mais, nunca a
    menos: as tampas são geradas em volta disso e o shader descarta as que sobram).

    * revelação: fora do espaço, tapa o cômodo (o raio para dentro da cena cai no espaço do andar) e, do centro do
      cômodo (``center``, x e z) para trás, está na borda virada para a câmera (o raio de volta não passa pelo
      espaço); na metade da frente, basta tapar;
    * corte do andar: do teto para cima, dentro do raio, a metade da frente (medida do centro do cômodo) e, atrás
      dele, o que tapa o cômodo;
    * corredor: do pé para cima, no cilindro entre a câmera e o personagem, o que tapa o cômodo;
    * as portas ficam.
    """
    window = room.window
    occupied = window.occupied
    interior = room.data == INTERIOR
    furniture = room.data == OBJECT
    ox, oy, oz = room.origin
    ys = np.arange(occupied.shape[1])[None, :, None] + oy
    # folgado de propósito: o shader só tapa entre os pés e o teto do andar; aqui qualquer espaço conta
    covers = _reaches(interior, view_dir, RAY_STEPS)
    toward_camera = _reaches(interior, -np.asarray(view_dir, dtype=np.float64), CAMERA_STEPS)
    xs = np.arange(occupied.shape[0])[:, None, None] + ox + 0.5
    zs = np.arange(occupied.shape[2])[None, None, :] + oz + 0.5
    flat = np.asarray(view_dir, dtype=np.float64)[[0, 2]]
    flat = flat / max(float(np.linalg.norm(flat)), 1e-9)
    if center is None and story is not None:
        center = story.center
    if center is not None:
        ahead = (xs - center[0]) * flat[0] + (zs - center[1]) * flat[1]   # < 0: do lado da câmera
        cut = occupied & ~interior & covers & ~furniture & ((ahead < -0.9) | ~toward_camera)
    else:
        cut = occupied & ~interior & ~furniture & covers & ~toward_camera
    # parede da frente: a face de dentro olha o cômodo do lado oposto à câmera (pega a ponta junto à quina)
    front_wall = np.zeros_like(interior)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if dx * flat[0] + dz * flat[1] > 0.3:
            front_wall |= _shifted(interior, (dx, 0, dz))
    band_ok = ys < story.cut_y if story is not None else True
    cut |= occupied & ~interior & ~furniture & front_wall & band_ok
    if sight is not None:
        cut &= ys > sight.feet_y                          # a fileira dos pés fica (a borda da parede)
    if story is not None:
        near = (xs - story.center[0]) ** 2 + (zs - story.center[1]) ** 2 < story.radius ** 2  # com o pontilhado
        cut |= occupied & (ys >= story.cut_y) & near & (~_behind_room(interior, room.origin, story, flat) | covers)
    if sight is not None:
        # a fileira dos pés (a borda da parede, os móveis no chão) fica; o piso de cima, na frente, sai
        candidates = occupied & (ys > sight.feet_y) & covers
        cut |= _in_corridor(occupied.shape, room.origin, sight, candidates)
    return cut & ~window.doors if window.doors is not None else cut


def _behind_room(interior: np.ndarray, origin, story: StoryCut, flat) -> np.ndarray:
    """Para cada célula: andando na horizontal em direção à câmera, passa por cima do chão do cômodo (o espaço na
    altura dos pés). É o fundo do cômodo — a parede do fundo fica inteira, até o topo. ``behindRoom`` no shader."""
    layer = story.feet_y - origin[1]
    if not 0 <= layer < interior.shape[1]:
        return np.zeros(interior.shape, dtype=bool)
    floor = np.zeros_like(interior)
    floor[:, :, :] = interior[:, layer:layer + 1, :]
    toward = (-float(flat[0]), 0.0, -float(flat[1]))
    return _reaches(floor, toward, CAMERA_STEPS)


def _in_corridor(shape, origin, sight: SightCut, candidates: Optional[np.ndarray] = None) -> np.ndarray:
    """As células (pelo centro) dentro do cilindro do corredor, como em ``sightCarved``. Com ``candidates`` (bool),
    só elas são medidas (o resto da janela fica False): a conta por célula é a parte cara."""
    ys_ok = (np.arange(shape[1]) + origin[1]) >= sight.feet_y
    pick = np.zeros(shape, dtype=bool) if candidates is None else candidates.copy()
    if candidates is None:
        pick[:, ys_ok, :] = True
    else:
        pick[:, ~ys_ok, :] = False
    cells = np.argwhere(pick)
    out = np.zeros(shape, dtype=bool)
    if len(cells) == 0:
        return out
    centers = cells + np.asarray(origin, dtype=np.float64) + 0.5
    target = np.asarray(sight.target, dtype=np.float64)
    line = np.asarray(sight.camera, dtype=np.float64) - target
    direction = line / max(float(np.linalg.norm(line)), 1e-4)
    rel = centers - target
    t = rel @ direction
    off = np.linalg.norm(rel - t[:, None] * direction, axis=-1)
    radius = sight.radius * (0.75 + 0.25 * np.clip((t - 0.9) / 3.0, 0.0, 1.0))
    inside = (t >= 0.85) & (off < radius)  # a borda pontilhada inteira
    out[tuple(cells[inside].T)] = True
    return out


def hidden_cells(occupied: np.ndarray, interior: np.ndarray, view_dir) -> np.ndarray:
    """Células desenhadas que o shader esconde: o raio da câmera, vindo delas, chega ao espaço do jogador.

    O raio parte do centro da célula (inteiro + 0,5), então a célula que ele atinge no passo i é
    ``c + floor(0,5 + dir * t_i)``: um deslocamento inteiro igual para todas as células. Em vez de
    lançar um raio por célula, desloca-se a máscara do espaço uma vez por passo distinto.

    Args:
        occupied: bool [x, y, z], o que é desenhado na janela (sólidos e enfeites).
        interior: bool [x, y, z], o espaço do jogador.
        view_dir: para onde a câmera olha, em coordenadas do mundo.
    """
    direction = np.asarray(view_dir, dtype=np.float64)
    offsets = {
        tuple(int(v) for v in np.floor(0.5 + direction * (RAY_START + RAY_STEP * step)))
        for step in range(RAY_STEPS)
    }
    reaches = np.zeros(occupied.shape, dtype=bool)
    for offset in offsets:
        reaches |= _shifted(interior, offset)
    return occupied & ~interior & reaches


def _toward(array: np.ndarray, offset) -> np.ndarray:
    """Para cada célula, o valor da vizinha em ``offset`` (False fora da janela)."""
    out = np.zeros_like(array)
    src, dst = [], []
    for d, size in zip(offset, array.shape):
        if d > 0:
            src.append(slice(1, size)), dst.append(slice(0, size - 1))
        elif d < 0:
            src.append(slice(0, size - 1)), dst.append(slice(1, size))
        else:
            src.append(slice(0, size)), dst.append(slice(0, size))
    out[tuple(dst)] = array[tuple(src)]
    return out


class Caps:
    """Vértices e índices das tampas, separados por atlas (terreno e construções têm texturas diferentes)."""

    EMPTY = (np.empty((0, 11), dtype=np.float32), np.empty(0, dtype=np.uint32))

    def __init__(self) -> None:
        self.terrain = self.EMPTY
        self.structures = self.EMPTY


def build_caps(room: RoomMask, view_dir, terrain_atlas, structure_uv: UvLookup,
               story: Optional[StoryCut] = None, sight: Optional[SightCut] = None,
               center: Optional[Tuple[float, float]] = None) -> Caps:
    """Gera as tampas para a máscara ``room`` e a direção da câmera ``view_dir``.

    Args:
        room: máscara do espaço, com as células da janela (``room.window``).
        view_dir: para onde a câmera olha, em coordenadas do mundo.
        terrain_atlas: TextureAtlas do mundo (tabelas ``uv_table`` e ``color_table``).
        structure_uv: função (nome do bloco, face) -> (u0, v0, u1, v1) do atlas das construções.
    """
    caps = Caps()
    window = room.window
    if window is None or not room.active:
        return caps
    hidden = cut_cells(room, view_dir, story, sight, center)
    if not hidden.any():
        return caps
    # toda célula ganha a tampa virada para um vizinho que PODE ter sumido: se ela mesma sumiu, o shader descarta a
    # tampa junto (a decisão é pela célula dona da face); se o vizinho ficou, a tampa fica escondida dentro dele
    visible = window.occupied
    origin = np.array(room.origin, dtype=np.float32)
    culling = hidden & window.culls  # só um cubo inteiro escondido deixou a face do vizinho sem tampa
    caps.terrain = _terrain_caps(window, visible, culling, origin, terrain_atlas)
    caps.structures = _structure_caps(window, visible, culling, origin, structure_uv)
    return caps


def _terrain_caps(window, visible, hidden, origin, atlas):
    vertices, indices, base = [], [], 0
    for face in range(6):
        normal = _NORMALS[face]
        mask = visible & _toward(hidden, normal) & (window.owner < 0) & (window.blocks > 0)
        cells = np.argwhere(mask)
        if len(cells) == 0:
            continue
        blocks = window.blocks[cells[:, 0], cells[:, 1], cells[:, 2]]
        count = len(cells)
        quad = np.empty((count, 4, 11), dtype=np.float32)
        quad[:, :, :3] = _CORNERS[face] + cells[:, None, :].astype(np.float32) + origin
        quad[:, :, 3:6] = normal
        quad[:, :, 6:8] = atlas.uv_table[blocks, face]
        quad[:, :, 8:11] = atlas.color_table[blocks, face][:, None, :]
        vertices.append(quad.reshape(-1, 11))
        corner_index = base + np.arange(count, dtype=np.uint32)[:, None] * 4
        indices.append((corner_index + np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)).ravel())
        base += count * 4
    return _join(vertices, indices)


def _structure_caps(window, visible, culling, origin, uv_lookup):
    """As tampas das construções. Os cubos inteiros saem em lote (numpy, por bloco e face); só os blocos com forma
    (laje, escada, porta) passam um a um, caixa por caixa."""
    vertices, indices = [], []
    cache = {}
    shapes = {}
    base = 0

    def uv_of(name, face_key):
        key = (name, face_key)
        if key not in cache:
            cache[key] = uv_lookup(name, face_key)
        return cache[key]

    for face, ((dx, dy, dz), normal, face_key, corners, uv_order) in enumerate(_STRUCTURE_FACES):
        mask = visible & _toward(culling, (dx, dy, dz)) & (window.owner >= 0)
        cells = np.argwhere(mask)
        if len(cells) == 0:
            continue
        owners = window.owner[tuple(cells.T)]
        corner_offsets = 0.5 * np.asarray(corners, dtype=np.float32)            # (4, 3)
        for index in np.unique(owners):
            placed = window.structures[int(index)]
            group = cells[owners == index]
            local = group + np.asarray(origin, dtype=np.int64) - np.asarray(placed.origin)
            names = placed.schematic.grid[local[:, 1], local[:, 2], local[:, 0]]
            centers = group.astype(np.float32) + origin + 0.5
            for name in set(names.tolist()):
                pick = names == name
                if name not in shapes:
                    shapes[name] = shape_for(name)
                boxes = shapes[name]
                if boxes is not None:
                    # um bloco com forma: só as faces das caixas que encostam, inteiras, no limite da célula
                    for center in centers[pick]:
                        for box in boxes:
                            if not box.covers_face(face):
                                continue
                            vertices.append(box_face_quad(box, face, center - 0.5, uv_of(box.texture or name,
                                                                                            face_key)))
                            indices.append(base + np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32))
                            base += 4
                    continue
                u0, v0, u1, v1 = uv_of(name, face_key)
                us, vs = (u0, u1), (v0, v1)
                at = centers[pick]
                count = len(at)
                quad = np.empty((count, 4, 11), dtype=np.float32)
                quad[:, :, :3] = at[:, None, :] + corner_offsets[None, :, :]
                quad[:, :, 3:6] = normal
                quad[:, :, 6:8] = np.array([(us[cu], vs[cv]) for cu, cv in uv_order], dtype=np.float32)
                quad[:, :, 8:11] = 1.0
                vertices.append(quad.reshape(-1, 11))
                first = base + np.arange(count, dtype=np.uint32)[:, None] * 4
                indices.append((first + np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)).ravel())
                base += count * 4
    return _join(vertices, indices)


def _join(vertices, indices):
    if not vertices:
        return Caps.EMPTY
    return np.concatenate(vertices).astype(np.float32), np.concatenate(indices).astype(np.uint32)
