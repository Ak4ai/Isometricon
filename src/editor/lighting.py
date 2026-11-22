"""Luzes pontuais pequenas para lâmpadas, lanternas e tochas do editor.

O material carrega ``light`` (0 a 15). Cada voxel emissivo vira uma luz
pontual local; o shader do mundo soma essas luzes à iluminação global. O
limite é pequeno de propósito: são luzes de detalhe, não um sistema de
iluminação global.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from src.editor.map_project import MapProject
from src.editor.voxel_object import EMPTY, VoxelObject
from src.world.light_blocks import light_for_block

MAX_POINT_LIGHTS = 8


@dataclass(frozen=True)
class PointLight:
    position: tuple[float, float, float]
    color: tuple[float, float, float]
    radius: float
    intensity: float

    @property
    def shader_color(self) -> tuple[float, float, float]:
        return tuple(component * self.intensity for component in self.color)  # type: ignore[return-value]


def _collect(obj: VoxelObject, offset: tuple[int, int, int] = (0, 0, 0),
             limit: int = MAX_POINT_LIGHTS) -> List[PointLight]:
    lights: List[PointLight] = []
    cells = [(int(x), int(y), int(z)) for x, y, z in np.argwhere(obj.blocks != EMPTY)]
    for x, y, z in cells:
        material = obj.materials[obj.get(x, y, z)]
        if material.light <= 0:
            continue
        r, g, b = (component / 255.0 for component in material.color)
        lights.append(PointLight(
            (offset[0] + x + 0.5, offset[1] + y + 0.5, offset[2] + z + 0.5),
            (r, g, b),
            5.0 + material.light * 0.55,
            material.light / 15.0,
        ))
        if len(lights) >= limit:
            break
    return lights


def collect_lights(project: MapProject, limit: int = MAX_POINT_LIGHTS) -> List[PointLight]:
    """Luzes locais do volume base e dos objetos colocados no mapa."""
    lights = _collect(project.base, limit=limit)
    for placed in project.objects:
        if len(lights) >= limit:
            break
        rendered = placed.rendered_object()
        remaining = limit - len(lights)
        lights.extend(_collect(rendered, placed.position, remaining))
    return lights[:limit]


def apply_lights(shader, lights: Sequence[PointLight], model=None) -> None:
    """Envia até ``MAX_POINT_LIGHTS`` luzes para o shader do mundo.

    As posições são locais; ``model`` as leva ao mesmo espaço dos vértices
    (o tabuleiro do editor pode estar girado).
    """
    count = min(len(lights), MAX_POINT_LIGHTS)
    shader.set_int("u_PointLightCount", count)
    for index in range(count):
        light = lights[index]
        position = light.position
        if model is not None:
            transformed = np.asarray(model, dtype=np.float64) @ np.array([*position, 1.0], dtype=np.float64)
            position = tuple(float(v) for v in transformed[:3])
        shader.set_vec3(f"u_PointLightPosition[{index}]", *position)
        shader.set_vec3(f"u_PointLightColor[{index}]", *light.shader_color)
        shader.set_float(f"u_PointLightRadius[{index}]", light.radius)


# Luz aproximada para schematics que não guardam materiais do editor.
def _spread(lights: List[PointLight], limit: int) -> List[PointLight]:
    """Escolhe luzes ao longo de toda a estrutura, em vez das primeiras oito."""
    if len(lights) <= limit:
        return lights
    if limit <= 1:
        return lights[:1]
    return [lights[round(index * (len(lights) - 1) / (limit - 1))] for index in range(limit)]


def collect_structure_lights(structures: Sequence, limit: int = MAX_POINT_LIGHTS,
                             near: Sequence[float] | None = None) -> List[PointLight]:
    """Luzes de construções colocadas no mundo.

    ``near`` (jogador/câmera) escolhe as luzes mais próximas; sem ele, as
    luzes são espalhadas pela estrutura."""

    lights: List[PointLight] = []
    gather_limit = 512
    for placed in structures:
        if len(lights) >= gather_limit:
            break
        schematic = getattr(placed, "schematic", None)
        origin = getattr(placed, "origin", (0, 0, 0))
        if schematic is None:
            continue
        stored = getattr(schematic, "lights", None)
        tints = getattr(schematic, "tints", None)
        grid = schematic.grid
        for y, z, x in np.argwhere(grid != "minecraft:air"):
            light = int(stored[y, z, x]) if stored is not None else 0
            inferred = light_for_block(grid[y, z, x]) if light <= 0 else None
            if inferred is not None:
                light, default_color = inferred
            elif light <= 0:
                continue
            else:
                default_color = (1.0, 0.78, 0.38)
            if tints is not None:
                color = tuple(float(v) for v in tints[y, z, x][:3])
            else:
                color = default_color
            lights.append(PointLight(
                (origin[0] + int(x) + 0.5, origin[1] + int(y) + 0.5, origin[2] + int(z) + 0.5),
                color, 5.0 + light * 0.55, light / 15.0,
            ))
            if len(lights) >= gather_limit:
                break
    if near is not None:
        origin = tuple(float(v) for v in near[:3])
        lights.sort(key=lambda light: sum((light.position[i] - origin[i]) ** 2 for i in range(3)))
        return lights[:limit]
    return _spread(lights, limit)
