"""A névoa de guerra do mestre (``/mestre``): o que o grupo ainda não explorou fica coberto de névoa.

Modos (``Ambience.fog_war``):

- 0: desligada.
- 1 "Revela": andando, a névoa se abre em volta do personagem e o que já foi visto fica limpo (o mapa do explorado
  é guardado no mundo).
- 2 "Em volta": só fica limpo em volta do personagem; a névoa volta a fechar atrás dele.

O explorado é guardado por bloco (x, z), em pedaços de 16 x 16, e vai para a GPU como uma textura 2D da área em
volta do jogador (``WINDOW`` blocos de lado), recentrada quando ele anda longe. O shader (``envGrade``) lê a textura
com filtro linear e mexe a borda com o ruído dos tufos de névoa, para não ficar um recorte em degraus.
"""

from __future__ import annotations

import base64
import math
from typing import Dict, Optional, Tuple

import numpy as np

PIECE = 16          # lado de um pedaço do mapa do explorado, em blocos
WINDOW = 192        # o lado da textura em volta do jogador, em blocos
RECENTER = 48       # recentra a textura quando o jogador se afasta isto do centro
RADIUS = 7.0        # o raio que o personagem enxerga (limpa), em blocos
UNIT = 6            # a unidade de textura (0 atlas, 2 cômodo, 3/4 sombras, 5 sombra dos personagens)

OFF, REVEAL, AROUND = 0, 1, 2


def disk(radius: float) -> Tuple[np.ndarray, np.ndarray]:
    """Os deslocamentos (dx, dz) dos blocos dentro do raio."""
    r = int(math.ceil(radius))
    dz, dx = np.mgrid[-r:r + 1, -r:r + 1]
    inside = dx * dx + dz * dz <= radius * radius
    return dx[inside], dz[inside]


class ExploredMap:
    """O que já foi explorado, por bloco (sem GL: testável e salvável)."""

    def __init__(self) -> None:
        self.pieces: Dict[Tuple[int, int], np.ndarray] = {}
        self.revision = 0
        self._last: Optional[Tuple[int, int]] = None

    def reveal(self, x: float, z: float, radius: float = RADIUS) -> bool:
        """Marca como explorado o disco em volta de (x, z); devolve se algo mudou."""
        cell = (int(math.floor(x)), int(math.floor(z)))
        if cell == self._last:
            return False
        self._last = cell
        dx, dz = disk(radius)
        xs, zs = dx + cell[0], dz + cell[1]
        changed = False
        for px, pz in set(zip((xs // PIECE).tolist(), (zs // PIECE).tolist())):
            mask = (xs // PIECE == px) & (zs // PIECE == pz)
            piece = self.pieces.get((px, pz))
            if piece is None:
                piece = self.pieces[(px, pz)] = np.zeros((PIECE, PIECE), dtype=np.uint8)
            lx, lz = xs[mask] - px * PIECE, zs[mask] - pz * PIECE
            if not piece[lz, lx].all():
                piece[lz, lx] = 255
                changed = True
        if changed:
            self.revision += 1
        return changed

    def explored(self, x: int, z: int) -> bool:
        piece = self.pieces.get((x // PIECE, z // PIECE))
        return piece is not None and bool(piece[z - (z // PIECE) * PIECE, x - (x // PIECE) * PIECE])

    def window(self, origin_x: int, origin_z: int, size: int = WINDOW) -> np.ndarray:
        """A área [origin, origin + size) como imagem [z, x] (255 explorado, 0 não)."""
        out = np.zeros((size, size), dtype=np.uint8)
        for (px, pz), piece in self.pieces.items():
            x0, z0 = px * PIECE - origin_x, pz * PIECE - origin_z
            if x0 >= size or z0 >= size or x0 + PIECE <= 0 or z0 + PIECE <= 0:
                continue
            sx0, sz0 = max(0, -x0), max(0, -z0)
            sx1, sz1 = min(PIECE, size - x0), min(PIECE, size - z0)
            out[z0 + sz0:z0 + sz1, x0 + sx0:x0 + sx1] = piece[sz0:sz1, sx0:sx1]
        return out

    def clear(self) -> None:
        """Cobre tudo de novo."""
        self.pieces.clear()
        self.revision += 1
        self._last = None

    def to_data(self) -> Dict[str, str]:
        """Para o save do mundo: cada pedaço explorado em bits, base64."""
        return {f"{px},{pz}": base64.b64encode(np.packbits(piece > 0).tobytes()).decode("ascii")
                for (px, pz), piece in self.pieces.items() if piece.any()}

    def load(self, data: Optional[Dict[str, str]]) -> None:
        self.clear()
        for key, value in (data or {}).items():
            try:
                px, pz = (int(v) for v in key.split(","))
                bits = np.unpackbits(np.frombuffer(base64.b64decode(value), dtype=np.uint8))[:PIECE * PIECE]
                self.pieces[(px, pz)] = (bits.reshape(PIECE, PIECE) * 255).astype(np.uint8)
            except (ValueError, TypeError):
                continue
        self.revision += 1


class FogOfWar:
    """O mapa do explorado na GPU e os uniforms da névoa de guerra."""

    def __init__(self) -> None:
        self.explored = ExploredMap()
        self.texture_id = 0
        self.origin = (0, 0)
        self._uploaded = None     # (revisão, origem) que está na GPU

    def update(self, mode: int, x: float, z: float) -> None:
        if mode == REVEAL:
            self.explored.reveal(x, z)
        cx, cz = self.origin[0] + WINDOW // 2, self.origin[1] + WINDOW // 2
        if abs(x - cx) > RECENTER or abs(z - cz) > RECENTER or self.texture_id == 0:
            self.origin = (int(math.floor(x)) - WINDOW // 2, int(math.floor(z)) - WINDOW // 2)
        if mode == REVEAL and self._uploaded != (self.explored.revision, self.origin):
            self._upload()

    def _upload(self) -> None:
        import OpenGL.GL as gl
        if not self.texture_id:
            self.texture_id = gl.glGenTextures(1)
            gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
            gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, (0.0, 0.0, 0.0, 0.0))
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R8, WINDOW, WINDOW, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE, None)
        data = np.ascontiguousarray(self.explored.window(*self.origin))
        gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0, WINDOW, WINDOW, gl.GL_RED, gl.GL_UNSIGNED_BYTE, data)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self._uploaded = (self.explored.revision, self.origin)

    def apply(self, shader, mode: int, inverse_model: np.ndarray, color, center_world) -> None:
        """Os uniforms ``u_FogWar*`` (o shader do mundo e o da grade usam os mesmos nomes)."""
        shader.set_int("u_FogWar", int(mode))
        if mode == OFF:
            return
        shader.set_mat4("u_FogInvModel", np.asarray(inverse_model, dtype=np.float32))
        shader.set_vec3("u_FogWarColor", *(float(c) for c in color))
        shader.set_vec2("u_FogWarCenter", float(center_world[0]), float(center_world[1]))
        shader.set_float("u_FogWarRadius", RADIUS)
        if mode == REVEAL and self.texture_id:
            import OpenGL.GL as gl
            gl.glActiveTexture(gl.GL_TEXTURE0 + UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            shader.set_int("u_FogWarMap", UNIT)
            shader.set_vec2("u_FogWarOrigin", float(self.origin[0]), float(self.origin[1]))
            shader.set_float("u_FogWarSize", float(WINDOW))

    def delete(self) -> None:
        if self.texture_id:
            import OpenGL.GL as gl
            gl.glDeleteTextures([self.texture_id])
            self.texture_id = 0
