"""Envia a máscara do espaço do jogador (ver ``src/world/room_reveal.py``) ao shader do mundo.

A máscara vai como textura 3D de 1 canal (255 = espaço do jogador, 128 = casca, 0 = fora). O shader:
- escurece o que está fora do espaço (brilho exterior ``exterior``);
- descarta o que fica entre a câmera e o espaço (teto, andar de cima, terra por cima), com dither.

``level`` (0 a 1) suaviza a entrada e a saída do efeito; ao sair de um espaço a máscara antiga
continua na GPU até o efeito apagar, para o mundo voltar ao normal sem pular.
"""

from typing import Optional

import numpy as np
import OpenGL.GL as gl

from src.world.room_reveal import WINDOW, RoomMask, RoomRevealTracker

MASK_UNIT = 2          # unidade de textura da máscara (a 0 é o atlas)
FADE_HALF_LIFE = 0.12  # segundos para o efeito andar metade do caminho


class RoomRevealRenderer:
    """Mantém a textura da máscara na GPU e os uniforms do efeito."""

    def __init__(self, exterior: float = 0.12) -> None:
        self.enabled = True
        self.exterior = float(exterior)  # brilho do que está fora do espaço: 0 preto, 1 normal
        self.level = 0.0                 # intensidade suavizada, 0 a 1
        self.texture_id = 0
        self._shown: Optional[RoomMask] = None  # a máscara que está na GPU
        self._uploaded = None

    # ------------------------------------------------------------------ estado
    def update(self, dt: float, tracker: RoomRevealTracker) -> None:
        """Avança a suavização e, se há espaço novo, manda a máscara para a GPU."""
        mask = tracker.mask
        wants = self.enabled and mask is not None and mask.active
        if wants:
            self._shown = mask
        target = 1.0 if wants else 0.0
        self.level += (target - self.level) * (1.0 - 0.5 ** (max(dt, 0.0) / FADE_HALF_LIFE))
        if abs(target - self.level) < 0.002:
            self.level = target
        if self.level == 0.0 and not wants:
            self._shown = None
        if self._shown is not None and self._uploaded is not self._shown:
            self._upload(self._shown)

    def _ensure_texture(self) -> None:
        if self.texture_id:
            return
        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_3D, name, value)
        sx, sy, sz = WINDOW
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage3D(gl.GL_TEXTURE_3D, 0, gl.GL_R8, sx, sy, sz, 0, gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        np.zeros((sz, sy, sx), dtype=np.uint8))

    def _upload(self, mask: RoomMask) -> None:
        self._ensure_texture()
        sx, sy, sz = WINDOW
        # a máscara é [x, y, z]; a textura 3D quer (profundidade z, altura y, largura x)
        data = np.ascontiguousarray(mask.data.transpose(2, 1, 0))
        gl.glActiveTexture(gl.GL_TEXTURE0 + MASK_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage3D(gl.GL_TEXTURE_3D, 0, 0, 0, 0, sx, sy, sz, gl.GL_RED, gl.GL_UNSIGNED_BYTE, data)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        self._uploaded = mask

    # ------------------------------------------------------------------ desenho
    @property
    def visible(self) -> bool:
        return self.level > 0.0 and self._shown is not None

    def apply(self, shader, base_model: np.ndarray, view: np.ndarray) -> None:
        """Liga o efeito no shader do mundo (chamar antes de desenhar o terreno e as construções)."""
        if not self.visible:
            shader.set_float("u_RoomActive", 0.0)
            return
        inverse_model = np.linalg.inv(np.asarray(base_model, dtype=np.float64))
        # o shader trabalha no espaço girado pelo modelo; a máscara está no espaço do mundo
        forward_render = -np.asarray(view, dtype=np.float64)[2, :3]  # para onde a câmera olha
        view_dir = inverse_model[:3, :3] @ forward_render
        view_dir /= max(float(np.linalg.norm(view_dir)), 1e-9)
        ox, oy, oz = self._shown.origin

        gl.glActiveTexture(gl.GL_TEXTURE0 + MASK_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_RoomMask", MASK_UNIT)
        shader.set_mat4("u_RoomInvModel", inverse_model.astype(np.float32))
        shader.set_vec3("u_RoomOrigin", float(ox), float(oy), float(oz))
        shader.set_vec3("u_RoomSize", float(WINDOW[0]), float(WINDOW[1]), float(WINDOW[2]))
        shader.set_vec3("u_ViewDir", float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
        shader.set_float("u_RoomExterior", self.exterior)
        shader.set_float("u_RoomActive", float(self.level))

    @staticmethod
    def disable(shader) -> None:
        """Desliga o efeito (o personagem e o resto não devem ser escurecidos nem descartados)."""
        shader.set_float("u_RoomActive", 0.0)

    def delete(self) -> None:
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])
            self.texture_id = 0
        self._shown = self._uploaded = None
