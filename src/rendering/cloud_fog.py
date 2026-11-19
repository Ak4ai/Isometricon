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
from typing import Callable, Dict, Iterable, Optional, Tuple

import numpy as np

from src.rendering.fog_of_war import AROUND, OFF, RADIUS, REVEAL, ExploredMap

CELL = 2            # o lado de uma célula de nuvem, em blocos
WINDOW = 64         # células de lado na manta (128 blocos)
RECENTER = 12       # células: recentra quando o jogador se afasta isto do centro
CLEARANCE = 2       # padrão: o topo fica isto acima do bloco mais alto da célula (cobre o capim e as flores)
FADE_SECONDS = 0.55
SHADES = {'top': 1.0, 'x': 0.86, 'z': 0.74}   # o sombreado chapado das nuvens do Minecraft
FLOATS = 6          # x, y, z, sombra, opacidade, abaixo do topo
FAR = 4             # células: daqui para dentro da manta a nuvem é densa
UNIT = 8            # a unidade de textura do campo de distância (7 é a do cursor)

Cell = Tuple[int, int]
Box = Tuple[Tuple[int, int, int], Tuple[int, int, int]]


def _hash(cx: int, cz: int) -> float:
    h = (cx * 73856093) ^ (cz * 19349663)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


class CloudField:
    """As células cobertas, as alturas e a animação (sem GL: testável)."""

    def __init__(self, height: Callable[[int, int], int], explored: Optional[ExploredMap] = None,
                 objects: Optional[Callable[[], Iterable[Box]]] = None) -> None:
        self.height = height                        # a altura do relevo num bloco (x, z)
        self.objects = objects                      # as caixas (mín, máx, inclusive) das construções no mundo
        self.clearance = CLEARANCE                  # blocos acima do relevo (o mestre: "Altura da névoa")
        self.cover_objects = True                   # as nuvens sobem por cima das construções
        self._boxes: Tuple[Box, ...] = ()
        self._object_tops: Dict[Cell, int] = {}
        self.explored = explored or ExploredMap()
        self.origin: Optional[Cell] = None          # a célula do canto da manta
        self.cover: Dict[Cell, float] = {}           # 1 nuvem inteira, 0 aberta; entre os dois, animando
        self.target: Dict[Cell, float] = {}
        self._columns: Dict[Cell, Tuple[int, int]] = {}   # (fundo, topo) de cada célula
        self._key = None
        self.revision = 0                            # muda quando a malha das células inteiras precisa ser refeita
        self._distance = None                        # (revisão, distance_map)

    def configure(self, clearance: int, cover_objects: bool) -> None:
        """A altura das nuvens e se elas cobrem as construções; refaz as colunas se mudou."""
        clearance, cover_objects = int(clearance), bool(cover_objects)
        if (clearance, cover_objects) != (self.clearance, self.cover_objects):
            self.clearance, self.cover_objects = clearance, cover_objects
            self._columns.clear()
            self.revision += 1

    def _sync_objects(self) -> None:
        """Relê as caixas das construções; se mudaram, refaz o topo delas por célula e as colunas."""
        boxes = tuple(self.objects()) if self.objects is not None else ()
        if boxes == self._boxes:
            return
        self._boxes = boxes
        tops: Dict[Cell, int] = {}
        for (x0, _, z0), (x1, y1, z1) in boxes:
            for cx in range(x0 // CELL, x1 // CELL + 1):
                for cz in range(z0 // CELL, z1 // CELL + 1):
                    tops[(cx, cz)] = max(tops.get((cx, cz), y1), y1)
        self._object_tops = tops
        self._columns.clear()
        self.revision += 1

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
        if self.cover_objects and cell in self._object_tops:   # por cima da construção também
            high = max(high, self._object_tops[cell])
        top = high + 1 + self.clearance + (1 if _hash(cx, cz) > 0.78 else 0)
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
        self._sync_objects()
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
    def _full_grid(self):
        """As células inteiras da manta como grades [ix, iz]: máscara, fundo e topo."""
        full = np.zeros((WINDOW, WINDOW), dtype=bool)
        bottom = np.zeros((WINDOW, WINDOW), dtype=np.float32)
        top = np.zeros((WINDOW, WINDOW), dtype=np.float32)
        if self.origin is None:
            return full, bottom, top
        ox, oz = self.origin
        for (cx, cz), value in self.cover.items():
            ix, iz = cx - ox, cz - oz
            if value >= 1.0 and 0 <= ix < WINDOW and 0 <= iz < WINDOW:
                full[ix, iz] = True
                bottom[ix, iz], top[ix, iz] = self.column((cx, cz))
        return full, bottom, top

    def full_mesh(self) -> np.ndarray:
        """As células inteiras: o topo e só os lados que dão para fora (ou para uma célula mais baixa)."""
        full, bottom, top = self._full_grid()
        if not full.any():
            return np.zeros((0, FLOATS), dtype=np.float32)
        ox, oz = self.origin
        ix, iz = np.nonzero(full)
        x0, z0 = ((ix + ox) * CELL).astype(np.float32), ((iz + oz) * CELL).astype(np.float32)
        parts = [_quads('top', x0, z0, CELL, bottom[ix, iz], top[ix, iz], 1.0)]
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            near_full = np.zeros_like(full)
            near_top = np.zeros_like(top)
            src = (slice(max(dx, 0), WINDOW + min(dx, 0)), slice(max(dz, 0), WINDOW + min(dz, 0)))
            dst = (slice(max(-dx, 0), WINDOW + min(-dx, 0)), slice(max(-dz, 0), WINDOW + min(-dz, 0)))
            near_full[dst], near_top[dst] = full[src], top[src]
            floor = np.where(near_full, near_top, bottom)
            show = full & (floor < top)
            sx, sz = np.nonzero(show)
            if len(sx):
                parts.append(_quads((dx, dz), ((sx + ox) * CELL).astype(np.float32),
                                    ((sz + oz) * CELL).astype(np.float32), CELL,
                                    np.maximum(floor, bottom)[sx, sz], top[sx, sz], 1.0))
        return np.concatenate(parts)

    def moving_mesh(self) -> np.ndarray:
        """As células que estão se desfazendo ou se formando: caixas menores, mais altas e transparentes."""
        moving = [(cell, value) for cell, value in self.cover.items() if value < 1.0]
        if not moving:
            return np.zeros((0, FLOATS), dtype=np.float32)
        cells = np.array([cell for cell, _ in moving], dtype=np.float32)
        value = np.array([v for _, v in moving], dtype=np.float32)
        columns = np.array([self.column(cell) for cell, _ in moving], dtype=np.float32)
        ease = value * value * (3 - 2 * value)
        size = CELL * (0.35 + 0.65 * ease)
        lift = (1.0 - ease) * 1.6
        x0 = cells[:, 0] * CELL + (CELL - size) / 2
        z0 = cells[:, 1] * CELL + (CELL - size) / 2
        height = (columns[:, 1] - columns[:, 0]) * (0.4 + 0.6 * ease)
        bottom, top = columns[:, 1] - height + lift, columns[:, 1] + lift
        return np.concatenate([_quads(face, x0, z0, size, bottom, top, ease)
                               for face in ('top', (1, 0), (-1, 0), (0, 1), (0, -1))])

    def distance_map(self) -> np.ndarray:
        """Quantas células cada nuvem inteira está da beira (do aberto), como imagem [iz, ix] de 0 a 1 (``FAR``
        células ou mais é 1). O shader lê com filtro linear: a beira da manta fica rala e o miolo, denso."""
        if self._distance is not None and self._distance[0] == self.revision:
            return self._distance[1]
        full = self._full_grid()[0]
        if full.all() or not full.any():
            out = np.full((WINDOW, WINDOW), 1.0 if full.any() else 0.0, dtype=np.float32)
        else:
            from scipy.ndimage import distance_transform_edt
            # fora da manta conta como coberto (a beira dela não é uma beira de verdade, é o vazio da névoa)
            padded = np.pad(full, FAR, mode='constant', constant_values=True)
            out = distance_transform_edt(padded)[FAR:-FAR, FAR:-FAR].astype(np.float32)
            out = np.minimum(out, FAR) / FAR
        out = np.ascontiguousarray(out.T)
        self._distance = (self.revision, out)
        return out


# os cantos de cada face numa caixa unitária (x, y, z): y 0 é o fundo e 1 o topo; anti-horário visto de fora
_FACES = {
    'top': ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
    (1, 0): ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
    (-1, 0): ((0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0)),
    (0, 1): ((1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1)),
    (0, -1): ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),
}
_TRIANGLES = (0, 1, 2, 0, 2, 3)


def _quads(face, x0, z0, size, bottom, top, alpha) -> np.ndarray:
    """Uma face por célula (arrays de mesmo tamanho), em triângulos: x, y, z, sombra, opacidade e quanto o vértice
    está abaixo do topo da nuvem (o shader escurece o lado para baixo)."""
    count = len(x0)
    corners = np.array(_FACES[face], dtype=np.float32)[list(_TRIANGLES)]          # (6, 3)
    shade = SHADES['top'] if face == 'top' else SHADES['x'] if face[0] else SHADES['z']
    out = np.empty((count, 6, FLOATS), dtype=np.float32)
    size = np.broadcast_to(np.asarray(size, dtype=np.float32), (count,))
    bottom = np.broadcast_to(np.asarray(bottom, dtype=np.float32), (count,))
    top = np.broadcast_to(np.asarray(top, dtype=np.float32), (count,))
    out[..., 0] = x0[:, None] + corners[None, :, 0] * size[:, None]
    out[..., 1] = np.where(corners[None, :, 1] > 0, top[:, None], bottom[:, None])
    out[..., 2] = z0[:, None] + corners[None, :, 2] * size[:, None]
    out[..., 3] = shade
    out[..., 4] = np.broadcast_to(np.asarray(alpha, dtype=np.float32), (count,))[:, None]
    out[..., 5] = np.where(corners[None, :, 1] > 0, 0.0, (top - bottom)[:, None])
    return out.reshape(-1, FLOATS)


class CloudFog:
    """Desenha a manta de nuvens (o shader ``cloud``) no lugar da névoa de guerra plana.

    As nuvens são translúcidas: primeiro só a profundidade delas, depois a cor por cima com mistura, só na face da
    frente (``GL_LEQUAL``), para que uma nuvem não se some à de trás e fique em degraus. A opacidade vem do campo de
    distância (``CloudField.distance_map``), uma textura pequena: rala na beira, densa no miolo.
    """

    def __init__(self, height: Callable[[int, int], int], explored: ExploredMap,
                 objects: Optional[Callable[[], Iterable[Box]]] = None) -> None:
        from src.rendering.shader import Shader
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.field = CloudField(height, explored, objects)
        self.shader = Shader(os.path.join(root, 'assets', 'shaders', 'cloud.vert'),
                             os.path.join(root, 'assets', 'shaders', 'cloud.frag'))
        self._meshes = {'full': self._new_mesh(), 'moving': self._new_mesh()}
        self._built = None
        self._origin = (0, 0)
        self.texture_id = self._new_texture()

    @staticmethod
    def _new_mesh():
        import ctypes
        import OpenGL.GL as gl
        vao, vbo = gl.glGenVertexArrays(1), gl.glGenBuffers(1)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        stride = FLOATS * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, None)
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(12))
        gl.glEnableVertexAttribArray(2)
        gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(20))
        gl.glBindVertexArray(0)
        return {'vao': vao, 'vbo': vbo, 'count': 0}

    @staticmethod
    def _new_texture() -> int:
        import OpenGL.GL as gl
        texture = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R16F, WINDOW, WINDOW, 0, gl.GL_RED, gl.GL_FLOAT, None)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        return texture

    @staticmethod
    def _upload(mesh, data: np.ndarray) -> None:
        import OpenGL.GL as gl
        mesh['count'] = int(len(data))
        if mesh['count']:
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, mesh['vbo'])
            gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_DYNAMIC_DRAW)

    def update(self, mode: int, x: float, z: float, dt: float) -> None:
        import OpenGL.GL as gl
        self.field.update(mode, x, z, dt)
        if self._built != self.field.revision:
            self._upload(self._meshes['full'], self.field.full_mesh())
            distance = np.ascontiguousarray(self.field.distance_map(), dtype=np.float32)
            gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, WINDOW, WINDOW, gl.GL_RED, gl.GL_FLOAT, distance)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            self._origin = self.field.origin or (0, 0)
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
        self.shader.set_vec2('u_Origin', float(self._origin[0]), float(self._origin[1]))
        self.shader.set_float('u_Window', float(WINDOW))
        self.shader.set_float('u_Cell', float(CELL))
        gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self.shader.set_int('u_Distance', UNIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # puxa a nuvem um pouco para a câmera (as duas passadas igual): numa face no mesmo plano da face de um bloco,
        # ganha sempre a nuvem, em vez de as duas piscarem uma sobre a outra
        gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glPolygonOffset(-1.0, -4.0)
        if full['count']:
            gl.glBindVertexArray(full['vao'])
            # 1. só a profundidade: a face da frente de cada ponto da manta
            gl.glColorMask(gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, full['count'])
            gl.glColorMask(gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
            # 2. a cor, misturada uma vez só, nessa face
            gl.glDepthFunc(gl.GL_LEQUAL)
            gl.glDepthMask(gl.GL_FALSE)
            self.shader.set_bool('u_Moving', False)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, full['count'])
            gl.glDepthFunc(gl.GL_LESS)
        if moving['count']:
            gl.glDepthMask(gl.GL_FALSE)
            self.shader.set_bool('u_Moving', True)
            gl.glBindVertexArray(moving['vao'])
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, moving['count'])
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glBindVertexArray(0)
        (gl.glEnable if culling else gl.glDisable)(gl.GL_CULL_FACE)
        (gl.glEnable if blending else gl.glDisable)(gl.GL_BLEND)

    def delete(self) -> None:
        import OpenGL.GL as gl
        for mesh in self._meshes.values():
            gl.glDeleteVertexArrays(1, [mesh['vao']])
            gl.glDeleteBuffers(1, [mesh['vbo']])
        if self.texture_id:
            gl.glDeleteTextures([self.texture_id])
            self.texture_id = 0
        self.shader.delete()
