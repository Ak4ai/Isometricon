"""Os dados do combate: d20, NdX+M, vantagem e desvantagem (sem OpenGL).

Toda rolagem passa por um ``Dice``: com semente o combate se repete igual (testes, replays); ``FixedDice`` entrega uma
fila de resultados escolhidos para os testes dizerem exatamente o que caiu.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

_EXPR = re.compile(r"^\s*(\d*)\s*d\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DiceExpr:
    """``count`` dados de ``sides`` lados mais ``bonus`` (ex.: 2d6+1)."""

    count: int
    sides: int
    bonus: int = 0

    @classmethod
    def parse(cls, text: str) -> "DiceExpr":
        match = _EXPR.match(text)
        if match is None:
            raise ValueError(f"expressão de dados inválida: {text!r}")
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        bonus = int(match.group(4) or 0) * (-1 if match.group(3) == "-" else 1)
        if count < 1 or sides < 1:
            raise ValueError(f"expressão de dados inválida: {text!r}")
        return cls(count, sides, bonus)

    def scaled(self, multiplier: int) -> "DiceExpr":
        """O mesmo dado com ``multiplier`` vezes mais dados (o crítico dobra os dados, não o bônus)."""
        return DiceExpr(self.count * multiplier, self.sides, self.bonus)

    @property
    def average(self) -> float:
        return self.count * (self.sides + 1) / 2.0 + self.bonus

    @property
    def maximum(self) -> int:
        return self.count * self.sides + self.bonus

    def __str__(self) -> str:
        if self.bonus == 0:
            return f"{self.count}d{self.sides}"
        return f"{self.count}d{self.sides}{self.bonus:+d}"


class Dice:
    """Rola dados com um ``random.Random`` próprio (semente opcional)."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._random = random.Random(seed)

    def die(self, sides: int) -> int:
        return self._random.randint(1, sides)

    def chance(self) -> float:
        """Um número em [0, 1) para desempates e escolhas da IA."""
        return self._random.random()

    def rolls(self, count: int, sides: int) -> List[int]:
        return [self.die(sides) for _ in range(count)]

    def roll(self, expr: DiceExpr) -> Tuple[int, List[int]]:
        """(total, dados que caíram)."""
        rolled = self.rolls(expr.count, expr.sides)
        return sum(rolled) + expr.bonus, rolled

    def d20(self, advantage: int = 0) -> Tuple[int, List[int]]:
        """O d20 que vale e os que caíram: ``advantage`` > 0 fica com o maior de dois, < 0 com o menor."""
        if advantage == 0:
            value = self.die(20)
            return value, [value]
        pair = [self.die(20), self.die(20)]
        return (max(pair) if advantage > 0 else min(pair)), pair


class FixedDice(Dice):
    """Dados de teste: entregam ``values`` na ordem; acabando a fila, cai sempre o mínimo (1)."""

    def __init__(self, values: Iterable[int] = (), chances: Sequence[float] = ()) -> None:
        super().__init__(0)
        self.values = list(values)
        self.chances = list(chances)

    def push(self, *values: int) -> None:
        self.values.extend(values)

    def die(self, sides: int) -> int:
        if not self.values:
            return 1
        value = self.values.pop(0)
        if not 1 <= value <= sides:
            raise ValueError(f"o teste pediu {value} num d{sides}")
        return value

    def chance(self) -> float:
        return self.chances.pop(0) if self.chances else 0.5
