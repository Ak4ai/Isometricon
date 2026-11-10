"""Água com as regras do Minecraft moderno (Java): fontes, água corrente, queda e fonte infinita.

Cada bloco de água é uma *fonte* (nível 0) ou *corrente* (níveis 1 a 7, um a mais a cada bloco que se afasta da
fonte), ou está *caindo* (tem água logo acima; conta como cheia). A cada atualização (``TICK`` segundos, os 5 ticks
do jogo) as células marcadas são reavaliadas todas juntas, a partir do mesmo estado, e a água avança um bloco:

* a água cai se o bloco de baixo deixa passar (ar ou água corrente); a corrente que pode cair não se espalha para os
  lados, a fonte se espalha mesmo assim;
* para os lados ela vai na direção da descida mais próxima, procurada até ``SLOPE_REACH`` blocos; sem descida ao
  alcance, vai para todos os lados;
* uma corrente com duas fontes vizinhas e chão sólido (ou fonte) embaixo vira fonte (a fonte infinita);
* sem quem a alimente, a corrente seca: o nível é sempre recalculado pelos vizinhos, e passa de 7 vira ar.

O mundo é visto por um ``FluidWorld``: ``block`` devolve ``None`` onde o chunk não está carregado (a água não entra
no que não se conhece) e ``set_block`` troca o bloco.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, Optional, Protocol, Set, Tuple

from src.world.block import BlockType

Cell = Tuple[int, int, int]

SOURCE = 0          # bloco-fonte
MAX_LEVEL = 7       # a corrente mais fraca; passa disso, seca
FALLING = 8         # tem água logo acima: cai, cheia
TICK = 0.25         # segundos entre atualizações (5 ticks do jogo)
SLOPE_REACH = 4     # até onde a corrente procura uma descida para escolher a direção

HORIZONTAL = ((1, 0), (-1, 0), (0, 1), (0, -1))


class FluidWorld(Protocol):
    def block(self, x: int, y: int, z: int) -> Optional[BlockType]: ...

    def set_block(self, x: int, y: int, z: int, block: BlockType) -> None: ...


def surface_height(level: int) -> float:
    """Altura da superfície no bloco (0..1): a fonte e a queda são cheias; a corrente baixa 1/8 por nível."""
    if level in (SOURCE, FALLING):
        return 1.0
    return (8 - level) / 8.0


class WaterSimulation:
    """Mantém o estado da água corrente e avança a simulação, uma onda de blocos por atualização."""

    def __init__(self, world: FluidWorld, budget: int = 512) -> None:
        self.world = world
        self.budget = budget                 # células reavaliadas por atualização, no máximo
        self._step = None                    # atualização em andamento: (células, próxima, cache, decisões)
        self.levels: Dict[Cell, int] = {}    # só a água que não é fonte (1..7 ou FALLING); a fonte é o padrão
        self.heights: Dict[Cell, float] = {} # altura da superfície por célula, para a malha (fonte fica de fora)
        self._pending: deque[Cell] = deque()
        self._queued: Set[Cell] = set()

    # ------------------------------------------------------------------ estado
    def level(self, cell: Cell) -> Optional[int]:
        """Nível da água na célula, ou ``None`` se ali não há água."""
        if self.world.block(*cell) is not BlockType.WATER:
            return None
        return self.levels.get(cell, SOURCE)

    def _set(self, cell: Cell, level: Optional[int]) -> None:
        if level is None:
            self.world.set_block(*cell, BlockType.AIR)
            self.levels.pop(cell, None)
            self.heights.pop(cell, None)
            return
        self.world.set_block(*cell, BlockType.WATER)
        if level == SOURCE:
            self.levels.pop(cell, None)
            self.heights.pop(cell, None)
        else:
            self.levels[cell] = level
            self.heights[cell] = surface_height(level)

    def forget(self, predicate) -> None:
        """Esquece o estado das células para as quais ``predicate(cell)`` é verdadeiro (um chunk descarregado)."""
        for store in (self.levels, self.heights):
            for cell in [c for c in store if predicate(c)]:
                del store[cell]
        kept = [c for c in self._pending if not predicate(c)]
        self._pending = deque(kept)
        self._queued = set(kept)

    # ------------------------------------------------------------------ agenda
    def schedule(self, cell: Cell) -> None:
        if cell not in self._queued:
            self._queued.add(cell)
            self._pending.append(cell)

    def schedule_around(self, cell: Cell) -> None:
        """A célula e as seis vizinhas: o que muda numa mexe no que as outras querem."""
        x, y, z = cell
        self.schedule(cell)
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            self.schedule((x + dx, y + dy, z + dz))

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    # ------------------------------------------------------------------ regras
    def _passable(self, cell: Cell) -> bool:
        """A água pode ocupar a célula: ar, ou água corrente (a fonte não é substituída)."""
        block = self.world.block(*cell)
        if block is BlockType.AIR:
            return True
        return block is BlockType.WATER and self.levels.get(cell, SOURCE) != SOURCE

    def _can_fall(self, cell: Cell) -> bool:
        x, y, z = cell
        return self._passable((x, y - 1, z))

    def _spreads_sideways(self, cell: Cell, level: int) -> bool:
        """A fonte sempre se espalha; a corrente (e a queda que chegou ao chão) só se não puder cair."""
        return level == SOURCE or not self._can_fall(cell)

    def _flow_directions(self, cell: Cell, cache: Dict[Cell, Set[Tuple[int, int]]]) -> Set[Tuple[int, int]]:
        """Para onde a água da célula corre: as direções com a descida mais próxima (até SLOPE_REACH blocos)."""
        if cell in cache:
            return cache[cell]
        x, y, z = cell
        best, chosen = None, set()
        for dx, dz in HORIZONTAL:
            start = (x + dx, y, z + dz)
            if not self._passable(start):
                continue
            distance = self._slope_distance(start, cell)
            if distance is None:
                continue
            if best is None or distance < best:
                best, chosen = distance, {(dx, dz)}
            elif distance == best:
                chosen.add((dx, dz))
        if best is None:  # nenhuma descida ao alcance: para todos os lados que dá
            chosen = {(dx, dz) for dx, dz in HORIZONTAL if self._passable((x + dx, y, z + dz))}
        cache[cell] = chosen
        return chosen

    def _slope_distance(self, start: Cell, origin: Cell) -> Optional[int]:
        """Passos até uma célula de onde a água cai, andando pelo plano a partir de ``start`` (sem voltar)."""
        frontier = deque([(start, 1)])
        seen = {start, origin}
        while frontier:
            cell, distance = frontier.popleft()
            if self._can_fall(cell):
                return distance
            if distance >= SLOPE_REACH:
                continue
            x, y, z = cell
            for dx, dz in HORIZONTAL:
                nxt = (x + dx, y, z + dz)
                if nxt not in seen and self._passable(nxt):
                    seen.add(nxt)
                    frontier.append((nxt, distance + 1))
        return None

    def _desired(self, cell: Cell, cache: Dict[Cell, Set[Tuple[int, int]]]) -> Optional[int]:
        """O que a célula (ar ou corrente) deve ser agora: nível novo, ou ``None`` (ar)."""
        x, y, z = cell
        if self.level((x, y + 1, z)) is not None:
            return FALLING
        sources = 0
        best: Optional[int] = None
        for dx, dz in HORIZONTAL:
            neighbour = (x + dx, y, z + dz)
            level = self.level(neighbour)
            if level is None:
                continue
            if level == SOURCE:
                sources += 1
            if not self._spreads_sideways(neighbour, level):
                continue
            if (-dx, -dz) not in self._flow_directions(neighbour, cache):
                continue
            fed = 1 if level in (SOURCE, FALLING) else level + 1
            if fed <= MAX_LEVEL and (best is None or fed < best):
                best = fed
        if sources >= 2:
            below = (x, y - 1, z)
            under = self.world.block(*below)
            solid_under = under is not None and under not in (BlockType.AIR, BlockType.WATER)
            if solid_under or self.level(below) == SOURCE:
                return SOURCE
        return best

    # ------------------------------------------------------------------ passo
    def step(self) -> Set[Cell]:
        """Uma atualização: reavalia as células marcadas a partir do mesmo estado; devolve as que mudaram."""
        self.begin_step()
        return self.advance(None)

    @property
    def stepping(self) -> bool:
        """Há uma atualização começada e ainda não aplicada (``advance`` continua)."""
        return self._step is not None

    def begin_step(self) -> None:
        """Separa as células da próxima atualização; ``advance`` avalia aos poucos e aplica no fim."""
        batch = []
        while self._pending and len(batch) < self.budget:
            cell = self._pending.popleft()
            self._queued.discard(cell)
            batch.append(cell)
        self._step = (batch, 0, {}, [])

    def advance(self, limit: Optional[int]) -> Optional[Set[Cell]]:
        """Avalia até ``limit`` células da atualização começada (``None``: todas). Quando a última foi avaliada,
        aplica as mudanças e devolve as células que mudaram; antes disso devolve ``None``. Dividir assim tira o
        travamento do quadro (cada célula custa ~40 µs em Python)."""
        if self._step is None:
            return set()
        batch, index, cache, decisions = self._step
        end = len(batch) if limit is None else min(len(batch), index + limit)
        for cell in batch[index:end]:
            block = self.world.block(*cell)
            if block is None or block not in (BlockType.AIR, BlockType.WATER):
                continue                      # sólido ou desconhecido: a água não entra
            current = self.level(cell)
            if current == SOURCE:
                continue                      # a fonte não muda sozinha
            desired = self._desired(cell, cache)
            if desired != current:
                decisions.append((cell, desired))
        if end < len(batch):
            self._step = (batch, end, cache, decisions)
            return None
        self._step = None

        changed: Set[Cell] = set()
        for cell, desired in decisions:
            self._set(cell, desired)
            changed.add(cell)
        for cell in changed:
            self.schedule_around(cell)
        return changed

    def wake(self, cells: Iterable[Cell]) -> None:
        """Marca as células para a próxima atualização (água nova, bloco quebrado ou colocado por perto)."""
        for cell in cells:
            self.schedule_around(cell)
