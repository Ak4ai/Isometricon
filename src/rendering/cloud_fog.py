"""A névoa de guerra em nuvens de blocos, como as do Minecraft: o que ninguém viu fica debaixo de uma manta de nuvens.

As nuvens são caixas brancas de ``CELL`` x ``CELL`` blocos, de topo chato e lados sombreados (o topo claro, um lado
um pouco mais escuro, o outro mais ainda), deitadas sobre o relevo: cada célula vai do chão até um pouco acima do
ponto mais alto dela (um bloco a mais aqui e ali), então a manta tem patamares como as nuvens do Minecraft, e não se
vê o terreno por baixo dela. Onde o grupo olha (``fog_of_war``: o explorado, ou só em volta), as células
se desfazem: encolhem, sobem e somem em meio segundo; no modo "Em volta", voltam a se formar atrás dele.

A manta cobre ``WINDOW`` células em volta do jogador. A malha das células inteiras só é refeita quando o que está
coberto muda (o jogador entra noutro bloco, o explorado cresce, a manta recentra); as que estão se desfazendo ou se
formando vão numa malha pequena, refeita a cada quadro.
"""

from __future__ import annotations

import math
import os
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from src.rendering.fog_of_war import AROUND, OFF, RADIUS, REVEAL, ExploredMap

CELL = 2            # o lado de uma célula de nuvem, em blocos
WINDOW = 64         # células de lado na manta (128 blocos)
RECENTER = 12       # células: recentra quando o jogador se afasta isto do centro
CLEARANCE = 2       # o topo fica isto acima do bloco mais alto da célula (cobre o capim e as flores)
FADE_SECONDS = 0.55
SHADES = {'top': 1.0, 'x': 0.86, 'z': 0.74}   # o sombreado chapado das nuvens do Minecraft
FLOATS = 5          # x, y, z, sombra, opacidade

Cell = Tuple[int, int]


def _hash(cx: int, cz: int) -> float:
    h = (cx * 73856093) ^ (cz * 19349663)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


