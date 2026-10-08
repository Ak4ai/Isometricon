"""O pincel de pele da tela de criação: pintar, sobre o personagem, onde a pele some sob a roupa.

A pele escondida sob cada roupa é uma marca por ponto da cage do corpo (``hsr``). Aqui esses
pontos são levados para a tela com as matrizes da cena (``BrushView``), para o pincel pegar os
que estão sob o cursor, do lado de cá do corpo, e para a tela mostrar o estado de cada um
(``overlay``), como numa pintura de pesos.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from src.clothing.hsr import _cage_vertex_normals, mirror_index

FACING = 0.05        # how much a cage point's normal must turn to the camera for the point to be on this side
DEPTH_SLACK = 0.12   # metres behind the nearest point under the brush that are still painted (not the arm behind the torso)
# What each point is: skin showing, skin hidden by the clothes, hidden by hand, shown by hand.
SHOWN, HIDDEN, PAINTED_HIDDEN, PAINTED_SHOWN = 0, 1, 2, 3
COLOURS = {SHOWN: (190, 195, 205, 90), HIDDEN: (255, 150, 60, 200), PAINTED_HIDDEN: (255, 60, 60, 255),
           PAINTED_SHOWN: (70, 230, 110, 255)}
RADII = {SHOWN: 1.5, HIDDEN: 2.5, PAINTED_HIDDEN: 3.5, PAINTED_SHOWN: 3.5}
STROKE = (255, 235, 80, 255)  # the points taken by the stroke being made

_cache: Dict[int, Tuple[Any, np.ndarray, np.ndarray]] = {}


def _of_cage(cage_points: np.ndarray, cage_faces: Optional[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """(normal of each cage point, the point that mirrors each one or -1), kept for the cage in use."""
    found = _cache.get(id(cage_points))
    if found is None or found[0] is not cage_points:
        points = np.asarray(cage_points, dtype=np.float64)
        normals = _cage_vertex_normals(points, np.asarray(cage_faces)) if cage_faces is not None and len(cage_faces) \
            else np.tile([0.0, 0.0, 1.0], (len(points), 1))
        _cache.clear()
        _cache[id(cage_points)] = found = (cage_points, normals, mirror_index(points))
    return found[1], found[2]


class BrushView:
    """Os pontos da cage vistos na tela num quadro: onde cada um cai (pixels da janela), a que
    distância da câmera e se está do lado de cá do corpo."""

    def __init__(self, cage_points: np.ndarray, cage_faces: Optional[np.ndarray], model: np.ndarray, view: np.ndarray,
                 projection: np.ndarray, rect: Tuple[float, float, float, float], pose: Any = None) -> None:
        points = np.asarray(cage_points, dtype=np.float64)
        normals, self.mirror = _of_cage(cage_points, cage_faces)
        # The cage is in the fitting pose: ``pose`` (CharacterAnimator.posed) takes it to the pose shown.
        moved = pose(cage_points, normals) if pose is not None else None
        if moved is not None:
            points, normals = moved
        seen = np.asarray(view, dtype=np.float64) @ np.asarray(model, dtype=np.float64)
        eye = points @ seen[:3, :3].T + seen[:3, 3]
        clip = np.column_stack((eye, np.ones(len(eye)))) @ np.asarray(projection, dtype=np.float64).T
        ndc = clip[:, :2] / np.where(np.abs(clip[:, 3:4]) < 1e-12, 1e-12, clip[:, 3:4])
        x0, y0, x1, y1 = rect
        self.xy = np.column_stack((x0 + (ndc[:, 0] * 0.5 + 0.5) * (x1 - x0), y0 + (0.5 - ndc[:, 1] * 0.5) * (y1 - y0)))
        self.depth = eye[:, 2]  # the camera looks down -z: the larger, the nearer
        self.facing = (normals @ seen[:3, :3].T)[:, 2] > FACING

    def pick(self, x: float, y: float, radius: float, mirror: bool = False) -> List[int]:
        """Os pontos sob o pincel (um círculo de ``radius`` pixels em x, y), do lado de cá do corpo
        e na frente; com ``mirror``, também os que os espelham do outro lado."""
        near = self.facing & (((self.xy - np.array([x, y])) ** 2).sum(axis=1) <= radius * radius)
        if not near.any():
            return []
        picked = np.flatnonzero(near & (self.depth >= self.depth[near].max() - DEPTH_SLACK))
        if mirror:
            other = self.mirror[picked]
            picked = np.union1d(picked, other[other >= 0])
        return [int(i) for i in picked]


def states(hidden: Sequence[bool], painted_hidden: Iterable[int], painted_shown: Iterable[int]) -> np.ndarray:
    """O que é cada ponto da cage (SHOWN, HIDDEN, PAINTED_HIDDEN, PAINTED_SHOWN)."""
    out = np.where(np.asarray(hidden, dtype=bool), HIDDEN, SHOWN).astype(np.uint8)
    for indices, value in ((painted_hidden, PAINTED_HIDDEN), (painted_shown, PAINTED_SHOWN)):
        ids = [int(i) for i in indices if 0 <= int(i) < len(out)]
        out[ids] = value
    return out


def overlay(size: Tuple[int, int], origin: Tuple[float, float], xy: np.ndarray, facing: np.ndarray, kinds: np.ndarray,
            stroke: Iterable[int] = ()) -> Any:
    """Imagem RGBA (do tamanho da cena, cujo canto fica em ``origin`` na janela) com um ponto por
    ponto da cage do lado de cá: a cor diz o que ele é, e os do traço em curso ficam em destaque."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (max(int(size[0]), 1), max(int(size[1]), 1)), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    taken = set(int(i) for i in stroke)
    for index in np.flatnonzero(facing):
        x, y = float(xy[index, 0]) - origin[0], float(xy[index, 1]) - origin[1]
        if not (-4 <= x <= size[0] + 4 and -4 <= y <= size[1] + 4):
            continue
        kind = int(kinds[index]) if index < len(kinds) else SHOWN
        radius, colour = (4.0, STROKE) if int(index) in taken else (RADII[kind], COLOURS[kind])
        pen.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colour)
    return image


def ring(radius: float) -> Any:
    """O cursor do pincel: um círculo vazado do tamanho dele."""
    from PIL import Image, ImageDraw
    side = int(2 * radius + 6)
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    pen.ellipse((2, 2, side - 3, side - 3), outline=(20, 20, 24, 255), width=3)
    pen.ellipse((2, 2, side - 3, side - 3), outline=(255, 255, 255, 255), width=1)
    return image
