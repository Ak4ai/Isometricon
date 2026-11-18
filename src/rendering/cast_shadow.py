"""A sombra dos personagens (o seu e os NPCs) em qualquer superfície: chão, parede, o degrau de uma descida.

As sombras do sol do terreno (``sun_shadows``) são raios pelos blocos; um personagem não é bloco e não entra nelas.
Aqui, a cada quadro, os personagens são desenhados vistos do sol numa textura de profundidade (um mapa de sombra
ortográfico em volta do jogador). Depois, ao iluminar o mundo, o shader leva cada pixel de bloco ao espaço do sol e
compara: se um personagem está entre ele e o sol, o sol que chega ali cai (``u_CharShadow*`` no shader). Como a
conta é feita no pixel do bloco, a sombra dobra no degrau e sobe na parede como a de um bloco faria.

A borda é nítida; a opacidade cai com a distância até o que tapa (forte nos pés, clara na cabeça); com o sol
baixo, comprida, ela some em ``FADE_MAX`` blocos em vez de virar uma faixa pelo chão. Ela só tira o
sol que chega ao lugar e, numa caverna ou dentro de casa, fica bem mais clara.

Tudo no espaço desenhado (o da matriz ``model`` da cena), onde já está o ``u_LightDir`` do terreno.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

import numpy as np

from src.math import mat4_look_at, mat4_ortho

SHADOW_MAP_UNIT = 5   # unidade de textura do mapa (0 atlas, 2 cômodo, 3 e 4 sombras do sol)
SIZE = 2048           # o lado do mapa, em texels
RADIUS = 24.0         # meia largura da área coberta, em blocos (um texel ~ 0,02 bloco)
DISTANCE = 48.0       # o quanto o "olho" do sol fica atrás do jogador
DEPTH = 110.0         # a profundidade coberta a partir do olho
STRENGTH = 1.0        # o quanto do sol a sombra de um personagem tira (vezes a força das sombras nas configurações)
FADE_MAX = 4.0        # a sombra esmaece até sumir em no máximo esta distância ao longo do raio, em blocos: com o sol
                      # baixo ela ficaria comprida demais (uma faixa pelo chão); assim, só a parte perto dos pés fica
TAIL = 0.15           # a opacidade no fim do esmaecido de uma sombra curta (a comprida vai a 0)

# do espaço de recorte [-1, 1] para as coordenadas da textura [0, 1]
CLIP_TO_TEXTURE = np.array([[0.5, 0, 0, 0.5], [0, 0.5, 0, 0.5], [0, 0, 0.5, 0.5], [0, 0, 0, 1]], dtype=np.float32)


def sun_camera(center: Sequence[float], sun: Sequence[float]) -> np.ndarray:
    """Projeção x vista do sol, olhando para ``center`` ao longo do raio do sol (``sun`` aponta para o sol)."""
    sun = np.asarray(sun, dtype=np.float32)
    sun = sun / max(float(np.linalg.norm(sun)), 1e-9)
    center = np.asarray(center, dtype=np.float32)[:3]
    up = np.array([0.0, 1.0, 0.0], dtype=np.float32) if abs(float(sun[1])) < 0.99 \
        else np.array([0.0, 0.0, 1.0], dtype=np.float32)
    view = mat4_look_at(center + sun * DISTANCE, center, up)
    return mat4_ortho(-RADIUS, RADIUS, -RADIUS, RADIUS, 0.5, DEPTH) @ view


def fade_profile(length: float) -> tuple:
    """(até onde esmaece, opacidade no fim) para uma sombra de ``length`` blocos ao longo do raio: a curta esmaece
    pelo corpo e fica a ``TAIL`` na cabeça; a comprida esmaece em ``FADE_MAX`` blocos e some."""
    fade = min(float(length), FADE_MAX)
    tail = TAIL * max(0.0, min(1.0, (FADE_MAX + 0.5 - float(length)) / 1.0))
    return fade, tail


class CharacterShadowMap:
    """O mapa de sombra dos personagens: desenha-os vistos do sol e liga a leitura dele no shader do mundo."""

    def __init__(self, strength: float = 1.0) -> None:
        self.strength = float(strength)
        self.texture_id = 0
        self.fbo = 0
        self.matrix = np.eye(4, dtype=np.float32)   # do espaço desenhado para a textura do mapa
        self.has_casters = False
        self.length = 6.0   # a distância, ao longo do raio do sol, dos pés até a sombra da cabeça (render a calcula)

    def _ensure(self) -> None:
        if self.fbo:
            return
        import OpenGL.GL as gl
        self.texture_id = gl.glGenTextures(1)
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_MAP_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, SIZE, SIZE, 0, gl.GL_DEPTH_COMPONENT,
                        gl.GL_FLOAT, None)
        for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST),
                            (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        previous = int(gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING))
        self.fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_TEXTURE_2D, self.texture_id, 0)
        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, previous)

    def render(self, shader, center: Sequence[float], sun: Sequence[float],
               casters: Iterable[Callable[[], None]]) -> None:
        """Desenha cada personagem (``caster()``: o draw de sempre dele) no mapa, visto do sol, em volta de ``center``
        (espaço desenhado). Deixa ``u_View`` e ``u_Projection`` com a câmera do sol: quem chama devolve as dele."""
        import OpenGL.GL as gl
        casters = list(casters)
        self.has_casters = bool(casters)
        if not casters:
            return
        self._ensure()
        # um personagem de 1,8 m: a cabeça fica a 1,8 / seno da altura do sol, ao longo do raio, do chão que ela tapa
        rise = abs(float(sun[1])) / max(float(np.linalg.norm(np.asarray(sun, dtype=np.float64))), 1e-9)
        self.length = min(1.8 / max(rise, 0.15), 12.0)
        camera = sun_camera(center, sun)
        self.matrix = CLIP_TO_TEXTURE @ camera
        previous = int(gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING))
        viewport = [int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)]
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, SIZE, SIZE)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        shader.set_mat4("u_View", np.eye(4, dtype=np.float32))
        shader.set_mat4("u_Projection", camera)
        shader.set_bool("u_CastShadow", True)   # o shader só descarta o transparente e grava a profundidade
        try:
            for caster in casters:
                gl.glDisable(gl.GL_CULL_FACE)    # as duas faces: a sombra não some pelo lado de uma malha aberta
                gl.glDepthMask(gl.GL_TRUE)
                caster()
        finally:
            shader.set_bool("u_CastShadow", False)
            gl.glEnable(gl.GL_CULL_FACE)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, previous)
            gl.glViewport(*viewport)

    def apply(self, shader) -> None:
        """Liga a leitura do mapa no shader do mundo (antes de desenhar o terreno e as construções)."""
        if not self.has_casters or not self.fbo:
            self.disable(shader)
            return
        import OpenGL.GL as gl
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_MAP_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture_id)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        shader.set_int("u_CharShadowMap", SHADOW_MAP_UNIT)
        shader.set_mat4("u_CharShadowMatrix", self.matrix)
        shader.set_float("u_CharShadowTexel", 1.0 / SIZE)
        shader.set_float("u_CharShadowDepth", DEPTH - 0.5)   # a diferença de profundidade do mapa, em blocos
        fade, tail = fade_profile(self.length)
        shader.set_float("u_CharShadowLength", fade)
        shader.set_float("u_CharShadowTail", tail)
        shader.set_float("u_CharShadowStrength", STRENGTH * max(0.0, min(1.0, self.strength)))

    @staticmethod
    def disable(shader) -> None:
        shader.set_float("u_CharShadowStrength", 0.0)

    def delete(self) -> None:
        if not self.fbo:
            return
        import OpenGL.GL as gl
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteTextures([self.texture_id])
        self.fbo = self.texture_id = 0
