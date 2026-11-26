"""A prévia do mundo na tela de criação: um recorte isométrico do começo do mundo, gerado de verdade.

O gerador do jogo (com as opções de criação) faz um quadrado pequeno de chunks em volta do começo; a prévia
desenha só as faces que dão para o ar, de trás para a frente, como um diorama cortado: o corte da frente mostra
as camadas e os túneis das cavernas, mais escuros. Leve: ~0,3 s numa thread, refeita quando uma opção muda.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.world.block import BlockType

AREA = 36          # o lado do recorte, em blocos
BOTTOM = -14       # o fundo do corte (Y)
CELL = 8           # o meio lado de um bloco na prévia, antes de reduzir pela metade (fica liso)

PLANTS = {int(BlockType.SHORT_GRASS): (78, 140, 52), int(BlockType.POPPY): (196, 52, 40),
          int(BlockType.DANDELION): (232, 204, 64), int(BlockType.RED_MUSHROOM): (190, 60, 50),
          int(BlockType.BROWN_MUSHROOM): (150, 112, 82)}
PLANTS.update({int(BlockType.CACTUS): (80, 130, 60), int(BlockType.DEAD_BUSH): (150, 110, 60),
               int(BlockType.FERN): (70, 120, 60), int(BlockType.LARGE_FERN_LOWER): (70, 120, 60),
               int(BlockType.LARGE_FERN_UPPER): (70, 120, 60), int(BlockType.SWEET_BERRY_BUSH): (60, 110, 60)})
COLORS = {int(BlockType.GRASS): (104, 158, 70), int(BlockType.DIRT): (134, 96, 62),
          int(BlockType.STONE): (128, 128, 124), int(BlockType.WATER): (64, 116, 168)}
# os blocos dos biomas (deserto e taiga)
COLORS.update({int(BlockType.SAND): (219, 205, 160), int(BlockType.SANDSTONE): (206, 188, 140),
               int(BlockType.TAIGA_GRASS): (84, 128, 70), int(BlockType.PODZOL): (110, 80, 48),
               int(BlockType.SPRUCE_LOG): (92, 64, 40), int(BlockType.SEQUOIA_LOG): (120, 64, 44),
               int(BlockType.SPRUCE_LOG_X): (92, 64, 40), int(BlockType.SPRUCE_LOG_Z): (92, 64, 40),
               int(BlockType.SEQUOIA_LOG_X): (120, 64, 44), int(BlockType.SEQUOIA_LOG_Z): (120, 64, 44),
               int(BlockType.SPRUCE_LEAVES): (52, 96, 60)})
GRASS_SIDE = (122, 100, 64)
SHADE = (1.0, 0.80, 0.64)      # topo, face +x, face +z


def volume(seed: int, options: Optional[Dict[str, Any]]) -> np.ndarray:
    """Os blocos do recorte, ``[x, y, z]``, de ``BOTTOM`` para cima."""
    from src.world.chunk import Chunk3D
    from src.world.terrain_options import make_generator
    size = Chunk3D.SIZE
    generator = make_generator(seed, options)
    half = AREA // 2
    first, last = (-half) // size, (half - 1) // size
    ys = range(BOTTOM // size, 2)
    chunks = generator.generate_region([(cx, cy, cz) for cx in range(first, last + 1)
                                        for cz in range(first, last + 1) for cy in ys])
    span = (last - first + 1) * size
    out = np.zeros((span, len(ys) * size, span), dtype=np.uint8)
    for (cx, cy, cz), chunk in chunks.items():
        if cy not in ys or not first <= cx <= last or not first <= cz <= last:
            continue                       # as cavernas podem criar chunks vizinhos
        out[(cx - first) * size:(cx - first + 1) * size, (cy - ys[0]) * size:(cy - ys[0] + 1) * size,
            (cz - first) * size:(cz - first + 1) * size] = chunk.blocks
    start = -half - first * size
    bottom = BOTTOM - ys[0] * size
    return out[start:start + AREA, bottom:, start:start + AREA]


def render(blocks: np.ndarray, cell: int = CELL) -> Image.Image:
    """O diorama: faces de bloco que dão para o ar, de trás para a frente."""
    sx_, sy_, sz_ = blocks.shape
    plants = np.isin(blocks, list(PLANTS))
    solid = (blocks != int(BlockType.AIR)) & ~plants
    top_y = np.where(solid.any(axis=1), sy_ - 1 - np.argmax(solid[:, ::-1, :], axis=1), -1)   # a superfície
    while sy_ > 1 and not solid[:, sy_ - 1, :].any() and not plants[:, sy_ - 1, :].any():
        sy_ -= 1                                                                                # corta o céu vazio

    padded = np.pad(solid, ((0, 1), (0, 1), (0, 1)))     # fora do recorte conta como ar: é o corte do diorama
    faces = (solid & ~padded[:-1, 1:, :-1],               # topo: o de cima é ar
             solid & ~padded[1:, :-1, :-1],               # face +x
             solid & ~padded[:-1, :-1, 1:])               # face +z
    width = (sx_ + sz_) * cell + 2
    height = (sx_ + sz_) * cell // 2 + sy_ * cell + 2
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    ox, oy = sz_ * cell, sy_ * cell

    def point(x, y, z):
        return ox + (x - z) * cell, oy + (x + z) * cell / 2 - y * cell

    # o fundo das cavernas que atravessam o recorte: paredes escuras atrás (x = 0, z = 0) e o chão
    back = tuple(int(c * SHADE[1] * 0.3) for c in COLORS[int(BlockType.STONE)]) + (255,)
    draw.polygon([point(0, 0, 0), point(sx_, 0, 0), point(sx_, 0, sz_), point(0, 0, sz_)], fill=back)
    for z in range(sz_):
        top = min(int(top_y[0, z]) + 1, sy_)
        draw.polygon([point(0, top, z), point(0, top, z + 1), point(0, 0, z + 1), point(0, 0, z)], fill=back)
    for x in range(sx_):
        top = min(int(top_y[x, 0]) + 1, sy_)
        draw.polygon([point(x, top, 0), point(x + 1, top, 0), point(x + 1, 0, 0), point(x, 0, 0)], fill=back)
    shown = faces[0] | faces[1] | faces[2] | plants
    cells = np.argwhere(shown[:, :sy_, :])
    order = np.lexsort((cells[:, 1], cells[:, 0] + cells[:, 1] + cells[:, 2]))
    for x, y, z in cells[order]:
        kind = int(blocks[x, y, z])
        if kind in PLANTS:
            bx, by = point(x + .5, y, z + .5)
            draw.line((bx, by, bx, by - cell * .9), fill=PLANTS[kind], width=max(1, cell // 3))
            continue
        under = y < top_y[x, z] and kind != int(BlockType.WATER)    # embaixo da superfície: o corte ou uma caverna
        cave = under and x < sx_ - 1 and z < sz_ - 1                 # dentro do recorte: um túnel
        for index, polygon in ((0, ((x, y + 1, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x, y + 1, z + 1))),
                               (1, ((x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x + 1, y, z + 1), (x + 1, y, z))),
                               (2, ((x, y + 1, z + 1), (x + 1, y + 1, z + 1), (x + 1, y, z + 1), (x, y, z + 1)))):
            if not faces[index][x, y, z]:
                continue
            color = GRASS_SIDE if kind == int(BlockType.GRASS) and index else COLORS.get(kind, COLORS[int(BlockType.STONE)])
            shade = SHADE[index] * (0.42 if cave else 1.0) * (0.92 if under and not cave else 1.0)
            fill = tuple(int(c * shade) for c in color) + ((215,) if kind == int(BlockType.WATER) else (255,))
            draw.polygon([point(*corner) for corner in polygon], fill=fill)
    return image.resize((max(1, width // 2), max(1, height // 2)), Image.Resampling.LANCZOS)


def build(seed: int, options: Optional[Dict[str, Any]]) -> Image.Image:
    return render(volume(seed, options))


class PreviewWorker:
    """Faz a prévia numa thread: ``request`` pede (a última vale), ``image`` dá a pronta (ou None ainda)."""

    def __init__(self, builder: Callable[[int, Optional[Dict[str, Any]]], Image.Image] = build,
                 on_ready: Optional[Callable[[], None]] = None) -> None:
        self.builder = builder
        self.on_ready = on_ready
        self.wanted: Optional[Tuple[int, str]] = None
        self.done: Optional[Tuple[int, str]] = None
        self.result: Optional[Image.Image] = None
        self._lock = threading.Lock()
        self._busy = False

    def request(self, seed: int, options: Dict[str, Any]) -> None:
        import json
        key = (int(seed), json.dumps(options, sort_keys=True))
        with self._lock:
            if key == self.wanted:
                return
            self.wanted = key
            if self._busy:
                return            # a thread pega o pedido novo quando terminar o atual
            self._busy = True
        threading.Thread(target=self._run, daemon=True, name='world-preview').start()

    def _run(self) -> None:
        import json
        while True:
            with self._lock:
                key = self.wanted
            try:
                image = self.builder(key[0], json.loads(key[1]))
            except Exception as error:          # a prévia nunca derruba a tela de criação
                print(f'[Menu] Prévia do mundo falhou: {error}')
                image = None
            with self._lock:
                self.result, self.done = image, key
                if self.wanted == key:
                    self._busy = False
                    break
        if self.on_ready is not None:
            self.on_ready()

    @property
    def pending(self) -> bool:
        return self.wanted != self.done

    def image(self) -> Optional[Image.Image]:
        return self.result
