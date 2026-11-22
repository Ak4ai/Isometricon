"""Girar blocos e construções em volta do eixo Y, em passos de 90°.

Uma volta é a mesma de ``VoxelObject.rotated_y(1)`` (os objetos do editor): a célula do lado leste vai para o lado
norte. As propriedades com direção giram junto (``facing``, as ligações ``north/east/south/west`` de cercas e muros,
``axis``, ``rotation`` de placas e cabeças, ``shape`` de trilhos); as relativas ao ``facing`` (``hinge``, ``half``,
``type=left/right`` do baú duplo, ``shape`` de escada) ficam como estão.
"""

from __future__ import annotations

import numpy as np

from src.world.schematic import Schematic

_TURN = {"east": "north", "north": "west", "west": "south", "south": "east"}
_SIDES = ("north", "east", "south", "west")
_RAIL_CURVES = {frozenset(("north", "east")): "north_east", frozenset(("north", "west")): "north_west",
                frozenset(("south", "east")): "south_east", frozenset(("south", "west")): "south_west"}


def _turn_dir(value: str, turns: int) -> str:
    for _ in range(turns):
        value = _TURN.get(value, value)
    return value


def _turn_rail(shape: str, turns: int) -> str:
    if shape in ("north_south", "east_west"):
        return shape if turns % 2 == 0 else ("east_west" if shape == "north_south" else "north_south")
    if shape.startswith("ascending_"):
        return "ascending_" + _turn_dir(shape[len("ascending_"):], turns)
    parts = shape.split("_")
    if len(parts) == 2 and all(p in _TURN for p in parts):
        return _RAIL_CURVES[frozenset(_turn_dir(p, turns) for p in parts)]
    return shape


def rotate_block_name(name: str, turns: int) -> str:
    """O nome do bloco (``minecraft:x[k=v,...]``) girado ``turns`` voltas; a ordem das propriedades é mantida."""
    turns %= 4
    head, bracket, rest = name.partition("[")
    if turns == 0 or not bracket:
        return name
    pairs = [p.split("=", 1) for p in rest.rstrip("]").split(",") if "=" in p]
    props = dict(pairs)
    out = {}
    for key, value in pairs:
        if key == "facing":
            out[key] = _turn_dir(value, turns)
        elif key in _SIDES:
            # a ligação que estava no lado ``side`` passa para o lado girado: quem fica com o valor de quem
            source = next(s for s in _SIDES if _turn_dir(s, turns) == key)
            out[key] = props.get(source, value)
        elif key == "axis" and value in ("x", "z") and turns % 2:
            out[key] = "z" if value == "x" else "x"
        elif key == "rotation" and value.isdigit():
            out[key] = str((int(value) - 4 * turns) % 16)
        elif key == "shape":
            out[key] = _turn_rail(value, turns)
        else:
            out[key] = value
    return head + "[" + ",".join(f"{k}={out[k]}" for k, _ in pairs) + "]"


def _turn_grid(array: np.ndarray, turns: int) -> np.ndarray:
    """Gira uma grade [y, z, x, ...] como ``VoxelObject.rotated_y``: (x, z) -> (z, largura - 1 - x) por volta."""
    for _ in range(turns % 4):
        array = np.swapaxes(array[:, :, ::-1], 1, 2)
    return np.ascontiguousarray(array)


def rotate_schematic(schematic: Schematic, turns: int) -> Schematic:
    """Uma cópia da construção girada ``turns`` voltas (grade, cores e nomes dos blocos); a original não muda."""
    turns %= 4
    grid = _turn_grid(schematic.grid, turns).copy()
    if turns:
        names = {name: rotate_block_name(str(name), turns) for name in set(grid.ravel().tolist())}
        grid = np.vectorize(names.__getitem__, otypes=[object])(grid) if grid.size else grid
    height, length, width = grid.shape
    rotated = Schematic(width, height, length, grid, dict(schematic.palette), schematic.name)
    tints = getattr(schematic, "tints", None)
    if tints is not None:
        rotated.tints = _turn_grid(tints, turns).copy()
    lights = getattr(schematic, "lights", None)
    if lights is not None:
        rotated.lights = _turn_grid(lights, turns).copy()
    return rotated
