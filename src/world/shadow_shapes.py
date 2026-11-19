"""A tabela das formas dos blocos para a sombra do sol.

Cada forma diferente (as caixas de uma laje, de um degrau, de uma cerca, de uma placa...) ganha um número; a máscara
de sombra guarda, em cada célula parcial, o número da forma, e o shader acha as caixas dela nesta tabela (uma linha por
forma, ``SHADOW_BOXES`` pares de texels: o canto de baixo, com w = 1, e o de cima). Uma planta em cruz tem um par
só: (número do desenho, y0, y1, 2); o desenho dela (onde a textura não é transparente, 16 x 16) fica em
``plant_masks``, um embaixo do outro. A tabela é uma só para o jogo todo e só cresce.
"""

import os
from typing import Dict, Tuple

import numpy as np

from src.world.block_shapes import SHADOW_BOXES, shadow_boxes, shadow_plant

MAX_SHAPES = 65535   # o número vai em dois bytes da máscara
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "assets", "textures", "blocks")


def _plant_mask(texture: str) -> np.ndarray:
    """O desenho da planta, 16 x 16 (linha 0 em cima): 255 onde a textura não é transparente. Sem o arquivo,
    o plano todo tapa."""
    path = os.path.join(TEXTURES_DIR, texture + ".png")
    try:
        from PIL import Image
        image = Image.open(path).convert("RGBA")
        side = image.width
        alpha = np.asarray(image.crop((0, 0, side, side)).resize((16, 16), Image.NEAREST))[..., 3]
        return np.where(alpha >= 128, 255, 0).astype(np.uint8)
    except (OSError, ValueError):
        return np.full((16, 16), 255, dtype=np.uint8)


class ShapeTable:
    def __init__(self) -> None:
        self._ids: Dict[Tuple, int] = {}
        self._names: Dict[str, int] = {}
        self._rows = [np.zeros((SHADOW_BOXES * 2, 4), dtype=np.float32)]   # a linha 0: sem forma
        self._masks = []                                                     # os desenhos das plantas
        self._mask_ids: Dict[str, int] = {}
        self.revision = 0

    def id_for(self, block_name: str) -> int:
        """O número da forma do bloco (0 se não tem caixas: cubo inteiro, planta, ar)."""
        known = self._names.get(block_name)
        if known is not None:
            return known
        boxes = tuple((lo, hi, 1.0) for lo, hi in shadow_boxes(block_name))
        plant = shadow_plant(block_name)
        if plant is not None:
            texture, y0, y1 = plant
            if texture not in self._mask_ids:
                self._mask_ids[texture] = len(self._masks)
                self._masks.append(_plant_mask(texture))
                self.revision += 1
            boxes = (((float(self._mask_ids[texture]), y0, y1), (0.0, 0.0, 0.0), 2.0),)
        shape = 0
        if boxes:
            shape = self._ids.get(boxes, 0)
            if not shape and len(self._rows) <= MAX_SHAPES:
                shape = len(self._rows)
                row = np.zeros((SHADOW_BOXES * 2, 4), dtype=np.float32)
                for k, (lo, hi, kind) in enumerate(boxes):
                    row[2 * k] = (*lo, kind)
                    row[2 * k + 1] = (*hi, 0.0)
                self._rows.append(row)
                self._ids[boxes] = shape
                self.revision += 1
        self._names[block_name] = shape
        return shape

    def boxes(self, shape: int) -> np.ndarray:
        """As caixas da forma, [n, 2, 3] (lo, hi)."""
        row = self._rows[shape]
        count = int((row[0::2, 3] > 0.5).sum())   # (numa planta: o desenho e as alturas, e zeros)
        return np.stack([row[0:2 * count:2, :3], row[1:2 * count:2, :3]], axis=1)

    def plant_flags(self) -> np.ndarray:
        """Por número de forma: True nas plantas em cruz."""
        return np.array([row[0, 3] > 1.5 for row in self._rows], dtype=bool)

    def plant_masks(self) -> np.ndarray:
        """Os desenhos das plantas, um embaixo do outro: [16 * n, 16] (pelo menos um, vazio)."""
        if not self._masks:
            return np.zeros((16, 16), dtype=np.uint8)
        return np.ascontiguousarray(np.concatenate(self._masks, axis=0))

    def texels(self) -> np.ndarray:
        """A tabela inteira, [formas, SHADOW_BOXES * 2, 4] (a textura 2D: largura as caixas, altura as formas)."""
        return np.ascontiguousarray(np.stack(self._rows))


TABLE = ShapeTable()


def terrain_shapes() -> np.ndarray:
    """Por BlockType (uint8): o número da forma dos enfeites do terreno (capim, flores, cogumelos, tocha); 0 no resto."""
    from src.world.block import SHAPED_BLOCK_NAMES

    lut = np.zeros(256, dtype=np.uint16)
    for block, name in SHAPED_BLOCK_NAMES.items():
        lut[int(block)] = TABLE.id_for("minecraft:" + name)
    return lut
