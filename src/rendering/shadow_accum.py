"""Sombra acumulada entre quadros (Configurações > Gráficos > Sombra acumulada).

A sombra do sol de um pixel custa até 18 raios (o cone borrado e o nítido, ver ``sunVisibility`` no shader do mundo).
O mundo e o sol quase não mudam de um quadro para o outro, então a passada de cor grava o que achou para cada pixel e,
no quadro seguinte, o mesmo ponto do mundo continua daquela média com 3 a 5 raios novos (``sunAccumulated``).

Duas texturas do tamanho da cena por quadro, alternando (uma é lida como o quadro anterior, a outra é escrita):
- RGBA16F: (borrada, nítida, quadros da borrada, quadros da nítida);
- RGBA32F: (o ponto do mundo do pixel, 1 = gravado), para reconhecer o ponto no quadro seguinte.

Uso no quadro, em volta da passada de cor (com EARLY_Z: um fragmento por pixel)::

    accum.begin(shader, scene_size, world_to_clip)   # liga SHADOW_ACCUM antes
    draw_solids()
    accum.end()
"""

from typing import List, Optional, Tuple

import numpy as np
import OpenGL.GL as gl

PREV_UNIT = 15       # o quadro anterior: as somas (Shader.EXTRA_SAMPLER_UNITS)
PREV_POS_UNIT = 16   # e os pontos do mundo
OUT_IMAGE = 0        # as unidades de imagem onde a passada escreve
OUT_POS_IMAGE = 1
_ZERO = np.zeros(4, dtype=np.float32)


class ShadowAccumulator:
    """As texturas do histórico da sombra e a matriz do quadro anterior."""

    def __init__(self) -> None:
        self._size: Optional[Tuple[int, int]] = None
        self._pairs: List[Tuple[int, int, int]] = []   # (somas, pontos, framebuffer para limpar), dois
        self.frame = 0
        self.history = False          # o par de leitura tem o quadro anterior desta cena
        self._prev_clip: Optional[np.ndarray] = None
        self._pending: Optional[np.ndarray] = None

    def reset(self) -> None:
        """Esquece o histórico (o próximo quadro traça o cone inteiro em todo pixel)."""
        self.history = False
        self._prev_clip = None

    def begin(self, shader, size: Tuple[int, int], world_to_clip) -> None:
        """Prepara a passada de cor deste quadro: limpa o par de escrita, liga o de leitura e passa ao shader a
        matriz do quadro anterior. ``world_to_clip`` é a matriz deste quadro (projeção @ vista @ modelo)."""
        size = (max(1, int(size[0])), max(1, int(size[1])))
        if size != self._size:
            self._allocate(size)
        write = self._pairs[self.frame % 2]
        read = self._pairs[(self.frame + 1) % 2]
        framebuffer = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, write[2])
        for attachment in (0, 1):     # (sem mexer na cor de limpar da cena)
            gl.glClearBufferfv(gl.GL_COLOR, attachment, _ZERO)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
        for unit, texture in ((PREV_UNIT, read[0]), (PREV_POS_UNIT, read[1])):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindImageTexture(OUT_IMAGE, write[0], 0, gl.GL_FALSE, 0, gl.GL_WRITE_ONLY, gl.GL_RGBA16F)
        gl.glBindImageTexture(OUT_POS_IMAGE, write[1], 0, gl.GL_FALSE, 0, gl.GL_WRITE_ONLY, gl.GL_RGBA32F)
        clip = np.asarray(world_to_clip, dtype=np.float32)
        history = self.history and self._prev_clip is not None
        shader.set_bool("u_AccumHistory", history)
        shader.set_mat4("u_AccumPrevClip", self._prev_clip if history else clip)
        shader.set_int("u_AccumFrame", self.frame % 65536)
        self._pending = clip

    def end(self) -> None:
        """Depois da passada: o que ela escreveu passa a ser o quadro anterior do próximo."""
        gl.glMemoryBarrier(gl.GL_TEXTURE_FETCH_BARRIER_BIT | gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
        self._prev_clip = self._pending
        self.history = self._pending is not None
        self.frame += 1

    # ------------------------------------------------------------------ recursos
    def _allocate(self, size: Tuple[int, int]) -> None:
        self.delete()
        width, height = size
        for _ in range(2):
            textures = []
            for internal, kind in ((gl.GL_RGBA16F, gl.GL_HALF_FLOAT), (gl.GL_RGBA32F, gl.GL_FLOAT)):
                texture = int(gl.glGenTextures(1))
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal, width, height, 0, gl.GL_RGBA, kind, None)
                for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                                    (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE),
                                    (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
                textures.append(texture)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            framebuffer = int(gl.glGenFramebuffers(1))
            previous = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, textures[0], 0)
            gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT1, gl.GL_TEXTURE_2D, textures[1], 0)
            gl.glDrawBuffers(2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, previous)
            self._pairs.append((textures[0], textures[1], framebuffer))
        self._size = size
        self.reset()

    def delete(self) -> None:
        """Libera as texturas (a próxima ``begin`` cria de novo)."""
        for soft, pos, framebuffer in self._pairs:
            gl.glDeleteTextures(2, [soft, pos])
            gl.glDeleteFramebuffers(1, [framebuffer])
        self._pairs = []
        self._size = None
        self.reset()
