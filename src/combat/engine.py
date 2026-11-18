"""A sessão de combate por turnos: iniciativa, a vez de cada um, ações, movimento e o fim (sem OpenGL).

Portado do ``CombatSession`` do mod RPG, sem nada do Minecraft:

- todos rolam ``d20 + DES`` de iniciativa; empata quem tem mais DES, depois o personagem; quem chega no meio do combate
  entra na ordem pela própria iniciativa sem tirar a vez de ninguém;
- na sua vez, cada um tem uma ação e ``speed`` blocos de movimento (8 por padrão), em qualquer ordem. O movimento é
  contado aqui (no mod só o cliente contava). A vez acaba quando as duas coisas acabam, ou com ``end_turn``;
- no início da vez a postura defensiva cai, os efeitos agem (regeneração, veneno) e perdem uma rodada, e as recargas
  das habilidades andam; atordoado perde a vez;
- o combate acaba em vitória (nenhum inimigo de pé), derrota (o personagem desmaiou) ou fuga (a ação Fugir deu certo,
  ou o personagem terminou a vez a mais de ``ESCAPE_DISTANCE`` blocos de todos os inimigos).

A sessão não espera nem anima nada: ela anota ``Event``s, e a tela (``combat_hud``) os mostra no ritmo dela. A vez dos
inimigos só anda quando a tela chama ``run_ai_turn``, um inimigo por vez.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from src.combat import actions
from src.combat.actions import ITEMS, SKILLS, AttackResult
from src.combat.combatant import ENEMIES, PLAYERS, Combatant, distance, flat_distance
from src.combat.dice import Dice, DiceExpr
from src.combat.effects import expire_one_round, potency

ESCAPE_DISTANCE = 16.0   # terminar a vez a esta distância de todos os inimigos é fugir
JOIN_RADIUS = 15.0       # inimigos até aqui entram no combate
STEP = 0.25              # passo da caminhada dos inimigos, em blocos
MAX_STEP_UP = 1.25       # o maior degrau que se sobe andando
POISON = DiceExpr(1, 4)
EPS = 1e-6

VICTORY = "vitoria"
DEFEAT = "derrota"
ESCAPED = "fuga"


class Terrain(Protocol):
    def ground(self, x: float, z: float, y_hint: float) -> Optional[float]:
        """A altura dos pés de quem fica em (x, z), perto de ``y_hint``; None se ali não dá para ficar."""

    def sight(self, a: Sequence[float], b: Sequence[float]) -> bool:
        """Dá para ver (e acertar à distância) de ``a`` até ``b``?"""


class FlatTerrain:
    """Chão plano e sem obstáculos (testes, e o padrão sem mundo)."""

    def ground(self, x: float, z: float, y_hint: float) -> Optional[float]:
        return y_hint

    def sight(self, a: Sequence[float], b: Sequence[float]) -> bool:
        return True


@dataclass
class Event:
    kind: str
    actor: Optional[str] = None
    target: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    ok: bool
    reason: str = ""


def _sort_key(c: Combatant) -> Tuple[int, int, int]:
    return (-c.initiative, -c.mod("des"), 0 if c.is_player else 1)


class CombatSession:
    def __init__(self, combatants: Iterable[Combatant], dice: Optional[Dice] = None,
                 terrain: Optional[Terrain] = None, surprise_by: Optional[str] = None) -> None:
        self.dice = dice or Dice()
        self.terrain: Terrain = terrain or FlatTerrain()
        self.events: List[Event] = []
        self._taken = 0
        self.outcome: Optional[str] = None
        self.round = 1
        self.index = 0
        self.movement_left = 0.0
        self.action_used = False
        self.target_id: Optional[str] = None
        self.order: List[Combatant] = []
        self.left: List[Combatant] = []          # quem saiu do combate fugindo
        roster = list(combatants)
        if not any(c.team == PLAYERS for c in roster) or not any(c.team == ENEMIES for c in roster):
            raise ValueError("o combate precisa de um personagem e de pelo menos um inimigo")
        if len({c.id for c in roster}) != len(roster):
            raise ValueError("dois combatentes com o mesmo id")
        for c in roster:
            self._roll_initiative(c)
            c.defending = False
            c.uses.clear()
            c.cooldowns.clear()
            c.hidden = c.id == surprise_by
        self.order = sorted(roster, key=_sort_key)
        self._emit("inicio", data={"order": [(c.id, c.initiative) for c in self.order],
                                   "surprise": surprise_by})
        self._choose_default_target()
        self._begin_turn()

    # ------------------------------------------------------------------ consultas

    @property
    def active(self) -> bool:
        return self.outcome is None

    @property
    def current(self) -> Combatant:
        return self.order[self.index]

    @property
    def is_player_turn(self) -> bool:
        return self.active and self.current.is_player

    def get(self, combatant_id: Optional[str]) -> Optional[Combatant]:
        for c in self.order:
            if c.id == combatant_id:
                return c
        return None

    def team(self, team: str, alive: bool = True) -> List[Combatant]:
        return [c for c in self.order if c.team == team and (c.alive or not alive)]

    def opponents_of(self, actor: Combatant) -> List[Combatant]:
        return self.team(ENEMIES if actor.team == PLAYERS else PLAYERS)

    @property
    def target(self) -> Optional[Combatant]:
        return self.get(self.target_id)

    def in_reach(self, actor: Combatant, target: Combatant) -> bool:
        if actor.distance_to(target) > actor.reach + EPS:
            return False
        return not actor.weapon.ranged or self.terrain.sight(actor.position, target.position)

    def take_events(self) -> List[Event]:
        """Os eventos novos desde a última chamada."""
        new = self.events[self._taken:]
        self._taken = len(self.events)
        return new

    # ------------------------------------------------------------------ ordem e turnos

    def _emit(self, kind: str, actor: Optional[str] = None, target: Optional[str] = None, **data: Any) -> Event:
        payload = data.pop("data", None) or {}
        payload.update(data)
        event = Event(kind, actor, target, payload)
        self.events.append(event)
        return event

    def _roll_initiative(self, c: Combatant) -> None:
        d20, _ = self.dice.d20()
        c.initiative = d20 + c.mod("des")

    def _choose_default_target(self) -> None:
        if self.target is not None and self.target.alive:
            return
        players = self.team(PLAYERS)
        enemies = self.team(ENEMIES)
        if not enemies:
            self.target_id = None
            return
        if players:
            anchor = next((p for p in players if p.is_player), players[0])
            self.target_id = min(enemies, key=lambda e: e.distance_to(anchor)).id
        else:
            self.target_id = enemies[0].id

    def select_target(self, combatant_id: str) -> bool:
        c = self.get(combatant_id)
        if c is None or not c.alive or c.team != ENEMIES:
            return False
        self.target_id = c.id
        return True

    def cycle_target(self, step: int = 1) -> Optional[str]:
        enemies = self.team(ENEMIES)
        if not enemies:
            return None
        ids = [e.id for e in enemies]
        position = ids.index(self.target_id) if self.target_id in ids else -step
        self.target_id = ids[(position + step) % len(ids)]
        return self.target_id

    def add_combatant(self, c: Combatant) -> None:
        """Alguém chega no meio do combate: rola iniciativa e entra na ordem sem pular nem repetir ninguém."""
        if not self.active or self.get(c.id) is not None:
            return
        self._roll_initiative(c)
        c.defending = False
        c.hidden = False
        at = len(self.order)
        for i, existing in enumerate(self.order):
            if _sort_key(c) < _sort_key(existing):
                at = i
                break
        self.order.insert(at, c)
        if at <= self.index:
            self.index += 1
        self._emit("entrou", c.id, data={"initiative": c.initiative})
        self._choose_default_target()

    def _leave(self, c: Combatant) -> None:
        at = self.order.index(c)
        self.order.remove(c)
        self.left.append(c)
        if at < self.index:
            self.index -= 1
        elif at == self.index:
            self.index -= 1           # o próximo da fila assume a vez no _advance
        if self.target_id == c.id:
            self.target_id = None
            self._choose_default_target()

    def _check_end(self) -> bool:
        if self.outcome is not None:
            return True
        if not any(c.is_player for c in self.team(PLAYERS)):   # sem o jogador de pé, os aliados não seguram
            self._finish(DEFEAT)
        elif not self.team(ENEMIES):
            self._finish(VICTORY)
        return self.outcome is not None

    def _finish(self, outcome: str) -> None:
        self.outcome = outcome
        for c in self.order:
            c.defending = False
        self._emit("fim", data={"outcome": outcome, "round": self.round})

    def _begin_turn(self) -> None:
        """Começa a vez de ``current``; quem está atordoado perde a vez e a fila anda."""
        for _ in range(4 * max(1, len(self.order))):
            if self._check_end():
                return
            actor = self.current
            if not actor.alive:
                self._advance_index()
                continue
            actor.defending = False
            self.movement_left = float(actor.speed)
            self.action_used = False
            self._emit("turno", actor.id, round=self.round)
            stunned = potency(actor.effects, "atordoado") > 0
            self._tick_effects(actor)
            for key in list(actor.cooldowns):
                actor.cooldowns[key] -= 1
                if actor.cooldowns[key] <= 0:
                    del actor.cooldowns[key]
            if self._check_end():
                return
            if stunned:
                self._emit("atordoado", actor.id)
                self._advance_index()
                continue
            return

    def _tick_effects(self, actor: Combatant) -> None:
        regen = potency(actor.effects, "regeneracao")
        if regen:
            healed = actor.heal(2 * regen)
            if healed > 0:
                self._emit("cura", actor.id, amount=healed, source="regeneracao")
        poison = potency(actor.effects, "veneno")
        if poison:
            total, rolls = self.dice.roll(POISON.scaled(poison))
            amount = min(float(total), max(0.0, actor.hp - 1.0))     # o veneno não derruba
            absorbed, hurt = actor.take_damage(amount)
            self._emit("dano_efeito", actor.id, amount=hurt + absorbed, source="veneno", rolls=rolls)
        for effect in expire_one_round(actor.effects):
            self._emit("efeito_fim", actor.id, effect=effect.kind)

    def _advance_index(self) -> None:
        self.index += 1
        if self.index >= len(self.order):
            self.index = 0
            self.round += 1

    def end_turn(self) -> None:
        """Termina a vez de quem está agindo e passa para o próximo vivo."""
        if not self.active:
            return
        actor = self.current
        if actor.is_player and actor.alive:
            enemies = self.team(ENEMIES)
            if enemies and all(actor.distance_to(e) > ESCAPE_DISTANCE for e in enemies):
                self._emit("fugiu", actor.id, distance=min(actor.distance_to(e) for e in enemies))
                self._finish(ESCAPED)
                return
        self._advance_index()
        self._begin_turn()

    def _after_action(self, actor: Combatant) -> None:
        self.action_used = True
        if self._check_end():
            return
        if self.movement_left <= EPS or not actor.alive:
            self.end_turn()

    # ------------------------------------------------------------------ movimento

    def spend_movement(self, amount: float) -> float:
        """Quanto de ``amount`` blocos a vez atual ainda pode andar (e já desconta)."""
        if not self.active:
            return 0.0
        granted = max(0.0, min(float(amount), self.movement_left))
        self.movement_left -= granted
        if self.movement_left <= EPS:
            self.movement_left = 0.0
            if self.action_used:
                self.end_turn()
        return granted

    def set_position(self, combatant_id: str, position: Sequence[float]) -> None:
        c = self.get(combatant_id)
        if c is not None:
            c.position = [float(v) for v in position]

    def _walk(self, actor: Combatant, direction: Tuple[float, float], length: float) -> List[List[float]]:
        """Anda ``length`` blocos (no chão) na direção (dx, dz), parando onde não dá; devolve o caminho."""
        norm = math.hypot(*direction)
        length = min(length, self.movement_left)
        if norm < EPS or length <= EPS:
            return []
        ux, uz = direction[0] / norm, direction[1] / norm
        path: List[List[float]] = []
        x, y, z = actor.position
        walked = 0.0
        while walked < length - EPS:
            step = min(STEP, length - walked)
            nx, nz = x + ux * step, z + uz * step
            ny = self.terrain.ground(nx, nz, y)
            if ny is None or abs(ny - y) > MAX_STEP_UP:
                break
            x, y, z = nx, ny, nz
            walked += step
            path.append([x, y, z])
        if path:
            start = list(actor.position)
            actor.position = list(path[-1])
            self.movement_left = max(0.0, self.movement_left - walked)
            self._emit("movimento", actor.id, start=start, path=path, distance=walked)
        return path

    def walk_toward(self, actor: Combatant, goal: Sequence[float], stop_at: float = 0.0) -> float:
        """Anda em direção a ``goal`` até ficar a ``stop_at`` dele (ou acabar o movimento); devolve o quanto andou."""
        dx, dz = float(goal[0]) - actor.position[0], float(goal[2]) - actor.position[2]
        path = self._walk(actor, (dx, dz), max(0.0, math.hypot(dx, dz) - stop_at))
        return len(path) and self.events[-1].data["distance"]

    def walk_away(self, actor: Combatant, threat: Sequence[float], length: float) -> float:
        dx, dz = actor.position[0] - float(threat[0]), actor.position[2] - float(threat[2])
        if math.hypot(dx, dz) < EPS:
            dx = 1.0
        path = self._walk(actor, (dx, dz), length)
        return len(path) and self.events[-1].data["distance"]

    # ------------------------------------------------------------------ ações

    def block_reason(self, action: str, target_id: Optional[str] = None, item: Optional[str] = None) -> Optional[str]:
        """Por que a ação não pode ser feita agora pela vez atual (ou None, se pode)."""
        if not self.active:
            return "o combate acabou"
        actor = self.current
        if self.action_used:
            return "a ação desta vez já foi usada"
        if action in ("atacar", "golpe_pesado", "ataque_furtivo"):
            if action != "atacar":
                reason = actions.skill_block_reason(actor, action)
                if reason:
                    return reason
            target = self.get(target_id) if target_id else self.target
            if target is None or not target.alive or target.team == actor.team:
                return "sem alvo"
            if not actor.has_ammo():
                return f"sem {actor.weapon.ammo}s"
            if action == "ataque_furtivo" and not (actor.hidden or potency(target.effects, "atordoado")):
                return "o alvo já te viu: o Ataque Furtivo precisa de surpresa"
            if not self.in_reach(actor, target):
                if actor.distance_to(target) > actor.reach + EPS:
                    return f"fora de alcance ({actor.distance_to(target):.1f} de {actor.reach:.1f} blocos)"
                return "sem linha de visão"
            return None
        if action in SKILLS:
            return actions.skill_block_reason(actor, action)
        if action == "usar_item":
            if item not in ITEMS or actor.items.get(item, 0) <= 0:
                return "sem esse item"
            return None
        if action in ("defender", "disparada", "fugir"):
            return None
        return "ação desconhecida"

    def act(self, action: str, target_id: Optional[str] = None, item: Optional[str] = None) -> Outcome:
        """A vez atual faz ``action``: atacar, golpe_pesado, ataque_furtivo, escudo_divino, foco_espiritual,
        defender, disparada, fugir ou usar_item."""
        reason = self.block_reason(action, target_id, item)
        if reason:
            if self.active:
                self._emit("recusado", self.current.id, action=action, reason=reason)
            return Outcome(False, reason)
        actor = self.current
        if action in ("atacar", "golpe_pesado", "ataque_furtivo"):
            target = self.get(target_id) if target_id else self.target
            self._attack(actor, target, action)
        elif action == "escudo_divino":
            actions.mark_skill_used(actor, action)
            amount = actions.DIVINE_SHIELD_BASE + max(0, actor.mod("sab"))
            actor.temp_hp = max(actor.temp_hp, float(amount))
            actor.defending = True
            self._emit("escudo", actor.id, temp_hp=amount)
        elif action == "foco_espiritual":
            actions.mark_skill_used(actor, action)
            roll = self.dice.die(actions.SECOND_WIND.sides)
            healed = actor.heal(roll + actor.level)
            self._emit("cura", actor.id, amount=healed, source="foco_espiritual", rolls=[roll], bonus=actor.level)
        elif action == "defender":
            actor.defending = True
            self._emit("defesa", actor.id, armor_class=actor.armor_class)
        elif action == "disparada":
            self.movement_left += float(actor.speed)
            self._emit("disparada", actor.id, movement=self.movement_left)
        elif action == "fugir":
            if self._try_flee(actor):
                return Outcome(True)
        elif action == "usar_item":
            used = actions.use_item(actor, item, self.dice)
            self._emit("item", actor.id, **used)
        self._after_action(actor)
        return Outcome(True)

    def _attack(self, actor: Combatant, target: Combatant, action: str) -> AttackResult:
        if action == "golpe_pesado":
            actions.mark_skill_used(actor, action)
            result = actions.resolve_attack(actor, target, self.dice, label="Golpe Pesado",
                                            to_hit=actions.HEAVY_STRIKE_TO_HIT, dice_multiplier=2)
        elif action == "ataque_furtivo":
            actions.mark_skill_used(actor, action)
            result = actions.resolve_attack(actor, target, self.dice, label="Ataque Furtivo",
                                            extra=actions.SNEAK_EXTRA, advantage=1)
        else:
            result = actions.resolve_attack(actor, target, self.dice, label="Ataque")
        actor.hidden = False                  # atacou: não está mais escondido
        self._emit("ataque", actor.id, target.id, result=result)
        if not target.alive:
            self._emit("derrotado", target.id, by=actor.id)
            if self.target_id == target.id:
                self.target_id = None
            self._choose_default_target()
        return result

    def flee_difficulty(self, actor: Combatant) -> Optional[int]:
        """A CD para fugir: 10 + 3 por inimigo que te alcança corpo a corpo; None se nenhum alcança (foge sem teste)."""
        threats = [e for e in self.opponents_of(actor)
                   if not e.weapon.ranged and e.distance_to(actor) <= e.melee_reach + 1.0]
        if not threats:
            return None
        return 10 + 3 * len(threats)

    def _try_flee(self, actor: Combatant) -> bool:
        dc = self.flee_difficulty(actor)
        if dc is None:
            self._emit("fuga", actor.id, success=True, dc=None)
            success = True
        else:
            d20, _ = self.dice.d20()
            total = d20 + actor.mod("des")
            success = d20 != 1 and (d20 == 20 or total >= dc)
            self._emit("fuga", actor.id, success=success, dc=dc, d20=d20, bonus=actor.mod("des"))
        if not success:
            return False
        if actor.is_player:
            self._finish(ESCAPED)
        else:
            self._leave(actor)
            self._after_enemy_left()
        return True

    def _after_enemy_left(self) -> None:
        if not self._check_end():
            self.action_used = True
            self.movement_left = 0.0
            self._advance_index()
            self._begin_turn()

    # ------------------------------------------------------------------ inimigos

    def enemy_escape(self, actor: Combatant) -> bool:
        """Quem a IA joga terminou longe o bastante de todos os do outro lado: sai do combate."""
        players = self.team(ENEMIES if actor.team == PLAYERS else PLAYERS)
        if players and all(actor.distance_to(p) > ESCAPE_DISTANCE for p in players):
            self._emit("fugiu", actor.id, distance=min(actor.distance_to(p) for p in players))
            self._leave(actor)
            self._after_enemy_left()
            return True
        return False

    def run_ai_turn(self) -> bool:
        """Joga a vez do inimigo atual (decide, anda, age) e passa a vez; False se não é a vez de um inimigo."""
        if not self.active or self.current.is_player:
            return False
        from src.combat.ai import take_turn
        actor = self.current
        take_turn(self, actor)
        if self.active and self.current is actor:
            if not self.enemy_escape(actor):
                self.end_turn()
        return True