class CloudField:
    """As células cobertas, as alturas e a animação (sem GL: testável)."""

    def __init__(self, height: Callable[[int, int], int], explored: Optional[ExploredMap] = None) -> None:
        self.height = height                        # a altura do relevo num bloco (x, z)
        self.explored = explored or ExploredMap()
        self.origin: Optional[Cell] = None          # a célula do canto da manta
        self.cover: Dict[Cell, float] = {}           # 1 nuvem inteira, 0 aberta; entre os dois, animando
        self.target: Dict[Cell, float] = {}
        self._columns: Dict[Cell, Tuple[int, int]] = {}   # (fundo, topo) de cada célula
        self._key = None
        self.revision = 0                            # muda quando a malha das células inteiras precisa ser refeita

    def reset(self) -> None:
        """Outro relevo (outro mundo ou outra seed): as alturas e a manta são refeitas."""
        self._columns.clear()
        self.cover.clear()
        self.target.clear()
        self.origin, self._key = None, None
        self.revision += 1

    # ---- o relevo debaixo das células ----
    def column(self, cell: Cell) -> Tuple[int, int]:
        """(fundo, topo) da nuvem da célula: do chão até acima do relevo das células em volta, em patamares."""
        found = self._columns.get(cell)
        if found is not None:
            return found
        cx, cz = cell
        low, high = 10 ** 9, -10 ** 9
        for x in range(cx * CELL, cx * CELL + CELL):
            for z in range(cz * CELL, cz * CELL + CELL):
                h = int(self.height(x, z))
                low, high = min(low, h), max(high, h)
        # rente ao relevo (numa vista isométrica, uma nuvem alta na frente taparia o que já foi revelado), com um
        # bloco a mais aqui e ali: o topo fica em patamares, como as nuvens do Minecraft
        top = high + 1 + CLEARANCE + (1 if _hash(cx, cz) > 0.78 else 0)
        found = self._columns[cell] = (low - 1, top)
        return found

    # ---- o que está coberto ----
    def seen(self, cell: Cell, mode: int, x: float, z: float) -> bool:
        center = ((cell[0] + 0.5) * CELL, (cell[1] + 0.5) * CELL)
        if math.hypot(center[0] - x, center[1] - z) <= RADIUS - 0.5:
            return True
        if mode == REVEAL:
            return self.explored.explored(int(math.floor(center[0])), int(math.floor(center[1])))
        return False

    def update(self, mode: int, x: float, z: float, dt: float) -> None:
        """Os alvos (coberto ou não) quando algo muda, e a animação das células que estão mudando."""
        here = (int(math.floor(x / CELL)), int(math.floor(z / CELL)))
        if (self.origin is None or abs(here[0] - (self.origin[0] + WINDOW // 2)) > RECENTER
                or abs(here[1] - (self.origin[1] + WINDOW // 2)) > RECENTER):
            self.origin = (here[0] - WINDOW // 2, here[1] - WINDOW // 2)
            self._key = None
        key = (mode, (int(math.floor(x)), int(math.floor(z))), self.explored.revision, self.origin)
        if key != self._key:
            first = self._key is None and not self.cover
            self._key = key
            ox, oz = self.origin
            target = {}
            for cx in range(ox, ox + WINDOW):
                for cz in range(oz, oz + WINDOW):
                    if mode != OFF and not self.seen((cx, cz), mode, x, z):
                        target[(cx, cz)] = 1.0
            self.target = target
            for cell in list(self.cover):              # o que saiu da manta some sem animar
                if not (ox <= cell[0] < ox + WINDOW and oz <= cell[1] < oz + WINDOW):
                    del self.cover[cell]
            if first or mode == OFF:
                self.cover = dict(target)
            for cell in target:                        # o que entrou na manta (recentrou) já vem inteiro
                if cell not in self.cover and not self._was_inside(cell):
                    self.cover[cell] = 1.0
            self._entered = (ox, oz)
            self.revision += 1
        step = dt / FADE_SECONDS if dt > 0 else 1.0
        changed = False
        for cell in set(self.cover) | set(self.target):
            want = self.target.get(cell, 0.0)
            have = self.cover.get(cell, 0.0)
            if have == want:
                continue
            have = min(want, have + step) if want > have else max(want, have - step)
            was_full = self.cover.get(cell, 0.0) >= 1.0
            if have <= 0.0:
                self.cover.pop(cell, None)
            else:
                self.cover[cell] = have
            if was_full != (have >= 1.0):
                changed = True
        if changed:
            self.revision += 1

    def _was_inside(self, cell: Cell) -> bool:
        """Se a célula já estava na manta antes de recentrar (então ela anima; se é nova, vem pronta)."""
        previous = getattr(self, '_entered', None)
        return previous is not None and previous[0] <= cell[0] < previous[0] + WINDOW \
            and previous[1] <= cell[1] < previous[1] + WINDOW

    # ---- as malhas ----
    def full_mesh(self) -> np.ndarray:
        """As células inteiras: o topo e só os lados que dão para fora (ou para uma célula mais baixa)."""
        full = {cell for cell, value in self.cover.items() if value >= 1.0}
        out: List[float] = []
        for cell in full:
            bottom, top = self.column(cell)
            x0, z0 = cell[0] * CELL, cell[1] * CELL
            _top(out, x0, z0, top, 1.0)
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                near = (cell[0] + dx, cell[1] + dz)
                floor = self.column(near)[1] if near in full else bottom
                if floor < top:
                    _side(out, x0, z0, dx, dz, max(floor, bottom), top, 1.0)
        return np.asarray(out, dtype=np.float32).reshape(-1, FLOATS)

    def moving_mesh(self) -> np.ndarray:
        """As células que estão se desfazendo ou se formando: caixas menores, mais altas e transparentes."""
        out: List[float] = []
        for cell, value in self.cover.items():
            if value >= 1.0:
                continue
            bottom, top = self.column(cell)
            ease = value * value * (3 - 2 * value)
            size = CELL * (0.35 + 0.65 * ease)
            lift = (1.0 - ease) * 1.6
            x0 = cell[0] * CELL + (CELL - size) / 2
            z0 = cell[1] * CELL + (CELL - size) / 2
            height = (top - bottom) * (0.4 + 0.6 * ease)
            _box(out, x0, z0, size, top - height + lift, top + lift, ease)
        return np.asarray(out, dtype=np.float32).reshape(-1, FLOATS)


def _quad(out: List[float], corners, shade: float, alpha: float) -> None:
    a, b, c, d = corners
    for p in (a, b, c, a, c, d):
        out.extend((p[0], p[1], p[2], shade, alpha))


def _top(out, x0, z0, top, alpha, size=CELL) -> None:
    _quad(out, ((x0, top, z0), (x0, top, z0 + size), (x0 + size, top, z0 + size), (x0 + size, top, z0)),
          SHADES['top'], alpha)


def _side(out, x0, z0, dx, dz, bottom, top, alpha, size=CELL) -> None:
    """O lado da célula que dá para (dx, dz), virado para fora (sentido anti-horário visto de fora)."""
    x1, z1 = x0 + size, z0 + size
    if dx == 1:
        corners = ((x1, bottom, z0), (x1, top, z0), (x1, top, z1), (x1, bottom, z1))
    elif dx == -1:
        corners = ((x0, bottom, z1), (x0, top, z1), (x0, top, z0), (x0, bottom, z0))
    elif dz == 1:
        corners = ((x1, bottom, z1), (x1, top, z1), (x0, top, z1), (x0, bottom, z1))
    else:
        corners = ((x0, bottom, z0), (x0, top, z0), (x1, top, z0), (x1, bottom, z0))
    _quad(out, corners, SHADES['x'] if dx else SHADES['z'], alpha)


def _box(out, x0, z0, size, bottom, top, alpha) -> None:
    _top(out, x0, z0, top, alpha, size)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        _side(out, x0, z0, dx, dz, bottom, top, alpha, size)


class CloudFog:
    """Desenha a manta de nuvens (o shader ``cloud``) no lugar da névoa de guerra plana."""

    def __init__(self, height: Callable[[int, int], int], explored: ExploredMap) -> None:
        from src.rendering.shader import Shader
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.field = CloudField(height, explored)
        self.shader = Shader(os.path.join(root, 'assets', 'shaders', 'cloud.vert'),
                             os.path.join(root, 'assets', 'shaders', 'cloud.frag'))
        self._meshes = {'full': self._new_mesh(), 'moving': self._new_mesh()}
        self._built = None

    @staticmethod
    def _new_mesh():
        import OpenGL.GL as gl
        vao, vbo = gl.glGenVertexArrays(1), gl.glGenBuffers(1)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        stride = FLOATS * 4
        import ctypes
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, None)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(12))
        gl.glBindVertexArray(0)
        return {'vao': vao, 'vbo': vbo, 'count': 0}

    @staticmethod
    def _upload(mesh, data: np.ndarray) -> None:
        import OpenGL.GL as gl
        mesh['count'] = int(len(data))
        if mesh['count']:
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, mesh['vbo'])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_DRAW)

    def update(self, mode: int, x: float, z: float, dt: float) -> None:
        self.field.update(mode, x, z, dt)
        if self._built != self.field.revision:
            self._upload(self._meshes['full'], self.field.full_mesh())
            self._built = self.field.revision
        self._upload(self._meshes['moving'], self.field.moving_mesh())

    def render(self, projection, view, model, tint, time: float) -> None:
        import OpenGL.GL as gl
        full, moving = self._meshes['full'], self._meshes['moving']
        if not full['count'] and not moving['count']:
            return
        culling, blending = gl.glIsEnabled(gl.GL_CULL_FACE), gl.glIsEnabled(gl.GL_BLEND)   # devolve como achou
        self.shader.use()
        self.shader.set_mat4('u_MVP', projection @ view @ model)
        self.shader.set_vec3('u_Tint', *(float(c) for c in tint))
        self.shader.set_float('u_Time', float(time))
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        if full['count']:
            gl.glBindVertexArray(full['vao'])
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, full['count'])
        if moving['count']:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glBindVertexArray(moving['vao'])
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, moving['count'])
            gl.glDepthMask(gl.GL_TRUE)
        gl.glBindVertexArray(0)
        (gl.glEnable if culling else gl.glDisable)(gl.GL_CULL_FACE)
        (gl.glEnable if blending else gl.glDisable)(gl.GL_BLEND)

    def delete(self) -> None:
        import OpenGL.GL as gl
        for mesh in self._meshes.values():
            gl.glDeleteVertexArrays(1, [mesh['vao']])
            gl.glDeleteBuffers(1, [mesh['vbo']])
        self.shader.delete()
