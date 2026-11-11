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
from .clips import ClipAnimator, pick_clips
from .procedural import ProceduralAnimator, Roles, auto_roles

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
        self.animator = None   # ProceduralAnimator ou ClipAnimator
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

    @property
    def rig(self):
        """O esqueleto do modelo (já na escala e no sentido do jogo), ou ``None`` se ele não tem."""
        return self.model.rig

    # ------------------------------------------------------------------ animação
    def animate(self, roles: Optional[Roles] = None, profile: Optional[str] = None) -> Optional[Roles]:
        """Liga a animação dos ossos.

        Se o arquivo traz clipes de animação e ``profile`` é ``None`` ou ``"clipes"``, toca os clipes (andar e parado)
        e devolve ``None``. Senão a animação é procedural: sem ``roles`` os papéis são achados pela forma do esqueleto.
        """
        if self.rig is None:
            raise ModelError("Este modelo não tem esqueleto: não dá para animar os ossos.")
        wants_clips = profile == "clipes" or (profile is None and roles is None)
        if profile == "clipes" and not self.clips_available:
            raise ModelError("Este arquivo não traz clipes de animação para os ossos dele.")
        if wants_clips and self.clips_available:
            walk, idle = pick_clips([c.name for c in self.model.clips])
            self.animator = ClipAnimator(self.rig, self.model.rest_pose, self.model.clips, walk, idle)
            return None
        roles = roles or auto_roles(self.rig, self.height)
        self.animator = ProceduralAnimator(self.rig, roles, self.height, None if profile == "clipes" else profile)
        return roles

    @property
    def clips_available(self) -> bool:
        return bool(self.model.clips) and self.model.rest_pose is not None

    def update(self, dt: float, speed: float = 0.0) -> None:
        """Avança a animação ``dt`` segundos, com o modelo andando a ``speed`` m/s."""
        if self.animator is not None:
            self.animator.update(dt, speed)

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
            mesh = TexturedMesh(vertices, sub.indices)
            if sub.joints is not None:
                mesh.set_skin(sub.joints.astype(np.float32), sub.weights)   # a malha fica na pose de montagem
            self.parts.append(_Part(sub.name, mesh, texture, float(sub.color[3]), sub.alpha_mode == "BLEND"))

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
        posed = self.animator is not None
        shader.set_bool("u_Skinned", posed)
        if posed:
            shader.set_mat4_array("u_Bones", self.animator.matrices)
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
        shader.set_bool("u_Skinned", False)

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
