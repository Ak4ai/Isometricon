"""Navegação do modo apresentação e o que a cena de cada slide pede à câmera. Sem OpenGL: testável à parte."""
from dataclasses import dataclass
import math
from typing import Iterable

import glfw
import numpy as np

from src.interactive.presentation_slides import SLIDES, Slide

PRESENTATION_SEED = 329436  # terreno com grama, água e encosta perto do início (sem --seed)
BASE_ZOOM = 1.3            # a apresentação começa um pouco mais afastada que o jogo
VIEW_SECONDS = 3.0        # tempo de cada modo de visualização do shader no ciclo
WOBBLE_PERIOD = 6.0


@dataclass(frozen=True)
class CameraTargets:
    yaw_degrees: float
    ortho_size: float
    perspective: bool
    debug_view: int
    wireframe: bool


def _smoothstep(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


class Presentation:
    """O slide e o passo atuais; ``key`` diz se a tecla foi da apresentação (e não deve chegar ao jogo)."""

    def __init__(self, slides: tuple[Slide, ...] = SLIDES, start: int = 0) -> None:
        self.slides = slides
        self.index = min(max(int(start), 0), len(slides) - 1)
        self.step = 0
        self.card_visible = True
        self.fullscreen = True     # o main.py acompanha: a apresentação abre em tela cheia e o F11 alterna
        self.active = True
        self.elapsed = 0.0

    @property
    def slide(self) -> Slide:
        return self.slides[self.index]

    def _go(self, index: int, step: int = 0) -> None:
        if index != self.index:
            self.elapsed = 0.0
        self.index, self.step = index, step

    def next(self) -> None:
        if self.step + 1 < self.slide.steps:
            self.step += 1
        elif self.index + 1 < len(self.slides):
            self._go(self.index + 1)

    def prev(self) -> None:
        if self.step > 0:
            self.step -= 1
        elif self.index > 0:
            self._go(self.index - 1, self.slides[self.index - 1].steps - 1)

    def first(self) -> None:
        self._go(0)

    def last(self) -> None:
        self._go(len(self.slides) - 1)

    def update(self, dt: float) -> None:
        self.elapsed += max(float(dt), 0.0)

    def key(self, key: int, action: int) -> bool:
        if not self.active or action not in (glfw.PRESS, glfw.REPEAT):
            return False
        if key in (glfw.KEY_RIGHT, glfw.KEY_SPACE, glfw.KEY_PAGE_DOWN):
            self.next()
        elif key in (glfw.KEY_LEFT, glfw.KEY_PAGE_UP):
            self.prev()
        elif key == glfw.KEY_HOME:
            self.first()
        elif key == glfw.KEY_END:
            self.last()
        elif key == glfw.KEY_H:
            if action == glfw.PRESS:
                self.card_visible = not self.card_visible
        elif key == glfw.KEY_F11:
            if action == glfw.PRESS:
                self.fullscreen = not self.fullscreen
        elif key == glfw.KEY_ESCAPE:
            if action == glfw.PRESS:
                self.active = False
        else:
            return False
        return True

    def camera_targets(self, base_yaw: float, base_ortho: float) -> CameraTargets:
        """Yaw, ortho_size e modos que a cena do slide pede agora (função só do tempo no slide)."""
        cue, t = self.slide.scene, self.elapsed
        yaw = base_yaw + cue.spin * t
        if cue.yaw_steps > 0.0:
            yaw += 45.0 * math.floor(t / cue.yaw_steps)
        factor = 1.0
        if cue.zoom is not None:
            start, end, seconds = cue.zoom
            factor = start + (end - start) * _smoothstep(t / seconds if seconds > 0 else 1.0)
        factor *= 1.0 + cue.wobble * math.sin(2.0 * math.pi * t / WOBBLE_PERIOD)
        perspective = cue.perspective_every > 0.0 and int(t // cue.perspective_every) % 2 == 1
        view = cue.views[int(t // VIEW_SECONDS) % len(cue.views)] if cue.views else 0
        return CameraTargets(yaw, base_ortho * factor, perspective, view, cue.wireframe)


def face_stats(chunk_blocks: Iterable[np.ndarray], mesh_index_counts: Iterable[int]) -> tuple[int, int]:
    """(faces desenhadas, faces possíveis): 6 índices por face na malha; 6 faces por cubo sólido nos chunks."""
    from src.world.block import CUBE_LUT
    drawn = sum(int(count) // 6 for count in mesh_index_counts)
    possible = 6 * sum(int(np.count_nonzero(CUBE_LUT[blocks])) for blocks in chunk_blocks)
    return drawn, possible
