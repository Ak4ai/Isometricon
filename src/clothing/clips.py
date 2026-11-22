"""Os clipes de animação de um .glb (andar, parado...) e quem os toca, sem OpenGL.

O leitor (``glb.py``) guarda cada clipe como canais de translação, rotação e escala por osso. ``ClipAnimator`` escolhe o
clipe de andar e o de parado pelo nome, mistura os dois conforme o personagem anda e entrega as mesmas matrizes de pele
(``matrices``) que o ``ProceduralAnimator`` entrega: o resto do jogo não precisa saber qual dos dois está tocando.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .rig import Rig

WALK_WORDS = ("walk", "andar", "andando", "caminh", "run", "corr", "move", "locomotion")
IDLE_WORDS = ("idle", "parad", "stand", "breath", "respir", "rest", "wait")


def quaternion_matrices(q: np.ndarray) -> np.ndarray:
    """(J, 4) quaternions (x, y, z, w) -> (J, 3, 3) rotações."""
    q = np.asarray(q, dtype=np.float64)
    q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-12)
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    out = np.empty((len(q), 3, 3))
    out[:, 0] = np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], axis=1)
    out[:, 1] = np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], axis=1)
    out[:, 2] = np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], axis=1)
    return out


def compose(t: np.ndarray, q: np.ndarray, s: np.ndarray) -> np.ndarray:
    """(J, 4, 4) matrizes a partir de translação, rotação (quaternion) e escala por osso."""
    matrices = np.tile(np.identity(4), (len(t), 1, 1))
    matrices[:, :3, :3] = quaternion_matrices(q) * np.asarray(s)[:, None, :]
    matrices[:, :3, 3] = t
    return matrices


def decompose(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Translação, quaternion (x, y, z, w) e escala de uma matriz 4x4 (sem cisalhamento)."""
    t = matrix[:3, 3].copy()
    scale = np.linalg.norm(matrix[:3, :3], axis=0)
    scale[scale < 1e-12] = 1.0
    r = matrix[:3, :3] / scale[None, :]
    trace = r[0, 0] + r[1, 1] + r[2, 2]
    if trace > 0:
        k = 2.0 * np.sqrt(trace + 1.0)
        q = np.array([(r[2, 1] - r[1, 2]) / k, (r[0, 2] - r[2, 0]) / k, (r[1, 0] - r[0, 1]) / k, k / 4.0])
    else:
        i = int(np.argmax(np.diag(r)))
        j, k_ = (i + 1) % 3, (i + 2) % 3
        k = 2.0 * np.sqrt(max(1.0 + r[i, i] - r[j, j] - r[k_, k_], 1e-12))
        q = np.zeros(4)
        q[i] = k / 4.0
        q[j] = (r[j, i] + r[i, j]) / k
        q[k_] = (r[k_, i] + r[i, k_]) / k
        q[3] = (r[k_, j] - r[j, k_]) / k
    return t, q / max(np.linalg.norm(q), 1e-12), scale


def slerp(a: np.ndarray, b: np.ndarray, u: float) -> np.ndarray:
    """Interpola dois quaternions (ou duas listas deles, ``u`` único)."""
    dot = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(dot < 0, -b, b)
    dot = np.abs(dot)
    near = dot > 0.9995
    theta = np.arccos(np.clip(dot, -1.0, 1.0))
    sin = np.maximum(np.sin(theta), 1e-9)
    mixed = (np.sin((1 - u) * theta) / sin) * a + (np.sin(u * theta) / sin) * b
    linear = a + u * (b - a)
    out = np.where(near, linear, mixed)
    return out / np.maximum(np.linalg.norm(out, axis=-1, keepdims=True), 1e-12)


@dataclass
class RestPose:
    """A pose de montagem de cada osso em translação/rotação/escala, e o que fica entre ele e o osso pai do esqueleto."""
    translation: np.ndarray      # (J, 3)
    rotation: np.ndarray         # (J, 4)
    scale: np.ndarray            # (J, 3)
    prefix: np.ndarray           # (J, 4, 4): nós que não são ossos entre o osso e o pai (ou o mundo, nas raízes)


@dataclass
class Channel:
    joint: int
    path: str                    # "translation" | "rotation" | "scale"
    times: np.ndarray            # (K,) crescente
    values: np.ndarray           # (K, 3 ou 4)
    step: bool = False


