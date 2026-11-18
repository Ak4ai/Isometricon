"""Efeitos de status contados em rodadas (sem OpenGL).

No mod a duração das poções do Minecraft era descontada 120 ticks por rodada; aqui a duração já nasce em rodadas.
Cada efeito perde uma rodada no início do turno de quem o carrega, depois de agir (curar, envenenar):

- ``regeneracao``: cura ``2 × potência`` no início do turno;
- ``veneno``: tira ``1d4 × potência`` no início do turno, mas nunca derruba (deixa com 1 de vida, como o veneno do jogo);
- ``forca`` / ``fraqueza``: ``+2`` / ``-2`` de dano por potência em cada acerto;
- ``atordoado``: perde o turno inteiro;
- ``abencoado``: ``+potência`` no d20 de ataque.

A absorção (vida temporária) não é um efeito: fica no ``temp_hp`` do combatente até ser gasta ou o combate acabar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

EFFECT_NAMES: Dict[str, str] = {
    "regeneracao": "Regeneração",
    "veneno": "Veneno",
    "forca": "Força",
    "fraqueza": "Fraqueza",
    "atordoado": "Atordoado",
    "abencoado": "Abençoado",
}


@dataclass
class Effect:
    kind: str
    rounds: Optional[int] = 1     # None: não expira sozinho
    potency: int = 1

    def __post_init__(self) -> None:
        if self.kind not in EFFECT_NAMES:
            raise ValueError(f"efeito desconhecido: {self.kind!r}")

    @property
    def name(self) -> str:
        return EFFECT_NAMES[self.kind]


def add_effect(effects: List[Effect], new: Effect) -> None:
    """Põe ``new`` na lista; o mesmo efeito não empilha: fica a maior potência e a maior duração."""
    for current in effects:
        if current.kind == new.kind:
            current.potency = max(current.potency, new.potency)
            if current.rounds is None or new.rounds is None:
                current.rounds = None
            else:
                current.rounds = max(current.rounds, new.rounds)
            return
    effects.append(Effect(new.kind, new.rounds, new.potency))


def potency(effects: List[Effect], kind: str) -> int:
    return sum(effect.potency for effect in effects if effect.kind == kind)


def damage_bonus(effects: List[Effect]) -> int:
    return 2 * potency(effects, "forca") - 2 * potency(effects, "fraqueza")


def expire_one_round(effects: List[Effect]) -> List[Effect]:
    """Desconta uma rodada de cada efeito; devolve os que acabaram (e os tira da lista)."""
    ended = []
    for effect in list(effects):
        if effect.rounds is None:
            continue
        effect.rounds -= 1
        if effect.rounds <= 0:
            effects.remove(effect)
            ended.append(effect)
    return ended
