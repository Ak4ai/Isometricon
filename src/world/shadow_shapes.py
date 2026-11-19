"""A tabela das formas dos blocos para a sombra do sol.

Cada forma diferente (as caixas de uma laje, de um degrau, de uma cerca, de uma placa...) ganha um número; a máscara
de sombra guarda, em cada célula parcial, o número da forma, e o shader acha as caixas dela nesta tabela (uma linha por
forma, ``SHADOW_BOXES`` pares de texels: o canto de baixo com w = 1 e o de cima). A tabela é uma só para o jogo todo
e só cresce.
"""

from typing import Dict, Tuple

import numpy as np

from src.world.block_shapes import SHADOW_BOXES, shadow_boxes

MAX_SHAPES = 65535   # o número vai em dois bytes da máscara


class ShapeTable:
    def __init__(self) -> None:
        self._ids: Dict[Tuple, int] = {}
        self._names: Dict[str, int] = {}
        self._rows = [np.zeros((SHADOW_BOXES * 2, 4), dtype=np.float32)]   # a linha 0: sem forma
        self.revision = 0

    def id_for(self, block_name: str) -> int:
        """O número da forma do bloco (0 se não tem caixas: cubo inteiro, planta, ar)."""
        known = self._names.get(block_name)
        if known is not None:
            return known
        boxes = shadow_boxes(block_name)
        shape = 0
        if boxes:
            shape = self._ids.get(boxes, 0)
            if not shape and len(self._rows) <= MAX_SHAPES:
                shape = len(self._rows)
                row = np.zeros((SHADOW_BOXES * 2, 4), dtype=np.float32)
                for k, (lo, hi) in enumerate(boxes):
                    row[2 * k] = (*lo, 1.0)
                    row[2 * k + 1] = (*hi, 0.0)
                self._rows.append(row)
                self._ids[boxes] = shape
                self.revision += 1
        self._names[block_name] = shape
        return shape

    def boxes(self, shape: int) -> np.ndarray:
        """As caixas da forma, [n, 2, 3] (lo, hi)."""
        row = self._rows[shape]
        count = int((row[0::2, 3] > 0.5).sum())
        return np.stack([row[0:2 * count:2, :3], row[1:2 * count:2, :3]], axis=1)

    def texels(self) -> np.ndarray:
        """A tabela inteira, [formas, SHADOW_BOXES * 2, 4] (a textura 2D: largura as caixas, altura as formas)."""
        return np.ascontiguousarray(np.stack(self._rows))


TABLE = ShapeTable()
