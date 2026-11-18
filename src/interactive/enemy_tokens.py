"""As miniaturas dos inimigos no tabuleiro, os anéis do combate (alvo, vez, movimento que sobra) e o rastro do personagem.

Cada criatura vira uma peça de mesa como a do personagem (``create_token_mesh``): base de ardósia, corpo na cor da
criatura, cabeça e dois olhos virados para onde ela olha; a altura e a largura vêm da ficha. Ao levar um golpe a peça
pisca vermelho; caída, afunda no chão. Os vértices saem de ``miniature_vertices`` (sem OpenGL, testável); as malhas
são criadas na primeira vez que cada uma é desenhada.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.combat.bestiary import Creature
from src.interactive.token_system import _build_cylinder, _build_disc
from src.math import mat4_rotate_y, mat4_translate

SLICES = 14
FLASH = (0.95, 0.15, 0.12)


def _shade(color: Tuple[float, float, float], k: float) -> Tuple[float, float, float]:
    return tuple(max(0.0, min(1.0, c * k)) for c in color)


def miniature_vertices(creature: Creature, flash: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """(vértices, índices) da miniatura; ``flash``: a versão toda vermelha do golpe."""
    v: List[list] = []
    i: List[int] = []
    width = max(0.6, creature.width)
    scale = width / 0.6
    body = FLASH if flash else tuple(c / 255.0 for c in creature.color)
    base = FLASH if flash else (0.22, 0.24, 0.28)
    rim = FLASH if flash else (0.55, 0.10, 0.10)          # o anel dos inimigos é vermelho (o do herói é dourado)
    radius = 0.36 * scale
    _build_disc(radius, 0.005, SLICES, -1.0, base, v, i)
    _build_cylinder(radius, radius, 0.005, 0.12, SLICES, base, v, i)
    _build_disc(radius, 0.12, SLICES, 1.0, base, v, i)
    _build_cylinder(radius * 0.94, radius * 0.94, 0.12, 0.16, SLICES, rim, v, i)
    _build_disc(radius * 0.94, 0.16, SLICES, 1.0, rim, v, i)
    h = max(0.6, creature.height)
    neck = 0.16 + (h - 0.16) * 0.66
    _build_cylinder(0.26 * scale, 0.16 * scale, 0.16, neck, SLICES, body, v, i)
    head = _shade(body, 1.15)
    _build_cylinder(0.16 * scale, 0.18 * scale, neck, neck + (h - neck) * 0.55, SLICES, head, v, i)
    _build_cylinder(0.18 * scale, 0.11 * scale, neck + (h - neck) * 0.55, h, SLICES, head, v, i)
    _build_disc(0.11 * scale, h, SLICES, 1.0, head, v, i)
    eye = FLASH if flash else (0.95, 0.85, 0.20)
    ey = neck + (h - neck) * 0.45
    ez = 0.19 * scale
    for side in (-1.0, 1.0):
        x0 = side * 0.04 * scale
        x1 = side * 0.10 * scale
        start = len(v)
        for x, y in ((min(x0, x1), ey), (max(x0, x1), ey), (max(x0, x1), ey + 0.05), (min(x0, x1), ey + 0.05)):
            v.append([x, y, ez, 0.0, 0.0, 1.0, 0.5, 0.5, *eye])
        i.extend([start, start + 1, start + 2, start + 2, start + 3, start])
    return np.array(v, dtype=np.float32), np.array(i, dtype=np.uint32)


def ring_vertices(radius: float, thickness: float, color: Tuple[float, float, float],
                  segments: int = 48) -> Tuple[np.ndarray, np.ndarray]:
    """Um anel deitado no chão (y = 0) de raio ``radius``."""
    v: List[list] = []
    idx: List[int] = []
    inner = max(0.0, radius - thickness)
    for s in range(segments + 1):
        a = 2.0 * math.pi * s / segments
        ca, sa = math.cos(a), math.sin(a)
        v.append([inner * ca, 0.0, inner * sa, 0.0, 1.0, 0.0, 0.5, 0.5, *color])
        v.append([radius * ca, 0.0, radius * sa, 0.0, 1.0, 0.0, 0.5, 0.5, *color])
    for s in range(segments):
        a, b, c, d = 2 * s, 2 * s + 1, 2 * s + 2, 2 * s + 3
        idx.extend([a, c, b, b, c, d])
    return np.array(v, dtype=np.float32), np.array(idx, dtype=np.uint32)


HOVER_COLOR = (1.0, 0.95, 0.85)   # o anel do inimigo sob o mouse
TRAIL_COLOR = (0.35, 0.85, 1.0)
TRAIL_SMALL, TRAIL_BIG = 0.07, 0.15    # raio do ponto mais antigo e do mais novo do rastro


def dot_vertices(radius: float, color: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Um disco deitado no chão (y = 0): um ponto do rastro."""
    v: List[list] = []
    i: List[int] = []
    _build_disc(radius, 0.0, 10, 1.0, color, v, i)
    return np.array(v, dtype=np.float32), np.array(i, dtype=np.uint32)


