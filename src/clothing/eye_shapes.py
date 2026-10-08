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


def _close(eye: np.ndarray, drop: int) -> np.ndarray:
    """Lower the lid by ``drop`` pixels over the eyeball: a half-closed eye."""
    dark = _dark(eye)
    if not dark.any():
        return eye
    top = np.nonzero(dark)[0].min()
    rows = np.arange(eye.shape[0])[:, None]
    lid = dark & (rows < top + LID)
    lowered = np.zeros_like(lid)
    lowered[drop:] = lid[:-drop]
    out = eye.copy()
    for x in range(eye.shape[1]):  # nothing shows above the lowered lid (between its lashes the eye still does)
        under = np.nonzero(lowered[:, x])[0]
        out[:(under.min() if len(under) else top + drop), x] = 0
    moved = np.zeros_like(eye)
    moved[drop:] = eye[:-drop]
    out[lowered] = moved[lowered]
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
            out[y:y + 4, x:x + 8] = colour
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


# name -> what is done to the eye (its outer corner on the left, padded by PAD all round)
EYE_SHAPES: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "padrao": lambda eye: eye,
    "arredondado": lambda eye: _scale(_stretch(eye, 1.26), 0.92, 1.0),
    "grande": lambda eye: _scale(eye, 1.14, 1.14),
    "feminino": lambda eye: _lashes(_tilt(_stretch(eye, 1.12), 4)),
    "fechado": lambda eye: _close(eye, 12),
    "sonolento": lambda eye: _tilt(_close(eye, 16), -4),
    "estreito": lambda eye: _scale(_stretch(eye, 0.70), 1.06, 1.0),
    "puxado": lambda eye: _tilt(eye, 8),
    "caido": lambda eye: _tilt(eye, -8),
    "suave": lambda eye: _soft(eye),
    "suave_redondo": lambda eye: _scale(_stretch(_soft(eye), 1.22), 0.94, 1.0),
}
SHAPE_NAMES = tuple(EYE_SHAPES)


def shape_eyes(layer: Image.Image, shape: str) -> Image.Image:
    """A camada dos olhos com os dois no formato ``shape`` (a mesma camada no formato padrão ou
    desconhecido). Cada olho fica centrado onde estava, apoiado na mesma linha de baixo."""
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
        left = x0 + (inner[0] + inner[2]) / 2 - drawn.width / 2   # centred where it was
        top = inner[3] - drawn.height                              # resting on the same line
        frame = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        frame.paste(drawn, (int(round(left)), int(top)))
        out.alpha_composite(frame)
    return out
