"""O combate por turnos dentro do mundo: inimigos no tabuleiro, quando a luta começa, o ritmo das vezes (sem OpenGL).

A regra está em ``src.combat``; aqui fica o que liga a regra ao jogo:

- os inimigos (``EnemyToken``) ficam no mundo desde o ``/inimigo``; cada um guarda o ``Combatant`` dele e a posição em
  que aparece na tela (que segue o caminho da regra andando, em vez de pular);
- a luta começa quando o personagem clica num inimigo a até ``ENGAGE_REACH`` blocos (ataque surpresa: vale o Ataque
  Furtivo) ou quando um inimigo o vê a até ``AGGRO_RADIUS`` blocos. Outros inimigos a até ``JOIN_RADIUS`` entram junto,
  e quem chegar perto depois entra no começo de uma rodada;
- na vez do personagem o WASD anda só o que sobra do movimento (``limit_step``) e trava quando acaba; fora da vez dele
  também trava. As teclas 1-6 escolhem a ação, Tab troca o alvo, Enter encerra a vez;
- a vez de cada inimigo espera a anterior terminar de andar na tela e mais ``ENEMY_DELAY`` segundos;
- no fim: vitória tira os inimigos caídos; derrota faz o personagem acordar com 1 de vida e os inimigos irem embora;
  fuga deixa os inimigos onde estão, sem perseguir por ``AFTER_ESCAPE`` segundos.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from src.combat.bestiary import BESTIARY, Creature, PlayerSheet, find_creature, spawn
from src.combat.combatant import Combatant, distance, flat_distance
from src.combat.engine import DEFEAT, ESCAPED, JOIN_RADIUS, VICTORY, CombatSession, Event
from src.combat.dice import Dice
from src.combat.log import Line, format_event

AGGRO_RADIUS = 6.0       # um inimigo que te vê a até tanto começa a luta
ENGAGE_REACH = 6.0       # clicar num inimigo a até tanto começa a luta de surpresa
ENEMY_DELAY = 0.7        # segundos entre a vez de um inimigo e a do próximo
WALK_SPEED = 5.0         # blocos por segundo dos inimigos andando na tela
AFTER_ESCAPE = 8.0       # segundos sem perseguir depois de uma fuga
FALL_SECONDS = 1.0       # o inimigo caído afunda no chão por tanto tempo e some
LOG_SIZE = 7
REST_HEAL_SECONDS = 3.0  # fora de combate, 1 de vida a cada tanto
PLAYER_ID = "jogador"

SolidFn = Callable[[int, int, int], bool]


class WorldTerrain:
    """O chão e a linha de visão do mundo de blocos para a regra do combate."""

    def __init__(self, solid: SolidFn) -> None:
        self.solid = solid

    def ground(self, x: float, z: float, y_hint: float) -> Optional[float]:
        bx, bz = int(math.floor(x)), int(math.floor(z))
        base = int(math.floor(y_hint + 0.01))
        for y in range(base + 1, base - 4, -1):           # sobe um degrau ou desce até três
            if self.solid(bx, y - 1, bz) and not self.solid(bx, y, bz) and not self.solid(bx, y + 1, bz):
                return float(y)
        return None

    def sight(self, a: Sequence[float], b: Sequence[float]) -> bool:
        ax, ay, az = a[0], a[1] + 1.4, a[2]
        bx, by, bz = b[0], b[1] + 1.2, b[2]
        length = math.dist((ax, ay, az), (bx, by, bz))
        steps = max(1, int(length / 0.3))
        for i in range(1, steps):
            t = i / steps
            if self.solid(int(math.floor(ax + (bx - ax) * t)), int(math.floor(ay + (by - ay) * t)),
                          int(math.floor(az + (bz - az) * t))):
                return False
        return True


def ascii_text(text: str) -> str:
    """O texto só com letras que a fonte do jogo tem (sem acento nem símbolos)."""
    for old, new in (("★", "*"), ("⚔", "!"), ("➜", ">"), ("✖", "x"), ("—", "-"), ("→", "->"), ("…", "...")):
        text = text.replace(old, new)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if ord(c) < 128 and not unicodedata.combining(c))


@dataclass
class EnemyToken:
    combatant: Combatant
    creature: Creature
    shown: List[float]                         # onde aparece na tela
    yaw: float = 0.0
    path: List[List[float]] = field(default_factory=list)
    fallen: float = 0.0                        # segundos desde que caiu (0: de pé)
    flash: float = 0.0                         # segundos de piscar vermelho depois de levar um golpe

    @property
    def id(self) -> str:
        return self.combatant.id

    @property
    def walking(self) -> bool:
        return bool(self.path)


@dataclass
class Floater:
    """Um número que sobe sobre a cabeça de alguém (dano, cura, "errou")."""

    target: str
    text: str
    color: Tuple[int, int, int]
    age: float = 0.0


def ray_hits_cylinder(origin: Sequence[float], direction: Sequence[float], base: Sequence[float], radius: float,
                      height: float) -> Optional[float]:
    """Onde (t) o raio entra no cilindro em pé com o pé em ``base``; None se não o atinge."""
    ox, oy, oz = (float(v) for v in origin)
    dx, dy, dz = (float(v) for v in direction)
    cx, cy, cz = (float(v) for v in base)
    a = dx * dx + dz * dz
    if a < 1e-12:
        if math.hypot(ox - cx, oz - cz) <= radius and dy:
            t = (cy + height - oy) / dy
            return t if t >= 0 else None
        return None
    px, pz = ox - cx, oz - cz
    b = 2.0 * (px * dx + pz * dz)
    c = px * px + pz * pz - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    root = math.sqrt(disc)
    t0, t1 = (-b - root) / (2 * a), (-b + root) / (2 * a)
    y0, y1 = oy + dy * t0, oy + dy * t1
    low, high = cy, cy + height
    if max(y0, y1) < low or min(y0, y1) > high or t1 < 0:
        return None
    if low <= y0 <= high:
        return max(0.0, t0)
    t_plane = (high - oy) / dy if y0 > high else (low - oy) / dy
    return max(0.0, t_plane)


class CombatController:
    def __init__(self, sheet: Optional[PlayerSheet] = None, dice: Optional[Dice] = None) -> None:
        self.sheet = sheet or PlayerSheet()
        self.dice = dice or Dice()
        self.enemies: List[EnemyToken] = []
        self.session: Optional[CombatSession] = None
        self.player: Optional[Combatant] = None
        self.terrain = None
        self.log: List[Line] = []
        self.floaters: List[Floater] = []
        self.menu = "main"            # main | skills | items
        self.wait = 0.0
        self.calm = 0.0               # segundos sem perseguir (depois de uma fuga)
        self.rest = 0.0
        self.banner: Optional[Tuple[str, Tuple[int, int, int], float]] = None   # texto do fim, cor, tempo
        self.messages: List[Tuple[str, Tuple[int, int, int]]] = []              # para o chat
        self.player_position: Optional[List[float]] = None
        self._serial = 0

    # ------------------------------------------------------------------ consultas

    @property
    def in_combat(self) -> bool:
        return self.session is not None

    @property
    def is_player_turn(self) -> bool:
        return self.session is not None and self.session.is_player_turn and not self.animating

    @property
    def animating(self) -> bool:
        return any(e.walking for e in self.enemies)

    @property
    def locks_movement(self) -> bool:
        """O personagem fica parado na vez dos outros e quando o movimento da vez dele acaba."""
        if self.session is None:
            return False
        return not self.is_player_turn or self.session.movement_left <= 1e-6

    def token(self, combatant_id: Optional[str]) -> Optional[EnemyToken]:
        return next((e for e in self.enemies if e.id == combatant_id), None)

    def name_of(self, combatant_id: Optional[str]) -> str:
        if combatant_id == PLAYER_ID:
            return self.sheet.name
        token = self.token(combatant_id)
        return token.combatant.name if token else (combatant_id or "")

    # ------------------------------------------------------------------ inimigos no mundo

    def spawn(self, name: str, count: int, around: Sequence[float], terrain=None) -> List[EnemyToken]:
        """Põe ``count`` criaturas ``name`` em volta de ``around`` (num círculo a 5 blocos, no chão)."""
        creature = find_creature(name)
        if creature is None:
            raise KeyError(name)
        terrain = terrain or self.terrain
        made = []
        for i in range(max(1, min(int(count), 8))):
            self._serial += 1
            angle = (self._serial * 2.399963) % (2 * math.pi)           # ângulo de ouro: espalha sem repetir
            x = float(around[0]) + 5.0 * math.cos(angle)
            z = float(around[2]) + 5.0 * math.sin(angle)
            y = float(around[1])
            if terrain is not None:
                for hint in range(4, -24, -4):          # do alto para baixo, em faixas de 4 (o ground olha 5 níveis)
                    ground = terrain.ground(x, z, y + hint)
                    if ground is not None:
                        y = ground
                        break
            combatant = spawn(creature, f"{creature.key}{self._serial}", (x, y, z))
            token = EnemyToken(combatant, creature, [x, y, z], yaw=math.atan2(around[0] - x, around[2] - z))
            self.enemies.append(token)
            made.append(token)
            if self.session is not None:
                self.session.add_combatant(combatant)
        return made

    def clear(self) -> int:
        """Tira todos os inimigos (e encerra um combate sem resultado)."""
        count = len(self.enemies)
        self.enemies.clear()
        self.session = None
        self.player = None
        self.menu = "main"
        return count

    def pick(self, origin: Sequence[float], direction: Sequence[float]) -> Optional[EnemyToken]:
        """O inimigo de pé mais perto ao longo do raio do mouse."""
        best, best_t = None, math.inf
        for enemy in self.enemies:
            if enemy.fallen:
                continue
            t = ray_hits_cylinder(origin, direction, enemy.shown, 0.45 * max(1.0, enemy.creature.width / 0.6) ** 0.5,
                                  enemy.creature.height)
            if t is not None and t < best_t:
                best, best_t = enemy, t
        return best

    # ------------------------------------------------------------------ começar e terminar

    def start(self, player_position: Sequence[float], first: Optional[EnemyToken] = None,
              surprise: bool = False) -> bool:
        if self.session is not None:
            return False
        standing = [e for e in self.enemies if not e.fallen]
        if first is None and not standing:
            return False
        center = first.combatant.position if first else player_position
        joining = [e for e in standing if e is first or distance(e.combatant.position, center) <= JOIN_RADIUS]
        if not joining:
            return False
        self.player = self.sheet.combatant(player_position, PLAYER_ID)
        for e in joining:
            e.combatant.position = list(e.shown)
        self.session = CombatSession([self.player] + [e.combatant for e in joining], dice=self.dice,
                                     terrain=self.terrain, surprise_by=PLAYER_ID if surprise else None)
        if first is not None:
            self.session.select_target(first.id)
        self.menu = "main"
        self.log.clear()
        self.banner = None
        self.wait = ENEMY_DELAY
        self._consume_events()
        return True

    def _finish(self) -> None:
        session, player = self.session, self.player
        outcome = session.outcome
        if outcome == VICTORY:
            self.banner = ("Vitoria!", (255, 200, 60), 3.0)
        elif outcome == DEFEAT:
            player.hp = 1.0
            for e in self.enemies:
                if e.combatant in session.order or e.combatant in session.left:
                    e.fallen = max(e.fallen, 1e-3)             # vão embora (somem afundando)
            self.banner = ("Voce desmaiou... e acordou com 1 de vida", (255, 85, 85), 4.0)
            self.messages.append(("[Combate] Você desmaiou. Os inimigos foram embora e você acordou com 1 de vida.",
                                  (255, 85, 85)))
        elif outcome == ESCAPED:
            self.calm = AFTER_ESCAPE
            self.banner = ("Voce fugiu", (110, 170, 255), 2.5)
        for e in self.enemies:
            if e.combatant in session.left:
                e.fallen = max(e.fallen, 1e-3)
        self.sheet.hp = player.hp
        player.temp_hp = 0.0
        player.effects.clear()
        for e in self.enemies:
            e.combatant.effects.clear()
            e.combatant.defending = False
        self.session = None
        self.player = None
        self.menu = "main"

    # ------------------------------------------------------------------ o quadro

    def limit_step(self, before: Sequence[float], after: Sequence[float]) -> List[float]:
        """Na vez do personagem, o passo deste quadro gasta movimento; o que passa da reserva não anda."""
        after = [float(v) for v in after]
        if self.session is None:
            return after
        if self.locks_movement:
            return [float(before[0]), after[1], float(before[2])]
        step = flat_distance(before, after)
        if step <= 1e-9:
            return after
        granted = self.session.spend_movement(step)
        if granted < step:
            k = granted / step
            after[0] = float(before[0]) + (after[0] - float(before[0])) * k
            after[2] = float(before[2]) + (after[2] - float(before[2])) * k
        return after

    def update(self, dt: float, player_position: Sequence[float]) -> None:
        dt = max(0.0, float(dt))
        self.player_position = [float(v) for v in player_position]
        self._animate(dt)
        if self.banner is not None:
            text, color, left = self.banner
            self.banner = (text, color, left - dt) if left - dt > 0 else None
        if self.session is None:
            self.calm = max(0.0, self.calm - dt)
            self._rest(dt)
            if self.calm <= 0.0:
                self._check_aggro(player_position)
            return
        session = self.session
        session.set_position(PLAYER_ID, player_position)
        if not session.active:
            if not self.animating:
                self._finish()
            return
        if session.current.is_player or self.animating:
            self.wait = ENEMY_DELAY
            return
        self.wait -= dt
        if self.wait > 0.0:
            return
        if session.index == 0 or session.current is session.order[0]:
            self._join_latecomers()
        session.run_ai_turn()
        self._consume_events()
        self.wait = ENEMY_DELAY

    def _rest(self, dt: float) -> None:
        if self.sheet.hp is None or self.sheet.hp >= self.sheet.max_hp:
            self.sheet.hp = None
            return
        self.rest += dt
        while self.rest >= REST_HEAL_SECONDS:
            self.rest -= REST_HEAL_SECONDS
            self.sheet.hp = min(float(self.sheet.max_hp), self.sheet.hp + 1.0)

    def _check_aggro(self, player_position: Sequence[float]) -> None:
        for e in self.enemies:
            if e.fallen:
                continue
            if distance(e.shown, player_position) <= AGGRO_RADIUS and (
                    self.terrain is None or self.terrain.sight(e.shown, player_position)):
                self.messages.append((f"[Combate] {e.combatant.name} te viu!", (255, 110, 110)))
                self.start(player_position, e, surprise=False)
                return

    def _join_latecomers(self) -> None:
        players = self.session.team("jogadores")
        if not players:
            return
        for e in self.enemies:
            if e.fallen or self.session.get(e.id) is not None or e.combatant in self.session.left:
                continue
            if distance(e.shown, players[0].position) <= JOIN_RADIUS:
                e.combatant.position = list(e.shown)
                self.session.add_combatant(e.combatant)
        self._consume_events()

    def _animate(self, dt: float) -> None:
        for e in self.enemies:
            if e.path:
                budget = WALK_SPEED * dt
                while e.path and budget > 0:
                    goal = e.path[0]
                    gap = distance(e.shown, goal)
                    if math.hypot(goal[0] - e.shown[0], goal[2] - e.shown[2]) > 1e-6:
                        e.yaw = math.atan2(goal[0] - e.shown[0], goal[2] - e.shown[2])
                    if gap <= budget:
                        e.shown = list(goal)
                        e.path.pop(0)
                        budget -= gap
                    else:
                        k = budget / gap
                        e.shown = [s + (g - s) * k for s, g in zip(e.shown, goal)]
                        budget = 0
            e.flash = max(0.0, e.flash - dt)
            if e.fallen:
                e.fallen += dt
        self.enemies = [e for e in self.enemies if e.fallen < FALL_SECONDS or e.fallen == 0.0]
        for f in self.floaters:
            f.age += dt
        self.floaters = [f for f in self.floaters if f.age < 1.4]

    def _face(self, actor_id: Optional[str], target_id: Optional[str]) -> None:
        token = self.token(actor_id)
        if token is None or self.session is None:
            return
        target = self.session.get(target_id)
        if target is not None:
            token.yaw = math.atan2(target.position[0] - token.combatant.position[0],
                                   target.position[2] - token.combatant.position[2])

    def _consume_events(self) -> None:
        if self.session is None:
            return
        is_player = lambda cid: cid == PLAYER_ID
        for event in self.session.take_events():
            line = format_event(event, self.name_of, is_player)
            if line is not None:
                self.log.append(line)
            self._react(event)
        self.log = self.log[-LOG_SIZE:]

    def _react(self, event: Event) -> None:
        data = event.data
        if event.kind == "movimento":
            token = self.token(event.actor)
            if token is not None:
                token.path.extend([list(p) for p in data["path"]])
        elif event.kind == "ataque":
            result = data["result"]
            self._face(event.actor, event.target)
            if result.hit:
                self.floaters.append(Floater(event.target, f"-{result.damage}" + ("!" if result.critical else ""),
                                             (255, 200, 60) if result.critical else (255, 85, 85)))
                token = self.token(event.target)
                if token is not None:
                    token.flash = 0.35
            else:
                self.floaters.append(Floater(event.target, "errou", (190, 190, 190)))
        elif event.kind == "cura":
            self.floaters.append(Floater(event.actor, f"+{int(data['amount'])}", (120, 255, 140)))
        elif event.kind == "dano_efeito":
            self.floaters.append(Floater(event.actor, f"-{int(data['amount'])}", (180, 120, 255)))
        elif event.kind == "derrotado":
            token = self.token(event.actor)
            if token is not None:
                token.fallen = 1e-3

    # ------------------------------------------------------------------ comandos do personagem

    def menu_entries(self) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
        """(tecla, rótulo, ação, item) do menu aberto; ``action`` None é um submenu."""
        if self.menu == "skills":
            from src.combat.actions import SKILLS
            return [(str(i + 1), SKILLS[k].name, k, None) for i, k in enumerate(self.player.skills)] + \
                [("0", "Voltar", "voltar", None)]
        if self.menu == "items":
            from src.combat.actions import ITEMS
            entries = [(str(i + 1), f"{ITEMS[k].name} x{n}", "usar_item", k)
                       for i, (k, n) in enumerate(sorted(self.player.items.items())) if k in ITEMS][:8]
            return entries + [("0", "Voltar", "voltar", None)]
        return [("1", "Atacar", "atacar", None), ("2", "Habilidades", None, "skills"), ("3", "Itens", None, "items"),
                ("4", "Defender", "defender", None), ("5", "Disparada", "disparada", None),
                ("6", "Fugir", "fugir", None)]

    def blocked(self, action: Optional[str], item: Optional[str] = None) -> Optional[str]:
        if self.session is None or action in (None, "voltar"):
            return None
        return self.session.block_reason(action, item=item)

    def choose(self, key: str) -> bool:
        """A tecla ``key`` (``"1"``…``"9"``, ``"0"``) no menu aberto; True se fez algo."""
        if not self.is_player_turn:
            return False
        for entry_key, _, action, extra in self.menu_entries():
            if entry_key != key:
                continue
            if action is None:
                self.menu = extra
                return True
            if action == "voltar":
                self.menu = "main"
                return True
            self.session.act(action, item=extra if action == "usar_item" else None)
            self.menu = "main"
            self._consume_events()
            return True
        return False

    def end_turn(self) -> bool:
        if not self.is_player_turn:
            return False
        self.session.end_turn()
        self.menu = "main"
        self._consume_events()
        return True

    def cycle_target(self) -> bool:
        if self.session is None:
            return False
        return self.session.cycle_target() is not None

    def click_enemy(self, enemy: EnemyToken, player_position: Sequence[float]) -> bool:
        """Clique num inimigo: fora do combate começa a luta (de surpresa, se perto); dentro, mira ou ataca."""
        if self.session is None:
            if distance(enemy.shown, player_position) > ENGAGE_REACH:
                self.messages.append((f"[Combate] {enemy.combatant.name} está longe demais.", (190, 190, 190)))
                return False
            return self.start(player_position, enemy, surprise=True)
        if self.session.target_id != enemy.id:
            return self.session.select_target(enemy.id)
        if self.is_player_turn:
            self.session.act("atacar", enemy.id)
            self._consume_events()
            return True
        return False

    def handle_key(self, key: int, action: int) -> bool:
        """Teclas do combate (com códigos do GLFW); True se a tecla foi do combate."""
        if self.session is None:
            return False
        import glfw
        if action != glfw.PRESS:
            return key in (glfw.KEY_TAB, glfw.KEY_ENTER, glfw.KEY_KP_ENTER) or glfw.KEY_0 <= key <= glfw.KEY_9
        if key == glfw.KEY_TAB:
            return self.cycle_target() or True
        if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
            self.end_turn()
            return True
        if glfw.KEY_0 <= key <= glfw.KEY_9:
            self.choose(str(key - glfw.KEY_0))
            return True
        if glfw.KEY_KP_0 <= key <= glfw.KEY_KP_9:
            self.choose(str(key - glfw.KEY_KP_0))
            return True
        return False

    def take_messages(self) -> List[Tuple[str, Tuple[int, int, int]]]:
        out, self.messages = self.messages, []
        return out
