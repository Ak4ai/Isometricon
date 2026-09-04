# Representação geométrica mínima de uma caixa alinhada aos eixos.

from typing import NamedTuple

import numpy as np


class AABB(NamedTuple):
    # Limites min/max como vetores NumPy de três componentes no mundo.
    # Apenas dados geométricos; testes de interseção pertencem a tarefas futuras.

    min: np.ndarray
    max: np.ndarray
