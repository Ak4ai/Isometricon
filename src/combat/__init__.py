"""Combate por turnos (portado e aprimorado do mod RPG): a regra pura, sem OpenGL.

- ``dice``: d20, NdX+M, vantagem; com semente para repetir um combate;
- ``stats``: atributos, armaduras (CA e redução de dano) e armas;
- ``effects``: efeitos contados em rodadas;
- ``combatant``: a ficha de quem luta;
- ``actions``: a resolução do golpe, as habilidades e os itens;
- ``engine``: a sessão (iniciativa, vez, movimento, fim);
- ``ai``: a vez dos inimigos;
- ``bestiary``: as fichas das criaturas e a ficha do personagem;
- ``log``: o texto do registro de combate.

A tela fica em ``src.interactive.combat_hud``, e as miniaturas dos inimigos em ``src.interactive.enemy_tokens``.
"""

from src.combat.bestiary import BESTIARY, PlayerSheet, find_creature, spawn
from src.combat.combatant import ENEMIES, PLAYERS, Combatant
from src.combat.dice import Dice, DiceExpr, FixedDice
from src.combat.engine import DEFEAT, ESCAPED, VICTORY, CombatSession, Event, FlatTerrain

__all__ = [
    "BESTIARY", "PlayerSheet", "find_creature", "spawn", "ENEMIES", "PLAYERS", "Combatant", "Dice", "DiceExpr",
    "FixedDice", "DEFEAT", "ESCAPED", "VICTORY", "CombatSession", "Event", "FlatTerrain",
]
