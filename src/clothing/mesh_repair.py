"""Conserta malhas coladas: acha os triângulos que esticam quando o modelo anda, sem OpenGL.

Um modelo gerado (Meshy e parecidos) às vezes tem partes que se tocam fundidas na malha: a mão encostada na coxa, por
exemplo, forma triângulos que ligam um vértice da mão a um da perna. Os pesos de cada lado estão certos, mas quando
a mão e a perna se mexem de modos diferentes esses triângulos viram espetos esticados. ``stretched_triangles`` pose o
modelo em vários instantes do andar e marca os triângulos cujas arestas crescem demais; tirá-los deixa uma fresta
pequena no lugar do espeto.
"""

from __future__ import annotations

from typing import Iterable, List

import numpy as np

from .glb import Submesh

RATIO = 1.8          # uma aresta que fica mais de 1,8 vezes maior...
GROWTH = 0.015       # ...e ganha mais de 1,5 cm por metro e oitenta de modelo, está esticada


def skinned_positions(sub: Submesh, matrices: np.ndarray) -> np.ndarray:
    """Onde ficam os vértices de ``sub`` com as matrizes de pele ``matrices`` (J, 4, 4): a conta do shader."""
    points = np.c_[sub.vertices[:, :3].astype(np.float64), np.ones(len(sub.vertices))]
    out = np.zeros((len(points), 3))
    skin = np.asarray(matrices, dtype=np.float64)
    for k in range(sub.joints.shape[1]):
        out += sub.weights[:, k:k + 1] * np.einsum("nij,nj->ni", skin[sub.joints[:, k]], points)[:, :3]
    return out


def stretched_triangles(sub: Submesh, poses: Iterable[np.ndarray], height: float = 1.8,
                        ratio: float = RATIO, growth: float = GROWTH) -> np.ndarray:
    """Máscara (T,) dos triângulos de ``sub`` com uma aresta esticada em alguma das ``poses``."""
    triangles = sub.indices.reshape(-1, 3)
    rest = sub.vertices[:, :3].astype(np.float64)
    pairs = [(0, 1), (1, 2), (2, 0)]
    before = [np.linalg.norm(rest[triangles[:, a]] - rest[triangles[:, b]], axis=1) for a, b in pairs]
    bad = np.zeros(len(triangles), dtype=bool)
    limit = growth * height / 1.8
    for pose in poses:
        moved = skinned_positions(sub, pose)
        for (a, b), length in zip(pairs, before):
            now = np.linalg.norm(moved[triangles[:, a]] - moved[triangles[:, b]], axis=1)
            bad |= (now > ratio * np.maximum(length, 1e-4)) & (now - length > limit)
    return bad


def without(sub: Submesh, bad: np.ndarray) -> np.ndarray:
    """Os índices de ``sub`` sem os triângulos marcados em ``bad``."""
    return sub.indices.reshape(-1, 3)[~bad].reshape(-1).astype(sub.indices.dtype)


def sample_poses(animator, steps: int = 36, dt: float = 1.0 / 18.0, speed: float = 3.0) -> List[np.ndarray]:
    """As matrizes de pele de um ciclo de andar (de uma cópia do animador, que não anda de verdade)."""
    import copy
    walker = copy.deepcopy(animator)
    poses = []
    for _ in range(steps):
        walker.update(dt, speed)
        poses.append(np.array(walker.matrices, dtype=np.float64))
    return poses


__all__ = ["stretched_triangles", "without", "sample_poses", "skinned_positions"]
