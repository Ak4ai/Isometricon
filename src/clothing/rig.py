"""O esqueleto de um modelo (.glb) e a conta da pose, sem OpenGL.

``Rig`` guarda, na ordem do ``skin`` do arquivo, os ossos, quem é pai de quem, a pose de montagem e as matrizes
inversas de montagem. ``Rig.solve`` recebe uma rotação por osso (e um deslocamento da raiz) e devolve, por osso, a
matriz que o shader usa para mover os vértices: ``pose do osso @ inversa da montagem``.

As rotações são aplicadas **em volta da posição do osso, com eixos do modelo** (x para o lado, y para cima, z para a
frente depois de normalizado), e os filhos seguem o pai. Assim o movimento não depende de como cada exportador
orientou os ossos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

MAX_BONES = 64   # o que o shader do mundo aceita (``u_Bones``)


def rotation_matrix(axis: Sequence[float], angle: float) -> np.ndarray:
    """Matriz 3x3 da rotação de ``angle`` radianos em volta de ``axis`` (fórmula de Rodrigues)."""
    axis = np.asarray(axis, dtype=np.float64)
    norm = float(np.linalg.norm(axis))
    if norm < 1e-12 or abs(angle) < 1e-12:
        return np.identity(3)
    x, y, z = axis / norm
    c, s = np.cos(angle), np.sin(angle)
    k = 1.0 - c
    return np.array([
        [c + x * x * k, x * y * k - z * s, x * z * k + y * s],
        [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
        [z * x * k - y * s, z * y * k + x * s, c + z * z * k],
    ])


@dataclass
class Rig:
    names: List[str]
    parents: np.ndarray                 # (J,) índice do pai, -1 para a raiz
    rest_local: np.ndarray              # (J, 4, 4) pose de montagem de cada osso, no espaço do pai
    inverse_bind: np.ndarray            # (J, 4, 4)
    children: List[List[int]] = field(default_factory=list)
    order: List[int] = field(default_factory=list)   # pais antes dos filhos
    base: np.ndarray = field(default_factory=lambda: np.identity(4))   # o que ``transformed`` fez nas raízes

    def __post_init__(self) -> None:
        count = len(self.names)
        self.children = [[] for _ in range(count)]
        for bone, parent in enumerate(self.parents):
            if parent >= 0:
                self.children[int(parent)].append(bone)
        self.order, seen = [], set()
        pending = [b for b in range(count) if self.parents[b] < 0]
        while pending:
            bone = pending.pop(0)
            if bone in seen:
                continue
            seen.add(bone)
            self.order.append(bone)
            pending.extend(self.children[bone])
        if len(self.order) != count:
            raise ValueError("O esqueleto tem um laço ou ossos soltos.")
        self._rest_world = None

    def __len__(self) -> int:
        return len(self.names)

    @property
    def roots(self) -> List[int]:
        return [b for b in range(len(self)) if self.parents[b] < 0]

    def index(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError as error:
            raise KeyError(f"Não há um osso chamado '{name}'.") from error

    # ---- pose de montagem
    @property
    def rest_world(self) -> np.ndarray:
        """Pose de montagem de cada osso no espaço do modelo, (J, 4, 4)."""
        if self._rest_world is None:
            world = np.zeros_like(self.rest_local)
            for bone in self.order:
                parent = int(self.parents[bone])
                world[bone] = self.rest_local[bone] if parent < 0 else world[parent] @ self.rest_local[bone]
            self._rest_world = world
        return self._rest_world

    @property
    def rest_positions(self) -> np.ndarray:
        return self.rest_world[:, :3, 3]

    def chain_from(self, bone: int, length: Optional[int] = None) -> List[int]:
        """O osso e os que descem dele seguindo sempre o primeiro filho mais longe do pai (até ``length``)."""
        chain = [bone]
        while self.children[chain[-1]] and (length is None or len(chain) < length):
            here = self.rest_positions[chain[-1]]
            chain.append(max(self.children[chain[-1]], key=lambda c: float(np.linalg.norm(self.rest_positions[c] - here))))
        return chain

    def transformed(self, matrix: np.ndarray) -> "Rig":
        """O mesmo esqueleto depois de o modelo passar por ``matrix`` (escala, giro, deslocamento)."""
        matrix = np.asarray(matrix, dtype=np.float64)
        local = self.rest_local.copy()
        for root in self.roots:
            local[root] = matrix @ local[root]
        return Rig(list(self.names), self.parents.copy(), local, self.inverse_bind @ np.linalg.inv(matrix),
                   base=matrix @ self.base)

    # ---- pose
    def solve(self, rotations: Optional[np.ndarray] = None, root_offset: Sequence[float] = (0.0, 0.0, 0.0)) -> np.ndarray:
        """As matrizes de pele (J, 4, 4) para as rotações pedidas.

        Args:
            rotations: (J, 3, 3), uma rotação por osso, em eixos do modelo e em volta da posição do osso;
                ``None`` deixa tudo na pose de montagem.
            root_offset: deslocamento somado às raízes (o balanço do corpo todo).
        """
        count = len(self)
        world = np.zeros((count, 4, 4))
        offset = np.asarray(root_offset, dtype=np.float64)
        for bone in self.order:
            parent = int(self.parents[bone])
            if parent < 0:
                matrix = self.rest_local[bone].copy()
                matrix[:3, 3] += offset
            else:
                matrix = world[parent] @ self.rest_local[bone]
            if rotations is not None:
                matrix[:3, :3] = rotations[bone] @ matrix[:3, :3]
            world[bone] = matrix
        return world @ self.inverse_bind

    def solve_local(self, local: np.ndarray) -> np.ndarray:
        """As matrizes de pele (J, 4, 4) para uma pose dada por matrizes locais (J, 4, 4) **nas unidades do arquivo**
        (as que ``rest_local`` tinha antes de ``transformed``): é o que um clipe de animação entrega."""
        world = np.zeros((len(self), 4, 4))
        for bone in self.order:
            parent = int(self.parents[bone])
            world[bone] = self.base @ local[bone] if parent < 0 else world[parent] @ local[bone]
        return world @ self.inverse_bind

    def identity_rotations(self) -> np.ndarray:
        return np.tile(np.identity(3), (len(self), 1, 1))
