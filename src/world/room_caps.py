"""Tampas dos blocos que ficam à vista quando o bloco da frente é escondido pelo efeito de revelar.

Os malhadores já não geram a face de um bloco que encosta em outro bloco opaco. Quando o shader
esconde o bloco da frente (o teto, a parede de frente, a terra por cima), o bloco que fica à vista
atrás dele está sem a face que encostava, e se vê o vazio por dentro. Este módulo repete, na CPU, a
regra do shader para achar os blocos escondidos e gera só as faces que faltam: as dos blocos à vista
voltadas para um bloco escondido. Sem OpenGL.

A regra (a mesma de ``world_textured.frag``): um bloco sólido, fora do espaço do jogador, some se o
raio da câmera, partindo do centro dele, chega ao espaço do jogador em até 64 passos de meio bloco.
"""

from typing import Callable, Tuple

import numpy as np

from src.world.mesher import _CORNERS, _NORMALS
from src.world.room_reveal import INTERIOR, RoomMask
from src.world.structure_mesher import _FACES as _STRUCTURE_FACES

RAY_START = 0.9   # distância do centro em que o raio começa (sai do bloco)
RAY_STEP = 0.5    # passo do raio, em blocos
RAY_STEPS = 64

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


def hidden_cells(solid: np.ndarray, interior: np.ndarray, view_dir) -> np.ndarray:
    """Células sólidas que o shader esconde: o raio da câmera, vindo delas, chega ao espaço do jogador.

    O raio parte do centro da célula (inteiro + 0,5), então a célula que ele atinge no passo i é
    ``c + floor(0,5 + dir * t_i)``: um deslocamento inteiro igual para todas as células. Em vez de
    lançar um raio por célula, desloca-se a máscara do espaço uma vez por passo distinto.

    Args:
        solid: bool [x, y, z], o que é sólido na janela.
        interior: bool [x, y, z], o espaço do jogador.
        view_dir: para onde a câmera olha, em coordenadas do mundo.
    """
    direction = np.asarray(view_dir, dtype=np.float64)
    offsets = {
        tuple(int(v) for v in np.floor(0.5 + direction * (RAY_START + RAY_STEP * step)))
        for step in range(RAY_STEPS)
    }
    reaches = np.zeros(solid.shape, dtype=bool)
    for offset in offsets:
        reaches |= _shifted(interior, offset)
    return solid & ~interior & reaches


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


def build_caps(room: RoomMask, view_dir, terrain_atlas, structure_uv: UvLookup) -> Caps:
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
    interior = room.data == INTERIOR
    hidden = hidden_cells(window.solid, interior, view_dir)
    if not hidden.any():
        return caps
    visible = window.solid & ~hidden
    origin = np.array(room.origin, dtype=np.float32)
    caps.terrain = _terrain_caps(window, visible, hidden, origin, terrain_atlas)
    caps.structures = _structure_caps(window, visible, hidden, origin, structure_uv)
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


def _structure_caps(window, visible, hidden, origin, uv_lookup):
    vertices, indices, base = [], [], 0
    cache = {}
    for (dx, dy, dz), normal, face_key, corners, uv_order in _STRUCTURE_FACES:
        mask = visible & _toward(hidden, (dx, dy, dz)) & (window.owner >= 0)
        for cell in np.argwhere(mask):
            placed = window.structures[window.owner[tuple(cell)]]
            world = cell + origin.astype(np.int64)
            lx, ly, lz = (int(world[0]) - placed.origin[0], int(world[1]) - placed.origin[1],
                          int(world[2]) - placed.origin[2])
            block = placed.schematic.grid[ly, lz, lx]
            key = (block, face_key)
            if key not in cache:
                cache[key] = uv_lookup(block, face_key)
            u0, v0, u1, v1 = cache[key]
            us, vs = (u0, u1), (v0, v1)
            center = cell.astype(np.float32) + origin + 0.5
            quad = np.empty((4, 11), dtype=np.float32)
            for i, (corner, (cu, cv)) in enumerate(zip(corners, uv_order)):
                quad[i, :3] = center + 0.5 * np.array(corner, dtype=np.float32)
                quad[i, 3:6] = normal
                quad[i, 6:8] = (us[cu], vs[cv])
                quad[i, 8:11] = 1.0
            vertices.append(quad)
            indices.append(base + np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32))
            base += 4
    return _join(vertices, indices)


def _join(vertices, indices):
    if not vertices:
        return Caps.EMPTY
    return np.concatenate(vertices).astype(np.float32), np.concatenate(indices).astype(np.uint32)
