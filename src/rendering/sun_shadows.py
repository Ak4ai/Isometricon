"""Sombras do sol: a textura 3D dos blocos sólidos ao redor do jogador, para o shader lançar raios.

O shader do mundo, para cada pixel, anda de ``u_ShadowSteps`` passos na direção do sol e olha, nesta textura,
se há um bloco no caminho. A janela é a mesma de ``src/world/room_reveal.py`` (48x32x48 células em volta do
jogador), então não custa uma varredura nova: usa-se a janela que o rastreador já calculou.
"""

from typing import Optional

import numpy as np
import OpenGL.GL as gl

from src.world.block import BlockType
from src.world.room_reveal import WINDOW, RoomRevealTracker

SHADOW_UNIT = 3  # unidade de textura da máscara de sombra (0 atlas, 2 máscara do espaço)


SOLID_VALUE, WATER_VALUE = 255, 128  # na textura: o shader lê sólido > 0.75 e água entre 0.25 e 0.75


def mask_values(window) -> np.ndarray:
    """O valor de cada célula da janela: sólido (bloqueia o sol), água (a luz atravessa tingida) ou ar."""
    values = np.where(window.solid, SOLID_VALUE, 0).astype(np.uint8)
    values[(window.blocks == int(BlockType.WATER)) & ~window.solid] = WATER_VALUE
    return values


class SunShadowRenderer:
    """Mantém a textura de blocos sólidos e os uniforms das sombras."""

    def __init__(self, strength: float = 1.0) -> None:
        self.enabled = True
        self.strength = float(strength)  # 0 sem sombra, 1 sombra inteira
        self.texture_id = 0
        self._uploaded = None  # as células da janela que estão na GPU
        self._origin = (0, 0, 0)

    def update(self, tracker: RoomRevealTracker) -> None:
        """Envia a janela de blocos sólidos para a GPU quando o rastreador calculou uma nova."""
        mask = tracker.mask
        if not self.enabled or mask is None or mask.window is None or mask.window is self._uploaded:
            return
        self._ensure_texture()
        sx, sy, sz = WINDOW
        # a janela é [x, y, z]; a textura 3D quer (profundidade z, altura y, largura x)
        data = np.ascontiguousarray(mask_values(mask.window).transpose(2, 1, 0))
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RED, gl.GL_UNSIGNED_BYTE, data)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self._uploaded = mask.window
        self._origin = mask.origin

    def _ensure_texture(self) -> None:
        if self.texture_id:
            return
        self.texture_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        sx, sy, sz = WINDOW
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_R8, sx, sy, sz, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx), dtype=np.uint8))
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @property
    def active(self) -> bool:
        return self.enabled and self._uploaded is not None

    def apply(self, shader, base_model: np.ndarray) -> None:
        """Liga as sombras no shader do mundo (antes de desenhar o terreno e as construções)."""
        if not self.active:
            shader.set_float("u_ShadowStrength", 0.0)
            return
        inverse_model = np.linalg.inv(np.asarray(base_model, dtype=np.float64)).astype(np.float32)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_ShadowMask", SHADOW_UNIT)
        shader.set_mat4("u_ShadowInvModel", inverse_model)
        shader.set_vec3("u_ShadowOrigin", float(self._origin[0]), float(self._origin[1]), float(self._origin[2]))
        shader.set_vec3("u_ShadowSize", float(WINDOW[0]), float(WINDOW[1]), float(WINDOW[2]))
        shader.set_float("u_ShadowStrength", self.strength)

    @staticmethod
    def disable(shader) -> None:
        shader.set_float("u_ShadowStrength", 0.0)

    def delete(self) -> None:
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
            self.texture_id = 0
        self._uploaded = None