def trail_sizes(count: int) -> List[float]:
    """O raio de cada ponto do rastro, do mais antigo (pequeno) ao mais novo (grande)."""
    if count <= 1:
        return [TRAIL_BIG] * count
    return [TRAIL_SMALL + (TRAIL_BIG - TRAIL_SMALL) * k / (count - 1) for k in range(count)]


def token_matrix(position: Sequence[float], yaw: float, sink: float = 0.0) -> np.ndarray:
    return mat4_translate(float(position[0]), float(position[1]) - sink, float(position[2])) @ mat4_rotate_y(yaw)


class EnemyTokenRenderer:
    """Desenha as miniaturas e os anéis com o shader do mundo (a mesma textura branca 1x1 da miniatura do herói)."""

    def __init__(self) -> None:
        self._meshes: Dict[Tuple[str, bool], Any] = {}
        self._rings: Dict[Tuple[int, str], Any] = {}
        self._dots: Dict[int, Any] = {}

    def _mesh(self, creature: Creature, flash: bool):
        key = (creature.key, flash)
        if key not in self._meshes:
            from src.rendering.mesh import TexturedMesh
            self._meshes[key] = TexturedMesh(*miniature_vertices(creature, flash))
        return self._meshes[key]

    def _ring(self, radius: float, color_name: str, color: Tuple[float, float, float], thickness: float):
        key = (int(round(radius * 4)), color_name)
        if key not in self._rings:
            if len(self._rings) > 64:
                for mesh in self._rings.values():
                    mesh.delete()
                self._rings.clear()
            from src.rendering.mesh import TexturedMesh
            self._rings[key] = TexturedMesh(*ring_vertices(key[0] / 4.0, thickness, color))
        return self._rings[key]

    def _dot(self, radius: float):
        key = int(round(radius * 100))
        if key not in self._dots:
            from src.rendering.mesh import TexturedMesh
            self._dots[key] = TexturedMesh(*dot_vertices(key / 100.0, TRAIL_COLOR))
        return self._dots[key]

    def draw_trail(self, shader: Any, model: np.ndarray, trail: Sequence[Sequence[float]]) -> None:
        """O rastro do personagem na vez dele: um ponto a cada passo, os mais antigos menores."""
        for point, radius in zip(trail, trail_sizes(len(trail))):
            shader.set_mat4("u_Model", model @ mat4_translate(point[0], point[1] + 0.035, point[2]))
            self._dot(radius).draw()

    def draw(self, shader: Any, model: np.ndarray, controller) -> None:
        import OpenGL.GL as gl
        from src.interactive.combat_controller import FALL_SECONDS
        session = controller.session
        gl.glDisable(gl.GL_CULL_FACE)
        if session is not None and controller.trail:
            self.draw_trail(shader, model, controller.trail[:-1])   # o último ponto fica sob os pés
        for enemy in controller.enemies:
            sink = enemy.creature.height * min(1.0, enemy.fallen / FALL_SECONDS) if enemy.fallen else 0.0
            shader.set_mat4("u_Model", model @ token_matrix(enemy.shown, enemy.yaw, sink))
            self._mesh(enemy.creature, enemy.flash > 0.0 and int(enemy.flash * 20) % 2 == 0).draw()
            if controller.hover == enemy.id and not enemy.fallen:   # o mouse em cima: um anel claro mais largo
                shader.set_mat4("u_Model", model @ mat4_translate(enemy.shown[0], enemy.shown[1] + 0.025,
                                                                  enemy.shown[2]))
                self._ring(0.7 * max(1.0, enemy.creature.width / 0.6), "hover", HOVER_COLOR, 0.06).draw()
            if session is None or enemy.fallen:
                continue
            ring = None
            if session.current.id == enemy.id:
                ring = self._ring(0.55 * max(1.0, enemy.creature.width / 0.6), "vez", (1.0, 0.78, 0.2), 0.08)
            elif session.target_id == enemy.id:
                ring = self._ring(0.55 * max(1.0, enemy.creature.width / 0.6), "alvo", (0.95, 0.2, 0.2), 0.08)
            if ring is not None:
                shader.set_mat4("u_Model", model @ mat4_translate(enemy.shown[0], enemy.shown[1] + 0.03,
                                                                  enemy.shown[2]))
                ring.draw()
        if session is not None and controller.is_player_turn and controller.player_position is not None:
            p = controller.player_position
            left = session.movement_left
            if left > 0.05:
                ring = self._ring(left, "movimento", (0.35, 0.85, 1.0), 0.07)
                shader.set_mat4("u_Model", model @ mat4_translate(p[0], p[1] + 0.04, p[2]))
                ring.draw()
            reach = session.current.reach
            if reach < 15:
                ring = self._ring(reach, "alcance", (0.95, 0.35, 0.3), 0.04)
                shader.set_mat4("u_Model", model @ mat4_translate(p[0], p[1] + 0.05, p[2]))
                ring.draw()
        gl.glEnable(gl.GL_CULL_FACE)

    def delete(self) -> None:
        for mesh in list(self._meshes.values()) + list(self._rings.values()) + list(self._dots.values()):
            mesh.delete()
        self._meshes.clear()
        self._rings.clear()
        self._dots.clear()