@dataclass
class Clip:
    name: str
    duration: float
    channels: List[Channel] = field(default_factory=list)

    def sample(self, time: float, rest: RestPose, loop: bool = True) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(translação, rotação, escala) de todos os ossos em ``time``; o que o clipe não mexe fica como na montagem."""
        t, q, s = rest.translation.copy(), rest.rotation.copy(), rest.scale.copy()
        if self.duration > 1e-9:
            time = time % self.duration if loop else min(max(time, 0.0), self.duration)
        for ch in self.channels:
            k = int(np.searchsorted(ch.times, time, side="right")) - 1
            if k < 0:
                value = ch.values[0]
            elif k >= len(ch.times) - 1:
                value = ch.values[-1]
            elif ch.step:
                value = ch.values[k]
            else:
                u = float((time - ch.times[k]) / max(ch.times[k + 1] - ch.times[k], 1e-12))
                a, b = ch.values[k], ch.values[k + 1]
                value = slerp(a, b, u) if ch.path == "rotation" else a + u * (b - a)
            target = {"translation": t, "rotation": q, "scale": s}[ch.path]
            target[ch.joint] = value
        return t, q, s


def pick_clips(names: Sequence[str]) -> Tuple[Optional[int], Optional[int]]:
    """Os índices do clipe de andar e do de parado, pelo nome. Um clipe só, sem nome que diga, vale como o de andar."""
    def find(words, exclude=()):
        for i, name in enumerate(names):
            low = name.lower()
            if any(w in low for w in words) and i not in exclude:
                return i
        return None

    walk = find(WALK_WORDS)
    idle = find(IDLE_WORDS, exclude=() if walk is None else (walk,))
    if walk is None and idle is None and names:
        walk = 0
    return walk, idle


class ClipAnimator:
    """Toca o clipe de andar e o de parado de um modelo, como o ``ProceduralAnimator`` toca os seus movimentos."""

    REFERENCE_SPEED = 3.0
    profile = "clipes"

    def __init__(self, rig: Rig, rest: RestPose, clips: Sequence[Clip], walk: Optional[int] = None,
                 idle: Optional[int] = None, lock_root: bool = True) -> None:
        self.rig, self.rest, self.clips = rig, rest, list(clips)
        self.walk_clip = None if walk is None else self.clips[walk]
        self.idle_clip = None if idle is None else self.clips[idle]
        self.lock_root = lock_root
        self.time = 0.0
        self.walk = 0.0
        self._walk_time = 0.0
        self._base_inverse = np.linalg.inv(rig.base)
        self._matrices = self._pose(0.0, 0.0)

    @property
    def matrices(self) -> np.ndarray:
        return self._matrices

    @property
    def names(self) -> Tuple[Optional[str], Optional[str]]:
        return (self.walk_clip.name if self.walk_clip else None, self.idle_clip.name if self.idle_clip else None)

    def update(self, dt: float, speed: float = 0.0) -> np.ndarray:
        dt = max(float(dt), 0.0)
        self.time += dt
        target = min(max(speed / self.REFERENCE_SPEED, 0.0), 1.0) if self.walk_clip is not None else 0.0
        self.walk += (target - self.walk) * (1.0 - 0.5 ** (dt / 0.10))
        if abs(target - self.walk) < 0.002:
            self.walk = target
        if self.walk > 0.02:
            self._walk_time += dt * min(max(speed / self.REFERENCE_SPEED, 0.6), 1.6)
        self._matrices = self._pose(self.time, self._walk_time)
        return self._matrices

    def _pose(self, idle_time: float, walk_time: float) -> np.ndarray:
        rest = self.rest
        t, q, s = (self.idle_clip.sample(idle_time, rest) if self.idle_clip is not None
                   else (rest.translation, rest.rotation, rest.scale))
        if self.walk_clip is not None and self.walk > 0.0:
            t2, q2, s2 = self.walk_clip.sample(walk_time, rest)
            w = self.walk
            t, s = t + w * (t2 - t), s + w * (s2 - s)
            q = slerp(q, q2, w)
        local = rest.prefix @ compose(t, q, s)
        if self.lock_root:   # o andar não leva o modelo embora: a raiz fica onde estava na horizontal
            for root in self.rig.roots:
                placed = self.rig.base @ local[root]
                placed[0, 3] = self.rig.rest_local[root][0, 3]
                placed[2, 3] = self.rig.rest_local[root][2, 3]
                local[root] = self._base_inverse @ placed
        return self.rig.solve_local(local).astype(np.float32)


__all__ = ["Clip", "Channel", "RestPose", "ClipAnimator", "pick_clips", "compose", "decompose"]
