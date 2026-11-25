"""A neblina de ambientação do mestre (``/mestre`` > Neblina): a neblina de cena, baixa, que se junta rente ao chão.

O shader do mundo (``mistFactor`` em ``world_textured.frag``) soma a neblina no caminho da câmera até cada ponto
desenhado. Para saber a que altura fica o chão e onde é "perto da água ou entre as árvores", ele lê um mapa 2D em
volta do jogador, feito aqui dos chunks carregados:

- canal 0: a altura do chão (o topo do que não é tronco, folha ou planta; a água conta como chão);
- canal 1: o quanto a coluna fica perto de água ou de árvore (1 em cima, caindo com a distância).

O mapa vai para a GPU como uma textura ``RG32F`` de ``SIZE`` blocos de lado, recentrada quando o jogador anda longe e
refeita quando os chunks mudam (no máximo a cada ``REBUILD_EVERY`` segundos).
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional, Sequence

import numpy as np
from scipy import ndimage

from src.world.block import FOLIAGE, OPAQUE_LUT, BlockType

SIZE = 128            # o lado do mapa, em blocos
RECENTER = 32         # recentra quando o jogador se afasta isto do centro
NEAR_FALLOFF = 5.0    # em quantos blocos o "perto da água/árvore" cai à metade
REBUILD_EVERY = 0.75  # segundos entre refazer o mapa por mudança nos chunks
UNIT = 13             # a unidade de textura (as outras: 0 atlas, 2 cômodo, 3/4/10-12 sombras, 5, 6 guerra, 7-9)

_LOGS = (BlockType.WOOD, BlockType.SPRUCE_LOG, BlockType.SEQUOIA_LOG, BlockType.SPRUCE_LOG_X,
         BlockType.SPRUCE_LOG_Z, BlockType.SEQUOIA_LOG_X, BlockType.SEQUOIA_LOG_Z)
TREE_LUT = np.zeros(256, dtype=bool)
TREE_LUT[[int(b) for b in _LOGS] + [int(b) for b in FOLIAGE]] = True
GROUND_LUT = OPAQUE_LUT.copy()
GROUND_LUT[[int(b) for b in _LOGS]] = False
GROUND_LUT[int(BlockType.WATER)] = True
WATER = int(BlockType.WATER)


def mist_map(chunk_at: Callable, origin_x: int, origin_z: int, size: int = SIZE,
             layers: Sequence[int] = (0,)) -> np.ndarray:
    """O mapa ``[z, x, 2]`` (float32) da área ``[origin_x, origin_x + size) x [origin_z, origin_z + size)``.

    ``chunk_at((cx, cy, cz))`` devolve o chunk ou None; ``layers``: as camadas de chunk de cada coluna. Coluna sem
    chunk: chão 0 e longe de tudo."""
    from src.world.chunk import Chunk3D
    n = Chunk3D.SIZE
    ground = np.zeros((size, size), dtype=np.float32)
    marks = np.zeros((size, size), dtype=bool)         # água ou árvore na coluna
    for cx in range(origin_x // n, (origin_x + size - 1) // n + 1):
        for cz in range(origin_z // n, (origin_z + size - 1) // n + 1):
            parts = [(cy, chunk_at((cx, cy, cz))) for cy in layers]
            parts = [(cy, c) for cy, c in parts if c is not None]
            if not parts:
                continue
            x0, z0 = cx * n, cz * n
            sx = slice(max(origin_x, x0) - x0, min(origin_x + size, x0 + n) - x0)
            sz = slice(max(origin_z, z0) - z0, min(origin_z + size, z0 + n) - z0)
            dx = slice(max(origin_x, x0) - origin_x, min(origin_x + size, x0 + n) - origin_x)
            dz = slice(max(origin_z, z0) - origin_z, min(origin_z + size, z0 + n) - origin_z)
            top = np.full((n, n), -1.0, dtype=np.float32)
            mark = np.zeros((n, n), dtype=bool)
            for cy, chunk in sorted(parts):
                blocks = chunk.blocks                        # [x, y, z]
                solid = GROUND_LUT[blocks]
                any_solid = solid.any(axis=1)
                highest = n - 1 - np.argmax(solid[:, ::-1, :], axis=1)
                top = np.where(any_solid, cy * n + highest + 1.0, top)   # o topo da face de cima do chão
                mark |= TREE_LUT[blocks].any(axis=1) | (blocks == WATER).any(axis=1)
            ground[dz, dx] = np.maximum(top, 0.0)[sx, sz].T
            marks[dz, dx] = mark[sx, sz].T
    out = np.zeros((size, size, 2), dtype=np.float32)
    out[:, :, 0] = ground
    if marks.any():
        distance = ndimage.distance_transform_edt(~marks)
        out[:, :, 1] = np.power(0.5, distance / NEAR_FALLOFF)
    return out


class MistField:
    """O mapa da neblina na GPU e os uniforms dela que dependem do mundo (o resto vem de ``Ambience.apply``)."""

    def __init__(self) -> None:
        self.texture_id = 0
        self.origin = (0, 0)
        self.top = 0.0                 # a maior altura de chão do mapa
        self._built: Optional[tuple] = None
        self._built_at = 0.0

    def update(self, x: float, z: float, revision: int, chunk_at: Callable, layers: Sequence[int],
               upload: bool = True) -> bool:
        """Recentra e refaz o mapa se precisa; devolve se refez."""
        cx, cz = self.origin[0] + SIZE // 2, self.origin[1] + SIZE // 2
        if abs(x - cx) > RECENTER or abs(z - cz) > RECENTER or self._built is None:
            self.origin = (int(math.floor(x)) - SIZE // 2, int(math.floor(z)) - SIZE // 2)
        key = (self.origin, revision)
        if self._built == key:
            return False
        now = time.monotonic()
        if self._built is not None and self._built[0] == self.origin and now - self._built_at < REBUILD_EVERY:
            return False                                 # só os chunks mudaram: espera um pouco
        data = mist_map(chunk_at, self.origin[0], self.origin[1], SIZE, layers)
        self.top = float(data[:, :, 0].max())
        if upload:
            self._upload(data)
        self._built, self._built_at = key, now
        return True

    def _upload(self, data: np.ndarray) -> None:
        import OpenGL.GL as gl
        if not self.texture_id:
            self.texture_id = gl.glGenTextures(1)
            gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RG32F, SIZE, SIZE, 0, gl.GL_RG, gl.GL_FLOAT, None)
        gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, SIZE, SIZE, gl.GL_RG, gl.GL_FLOAT, np.ascontiguousarray(data))
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def apply(self, shader, inverse_model: np.ndarray, toward_camera, height: float) -> None:
        """Os uniforms do mapa (``toward_camera``: a direção do ponto para a câmera, no espaço desenhado)."""
        if not self.texture_id:
            shader.set_float("u_MistAmount", 0.0)
            return
        import OpenGL.GL as gl
        gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_MistMap", UNIT)
        shader.set_vec2("u_MistOrigin", float(self.origin[0]), float(self.origin[1]))
        shader.set_float("u_MistSize", float(SIZE))
        shader.set_float("u_MistTop", self.top + float(height))
        shader.set_mat4("u_MistInvModel", np.asarray(inverse_model, dtype=np.float32))
        d = np.asarray(toward_camera, dtype=np.float64)[:3]
        d = d / max(float(np.linalg.norm(d)), 1e-9)
        shader.set_vec3("u_MistToCamera", *(float(v) for v in d))

    def delete(self) -> None:
        if self.texture_id:
            import OpenGL.GL as gl
            gl.glDeleteTextures([self.texture_id])
            self.texture_id = 0
