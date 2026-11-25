"""O personagem está encoberto? Decide se o corredor da câmera precisa abrir (sem OpenGL).

Ao ar livre o corredor só deve abrir quando algo bloqueia a vista do corpo. Um degrau de 1 bloco na frente do
personagem esconde só as pernas: abrir um buraco ali só mostra o vazio por dentro dos blocos. Aqui se segue, da altura
do peito e da cabeça até a câmera, o que a janela de blocos tem no caminho; se bloqueia, o corredor abre (e abre por
inteiro, dos pés para cima, para os pés aparecerem também).
"""

from typing import Sequence

import numpy as np

CHEST = 1.1      # altura do peito acima dos pés, em blocos
HEAD = 1.65      # e da cabeça
REACH = 18.0     # até onde se segue o raio, em blocos
STEP = 0.25
START = 0.9      # o raio só passa a contar depois do bloco em que o personagem está


def sight_blocked(solid: np.ndarray, origin: Sequence[int], start: Sequence[float], direction: Sequence[float]) -> bool:
    """Há um bloco sólido no raio que sai de ``start`` em ``direction`` (até ``REACH``), na janela ``solid`` [x, y, z]?"""
    direction = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(direction))
    if length < 1e-9:
        return False
    direction = direction / length
    ts = np.arange(START, REACH, STEP)
    points = np.asarray(start, dtype=np.float64) + direction * ts[:, None]
    cells = np.floor(points - np.asarray(origin, dtype=np.float64)).astype(np.int64)
    shape = np.array(solid.shape)
    inside = ((cells >= 0) & (cells < shape)).all(axis=1)
    cells = cells[inside]
    return bool(len(cells) and solid[cells[:, 0], cells[:, 1], cells[:, 2]].any())


def sight_needed(solid: np.ndarray, origin: Sequence[int], feet: Sequence[float], direction: Sequence[float]) -> bool:
    """O corpo está encoberto: algo bloqueia a vista do peito ou da cabeça até a câmera.

    Args:
        solid: bool [x, y, z] dos blocos sólidos da janela.
        origin: célula do mundo do canto (0, 0, 0) da janela.
        feet: posição dos pés, no mundo.
        direction: do personagem para a câmera, no mundo.
    """
    fx, fy, fz = (float(v) for v in feet)
    return (sight_blocked(solid, origin, (fx, fy + CHEST, fz), direction)
            or sight_blocked(solid, origin, (fx, fy + HEAD, fz), direction))


FAR_STEP = 0.5    # o passo do raio fora da janela, em blocos


def sight_blocked_world(chunk_at, start: Sequence[float], direction: Sequence[float], t0: float, t1: float) -> bool:
    """Há tronco, chão ou parede (opaco; folha não) no raio de ``start`` em ``direction``, entre ``t0`` e ``t1``
    blocos, nos chunks carregados (``chunk_at((cx, cy, cz))``)? Para o que tapa o personagem de longe: uma árvore
    alta lá na frente, fora da janela de blocos em volta dele (a câmera isométrica sobe devagar; uma sequoia de 36
    blocos tapa a vista a dezenas de blocos)."""
    from src.world.block import OPAQUE_LUT
    direction = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(direction))
    if length < 1e-9 or t1 <= t0:
        return False
    direction = direction / length
    ts = np.arange(t0, t1, FAR_STEP)
    cells = np.floor(np.asarray(start, dtype=np.float64) + direction * ts[:, None]).astype(np.int64)
    keys = cells // 16
    # os pontos em ordem passam por poucos chunks: um corte por chunk
    change = np.flatnonzero(np.any(np.diff(keys, axis=0) != 0, axis=1)) + 1
    for part in np.split(np.arange(len(cells)), change):
        chunk = chunk_at(tuple(int(v) for v in keys[part[0]]))
        if chunk is None:
            continue
        local = cells[part] - keys[part[0]] * 16
        if OPAQUE_LUT[chunk.blocks[local[:, 0], local[:, 1], local[:, 2]]].any():
            return True
    return False


# O buraco das folhas (no shader, ``leafHole``): ao ar livre, a copa das árvores entre a câmera e o personagem some num
# círculo em volta dele, bloco a bloco como o corredor da câmera; só as folhas, o tronco e o chão ficam. O raio acompanha o zoom: é uma fração da meia-altura
# visível, para o buraco ter sempre o mesmo tamanho na tela.
LEAF_HOLE_SCREEN = 1.0    # fração da meia-altura visível (ortho_size): o círculo vai de cima a baixo da tela
LEAF_HOLE_MIN = 2.6       # de muito perto, não fica menor que o corredor da câmera (blocos)


def leaf_hole_radius(ortho_size: float) -> float:
    """O raio do buraco das folhas, em blocos, para a câmera com essa meia-altura visível."""
    return max(LEAF_HOLE_MIN, LEAF_HOLE_SCREEN * float(ortho_size))


def sight_cover(cells) -> np.ndarray:
    """O que conta para o corredor da câmera abrir: o sólido sem a folhagem (as folhas abrem pelo buraco delas)."""
    return cells.roof
