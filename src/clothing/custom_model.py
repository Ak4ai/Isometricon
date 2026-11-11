"""Um modelo personalizado (.glb) como personagem: lê, normaliza e desenha com o shader dos personagens.

Fase 1: modelo estático, na pose do arquivo. A interface é a mínima que o resto do jogo usa de um avatar
(``draw``, ``delete``, ``is_loading``), para entrar no lugar do ``CharacterModel`` nas fases seguintes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .glb import GlbModel, ModelError, Submesh, load_model, parse_model

DEFAULT_HEIGHT = 1.8   # altura, em metros, a que o modelo é normalizado (o jogo usa metros)


@dataclass
class _Part:
    name: str
    mesh: object          # TexturedMesh
    texture_id: int
    alpha: float
    blend: bool


class CustomModel:
    """Um ``GlbModel`` normalizado e enviado à GPU."""

    is_loading = False   # o resto do jogo pergunta; o modelo é lido de uma vez

    def __init__(self, model: GlbModel, height: float = DEFAULT_HEIGHT, yaw_turns: int = 0,
                 create_gl: bool = True, name: str = "modelo") -> None:
        self.name = name
        self.warnings = list(model.warnings)
        self.height = float(height)
        self.model = model.normalize(self.height, yaw_turns)
        self.parts: List[_Part] = []
        self._white: int = 0
        if create_gl:
            self.upload()

    # ------------------------------------------------------------------ criação
    @classmethod
    def from_file(cls, path: str, height: float = DEFAULT_HEIGHT, yaw_turns: int = 0,
                  create_gl: bool = True) -> "CustomModel":
        """Lê o arquivo (``ModelError`` se não serve) e devolve o modelo pronto."""
        return cls(load_model(path), height, yaw_turns, create_gl, name=os.path.splitext(os.path.basename(path))[0])

    @classmethod
    def from_bytes(cls, data: bytes, **options) -> "CustomModel":
        return cls(parse_model(data), **options)

    @property
    def triangles(self) -> int:
        return self.model.triangles

    def bounds(self):
        return self.model.bounds()

    # ------------------------------------------------------------------ GPU
    def upload(self) -> None:
        """Cria as malhas e as texturas na GPU (precisa de contexto OpenGL)."""
        from src.rendering.mesh import TexturedMesh

        self.delete()
        self._white = self._texture(None)
        for sub in self.model.submeshes:
            vertices = sub.vertices.copy()
            vertices[:, 8:11] *= np.asarray(sub.color[:3], dtype=np.float32)   # o fator de cor do material
            texture = self._texture(sub.image) if sub.image is not None else self._white
            self.parts.append(_Part(sub.name, TexturedMesh(vertices, sub.indices), texture, float(sub.color[3]),
                                    sub.alpha_mode == "BLEND"))

    def _texture(self, image) -> int:
        import OpenGL.GL as gl

        if image is None:
            data, size = np.full((1, 1, 4), 255, dtype=np.uint8), (1, 1)
        else:
            data, size = np.asarray(image, dtype=np.uint8), image.size
        texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, size[0], size[1], 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
        gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)
        return int(texture)

    def draw(self, shader, base_model: np.ndarray) -> None:
        """Desenha o modelo com ``base_model`` (os pés ficam na origem dele, de frente para +z)."""
        import OpenGL.GL as gl

        gl.glDisable(gl.GL_CULL_FACE)  # os modelos de fora nem sempre têm o sentido das faces que o jogo espera
        shader.set_bool("u_Skinned", False)
        shader.set_mat4("u_Model", np.asarray(base_model, dtype=np.float32))
        shader.set_int("u_TextureAtlas", 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        for part in self.parts:
            gl.glBindTexture(gl.GL_TEXTURE_2D, part.texture_id)
            shader.set_float("u_Alpha", part.alpha if part.blend else 1.0)
            if part.blend:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            part.mesh.draw()
            if part.blend:
                gl.glDisable(gl.GL_BLEND)
        shader.set_float("u_Alpha", 1.0)

    def delete(self) -> None:
        import OpenGL.GL as gl

        textures = {p.texture_id for p in self.parts}
        if self._white:
            textures.add(self._white)
        for part in self.parts:
            part.mesh.delete()
        if textures:
            gl.glDeleteTextures(len(textures), list(textures))
        self.parts, self._white = [], 0


__all__ = ["CustomModel", "ModelError", "DEFAULT_HEIGHT"]
