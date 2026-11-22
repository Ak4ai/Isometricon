"""A vez dos inimigos: quem atacar, quando andar, defender, correr ou fugir (sem OpenGL).

No mod a IA era um sorteio: longe, anda (70% de chance de disparar se a mais de 6 m); perto, 70% ataca e 30% defende.
Aqui ela pesa a situação, com um pouco de sorte só para desempatar:

- alvo: o oponente mais fácil, pela distância e pela vida que resta (``target_score``);
- corpo a corpo: fora de alcance, anda até o alvo e ataca se chegar; longe demais para chegar nesta vez, dispara
  (movimento dobrado, sem ataque), como o "Disparou!" do mod;
- à distância (``atirador``): perto demais, recua antes de atirar; fora de alcance, chega só até poder atirar;
- ferido: se o próximo golpe do alvo provavelmente o derruba, defende (``agressivo``) ou foge (``covarde``);
- o Golpe Pesado entra quando o acerto é fácil (chance alta mesmo com -2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.combat.combatant import Combatant

if TYPE_CHECKING:
    from src.combat.engine import CombatSession

TOO_CLOSE = 3.0          # um atirador recua quando o alvo está mais perto que isto
KITE_DISTANCE = 7.0      # e tenta ficar a esta distância
LOW_HP = 0.35            # abaixo desta fração da vida o inimigo passa a se proteger
DASH_MIN_DISTANCE = 6.0  # só dispara quem está mais longe que isto


def hit_chance(attacker: Combatant, target: Combatant, to_hit: int = 0) -> float:
    """A chance de ``attacker`` acertar ``target`` (o 1 sempre erra, o 20 sempre acerta)."""
    need = target.armor_class - attacker.attack_bonus - to_hit
    faces = 21 - max(2, min(20, need))
    return faces / 20.0


def expected_damage(attacker: Combatant, target: Combatant) -> float:
    average = attacker.weapon.damage.average + attacker.mod(attacker.attack_ability)
    return hit_chance(attacker, target) * max(1.0, average)


def target_score(actor: Combatant, target: Combatant) -> float:
    """Menor é melhor: perto e com pouca vida."""
    return actor.distance_to(target) + 0.5 * target.total_hp


def choose_target(session: "CombatSession", actor: Combatant) -> Optional[Combatant]:
    options = session.opponents_of(actor)
    if not options:
        return None
    return min(options, key=lambda t: target_score(actor, t))


def _attack(session: "CombatSession", actor: Combatant, target: Combatant) -> bool:
    if session.block_reason("atacar", target.id) is not None:
        return False
    heavy = ("golpe_pesado" in actor.skills and session.block_reason("golpe_pesado", target.id) is None
             and hit_chance(actor, target, -2) >= 0.6)
    session.act("golpe_pesado" if heavy else "atacar", target.id)
    return True


def take_turn(session: "CombatSession", actor: Combatant) -> None:
    target = choose_target(session, actor)
    if target is None:
        return
    threatened = expected_damage(target, actor) * 1.5 >= actor.total_hp
    wounded = actor.hp_ratio <= LOW_HP

    if wounded and threatened and actor.ai == "covarde":
        session.walk_away(actor, target.position, session.movement_left)
        if session.active and session.current is actor and session.enemy_escape(actor):
            return
        if session.active and session.current is actor:
            if session.in_reach(target, actor):
                session.act("defender")
            elif not _attack(session, actor, target):
                session.act("defender")
        return

    if actor.weapon.ranged:
        if actor.distance_to(target) < TOO_CLOSE:
            session.walk_away(actor, target.position, KITE_DISTANCE - actor.distance_to(target))
        elif not session.in_reach(actor, target):
            session.walk_toward(actor, target.position, stop_at=actor.reach - 1.0)
        if session.active and session.current is actor and not _attack(session, actor, target):
            session.act("defender")
        return

    if session.in_reach(actor, target):
        if wounded and threatened and session.dice.chance() < 0.6:
            session.act("defender")
        else:
            _attack(session, actor, target)
        return

    gap = actor.distance_to(target) - actor.melee_reach
    if gap > session.movement_left and actor.distance_to(target) > DASH_MIN_DISTANCE:
        session.act("disparada")
        if session.active and session.current is actor:
            session.walk_toward(actor, target.position, stop_at=actor.melee_reach - 0.4)
        return
    session.walk_toward(actor, target.position, stop_at=actor.melee_reach - 0.4)
    if session.active and session.current is actor and session.in_reach(actor, target):
        _attack(session, actor, target)
