"""Formatos de olho, gerados a partir do desenho de olho que o rosto já tem.

O olho anime é pixel art numa camada da textura da cabeça: a massa escura dos cílios com pontas no
canto de fora, pontinhos de cílio embaixo, a íris e o branco. Cada formato é uma transformação
desse mesmo desenho (o globo esticado ou achatado, colunas deslocadas, cílios acrescentados ou
tirados), feita em cada olho por si e espelhada no outro, sem borrar os pixels.
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


# ---------------------------------------------------------------------------------------------
# Modelos de olho desenhados: outros traços, na mesma pixel art do olho original (a grade de
# pixels de 4 px, o lugar no rosto e a paleta dele), montados a partir das curvas das pálpebras,
# da íris, da pupila, dos brilhos e dos cílios. A íris é desenhada em azul, como a original,
# para a cor escolhida ser aplicada do mesmo jeito.
# ---------------------------------------------------------------------------------------------
from dataclasses import dataclass, field
from typing import Optional, Tuple

CELL = 4                    # atlas pixels to one pixel of the drawing
GRID = (22, 15)             # cells of one eye, its outer corner on the left
EYE_AT = (9, 125)           # where the first eye's grid starts in the 512 px atlas; the other mirrors it
FACE_MIDDLE = 128.5         # the column the two eyes mirror about
# The colours of the original eye (sampled from it). The white's shade is kept just short of
# blue, so that only the iris takes the chosen colour.
LASH, WHITE, SHADE, CREAM = (50, 35, 35), (255, 255, 255), (196, 196, 208), (249, 246, 226)
IRIS_DARK, IRIS_MID, IRIS_BRIGHT, IRIS_GLOW, PUPIL = (51, 69, 107), (91, 116, 172), (122, 175, 215), (186, 221, 225), (46, 61, 92)

RIMMED_IRIS = 4.5           # an iris at least this wide (its radius, in cells) is drawn with a darker rim

Points = Tuple[Tuple[float, float], ...]


@dataclass(frozen=True)
class EyeModel:
    """Um olho, em células da grade (x da esquerda, o canto de fora; y de cima)."""
    upper: Points                                   # the upper edge of the opening, from the outer corner inwards
    lower: Points                                   # its lower edge
    iris: Tuple[float, float, float, float]         # centre x, centre y, radius across, radius down
    lid: float = 1.6                                # thickness of the upper lid
    pupil: Tuple[int, int] = (2, 3)                 # width and height
    # Each shine: how far from the centre of the iris (across, down), and its width and height. It is
    # on the same side in both eyes (the light comes from one place), unlike the rest, which mirrors.
    highlights: Tuple[Tuple[float, float, int, int], ...] = ()
    lashes: Tuple[Tuple[int, int], ...] = ()        # loose cells of lash
    lower_line: Optional[Tuple[int, int]] = None    # from which column to which the lower lid is drawn
    crease: Optional[Points] = None                 # a thin line over the lid (a heavy eyelid)
    under: Optional[Tuple[int, int]] = None         # a dotted line under the eye, between two columns (tired)
    glow: bool = False                              # the bright crescent at the bottom of the iris


def _edge(points: Points, x: float) -> Optional[float]:
    """Height of a lid's edge at a column (None outside it)."""
    if x < points[0][0] or x > points[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def draw_eye(model: EyeModel, mirrored: bool = False) -> np.ndarray:
    """Um olho em RGBA, de GRID células de CELL pixels: o primeiro (canto de fora à esquerda) ou, com
    ``mirrored``, o outro, espelhado em tudo menos nos brilhos, que ficam do mesmo lado nos dois."""
    width, height = GRID
    cells = np.zeros((height, width, 4), dtype=np.uint8)

    def put(x: int, y: int, colour) -> None:
        if 0 <= x < width and 0 <= y < height:
            cells[y, x] = tuple(colour) + (255,)

    cx, cy, rx, ry = model.iris
    opening = np.zeros((height, width), dtype=bool)
    for x in range(width):
        top, bottom = _edge(model.upper, x + 0.5), _edge(model.lower, x + 0.5)
        if top is None or bottom is None:
            continue
        first, last = int(np.ceil(top - 0.5)), int(np.floor(bottom - 0.5))
        for y in range(max(first, 0), min(last, height - 1) + 1):
            opening[y, x] = True
            put(x, y, SHADE if y == first else WHITE)   # the lid shades the white right under it
    inside = lambda x, y: ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0
    for y in range(height):
        for x in range(width):
            if not (opening[y, x] and inside(x, y)):
                continue
            t = (y + 0.5 - (cy - ry)) / (2 * ry)   # 0 at the top of the iris, 1 at its bottom
            colour = IRIS_DARK if t < 0.40 else IRIS_MID if t < 0.72 else IRIS_BRIGHT
            if model.glow and t > 0.80:
                colour = IRIS_GLOW
            # A large iris has a darker rim at its sides; on a small one that reads as stripes.
            rim = rx >= RIMMED_IRIS and any(not (0 <= u < width and opening[y, u] and inside(u, y)) for u in (x - 1, x + 1))
            put(x, y, IRIS_DARK if rim else colour)
    pw, ph = model.pupil
    for y in range(int(round(cy - ph / 2)), int(round(cy - ph / 2)) + ph):
        for x in range(int(round(cx - pw / 2)), int(round(cx - pw / 2)) + pw):
            if 0 <= x < width and 0 <= y < height and opening[y, x] and inside(x, y):
                put(x, y, PUPIL)
    for x in range(width):                           # the upper lid, over the top of the opening
        top = _edge(model.upper, x + 0.5)
        if top is None:
            continue
        for y in range(int(np.ceil(top - 0.5 - model.lid)), int(np.ceil(top - 0.5))):
            put(x, y, LASH)
    if model.lower_line is not None:
        for x in range(model.lower_line[0], model.lower_line[1] + 1):
            bottom = _edge(model.lower, x + 0.5)
            if bottom is not None:
                put(x, int(np.floor(bottom - 0.5)) + 1, LASH)
    if model.crease is not None:
        for x in range(width):
            y = _edge(model.crease, x + 0.5)
            if y is not None:
                put(x, int(round(y - 0.5)), LASH)
    if model.under is not None:
        for x in range(model.under[0], model.under[1] + 1, 2):
            bottom = _edge(model.lower, x + 0.5)
            if bottom is not None:
                put(x, int(np.floor(bottom - 0.5)) + 2, LASH)
    for x, y in model.lashes:
        put(x, y, LASH)
    centre = cx
    if mirrored:
        cells, opening, centre = cells[:, ::-1].copy(), opening[:, ::-1], width - cx
    iris = np.isin(cells[:, :, 2], [c[2] for c in (IRIS_DARK, IRIS_MID, IRIS_BRIGHT, IRIS_GLOW, PUPIL)]) & (cells[:, :, 3] > 0)
    for dx, dy, hw, hh in model.highlights:          # the shines, where the iris shows
        for y in range(int(round(cy + dy - 0.5)), int(round(cy + dy - 0.5)) + hh):
            for x in range(int(round(centre + dx - 0.5)), int(round(centre + dx - 0.5)) + hw):
                if 0 <= x < width and 0 <= y < height and iris[y, x]:
                    cells[y, x] = CREAM + (255,)
    return np.repeat(np.repeat(cells, CELL, axis=0), CELL, axis=1)


# In every model the iris sits a little to the outside of the middle of the opening, as in the
# original (towards the nose the character looks cross-eyed), and the shine is up and to the left.
EYE_MODELS: Dict[str, EyeModel] = {
    # Narrow under a straight lid that comes down towards the nose; one point of shine, no lashes.
    "serio": EyeModel(upper=((1, 5.6), (6, 6.0), (20, 8.0)), lower=((3, 9.0), (7, 12.0), (16, 12.0), (20, 9.8)),
                      iris=(10.9, 9.3, 3.8, 3.8), lid=1.5, pupil=(2, 2), highlights=((-1.5, -1.0, 1, 1),), lower_line=(4, 6)),
    # Calmer: a straight lid without lashes, a smaller iris, one bar of shine, a short line under the corner.
    "masculino": EyeModel(upper=((1, 6.2), (5, 4.9), (16, 4.9), (21, 7.2)), lower=((3, 9.0), (7, 12.2), (17, 12.2), (21, 9.2)),
                          iris=(11.3, 8.8, 4.1, 4.3), lid=1.6, pupil=(2, 2), highlights=((-2.5, -2.3, 2, 1),), lower_line=(5, 8)),
    # Long and slanted, its outer corner high and pointed; a narrow iris.
    "afiado": EyeModel(upper=((0, 4.4), (6, 5.4), (21, 8.6)), lower=((2, 7.0), (8, 10.8), (17, 11.2), (21, 9.8)),
                       iris=(11.0, 8.7, 3.6, 3.8), lid=1.2, pupil=(2, 2), highlights=((-1.5, -1.0, 1, 1),),
                       lashes=((0, 3),), lower_line=(3, 5)),
    # Round and open, a large iris with a big shine: a cuter, simpler line.
    "redondo": EyeModel(upper=((2, 6.2), (6, 3.2), (15, 3.2), (20, 6.6)), lower=((2, 9.0), (6, 13.4), (16, 13.4), (20, 9.0)),
                        iris=(10.6, 8.5, 5.2, 5.4), lid=1.5, pupil=(2, 3), highlights=((-3.0, -3.5, 3, 2), (1.5, 1.5, 2, 1)),
                        lashes=((1, 4), (0, 5)), glow=True),
    # Tall, as in older anime: an oval iris, large blocks of shine, a thick lid and the lower lid at the corner.
    "retro": EyeModel(upper=((3, 6.0), (6, 2.2), (14, 1.6), (19, 5.6)), lower=((3, 9.0), (6, 13.6), (15, 14.0), (19, 10.0)),
                      iris=(10.6, 8.4, 4.6, 6.0), lid=2.0, pupil=(2, 3), highlights=((-3.0, -4.0, 2, 3), (1.5, 2.0, 1, 2)),
                      lashes=((2, 3), (1, 2), (1, 5)), lower_line=(4, 8), glow=True),
    # A heavy lid half over the eye, and a short line under it.
    "cansado": EyeModel(upper=((1, 7.2), (6, 7.6), (20, 8.2)), lower=((3, 9.6), (7, 12.6), (16, 12.6), (20, 10.0)),
                        iris=(10.8, 9.9, 4.0, 4.0), lid=1.6, pupil=(2, 2), highlights=((-1.5, 0.0, 1, 1),), under=(8, 13)),
    # Wide at the outer corner and pointed at the inner one, with a slit pupil.
    "felino": EyeModel(upper=((0, 5.2), (5, 3.6), (15, 4.6), (21, 8.2)), lower=((2, 8.0), (7, 12.6), (16, 12.6), (21, 9.2)),
                       iris=(11.0, 8.6, 4.4, 5.0), lid=1.6, pupil=(1, 5), highlights=((-3.0, -3.0, 2, 2),),
                       lashes=((0, 3), (1, 3)), glow=True),
}
MODEL_NAMES = tuple(EYE_MODELS)
SHAPE_NAMES = SHAPE_NAMES + MODEL_NAMES


def draw_eyes(name: str, size: Tuple[int, int] = (512, 512)) -> Optional[Image.Image]:
    """A camada dos olhos com os dois no modelo ``name`` (None se não é um modelo desenhado)."""
    model = EYE_MODELS.get(name)
    if model is None:
        return None
    unit = size[0] / 512.0
    eye = Image.fromarray(draw_eye(model))
    if unit != 1.0:
        eye = eye.resize((round(eye.width * unit), round(eye.height * unit)), Image.NEAREST)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    x, y = round(EYE_AT[0] * unit), round(EYE_AT[1] * unit)
    layer.paste(eye, (x, y), eye)
    other = Image.fromarray(draw_eye(model, mirrored=True))
    if unit != 1.0:
        other = other.resize(eye.size, Image.NEAREST)
    layer.paste(other, (round(2 * FACE_MIDDLE * unit) - x - eye.width, y), other)
    return layer
