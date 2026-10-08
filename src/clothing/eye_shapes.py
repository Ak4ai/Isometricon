"""Formatos de olho, gerados a partir do desenho de olho que o rosto já tem.

O olho anime é pixel art numa camada da textura da cabeça: a massa escura dos cílios com pontas no
canto de fora, pontinhos de cílio embaixo, a íris e o branco. Cada formato é uma transformação
desse mesmo desenho (o globo esticado ou achatado, a pálpebra descida, colunas deslocadas, cílios
acrescentados ou tirados), feita em cada olho por si e espelhada no outro, sem borrar os pixels.
Assim todos continuam no estilo do original e seguem a cor da íris, que já foi pintada antes.
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np
from PIL import Image

PAD = 16      # transparent pixels kept around an eye while it is reshaped
DARK = 70     # a pixel darker than this is lash or lid
EDGE = 150    # and one darker than this is lash or the soft edge of one (the white and the iris are lighter)
LID = 22      # rows from the top of the eye that are lid and lashes; the eyeball shows below them


def _light(eye: np.ndarray) -> np.ndarray:
    return eye[:, :, :3].astype(int).mean(axis=2)


def _dark(eye: np.ndarray) -> np.ndarray:
    return (eye[:, :, 3] > 0) & (_light(eye) < DARK)


def _stretch(eye: np.ndarray, factor: float) -> np.ndarray:
    """Make the eyeball (what is below the lid) taller or lower, its rows spread evenly; the lid stays."""
    top = PAD + LID
    ball = Image.fromarray(np.ascontiguousarray(eye[top:]))
    ball = ball.resize((ball.width, max(1, round(ball.height * factor))), Image.NEAREST)
    return np.concatenate([eye[:top], np.array(ball)], axis=0)


def _scale(eye: np.ndarray, across: float, down: float) -> np.ndarray:
    size = (max(1, round(eye.shape[1] * across)), max(1, round(eye.shape[0] * down)))
    return np.array(Image.fromarray(np.ascontiguousarray(eye)).resize(size, Image.NEAREST))


def _tilt(eye: np.ndarray, lift: int) -> np.ndarray:
    """Raise the outer corner (the left of the picture) by ``lift`` pixels, the inner one staying."""
    out = np.zeros_like(eye)
    width = eye.shape[1]
    for x in range(width):
        shift = 2 * int(round(lift * (1.0 - x / max(width - 1, 1)) / 2.0))  # in steps of two: the art's pixels stay whole
        column = eye[:, x]
        if shift > 0:
            out[:-shift, x] = column[shift:]
        elif shift < 0:
            out[-shift:, x] = column[:shift]
        else:
            out[:, x] = column
    return out


def _lashes(eye: np.ndarray) -> np.ndarray:
    """Longer lashes at the outer corner: two more steps up and out from the tip of the wing."""
    dark = _dark(eye)
    if not dark.any():
        return eye
    shades, counts = np.unique(eye[dark], axis=0, return_counts=True)
    colour = shades[counts.argmax()]  # the lash colour the drawing uses most
    rows, columns = np.nonzero(dark)
    left = columns.min()
    tip = rows[columns <= left + 3].min()  # the top of the wing, at its outer end
    out = eye.copy()
    for step in (1, 2):
        y, x = tip - 4 * step, left - 4 * step
        if y >= 0 and x >= 0:
            out[y:y + 4, x:x + 4] = colour
    return out


def _soft(eye: np.ndarray) -> np.ndarray:
    """Without the loose lashes: the spikes above the lid and the dots under the outer corner."""
    dark = _dark(eye)
    if not dark.any():
        return eye
    rows, columns = np.nonzero(dark)
    top, bottom, left, right = rows.min(), rows.max(), columns.min(), columns.max()
    grid_y, grid_x = np.mgrid[0:eye.shape[0], 0:eye.shape[1]]
    lash = (eye[:, :, 3] > 0) & (_light(eye) < EDGE)  # the lashes and their soft edges
    out = eye.copy()
    out[grid_y < top + 8] = 0
    out[lash & (grid_y > bottom - 16) & (grid_x < left + 0.42 * (right - left))] = 0
    return out


def _trim(eye: np.ndarray, keep: int = 10) -> np.ndarray:
    """Without the wing: the lashes that run out past the outer corner, but for ``keep`` pixels of them."""
    dark = _dark(eye)
    ball = (eye[:, :, 3] > 0) & (_light(eye) >= EDGE)
    if not dark.any() or not ball.any():
        return eye
    edge = np.nonzero(ball.any(axis=0))[0].min()  # where the eyeball starts
    out = eye.copy()
    out[:, :max(edge - keep, 0)] = 0
    return out


def _lid(eye: np.ndarray, drop: int, slant: int = 0) -> np.ndarray:
    """Lower the upper lid over the eyeball by ``drop`` pixels, and by ``slant`` more at the inner
    corner (a frown). What the lid passes over is hidden, the iris too."""
    top, width = PAD + LID, eye.shape[1]
    out = eye.copy()
    for x in range(width):
        shift = 2 * int(round((drop + slant * x / max(width - 1, 1)) / 2.0))
        lid = np.zeros_like(eye[:, x])
        lid[shift:top + shift] = eye[:top, x]
        rows = np.nonzero((lid[:, 3] > 0) & (lid[:, :3].astype(int).mean(axis=1) < DARK))[0]
        if shift <= 0 or not len(rows):
            continue
        out[:rows.max() + 1, x] = 0
        out[rows, x] = lid[rows]
    return out


def _under(eye: np.ndarray, length: int = 16) -> np.ndarray:
    """A short line under the eye (a tired one)."""
    dark = _dark(eye)
    shown = eye[:, :, 3] > 0
    if not dark.any():
        return eye
    shades, counts = np.unique(eye[dark], axis=0, return_counts=True)
    bottom, columns = np.nonzero(shown.any(axis=1))[0].max(), np.nonzero(shown.any(axis=0))[0]
    middle = (columns.min() + columns.max()) // 2
    out = np.concatenate([eye, np.zeros((8,) + eye.shape[1:], dtype=eye.dtype)], axis=0)
    out[bottom + 5:bottom + 7, middle - length // 2:middle + length // 2] = shades[counts.argmax()]
    return out


def _ball_middle(eye: np.ndarray):
    """The column in the middle of the eyeball (what is not lash), or None without one."""
    columns = np.nonzero(((eye[:, :, 3] > 0) & (_light(eye) >= DARK)).any(axis=0))[0]
    return (columns.min() + columns.max() + 1) / 2 if len(columns) else None


# name -> what is done to the eye (its outer corner on the left, padded by PAD all round)
EYE_SHAPES: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "padrao": lambda eye: eye,
    "arredondado": lambda eye: _scale(_stretch(eye, 1.26), 0.92, 1.0),
    "grande": lambda eye: _scale(eye, 1.14, 1.14),
    "feminino": lambda eye: _lashes(_tilt(_stretch(eye, 1.12), 4)),
    # Half closed: the eyeball lower under the same lid (lowering the lid over the iris left
    # bits of iris showing between the lashes above it).
    "fechado": lambda eye: _stretch(eye, 0.56),
    "sonolento": lambda eye: _tilt(_stretch(eye, 0.48), -4),
    "estreito": lambda eye: _scale(_stretch(eye, 0.80), 1.06, 1.0),
    "puxado": lambda eye: _tilt(eye, 8),
    "caido": lambda eye: _tilt(eye, -8),
    "suave": lambda eye: _soft(eye),
    "suave_redondo": lambda eye: _scale(_stretch(_soft(eye), 1.22), 0.94, 1.0),
    # Other characters of eye, all cut from the same drawing: its iris, its shine and its place.
    "serio": lambda eye: _lid(_trim(_soft(eye)), 4, 6),
    "masculino": lambda eye: _stretch(_trim(_soft(eye), 6), 0.88),
    "afiado": lambda eye: _scale(_tilt(_lid(_stretch(_soft(eye), 0.84), 2, 4), 6), 1.08, 1.0),
    "redondo": lambda eye: _scale(_stretch(_trim(_soft(eye), 6), 1.24), 0.90, 1.0),
    "retro": lambda eye: _scale(_stretch(_lashes(eye), 1.20), 0.82, 1.0),
    "cansado": lambda eye: _under(_lid(_trim(_soft(eye)), 8)),
    "felino": lambda eye: _scale(_tilt(_lashes(_stretch(eye, 0.92)), 10), 1.10, 1.0),
}
SHAPE_NAMES = tuple(EYE_SHAPES)


def shape_eyes(layer: Image.Image, shape: str) -> Image.Image:
    """A camada dos olhos com os dois no formato ``shape`` (a mesma camada no formato padrão ou
    desconhecido). Cada olho fica com o globo onde estava, apoiado na mesma linha de baixo."""
    change = EYE_SHAPES.get(shape)
    box = layer.getbbox()
    if change is None or shape == "padrao" or box is None:
        return layer
    layer = layer.convert("RGBA")
    middle = (box[0] + box[2]) // 2
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    for x0, x1, mirrored in ((0, middle, False), (middle, layer.width, True)):
        half = layer.crop((x0, 0, x1, layer.height))
        inner = half.getbbox()
        if inner is None:
            continue
        eye = np.zeros((inner[3] - inner[1] + 2 * PAD, inner[2] - inner[0] + 2 * PAD, 4), dtype=np.uint8)
        eye[PAD:-PAD, PAD:-PAD] = np.array(half.crop(inner))
        if mirrored:
            eye = eye[:, ::-1]  # the outer corner on the left, as in the first eye
        eye = np.ascontiguousarray(change(np.ascontiguousarray(eye)))
        if mirrored:
            eye = eye[:, ::-1]
        drawn = Image.fromarray(np.ascontiguousarray(eye))
        shaped = drawn.getbbox()
        if shaped is None:
            continue
        drawn = drawn.crop(shaped)
        # The eyeball stays where it was across the face (centring the whole drawing would move
        # the iris when lashes are added or taken at one side), or the drawing when there is none.
        was, now = _ball_middle(np.array(half.crop(inner))), _ball_middle(np.array(drawn))
        if was is None or now is None:
            was, now = (inner[2] - inner[0]) / 2, drawn.width / 2
        left = x0 + inner[0] + was - now
        top = inner[3] - drawn.height                              # resting on the same line
        frame = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        frame.paste(drawn, (int(round(left)), int(top)))
        out.alpha_composite(frame)
    return out
